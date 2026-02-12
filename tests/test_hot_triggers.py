from __future__ import annotations

from sentinel_api import hot_triggers
from sentinel_api.lexicon_repository import LexiconEntry


def _entry(
    term: str,
    *,
    action: str = "BLOCK",
    severity: int = 3,
    label: str = "INCITEMENT_VIOLENCE",
    reason_code: str = "R_INCITE_CALL_TO_HARM",
    lang: str = "en",
) -> LexiconEntry:
    return LexiconEntry(
        term=term,
        action=action,
        label=label,
        reason_code=reason_code,
        severity=severity,
        lang=lang,
    )


class _FakePipeline:
    def __init__(self, client: "_FakeRedisClient") -> None:
        self.client = client
        self.key: str | None = None
        self.mapping: dict[str, str] = {}
        self.ttl: int | None = None

    def hset(self, key: str, mapping: dict[str, str]) -> "_FakePipeline":
        self.key = key
        self.mapping = mapping
        return self

    def expire(self, key: str, ttl_seconds: int) -> "_FakePipeline":
        self.key = key
        self.ttl = ttl_seconds
        return self

    def execute(self) -> list[int]:
        assert self.key is not None
        bucket = self.client.store.setdefault(self.key, {})
        bucket.update(self.mapping)
        if self.ttl is not None:
            self.client.expiry[self.key] = self.ttl
        return [1]


class _FakeRedisClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}
        self.expiry: dict[str, int] = {}

    def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    def hmget(self, key: str, tokens: list[str]) -> list[str | None]:
        bucket = self.store.get(key, {})
        return [bucket.get(token) for token in tokens]


def test_find_hot_trigger_matches_returns_empty_without_redis_client(monkeypatch) -> None:
    monkeypatch.setattr(hot_triggers, "_get_redis_client", lambda: None)
    matches = hot_triggers.find_hot_trigger_matches(
        "They should kill now.",
        lexicon_version="hatelex-v2.1",
        entries=[_entry("kill")],
    )
    assert matches == []


def test_find_hot_trigger_matches_primes_cache_and_matches_single_token_terms(
    monkeypatch,
) -> None:
    fake = _FakeRedisClient()
    monkeypatch.setattr(hot_triggers, "_get_redis_client", lambda: fake)
    entries = [
        _entry("kill"),
        _entry("burn them"),
        _entry("deal with them", action="REVIEW", severity=2),
    ]

    matches = hot_triggers.find_hot_trigger_matches(
        "They should kill now.",
        lexicon_version="hatelex-v2.1",
        entries=entries,
    )

    assert len(matches) == 1
    assert matches[0].term == "kill"
    key = "sentinel:hot-triggers:hatelex-v2.1"
    assert key in fake.store
    assert "kill" in fake.store[key]
    assert "burn" not in fake.store[key]


def test_find_hot_trigger_matches_falls_back_on_redis_error(monkeypatch) -> None:
    class _BrokenRedisClient:
        def exists(self, _key: str) -> int:
            raise RuntimeError("redis down")

    monkeypatch.setattr(hot_triggers, "_get_redis_client", lambda: _BrokenRedisClient())
    matches = hot_triggers.find_hot_trigger_matches(
        "They should kill now.",
        lexicon_version="hatelex-v2.1",
        entries=[_entry("kill")],
    )
    assert matches == []

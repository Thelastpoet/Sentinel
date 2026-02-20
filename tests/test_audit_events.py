from __future__ import annotations

import json

import pytest

from sentinel_api.audit_events import (
    AUDIT_RING_BUFFER_SIZE,
    AuditEvent,
    events_since,
    publish_audit_event,
    reset_audit_events_state,
)
from sentinel_api.main import _generate_audit_sse


def setup_function() -> None:
    reset_audit_events_state()


def teardown_function() -> None:
    reset_audit_events_state()


def test_events_since_respects_cursor() -> None:
    publish_audit_event(
        AuditEvent(
            timestamp="2026-01-01T00:00:00Z",
            action="ALLOW",
            labels=["BENIGN_POLITICAL_SPEECH"],
            reason_codes=["R_ALLOW_NO_POLICY_MATCH"],
            latency_ms=12,
            deployment_stage="supervised",
            lexicon_version="lex-0",
            policy_version="policy-0",
        )
    )
    publish_audit_event(
        AuditEvent(
            timestamp="2026-01-01T00:00:01Z",
            action="REVIEW",
            labels=["ELECTION_INTERFERENCE"],
            reason_codes=["R_ELECTION_CLAIM_MATCH"],
            latency_ms=25,
            deployment_stage="supervised",
            lexicon_version="lex-0",
            policy_version="policy-0",
        )
    )

    events, cursor = events_since(0)
    assert cursor == 2
    assert [event.action for event in events] == ["ALLOW", "REVIEW"]

    events, cursor = events_since(1)
    assert cursor == 2
    assert [event.action for event in events] == ["REVIEW"]

    events, cursor = events_since(2)
    assert cursor == 2
    assert events == []


def test_ring_buffer_drops_oldest_events() -> None:
    for index in range(AUDIT_RING_BUFFER_SIZE + 5):
        publish_audit_event(
            AuditEvent(
                timestamp=f"2026-01-01T00:00:{index:02d}Z",
                action="ALLOW",
                labels=[],
                reason_codes=[],
                latency_ms=1,
                deployment_stage="supervised",
                lexicon_version="lex-0",
                policy_version=f"policy-{index}",
            )
        )

    events, cursor = events_since(0)
    assert cursor == AUDIT_RING_BUFFER_SIZE + 5
    assert len(events) == AUDIT_RING_BUFFER_SIZE
    assert events[0].policy_version == "policy-5"


@pytest.mark.anyio
async def test_generate_audit_sse_emits_data_lines() -> None:
    publish_audit_event(
        AuditEvent(
            timestamp="2026-02-20T00:00:00+00:00",
            action="ALLOW",
            labels=["BENIGN_POLITICAL_SPEECH"],
            reason_codes=["R_ALLOW_NO_POLICY_MATCH"],
            latency_ms=5,
            deployment_stage="supervised",
            lexicon_version="lex-0",
            policy_version="policy-0",
        )
    )

    generator = _generate_audit_sse(0)
    chunk = await anext(generator)
    assert chunk.startswith("data: ")
    payload = json.loads(chunk.removeprefix("data: ").strip())
    assert payload["action"] == "ALLOW"
    await generator.aclose()


@pytest.mark.anyio
async def test_generate_audit_sse_awaits_sleep_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_called = False

    async def _fake_sleep(_seconds: float) -> None:
        nonlocal sleep_called
        sleep_called = True
        publish_audit_event(
            AuditEvent(
                timestamp="2026-02-20T00:00:00+00:00",
                action="ALLOW",
                labels=[],
                reason_codes=[],
                latency_ms=1,
                deployment_stage="supervised",
                lexicon_version="lex-0",
                policy_version="policy-0",
            )
        )

    monkeypatch.setattr("sentinel_api.main.asyncio.sleep", _fake_sleep)

    generator = _generate_audit_sse(0)
    _chunk = await anext(generator)
    assert sleep_called is True
    await generator.aclose()

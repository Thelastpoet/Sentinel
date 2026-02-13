from __future__ import annotations

import json
from pathlib import Path

from scripts import manage_lexicon_release as mlr

from sentinel_api.lexicon_repository import FileLexiconRepository


def test_seed_includes_required_metadata_and_taxonomy_coverage() -> None:
    payload = json.loads(Path("data/lexicon_seed.json").read_text(encoding="utf-8"))
    entries = payload["entries"]

    required_metadata = {"first_seen", "last_seen", "status", "change_history"}
    labels = set()
    for entry in entries:
        labels.add(str(entry["label"]))
        assert required_metadata.issubset(set(entry.keys()))
        assert entry["status"] == "active"
        assert isinstance(entry["change_history"], list)
        assert entry["change_history"]

    assert "ETHNIC_CONTEMPT" in labels
    assert "INCITEMENT_VIOLENCE" in labels
    assert "HARASSMENT_THREAT" in labels


def test_file_repository_backfills_legacy_metadata_defaults(tmp_path) -> None:
    path = tmp_path / "legacy-seed.json"
    path.write_text(
        json.dumps(
            {
                "version": "legacy-1",
                "entries": [
                    {
                        "term": "alpha",
                        "action": "REVIEW",
                        "label": "DOGWHISTLE_WATCH",
                        "reason_code": "R_DOGWHISTLE_CONTEXT_REQUIRED",
                        "severity": 2,
                        "lang": "en",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    snapshot = FileLexiconRepository(path).fetch_active()
    entry = snapshot.entries[0]
    assert entry.first_seen == "1970-01-01T00:00:00+00:00"
    assert entry.last_seen == "1970-01-01T00:00:00+00:00"
    assert entry.status == "active"
    assert entry.change_history


def test_ingest_normalizer_backfills_legacy_metadata_defaults() -> None:
    entries = [
        {
            "term": "Alpha",
            "action": "review",
            "label": "dogwhistle_watch",
            "reason_code": "r_dogwhistle_context_required",
            "severity": 2,
            "lang": "EN",
        }
    ]
    normalized = mlr.normalize_ingest_entries(entries)
    assert normalized[0]["first_seen"] == "1970-01-01T00:00:00+00:00"
    assert normalized[0]["last_seen"] == "1970-01-01T00:00:00+00:00"
    assert normalized[0]["change_history"]

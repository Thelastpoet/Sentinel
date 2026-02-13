from __future__ import annotations

import pytest
from scripts import manage_model_artifact as mma


class _RecordingCursor:
    def __init__(self, *, rowcount: int = 1) -> None:
        self.executed: list[tuple[str, tuple[object, ...] | None]] = []
        self.rowcount = rowcount

    def execute(self, query: str, params=None) -> None:  # type: ignore[no-untyped-def]
        self.executed.append((query, params))


def test_register_model_artifact_writes_record_and_audit() -> None:
    cursor = _RecordingCursor(rowcount=1)
    mma.register_model_artifact(
        cursor,
        model_id="model-alpha-v1",
        artifact_uri="s3://sentinel/models/model-alpha-v1.tar.gz",
        sha256="A" * 64,
        dataset_ref="ml-calibration-v1",
        metrics_ref="metrics/model-alpha-v1.json",
        compatibility_json='{"runtime":"cpu","python":"3.12"}',
        notes="candidate rollout",
        actor="ops-user",
    )

    assert len(cursor.executed) == 2
    insert_params = cursor.executed[0][1]
    assert insert_params is not None
    assert insert_params[0] == "model-alpha-v1"
    assert insert_params[2] == "a" * 64
    assert insert_params[5] == '{"python": "3.12", "runtime": "cpu"}'

    audit_params = cursor.executed[1][1]
    assert audit_params is not None
    assert audit_params[0] == "model-alpha-v1"
    assert audit_params[2] == "draft"
    assert audit_params[3] == "register"


def test_register_model_artifact_rejects_duplicate() -> None:
    cursor = _RecordingCursor(rowcount=0)
    with pytest.raises(ValueError, match="already exists"):
        mma.register_model_artifact(
            cursor,
            model_id="model-alpha-v1",
            artifact_uri="s3://sentinel/models/model-alpha-v1.tar.gz",
            sha256="b" * 64,
            dataset_ref="ml-calibration-v1",
            metrics_ref="metrics/model-alpha-v1.json",
            compatibility_json="{}",
            notes=None,
            actor="ops-user",
        )


def test_activate_model_artifact_deprecates_previous_active(monkeypatch) -> None:
    status_by_model = {
        "model-next-v2": "validated",
        "model-prev-v1": "active",
    }
    set_calls: list[tuple[str, str, str | None]] = []
    audit_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        mma,
        "get_model_artifact_status",
        lambda _cur, model_id, for_update=False: status_by_model.get(model_id),
    )
    monkeypatch.setattr(
        mma,
        "get_model_artifact_legal_hold",
        lambda _cur, _model_id: False,
    )
    monkeypatch.setattr(
        mma,
        "get_active_model_id",
        lambda _cur, exclude_model_id=None, for_update=False: "model-prev-v1",
    )
    monkeypatch.setattr(
        mma,
        "_set_model_status",
        lambda _cur, *, model_id, to_status, notes: set_calls.append((model_id, to_status, notes)),
    )
    monkeypatch.setattr(
        mma,
        "write_model_artifact_audit",
        lambda _cur, **kwargs: audit_calls.append(kwargs),
    )

    previous_active = mma.activate_model_artifact(
        object(),
        model_id="model-next-v2",
        actor="ops-user",
        notes="promote candidate",
    )

    assert previous_active == "model-prev-v1"
    assert set_calls == [
        ("model-prev-v1", "deprecated", "promote candidate"),
        ("model-next-v2", "active", "promote candidate"),
    ]
    assert [str(item["action"]) for item in audit_calls] == ["deprecate", "activate"]


def test_validate_model_artifact_rejects_legal_hold(monkeypatch) -> None:
    monkeypatch.setattr(
        mma,
        "get_model_artifact_status",
        lambda _cur, _model_id, for_update=False: "draft",
    )
    monkeypatch.setattr(
        mma,
        "get_model_artifact_legal_hold",
        lambda _cur, _model_id: True,
    )

    with pytest.raises(ValueError, match="legal hold"):
        mma.validate_model_artifact(
            object(),
            model_id="model-alpha-v1",
            actor="ops-user",
            notes=None,
        )


def test_rollback_uses_candidate_when_not_explicit(monkeypatch) -> None:
    calls: list[tuple[str, str | None, str, str | None]] = []
    monkeypatch.setattr(mma, "_find_rollback_candidate", lambda _cur: "model-prev-v1")
    monkeypatch.setattr(
        mma,
        "activate_model_artifact",
        lambda _cur, *, model_id, actor, notes, action="activate": calls.append(
            (model_id, actor, action, notes)
        ),
    )

    target = mma.rollback_model_artifact(
        object(),
        actor="ops-user",
        to_model_id=None,
        notes="incident rollback",
    )

    assert target == "model-prev-v1"
    assert calls == [("model-prev-v1", "ops-user", "rollback", "incident rollback")]

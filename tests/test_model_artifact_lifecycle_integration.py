from __future__ import annotations

import importlib
import os
from uuid import uuid4

import pytest
from scripts import manage_model_artifact as mma


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_model_artifact_lifecycle_register_activate_and_rollback() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")

    model_a = f"itest-model-{uuid4().hex[:12]}-a"
    model_b = f"itest-model-{uuid4().hex[:12]}-b"

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            mma.register_model_artifact(
                cur,
                model_id=model_a,
                artifact_uri=f"s3://sentinel/{model_a}.tar.gz",
                sha256="a" * 64,
                dataset_ref="ml-calibration-v1",
                metrics_ref=f"metrics/{model_a}.json",
                compatibility_json='{"python":"3.12","runtime":"cpu"}',
                notes="integration registration",
                actor="integration-suite",
            )
            mma.validate_model_artifact(
                cur,
                model_id=model_a,
                actor="integration-suite",
                notes="integration validate",
            )
            first_previous = mma.activate_model_artifact(
                cur,
                model_id=model_a,
                actor="integration-suite",
                notes="integration activate a",
            )
            assert first_previous is None

            mma.register_model_artifact(
                cur,
                model_id=model_b,
                artifact_uri=f"s3://sentinel/{model_b}.tar.gz",
                sha256="b" * 64,
                dataset_ref="ml-calibration-v1",
                metrics_ref=f"metrics/{model_b}.json",
                compatibility_json='{"python":"3.12","runtime":"cpu"}',
                notes="integration registration",
                actor="integration-suite",
            )
            mma.validate_model_artifact(
                cur,
                model_id=model_b,
                actor="integration-suite",
                notes="integration validate",
            )
            second_previous = mma.activate_model_artifact(
                cur,
                model_id=model_b,
                actor="integration-suite",
                notes="integration activate b",
            )
            assert second_previous == model_a

            cur.execute(
                "SELECT status FROM model_artifacts WHERE model_id = %s",
                (model_a,),
            )
            status_a_before = cur.fetchone()
            assert status_a_before == ("deprecated",)

            cur.execute(
                "SELECT status FROM model_artifacts WHERE model_id = %s",
                (model_b,),
            )
            status_b_before = cur.fetchone()
            assert status_b_before == ("active",)

            rollback_target = mma.rollback_model_artifact(
                cur,
                actor="integration-suite",
                to_model_id=model_a,
                notes="integration rollback",
            )
            assert rollback_target == model_a

            cur.execute(
                "SELECT status FROM model_artifacts WHERE model_id = %s",
                (model_a,),
            )
            status_a_after = cur.fetchone()
            assert status_a_after == ("active",)

            cur.execute(
                "SELECT status FROM model_artifacts WHERE model_id = %s",
                (model_b,),
            )
            status_b_after = cur.fetchone()
            assert status_b_after == ("deprecated",)

            cur.execute(
                """
                SELECT COUNT(1)
                FROM model_artifact_audit
                WHERE model_id = %s
                  AND action = 'rollback'
                """,
                (model_a,),
            )
            audit_row = cur.fetchone()
            assert audit_row is not None
            assert int(audit_row[0]) == 1
    finally:
        conn.rollback()
        conn.close()

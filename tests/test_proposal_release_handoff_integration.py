from __future__ import annotations

import importlib
import os
from uuid import uuid4

import pytest
from scripts import manage_lexicon_release as mlr


def _integration_db_url() -> str | None:
    return os.getenv("SENTINEL_INTEGRATION_DB_URL")


@pytest.mark.skipif(
    not _integration_db_url(),
    reason="SENTINEL_INTEGRATION_DB_URL is required for postgres integration tests",
)
def test_approved_proposal_promotes_to_governed_draft_release() -> None:
    db_url = _integration_db_url()
    assert db_url is not None
    psycopg = importlib.import_module("psycopg")

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO release_proposals
                  (
                    proposal_type, status, title, description, evidence,
                    policy_impact_summary, proposed_by
                  )
                VALUES
                  ('lexicon', 'approved', %s, %s, '[]'::jsonb, %s, %s)
                RETURNING id
                """,
                (
                    "Integration promotion candidate",
                    "Integration test proposal for release handoff.",
                    "integration-policy-impact",
                    "integration-suite",
                ),
            )
            row = cur.fetchone()
            assert row is not None
            proposal_id = int(row[0])
            target_version = f"itest-hatelex-{uuid4().hex[:10]}"

            report = mlr.promote_proposal_to_release(
                cur,
                proposal_id=proposal_id,
                target_version=target_version,
                actor="integration-suite",
                notes="integration promotion artifact",
                rationale="approved for governance handoff",
            )

            assert report["proposal_status"] == "promoted"
            assert report["target_release_version"] == target_version

            cur.execute(
                (
                    "SELECT status, reviewed_by, promoted_at IS NOT NULL "
                    "FROM release_proposals WHERE id = %s"
                ),
                (proposal_id,),
            )
            proposal_row = cur.fetchone()
            assert proposal_row == ("promoted", "integration-suite", True)

            cur.execute(
                "SELECT status FROM lexicon_releases WHERE version = %s",
                (target_version,),
            )
            release_row = cur.fetchone()
            assert release_row == ("draft",)

            cur.execute(
                """
                SELECT COUNT(1)
                FROM lexicon_release_audit
                WHERE release_version = %s
                  AND action = 'proposal_promote'
                """,
                (target_version,),
            )
            release_audit_row = cur.fetchone()
            assert release_audit_row is not None
            assert int(release_audit_row[0]) == 1

            cur.execute(
                """
                SELECT COUNT(1)
                FROM release_proposal_audit
                WHERE proposal_id = %s
                  AND from_status = 'approved'
                  AND to_status = 'promoted'
                """,
                (proposal_id,),
            )
            proposal_audit_row = cur.fetchone()
            assert proposal_audit_row is not None
            assert int(proposal_audit_row[0]) == 1
    finally:
        conn.rollback()
        conn.close()

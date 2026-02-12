from __future__ import annotations

import pytest

from scripts import manage_lexicon_release as mlr


class _ProposalPromotionCursor:
    def __init__(
        self,
        *,
        proposal_row: tuple[int, str, str, str] | None,
        release_status: str | None = None,
    ) -> None:
        self.proposal_row = proposal_row
        self.release_status = release_status
        self.executed: list[tuple[str, tuple | None]] = []
        self.last_query = ""
        self.rowcount = 1

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))
        self.last_query = query
        if "UPDATE release_proposals" in query:
            self.rowcount = 1

    def fetchone(self):
        if "FROM release_proposals" in self.last_query:
            return self.proposal_row
        if "SELECT status FROM lexicon_releases" in self.last_query:
            if self.release_status is None:
                return None
            return (self.release_status,)
        return None


def test_promote_proposal_to_release_creates_draft_and_audits() -> None:
    cursor = _ProposalPromotionCursor(
        proposal_row=(11, "lexicon", "approved", "Emerging harmful term"),
    )

    report = mlr.promote_proposal_to_release(
        cursor,
        proposal_id=11,
        target_version="hatelex-v2.4",
        actor="reviewer-a",
        notes=None,
        rationale="ready for governed rollout",
    )

    assert report == {
        "proposal_id": 11,
        "proposal_status": "promoted",
        "target_release_version": "hatelex-v2.4",
        "release_status": "draft",
    }

    executed_sql = "\n".join(query for query, _ in cursor.executed)
    assert "INSERT INTO lexicon_releases" in executed_sql
    assert "INSERT INTO lexicon_release_audit" in executed_sql
    assert "UPDATE release_proposals" in executed_sql
    assert "INSERT INTO release_proposal_audit" in executed_sql
    assert "INSERT INTO proposal_reviews" in executed_sql

    create_params = cursor.executed[2][1]
    assert create_params == (
        "hatelex-v2.4",
        "proposal:11 title:Emerging harmful term",
        "decision_record",
    )


def test_promote_proposal_to_release_rejects_non_lexicon_proposals() -> None:
    cursor = _ProposalPromotionCursor(
        proposal_row=(14, "policy", "approved", "Policy tweak"),
    )
    with pytest.raises(ValueError, match="proposal type is not supported"):
        mlr.promote_proposal_to_release(
            cursor,
            proposal_id=14,
            target_version="hatelex-v2.5",
            actor="reviewer-a",
            notes=None,
            rationale=None,
        )


def test_promote_proposal_to_release_rejects_invalid_transition() -> None:
    cursor = _ProposalPromotionCursor(
        proposal_row=(19, "lexicon", "draft", "Not yet approved"),
    )
    with pytest.raises(ValueError, match="transition not allowed: draft -> promoted"):
        mlr.promote_proposal_to_release(
            cursor,
            proposal_id=19,
            target_version="hatelex-v2.6",
            actor="reviewer-a",
            notes=None,
            rationale=None,
        )


def test_promote_proposal_to_release_rejects_non_draft_target_release() -> None:
    cursor = _ProposalPromotionCursor(
        proposal_row=(21, "lexicon", "approved", "Ready"),
        release_status="active",
    )
    with pytest.raises(ValueError, match="non-draft status"):
        mlr.promote_proposal_to_release(
            cursor,
            proposal_id=21,
            target_version="hatelex-v2.1",
            actor="reviewer-a",
            notes=None,
            rationale=None,
        )

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "s0004"
down_revision = "s0003"
branch_labels = None
depends_on = None


def _read_sql(filename: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "migrations" / filename).read_text(encoding="utf-8")


def upgrade() -> None:
    op.execute(sa.text(_read_sql("0004_async_monitoring_core.sql")))


def downgrade() -> None:
    raise NotImplementedError("Irreversible raw SQL migration")

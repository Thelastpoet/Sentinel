from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import alembic.command as alembic_command
from alembic.config import Config

LEGACY_ALEMBIC_ID_MAP: dict[str, str] = {
    "0001_lexicon_entries": "s0001",
    "0002_lexicon_releases": "s0002",
    "0003_lexicon_release_audit": "s0003",
    "0004_async_monitoring_core": "s0004",
    "0005_lexicon_release_audit_proposal_promote": "s0005",
    "0006_retention_legal_hold_primitives": "s0006",
    "0007_lexicon_entry_embeddings": "s0007",
    "0008_appeals_core": "s0008",
    "0009_appeals_original_decision_id_backfill": "s0009",
    "0010_monitoring_queue_event_uniqueness": "s0010",
    "0011_lexicon_entry_metadata_hardening": "s0011",
    "0012_model_artifact_lifecycle": "s0012",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply database migrations using Alembic.",
    )
    parser.add_argument("--database-url", required=True, help="Postgres connection URL.")
    parser.add_argument(
        "--revision",
        default="head",
        help="Alembic target revision (default: head).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render SQL for the requested upgrade without applying it.",
    )
    parser.add_argument(
        "--migrations-dir",
        default="migrations",
        help=(
            "Deprecated compatibility flag. Alembic revisions under alembic/versions "
            "are authoritative."
        ),
    )
    return parser.parse_args()


def _build_alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    sqlalchemy_url = database_url.strip()
    if sqlalchemy_url.startswith("postgresql://"):
        sqlalchemy_url = sqlalchemy_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if sqlalchemy_url.startswith("postgres://"):
        sqlalchemy_url = sqlalchemy_url.replace("postgres://", "postgresql+psycopg://", 1)
    config.set_main_option("sqlalchemy.url", sqlalchemy_url)
    return config


def _normalize_existing_alembic_version(database_url: str) -> None:
    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.alembic_version')")
            row = cur.fetchone()
            if row is None or row[0] is None:
                conn.commit()
                return
            cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
            version_row = cur.fetchone()
            if version_row is None:
                conn.commit()
                return
            current_version = str(version_row[0])
            mapped = LEGACY_ALEMBIC_ID_MAP.get(current_version)
            if mapped and mapped != current_version:
                cur.execute("UPDATE alembic_version SET version_num = %s", (mapped,))
        conn.commit()


def main() -> None:
    args = parse_args()
    if not args.dry_run:
        _normalize_existing_alembic_version(args.database_url)
    config = _build_alembic_config(args.database_url)
    if args.dry_run:
        alembic_command.upgrade(config, args.revision, sql=True)
        return
    alembic_command.upgrade(config, args.revision)
    print(f"alembic upgrade complete: {args.revision}")


if __name__ == "__main__":
    main()

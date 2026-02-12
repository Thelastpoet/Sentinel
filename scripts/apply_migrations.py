from __future__ import annotations

import argparse
import importlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply all SQL migrations in order.")
    parser.add_argument("--database-url", required=True, help="Postgres connection URL.")
    parser.add_argument(
        "--migrations-dir",
        default="migrations",
        help="Directory containing *.sql migrations.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    migrations_dir = Path(args.migrations_dir)
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        raise SystemExit(f"no migration files found in {migrations_dir}")

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            for migration in files:
                sql = migration.read_text(encoding="utf-8")
                cur.execute(sql)
                print(f"applied migration: {migration.name}")
        conn.commit()


if __name__ == "__main__":
    main()

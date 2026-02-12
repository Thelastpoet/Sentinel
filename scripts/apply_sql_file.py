from __future__ import annotations

import argparse
import importlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a SQL file to Postgres.")
    parser.add_argument("--database-url", required=True, help="Postgres connection URL.")
    parser.add_argument("--sql-file", required=True, help="Path to SQL file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sql = Path(args.sql_file).read_text(encoding="utf-8")
    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"applied sql file: {args.sql_file}")


if __name__ == "__main__":
    main()


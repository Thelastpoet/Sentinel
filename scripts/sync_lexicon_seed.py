from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync lexicon seed JSON into Postgres lexicon_entries table."
    )
    parser.add_argument(
        "--seed-path",
        default="data/lexicon_seed.json",
        help="Path to lexicon seed JSON file.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("SENTINEL_DATABASE_URL"),
        help="Postgres connection URL. Defaults to SENTINEL_DATABASE_URL.",
    )
    parser.add_argument(
        "--activate-if-none",
        action="store_true",
        help="Activate this release if no active release exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("SENTINEL_DATABASE_URL or --database-url is required")

    payload = json.loads(Path(args.seed_path).read_text(encoding="utf-8"))
    version = str(payload["version"])
    entries = payload["entries"]

    psycopg = importlib.import_module("psycopg")
    with psycopg.connect(args.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO lexicon_releases (version, status, created_at, updated_at)
                VALUES (%s, 'draft', NOW(), NOW())
                ON CONFLICT (version) DO NOTHING
                """,
                (version,),
            )

            for item in entries:
                cur.execute(
                    """
                    INSERT INTO lexicon_entries
                      (term, action, label, reason_code, severity, lang, status, lexicon_version)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, 'active', %s)
                    ON CONFLICT (term, action, label, reason_code, lang, lexicon_version)
                    DO UPDATE SET
                      severity = EXCLUDED.severity,
                      status = EXCLUDED.status,
                      updated_at = NOW()
                    """,
                    (
                        item["term"].lower(),
                        item["action"],
                        item["label"],
                        item["reason_code"],
                        int(item["severity"]),
                        item["lang"],
                        version,
                    ),
                )

            if args.activate_if_none:
                cur.execute(
                    "SELECT 1 FROM lexicon_releases WHERE status = 'active' LIMIT 1"
                )
                if cur.fetchone() is None:
                    cur.execute(
                        """
                        UPDATE lexicon_releases
                        SET status = 'active',
                            activated_at = COALESCE(activated_at, NOW()),
                            deprecated_at = NULL,
                            updated_at = NOW()
                        WHERE version = %s
                        """,
                        (version,),
                    )
        conn.commit()

    print(f"synced {len(entries)} entries to lexicon_entries (version={version})")


if __name__ == "__main__":
    main()

CREATE TABLE IF NOT EXISTS lexicon_releases (
    version TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'deprecated')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lexicon_releases_single_active
ON lexicon_releases (status)
WHERE status = 'active';

INSERT INTO lexicon_releases (version, status, created_at, updated_at)
SELECT DISTINCT lexicon_version, 'draft', NOW(), NOW()
FROM lexicon_entries
ON CONFLICT (version) DO NOTHING;

WITH latest_version AS (
    SELECT lexicon_version AS version
    FROM lexicon_entries
    GROUP BY lexicon_version
    ORDER BY lexicon_version DESC
    LIMIT 1
)
UPDATE lexicon_releases
SET status = 'active',
    activated_at = COALESCE(activated_at, NOW()),
    deprecated_at = NULL,
    updated_at = NOW()
WHERE version IN (SELECT version FROM latest_version)
  AND NOT EXISTS (
      SELECT 1
      FROM lexicon_releases
      WHERE status = 'active'
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_lexicon_entries_release_version'
    ) THEN
        ALTER TABLE lexicon_entries
            ADD CONSTRAINT fk_lexicon_entries_release_version
            FOREIGN KEY (lexicon_version)
            REFERENCES lexicon_releases (version);
    END IF;
END
$$;

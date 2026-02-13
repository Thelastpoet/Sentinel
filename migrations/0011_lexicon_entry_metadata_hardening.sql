ALTER TABLE lexicon_entries
    ADD COLUMN IF NOT EXISTS first_seen TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS change_history JSONB NOT NULL DEFAULT '[]'::jsonb;

UPDATE lexicon_entries
SET
    first_seen = COALESCE(first_seen, created_at),
    last_seen = COALESCE(last_seen, updated_at),
    change_history = CASE
        WHEN change_history IS NULL OR jsonb_typeof(change_history) <> 'array'
            OR jsonb_array_length(change_history) = 0
        THEN jsonb_build_array(
            jsonb_build_object(
                'action', 'seed_import',
                'actor', 'system',
                'details', 'migration-backfill-placeholder',
                'created_at', to_char(COALESCE(created_at, NOW()), 'YYYY-MM-DD"T"HH24:MI:SSOF')
            )
        )
        ELSE change_history
    END;

ALTER TABLE lexicon_entries
    ALTER COLUMN first_seen SET NOT NULL,
    ALTER COLUMN last_seen SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_lexicon_entries_last_seen_not_before_first_seen'
    ) THEN
        ALTER TABLE lexicon_entries
            ADD CONSTRAINT ck_lexicon_entries_last_seen_not_before_first_seen
            CHECK (last_seen >= first_seen);
    END IF;
END
$$;

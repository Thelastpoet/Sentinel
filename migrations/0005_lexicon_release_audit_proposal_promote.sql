DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'lexicon_release_audit_action_check'
          AND conrelid = 'lexicon_release_audit'::regclass
    ) THEN
        ALTER TABLE lexicon_release_audit
            DROP CONSTRAINT lexicon_release_audit_action_check;
    END IF;

    ALTER TABLE lexicon_release_audit
        ADD CONSTRAINT lexicon_release_audit_action_check
        CHECK (
            action IN (
                'create',
                'ingest',
                'activate',
                'deprecate',
                'validate',
                'proposal_promote'
            )
        );
END
$$;

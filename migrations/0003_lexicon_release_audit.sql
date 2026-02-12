CREATE TABLE IF NOT EXISTS lexicon_release_audit (
    id BIGSERIAL PRIMARY KEY,
    release_version TEXT NOT NULL REFERENCES lexicon_releases (version),
    action TEXT NOT NULL CHECK (
        action IN ('create', 'ingest', 'activate', 'deprecate', 'validate')
    ),
    actor TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_lexicon_release_audit_version_created
ON lexicon_release_audit (release_version, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_lexicon_release_audit_action_created
ON lexicon_release_audit (action, created_at DESC);

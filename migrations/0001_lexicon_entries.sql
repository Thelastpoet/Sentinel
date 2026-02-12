CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS lexicon_entries (
    id BIGSERIAL PRIMARY KEY,
    term TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('BLOCK', 'REVIEW')),
    label TEXT NOT NULL,
    reason_code TEXT NOT NULL CHECK (reason_code ~ '^R_[A-Z0-9_]+$'),
    severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 3),
    lang VARCHAR(16) NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deprecated')),
    lexicon_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_lexicon_entries_identity
ON lexicon_entries (term, action, label, reason_code, lang, lexicon_version);

CREATE INDEX IF NOT EXISTS ix_lexicon_entries_active_action
ON lexicon_entries (status, action);

CREATE INDEX IF NOT EXISTS ix_lexicon_entries_term
ON lexicon_entries (term);

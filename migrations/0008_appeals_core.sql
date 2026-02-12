CREATE TABLE IF NOT EXISTS appeals (
    id BIGSERIAL PRIMARY KEY,
    status TEXT NOT NULL CHECK (
        status IN (
            'submitted',
            'triaged',
            'in_review',
            'rejected_invalid',
            'resolved_upheld',
            'resolved_reversed',
            'resolved_modified'
        )
    ),
    request_id TEXT NOT NULL,
    original_decision_id TEXT NOT NULL,
    original_action TEXT NOT NULL CHECK (original_action IN ('ALLOW', 'REVIEW', 'BLOCK')),
    original_reason_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    original_model_version TEXT NOT NULL,
    original_lexicon_version TEXT NOT NULL,
    original_policy_version TEXT NOT NULL,
    original_pack_versions JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_by TEXT NOT NULL,
    reviewer_actor TEXT,
    resolution_code TEXT,
    resolution_reason_codes JSONB,
    retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_appeals_status_created
ON appeals (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_appeals_request_id
ON appeals (request_id, created_at DESC);

CREATE TABLE IF NOT EXISTS appeal_audit (
    id BIGSERIAL PRIMARY KEY,
    appeal_id BIGINT NOT NULL REFERENCES appeals (id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor TEXT NOT NULL,
    rationale TEXT,
    retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_appeal_audit_appeal_created
ON appeal_audit (appeal_id, created_at ASC, id ASC);

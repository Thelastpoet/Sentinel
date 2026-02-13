DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'model_artifact_status_t'
    ) THEN
        CREATE DOMAIN model_artifact_status_t AS TEXT
        CHECK (VALUE IN ('draft', 'validated', 'active', 'deprecated', 'revoked'));
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS model_artifacts (
    id BIGSERIAL PRIMARY KEY,
    model_id TEXT NOT NULL UNIQUE,
    artifact_uri TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (sha256 ~ '^[A-Fa-f0-9]{64}$'),
    dataset_ref TEXT NOT NULL,
    metrics_ref TEXT NOT NULL,
    compatibility JSONB NOT NULL DEFAULT '{}'::jsonb,
    status model_artifact_status_t NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    activated_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    retention_class retention_class_t NOT NULL DEFAULT 'decision_record',
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_model_artifacts_single_active
ON model_artifacts (status)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS ix_model_artifacts_status_updated
ON model_artifacts (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS model_artifact_audit (
    id BIGSERIAL PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES model_artifacts(model_id) ON DELETE CASCADE,
    from_status model_artifact_status_t,
    to_status model_artifact_status_t NOT NULL,
    action TEXT NOT NULL CHECK (
        action IN ('register', 'validate', 'activate', 'deprecate', 'revoke', 'rollback')
    ),
    actor TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS ix_model_artifact_audit_model_created
ON model_artifact_audit (model_id, created_at DESC);

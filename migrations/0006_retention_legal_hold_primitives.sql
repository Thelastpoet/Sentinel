DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'retention_class_t'
    ) THEN
        CREATE DOMAIN retention_class_t AS TEXT
        CHECK (
            VALUE IN (
                'operational_runtime',
                'async_monitoring_raw',
                'decision_record',
                'governance_audit',
                'analytics_aggregate',
                'legal_hold'
            )
        );
    END IF;
END
$$;

ALTER TABLE lexicon_entries
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'decision_record',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE lexicon_releases
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'decision_record',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE lexicon_release_audit
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE monitoring_events
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'async_monitoring_raw',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE monitoring_queue
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'operational_runtime',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE monitoring_queue_audit
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE monitoring_clusters
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'operational_runtime',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE release_proposals
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'decision_record',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE release_proposal_audit
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE proposal_reviews
    ADD COLUMN IF NOT EXISTS retention_class retention_class_t NOT NULL DEFAULT 'governance_audit',
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS legal_holds (
    id BIGSERIAL PRIMARY KEY,
    record_class retention_class_t NOT NULL,
    table_name TEXT,
    record_id BIGINT,
    record_key TEXT,
    reason TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    released_by TEXT,
    released_at TIMESTAMPTZ,
    release_reason TEXT,
    CHECK (NOT (record_id IS NOT NULL AND record_key IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_legal_holds_active_target
ON legal_holds (
    record_class,
    COALESCE(table_name, '__all__'),
    COALESCE(record_id, -1),
    COALESCE(record_key, '__all__')
)
WHERE released_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_legal_holds_active_class
ON legal_holds (record_class, created_at DESC)
WHERE released_at IS NULL;

CREATE TABLE IF NOT EXISTS retention_action_audit (
    id BIGSERIAL PRIMARY KEY,
    action TEXT NOT NULL CHECK (
        action IN ('apply_legal_hold', 'release_legal_hold', 'delete', 'archive', 'dry_run')
    ),
    record_class retention_class_t NOT NULL,
    table_name TEXT,
    actor TEXT NOT NULL,
    record_count INTEGER NOT NULL DEFAULT 0 CHECK (record_count >= 0),
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_retention_action_audit_class_created
ON retention_action_audit (record_class, created_at DESC);

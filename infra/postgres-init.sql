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

CREATE TABLE IF NOT EXISTS lexicon_release_audit (
    id BIGSERIAL PRIMARY KEY,
    release_version TEXT NOT NULL REFERENCES lexicon_releases (version),
    action TEXT NOT NULL CHECK (
        action IN (
            'create',
            'ingest',
            'activate',
            'deprecate',
            'validate',
            'proposal_promote'
        )
    ),
    actor TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_lexicon_release_audit_version_created
ON lexicon_release_audit (release_version, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_lexicon_release_audit_action_created
ON lexicon_release_audit (action, created_at DESC);

CREATE TABLE IF NOT EXISTS monitoring_events (
    id BIGSERIAL PRIMARY KEY,
    request_id TEXT,
    source TEXT NOT NULL,
    source_event_id TEXT,
    lang VARCHAR(16),
    content_hash TEXT,
    reliability_score SMALLINT CHECK (reliability_score BETWEEN 1 AND 5),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_monitoring_events_source_event
ON monitoring_events (source, source_event_id)
WHERE source_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_monitoring_events_source_observed
ON monitoring_events (source, observed_at DESC);

CREATE INDEX IF NOT EXISTS ix_monitoring_events_request_id
ON monitoring_events (request_id)
WHERE request_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS monitoring_queue (
    id BIGSERIAL PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES monitoring_events (id) ON DELETE CASCADE,
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'urgent', 'standard', 'batch')),
    state TEXT NOT NULL CHECK (
        state IN ('queued', 'processing', 'clustered', 'proposed', 'dropped', 'error')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ,
    sla_due_at TIMESTAMPTZ NOT NULL,
    policy_impact_summary TEXT,
    assigned_worker TEXT,
    last_error TEXT,
    last_actor TEXT NOT NULL DEFAULT 'system',
    state_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_monitoring_queue_event
ON monitoring_queue (event_id);

CREATE INDEX IF NOT EXISTS ix_monitoring_queue_priority_state
ON monitoring_queue (priority, state, created_at);

CREATE INDEX IF NOT EXISTS ix_monitoring_queue_state_sla
ON monitoring_queue (state, sla_due_at);

CREATE TABLE IF NOT EXISTS monitoring_queue_audit (
    id BIGSERIAL PRIMARY KEY,
    queue_id BIGINT NOT NULL REFERENCES monitoring_queue (id) ON DELETE CASCADE,
    from_state TEXT,
    to_state TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_monitoring_queue_audit_queue_created
ON monitoring_queue_audit (queue_id, created_at DESC);

CREATE TABLE IF NOT EXISTS monitoring_clusters (
    id BIGSERIAL PRIMARY KEY,
    cluster_key TEXT NOT NULL,
    lang VARCHAR(16),
    state TEXT NOT NULL DEFAULT 'draft' CHECK (
        state IN ('draft', 'proposed', 'merged', 'rejected')
    ),
    signal_count INTEGER NOT NULL DEFAULT 0 CHECK (signal_count >= 0),
    summary TEXT,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_monitoring_clusters_key
ON monitoring_clusters (cluster_key);

CREATE INDEX IF NOT EXISTS ix_monitoring_clusters_state
ON monitoring_clusters (state, updated_at DESC);

CREATE TABLE IF NOT EXISTS release_proposals (
    id BIGSERIAL PRIMARY KEY,
    proposal_type TEXT NOT NULL CHECK (proposal_type IN ('lexicon', 'narrative', 'policy')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'in_review', 'needs_revision', 'approved', 'promoted', 'rejected')
    ),
    queue_id BIGINT REFERENCES monitoring_queue (id) ON DELETE SET NULL,
    cluster_id BIGINT REFERENCES monitoring_clusters (id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_impact_summary TEXT,
    proposed_by TEXT NOT NULL DEFAULT 'system',
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    promoted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_release_proposals_status_type
ON release_proposals (status, proposal_type, created_at DESC);

CREATE TABLE IF NOT EXISTS release_proposal_audit (
    id BIGSERIAL PRIMARY KEY,
    proposal_id BIGINT NOT NULL REFERENCES release_proposals (id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_release_proposal_audit_proposal_created
ON release_proposal_audit (proposal_id, created_at DESC);

CREATE TABLE IF NOT EXISTS proposal_reviews (
    id BIGSERIAL PRIMARY KEY,
    proposal_id BIGINT NOT NULL REFERENCES release_proposals (id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (
        action IN ('submit_review', 'approve', 'reject', 'request_changes', 'promote')
    ),
    actor TEXT NOT NULL,
    rationale TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_proposal_reviews_proposal_created
ON proposal_reviews (proposal_id, created_at DESC);

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

CREATE TABLE IF NOT EXISTS lexicon_entry_embeddings (
    lexicon_entry_id BIGINT PRIMARY KEY
        REFERENCES lexicon_entries (id)
        ON DELETE CASCADE,
    embedding VECTOR(64) NOT NULL,
    embedding_model TEXT NOT NULL DEFAULT 'hash-bow-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_lexicon_entry_embeddings_model
ON lexicon_entry_embeddings (embedding_model, updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_lexicon_entry_embeddings_vector
ON lexicon_entry_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 32);

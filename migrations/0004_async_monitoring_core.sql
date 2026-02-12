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

-- Ensure monitoring_queue supports idempotent enqueue semantics:
-- one queue row per monitoring event.

CREATE TEMP TABLE IF NOT EXISTS _monitoring_queue_dupe_map (
    duplicate_id BIGINT PRIMARY KEY,
    keep_id BIGINT NOT NULL
) ON COMMIT DROP;

TRUNCATE _monitoring_queue_dupe_map;

INSERT INTO _monitoring_queue_dupe_map (duplicate_id, keep_id)
SELECT ranked.id AS duplicate_id, ranked.keep_id
FROM (
    SELECT
        id,
        event_id,
        ROW_NUMBER() OVER (
            PARTITION BY event_id
            ORDER BY updated_at DESC, id DESC
        ) AS row_rank,
        FIRST_VALUE(id) OVER (
            PARTITION BY event_id
            ORDER BY updated_at DESC, id DESC
        ) AS keep_id
    FROM monitoring_queue
) AS ranked
WHERE ranked.row_rank > 1;

UPDATE monitoring_queue_audit AS audit
SET queue_id = dupe.keep_id
FROM _monitoring_queue_dupe_map AS dupe
WHERE audit.queue_id = dupe.duplicate_id;

UPDATE release_proposals AS proposals
SET queue_id = dupe.keep_id
FROM _monitoring_queue_dupe_map AS dupe
WHERE proposals.queue_id = dupe.duplicate_id;

DELETE FROM monitoring_queue AS queue_rows
USING _monitoring_queue_dupe_map AS dupe
WHERE queue_rows.id = dupe.duplicate_id;

CREATE UNIQUE INDEX IF NOT EXISTS ux_monitoring_queue_event
ON monitoring_queue (event_id);

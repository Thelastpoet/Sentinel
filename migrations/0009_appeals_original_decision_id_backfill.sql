ALTER TABLE IF EXISTS appeals
ADD COLUMN IF NOT EXISTS original_decision_id TEXT;

UPDATE appeals
SET original_decision_id = request_id
WHERE original_decision_id IS NULL;

ALTER TABLE IF EXISTS appeals
ALTER COLUMN original_decision_id SET NOT NULL;

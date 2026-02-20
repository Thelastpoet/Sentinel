-- 0013_multi_model_embeddings.sql
--
-- Adds a multi-model embedding table to support coexisting embedding backends
-- (e.g. 64-dim hash-bow-v1 and 384-dim e5-multilingual-small-v1) while keeping
-- per-model ANN indexes dimension-consistent via partial indexes.
--
-- This migration is additive: it does not modify or drop lexicon_entry_embeddings (v1).

CREATE TABLE IF NOT EXISTS lexicon_entry_embeddings_v2 (
    lexicon_entry_id BIGINT NOT NULL
        REFERENCES lexicon_entries (id)
        ON DELETE CASCADE,
    embedding_model TEXT NOT NULL,
    embedding_dim INT NOT NULL,
    embedding VECTOR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (lexicon_entry_id, embedding_model),
    CONSTRAINT lexicon_entry_embeddings_v2_embedding_dim_check
        CHECK (vector_dims(embedding) = embedding_dim)
);

CREATE INDEX IF NOT EXISTS ix_lex_emb_v2_model
ON lexicon_entry_embeddings_v2 (embedding_model, updated_at DESC);

-- Partial ANN indexes (IVFFlat requires a fixed vector dimension per index).
CREATE INDEX IF NOT EXISTS ix_lex_emb_v2_hash_bow_v1
ON lexicon_entry_embeddings_v2
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 32)
WHERE embedding_model = 'hash-bow-v1';

CREATE INDEX IF NOT EXISTS ix_lex_emb_v2_e5_small_v1
ON lexicon_entry_embeddings_v2
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 32)
WHERE embedding_model = 'e5-multilingual-small-v1';

-- Backfill existing hash-bow-v1 vectors from v1 to v2 (idempotent).
INSERT INTO lexicon_entry_embeddings_v2
  (lexicon_entry_id, embedding_model, embedding_dim, embedding, created_at, updated_at)
SELECT
  lexicon_entry_id,
  'hash-bow-v1',
  64,
  embedding,
  created_at,
  updated_at
FROM lexicon_entry_embeddings
WHERE embedding_model = 'hash-bow-v1'
ON CONFLICT (lexicon_entry_id, embedding_model) DO NOTHING;

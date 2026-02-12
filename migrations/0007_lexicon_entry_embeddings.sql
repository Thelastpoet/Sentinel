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

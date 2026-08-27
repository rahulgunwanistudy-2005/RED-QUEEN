-- M1 corpus columns (SOF-166). Idempotent — safe to re-apply.
-- The mutation loop stores each candidate's operators + score so a later campaign
-- can retrieve successful ancestors and few-shot the mutator from what worked.

ALTER TABLE payload_corpus ADD COLUMN IF NOT EXISTS operators JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE payload_corpus ADD COLUMN IF NOT EXISTS parent_id VARCHAR(64);
ALTER TABLE payload_corpus ADD COLUMN IF NOT EXISTS score INTEGER;
ALTER TABLE payload_corpus ADD COLUMN IF NOT EXISTS trace_id VARCHAR(32);

-- Cosine-distance index for top-k retrieval over the 768-d embedding.
CREATE INDEX IF NOT EXISTS payload_corpus_embedding_idx
    ON payload_corpus USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

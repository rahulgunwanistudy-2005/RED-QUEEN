-- M0 schema. Idempotent so run_migrations() can re-apply safely.

CREATE EXTENSION IF NOT EXISTS vector;

-- Findings: one row per red-team attempt (SOF-160 persists here).
CREATE TABLE IF NOT EXISTS findings (
    id            SERIAL PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    attack_class  VARCHAR(64) NOT NULL,
    payload       TEXT        NOT NULL,
    scan_blocked  BOOLEAN     NOT NULL,
    scan_detected JSONB       NOT NULL,
    scan_score    DOUBLE PRECISION NOT NULL,
    agent_action  VARCHAR(64) NOT NULL,
    authorized    BOOLEAN     NOT NULL,
    bypass        BOOLEAN     NOT NULL,
    verdict       JSONB       NOT NULL,
    trace_id      VARCHAR(32) NOT NULL
);

-- Payload corpus with pgvector embedding column. M1 (SOF-163) fills this; M0
-- only proves the extension + column type work.
CREATE TABLE IF NOT EXISTS payload_corpus (
    id           SERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    attack_class VARCHAR(64) NOT NULL,
    payload      TEXT        NOT NULL,
    generation   INTEGER     NOT NULL DEFAULT 0,
    bypass       BOOLEAN,
    embedding    vector(768)
);

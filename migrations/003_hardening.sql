-- M2 schema (SOF-168/169/170/171). Idempotent so run_migrations() can re-apply safely.
--
-- The hardening loop is "a table + a reducer": `hardening_runs` holds one row per
-- (agent_id, payload_hash) — that pair IS the idempotency key (SOF-168). `policies`
-- holds the applied policy deltas (policy is data, not code — SOF-169), keyed by a
-- deterministic policy_id whose UNIQUE constraint is the exactly-once apply guard.
-- `verifications` is written by the FIREWALLED verifier under its own restricted DB
-- role (SOF-170); the machine only reads it.

-- --- policies: the applied deltas (uniform shape across the 3 GEAP targets) ------
CREATE TABLE IF NOT EXISTS policies (
    id             SERIAL PRIMARY KEY,
    policy_id      VARCHAR(96) NOT NULL UNIQUE,   -- deterministic; UNIQUE = the apply guard
    agent_id       VARCHAR(64) NOT NULL,
    attack_class   VARCHAR(64) NOT NULL,
    target         VARCHAR(32) NOT NULL,          -- model_armor | gateway | identity
    payload_hash   VARCHAR(64) NOT NULL,
    delta          JSONB       NOT NULL,          -- the rule (data)
    is_destructive BOOLEAN     NOT NULL DEFAULT FALSE,
    applied        BOOLEAN     NOT NULL DEFAULT FALSE,
    applied_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --- hardening_runs: one durable state-machine instance per idempotency key ------
CREATE TABLE IF NOT EXISTS hardening_runs (
    id                SERIAL PRIMARY KEY,
    agent_id          VARCHAR(64) NOT NULL,
    payload_hash      VARCHAR(64) NOT NULL,
    attack_class      VARCHAR(64) NOT NULL,
    state             VARCHAR(32) NOT NULL,       -- BYPASS_FOUND|HARDENING|AWAIT_APPROVAL|VERIFYING|CLOSED|FALSE_CLOSED|STILL_OPEN
    finding_id        INTEGER,
    winning_payload   TEXT        NOT NULL,       -- red-team state (hardener may hold; verifier may NOT)
    remedy            VARCHAR(16) NOT NULL DEFAULT 'content',  -- content | identity | exact
    policy_id         VARCHAR(96),                -- fk-ish to policies.policy_id
    policy_intent     JSONB,                      -- written BEFORE geap.enforce_policy (SOF-168)
    is_destructive    BOOLEAN     NOT NULL DEFAULT FALSE,
    approval          VARCHAR(16),                -- NULL | approved | rejected (SOF-171)
    verdict           VARCHAR(16),                -- CLOSED | FALSE_CLOSED | STILL_OPEN
    sub_scores        JSONB,
    verify_seed       INTEGER     NOT NULL DEFAULT 0,
    attack_trace_id   VARCHAR(32),
    harden_trace_id   VARCHAR(32),
    verify_trace_id   VARCHAR(32),
    error             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (agent_id, payload_hash)               -- THE idempotency key (SOF-168)
);

-- --- run_spans: ordered OTel span summaries for the trace waterfall (SOF-172) ----
CREATE TABLE IF NOT EXISTS run_spans (
    id           SERIAL PRIMARY KEY,
    run_id       INTEGER     NOT NULL,
    phase        VARCHAR(16) NOT NULL,            -- attack | harden | verify
    name         VARCHAR(96) NOT NULL,
    trace_id     VARCHAR(32) NOT NULL,
    started_ms   DOUBLE PRECISION NOT NULL,       -- ms offset from cycle start
    duration_ms  DOUBLE PRECISION NOT NULL,
    attributes   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS run_spans_run_idx ON run_spans (run_id, started_ms);

-- --- verifications: the FIREWALLED verifier's independent record (SOF-170) -------
-- Written by the verifier subprocess under the restricted `sentinel_verifier`
-- role. The verifier can write here and read `policies`, but is DENIED the
-- attacker's corpus and findings (the "known answer") — see the role block below.
CREATE TABLE IF NOT EXISTS verifications (
    id                SERIAL PRIMARY KEY,
    run_id            INTEGER     NOT NULL,
    attack_class      VARCHAR(64) NOT NULL,
    verdict           VARCHAR(16) NOT NULL,       -- CLOSED | FALSE_CLOSED | STILL_OPEN
    sub_scores        JSONB       NOT NULL,
    seed_blocked      BOOLEAN     NOT NULL,       -- public naive seed blocked under the patch?
    evolved_bypass    BOOLEAN     NOT NULL,       -- did an independently-evolved attack bypass?
    evolved_payload_id VARCHAR(64),
    evolved_gen       INTEGER,
    verify_trace_id   VARCHAR(32),
    backend           VARCHAR(16) NOT NULL DEFAULT 'shim',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS verifications_run_idx ON verifications (run_id);

-- --- the firewalled verifier DB role (SOF-170 isolation) ------------------------
-- Enforces genuine isolation at the credential level: a DISTINCT role that CANNOT
-- read the red-team corpus or findings. This stands in for a distinct GCP Agent
-- Identity / service account whose IAM binding denies read on the red-team's
-- Cloud SQL tables + Memory Bank. Swap = point VERIFIER_DATABASE_URL at the SA.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sentinel_verifier') THEN
        CREATE ROLE sentinel_verifier LOGIN PASSWORD 'verifierpass';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO sentinel_verifier;
-- What the verifier MAY do: read the active policy (to test the patch) + write its verdict.
GRANT SELECT ON policies TO sentinel_verifier;
GRANT SELECT, INSERT ON verifications TO sentinel_verifier;
GRANT USAGE, SELECT ON SEQUENCE verifications_id_seq TO sentinel_verifier;
-- What the verifier MUST NOT do: read the attacker's corpus or the stored winner.
REVOKE ALL ON payload_corpus FROM sentinel_verifier;
REVOKE ALL ON findings       FROM sentinel_verifier;
REVOKE ALL ON hardening_runs FROM sentinel_verifier;

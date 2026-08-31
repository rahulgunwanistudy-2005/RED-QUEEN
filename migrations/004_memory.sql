-- M3 schema (SOF-174). The Postgres shim tier for the per-agent risk profile that
-- backs the Memory Bank seam. Idempotent so run_migrations() can re-apply safely.
--
-- One row per agent: the durable, cross-campaign risk profile (known weaknesses,
-- the operator sequence that won, the policy that closed it, campaigns seen). The
-- REAL tier is Vertex AI Agent Engine Memory Bank (behind USE_REAL_MEMORY); this
-- table is the faithful stand-in behind the same `platform.memory` seam.
CREATE TABLE IF NOT EXISTS agent_memory (
    agent_id    VARCHAR(64) PRIMARY KEY,
    profile     JSONB       NOT NULL,          -- {known_weaknesses, winning_operators, applied_policies, campaigns}
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The firewalled verifier (SOF-170) must NOT read the agent's memory profile — it
-- re-derives independently. Deny it explicitly (belt-and-suspenders; it has no grant
-- here anyway). Guarded so it is a no-op before the role exists.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sentinel_verifier') THEN
        REVOKE ALL ON agent_memory FROM sentinel_verifier;
    END IF;
END
$$;

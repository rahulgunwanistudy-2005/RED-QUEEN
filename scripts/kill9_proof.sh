#!/usr/bin/env bash
# SOF-168 money proof: a REAL kill -9 of the worker mid-HARDENING (right after the
# policy is applied, before the state commits to VERIFYING). On restart the worker
# resumes from Postgres and drives to CLOSED with EXACTLY ONE policy — no duplicate.
set -uo pipefail
cd /Users/rahul/RED-QUEEN
export PYTHONPATH=.
PY=.venv/bin/python
PIDFILE=/tmp/sentinel_crash.pid
PSQL() { docker compose exec -T db psql -tA -U sentinel -d sentinel "$@"; }

echo "### 0. reset hardening tables"
PSQL -c "TRUNCATE hardening_runs, policies, verifications, run_spans RESTART IDENTITY;" >/dev/null

echo "### 1. evolve an attack + open a BYPASS_FOUND run (not yet driven)"
TRACE_CONSOLE=0 $PY - <<'PY'
from sentinel.harden.orchestrator import attack_and_open
run = attack_and_open("prompt_injection", seed=1337, remedy="content", use_corpus=False)
print(f"opened run id={run.id} state={run.state} payload_hash={run.payload_hash}")
PY

echo "### 2. start worker with CRASH_AT=post_apply (blocks after enforce_policy, pre-commit)"
rm -f "$PIDFILE"
CRASH_AT=post_apply CRASH_PIDFILE="$PIDFILE" CRASH_STALL_S=60 TRACE_CONSOLE=0 \
    $PY -m sentinel.harden worker --quiet >/tmp/sentinel_worker1.log 2>&1 &
WPID=$!
echo "worker pid=$WPID"

echo "### 3. wait for the worker to reach the crash hook (mid-HARDENING)"
for i in $(seq 1 60); do [ -f "$PIDFILE" ] && break; sleep 0.5; done
HOOKPID=$(cat "$PIDFILE" 2>/dev/null || echo "$WPID")

echo "--- DB state AT the crash boundary (policy applied, run still HARDENING) ---"
PSQL -c "SELECT id,state FROM hardening_runs;"
PSQL -c "SELECT count(*) AS applied_policies FROM policies WHERE applied;"

echo "### 4. >>> kill -9 the worker (real SIGKILL) <<<"
kill -9 "$HOOKPID" 2>/dev/null
kill -9 "$WPID" 2>/dev/null
wait "$WPID" 2>/dev/null
echo "worker exit code: $?  (137 = 128+SIGKILL(9))"

echo "--- DB state AFTER the kill (unchanged; durable) ---"
PSQL -c "SELECT id,state,verdict FROM hardening_runs;"
PSQL -c "SELECT policy_id,applied FROM policies;"

echo "### 5. restart the worker (no CRASH_AT) -> it must resume to CLOSED, one policy"
TRACE_CONSOLE=0 $PY -m sentinel.harden worker --once >/tmp/sentinel_worker2.log 2>&1
grep -E 'STATE=|APPLIED|VERDICT' /tmp/sentinel_worker2.log | sed 's/^/    /'

echo "--- FINAL DB state ---"
PSQL -c "SELECT id,state,verdict FROM hardening_runs;"
echo "applied policy rows (MUST be exactly 1):"
PSQL -c "SELECT count(*) FROM policies WHERE applied;"
PSQL -c "SELECT policy_id, applied, applied_at FROM policies;"

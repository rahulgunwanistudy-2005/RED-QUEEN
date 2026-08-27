<script>
  // Verifier verdict panel (SOF-172). Per hardening run: the firewalled verifier's
  // independent verdict (CLOSED / FALSE-CLOSED / STILL-OPEN) + the three orthogonal
  // sub-scores, plus a one-click approve/reject gate when a destructive policy is
  // paused at AWAIT_APPROVAL (SOF-171). Pure view off the shared stream + fetches.
  import { runs, selectedRun, approveRun, fetchTraces } from "./store.js";

  $: runList = Object.values($runs).sort((a, b) => b.run_id - a.run_id);

  const VERDICT_LABEL = {
    CLOSED: "CLOSED",
    FALSE_CLOSED: "FALSE-CLOSED",
    STILL_OPEN: "STILL-OPEN",
  };
  const SUBS = [
    ["armor_blocked", "blocked?"],
    ["behavior_unchanged", "behavior?"],
    ["secret_contained", "secret?"],
  ];

  function verdictClass(v) {
    if (v === "CLOSED") return "ok";
    if (v === "FALSE_CLOSED") return "false";
    if (v === "STILL_OPEN") return "open";
    return "pending";
  }

  let busy = {};
  async function decide(runId, decision) {
    busy = { ...busy, [runId]: true };
    try {
      await approveRun(runId, decision);
    } finally {
      busy = { ...busy, [runId]: false };
    }
  }

  function select(runId) {
    selectedRun.set(runId);
    fetchTraces(runId);
  }
</script>

<h2>VERIFIER VERDICTS <span class="muted mono">firewalled · independent</span></h2>

<div class="runs">
  {#each runList as r (r.run_id)}
    <div
      class="run"
      class:sel={$selectedRun === r.run_id}
      on:click={() => select(r.run_id)}
      on:keydown={(e) => (e.key === "Enter" || e.key === " ") && select(r.run_id)}
      role="button"
      tabindex="0"
    >
      <div class="top">
        <span class="rid mono">run {r.run_id}</span>
        <span class="ac">{r.attack_class || "—"}</span>
        <span class="verdict {verdictClass(r.verdict)}">
          {r.verdict ? VERDICT_LABEL[r.verdict] : (r.state || "…")}
        </span>
      </div>

      {#if r.sub_scores}
        <div class="subs">
          {#each SUBS as [key, label]}
            <span class="sub" class:pass={r.sub_scores[key]} class:fail={!r.sub_scores[key]}>
              {r.sub_scores[key] ? "✓" : "✕"} {label}
            </span>
          {/each}
        </div>
      {/if}

      {#if r.policy_id}
        <div class="pol mono">
          ⛊ {r.policy_id}
          {#if r.is_destructive}<span class="destr">DESTRUCTIVE</span>{/if}
        </div>
      {/if}

      {#if r.awaiting}
        <div class="approval">
          <div class="rationale">{r.rationale || "Destructive policy — approval required."}</div>
          <div class="btns">
            <button class="approve" disabled={busy[r.run_id]} on:click|stopPropagation={() => decide(r.run_id, "approved")}>
              APPROVE
            </button>
            <button class="reject" disabled={busy[r.run_id]} on:click|stopPropagation={() => decide(r.run_id, "rejected")}>
              REJECT
            </button>
          </div>
        </div>
      {/if}
    </div>
  {:else}
    <div class="empty muted">no hardening runs yet — run a harden cycle</div>
  {/each}
</div>

<style>
  h2 {
    margin: 0 0 14px;
    font-size: 13px;
    letter-spacing: 0.16em;
    color: var(--muted);
    font-weight: 700;
  }
  .runs { display: flex; flex-direction: column; gap: 10px; }
  .run {
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    cursor: pointer;
    background: rgba(255, 255, 255, 0.015);
    transition: border-color 0.15s;
  }
  .run:hover { border-color: #2c3e50; }
  .run.sel { border-color: var(--blue); box-shadow: 0 0 0 1px var(--blue) inset; }
  .top { display: flex; align-items: center; gap: 10px; }
  .rid { color: var(--muted); font-size: 12px; }
  .ac { color: #b9c6d3; font-size: 12px; flex: 1; }
  .verdict {
    font-weight: 800;
    font-size: 12px;
    letter-spacing: 0.06em;
    padding: 2px 8px;
    border-radius: 5px;
  }
  .verdict.ok { color: #041; background: #2ecc71; }
  .verdict.false { color: #fff; background: #e67e22; }
  .verdict.open { color: #fff; background: var(--red); }
  .verdict.pending { color: var(--muted); background: #1e2b37; }
  .subs { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
  .sub {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 5px;
    letter-spacing: 0.03em;
  }
  .sub.pass { color: #2ecc71; background: rgba(46, 204, 113, 0.12); }
  .sub.fail { color: var(--red); background: rgba(255, 59, 82, 0.12); }
  .pol { margin-top: 9px; font-size: 11px; color: var(--muted); }
  .destr {
    color: #e67e22;
    border: 1px solid #e67e22;
    border-radius: 4px;
    padding: 0 5px;
    margin-left: 6px;
    font-weight: 700;
  }
  .approval {
    margin-top: 11px;
    padding-top: 11px;
    border-top: 1px dashed #2c3e50;
  }
  .rationale { font-size: 11.5px; color: #cdd8e2; margin-bottom: 9px; line-height: 1.4; }
  .btns { display: flex; gap: 8px; }
  button {
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.08em;
    cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: default; }
  .approve { background: #2ecc71; color: #04210f; }
  .reject { background: #33404c; color: #e6edf3; }
  .empty { padding: 16px 4px; font-size: 12px; }
  .muted { color: var(--muted); }
</style>

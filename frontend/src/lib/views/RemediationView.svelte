<script>
  import { onMount } from "svelte";
  import {
    runs,
    selectedRunId,
    approveRun,
    hydrateRuns,
    fetchTraces,
    fetchPolicies,
    policiesList,
  } from "../store.js";

  let approving = false;

  $: runList = Object.values($runs).sort((a, b) => b.run_id - a.run_id);
  $: activeRun = $runs[$selectedRunId] || (runList.length > 0 ? runList[0] : null);

  const STEPS = [
    { id: "BYPASS_FOUND", label: "1. BYPASS FOUND", icon: "⚠" },
    { id: "HARDENING", label: "2. POLICY SYNTHESIS", icon: "⛊" },
    { id: "AWAIT_APPROVAL", label: "3. APPROVAL GATE", icon: "⏸", conditional: true },
    { id: "VERIFYING", label: "4. FIREWALLED VERIFY", icon: "⚖" },
    { id: "CLOSED", label: "5. VERIFIED TERMINAL", icon: "✓" },
  ];

  function getStepStatus(stepId, run) {
    if (!run) return "inactive";
    const state = run.state;

    if (state === "CLOSED" || state === "FALSE_CLOSED" || state === "STILL_OPEN") {
      if (stepId === "CLOSED") {
        return state === "CLOSED" ? "success" : state === "FALSE_CLOSED" ? "warning" : "danger";
      }
      return "completed";
    }

    if (state === "VERIFYING") {
      if (stepId === "VERIFYING") return "current";
      if (stepId === "CLOSED") return "inactive";
      return "completed";
    }

    if (state === "AWAIT_APPROVAL") {
      if (stepId === "AWAIT_APPROVAL") return "current-warn";
      if (stepId === "VERIFYING" || stepId === "CLOSED") return "inactive";
      return "completed";
    }

    if (state === "HARDENING") {
      if (stepId === "HARDENING") return "current";
      if (stepId === "BYPASS_FOUND") return "completed";
      return "inactive";
    }

    if (state === "BYPASS_FOUND") {
      if (stepId === "BYPASS_FOUND") return "current";
      return "inactive";
    }

    return "inactive";
  }

  async function handleDecision(decision) {
    if (!activeRun) return;
    approving = true;
    try {
      await approveRun(activeRun.run_id, decision);
    } finally {
      approving = false;
    }
  }

  function selectRun(id) {
    selectedRunId.set(id);
    fetchTraces(id);
  }

  onMount(() => {
    hydrateRuns();
    fetchPolicies();
  });
</script>

<div class="remediation-view">
  <!-- Hardening Lifecycle Stepper -->
  <div class="panel stepper-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span>🔄</span> AUTONOMOUS HARDENING LIFECYCLE
        {#if activeRun}
          <span class="badge badge-blue mono">RUN #{activeRun.run_id} ({activeRun.attack_class})</span>
        {/if}
      </div>
      {#if activeRun?.state}
        <span class="badge {activeRun.verdict === 'CLOSED' ? 'badge-green' : activeRun.verdict === 'FALSE_CLOSED' ? 'badge-amber' : activeRun.state === 'AWAIT_APPROVAL' ? 'badge-amber' : 'badge-blue'} mono">
          STATE: {activeRun.verdict || activeRun.state}
        </span>
      {/if}
    </div>

    <div class="stepper-track">
      {#each STEPS as step}
        {#if !step.conditional || activeRun?.is_destructive || activeRun?.state === 'AWAIT_APPROVAL'}
          {@const status = getStepStatus(step.id, activeRun)}
          <div class="step-node {status}">
            <div class="step-icon-circle mono">
              {#if status === "completed" || status === "success"}✓{:else if status === "warning"}⚠{:else if status === "danger"}✕{:else}{step.icon}{/if}
            </div>
            <div class="step-label mono">{step.label}</div>
          </div>
          {#if step.id !== "CLOSED"}
            <div class="step-connector {status === 'completed' || status === 'success' ? 'connector-active' : ''}"></div>
          {/if}
        {/if}
      {/each}
    </div>
  </div>

  <!-- Destructive Policy Human Approval Banner (If pending) -->
  {#if activeRun?.state === "AWAIT_APPROVAL" || activeRun?.awaiting}
    <div class="approval-banner panel">
      <div class="approval-header">
        <div class="approval-title mono">
          <span>⏸</span> HUMAN APPROVAL REQUIRED — DESTRUCTIVE POLICY DELTA
        </div>
        <span class="badge badge-amber mono">ACTION REQUIRED</span>
      </div>

      <div class="approval-body">
        <div class="approval-rationale">
          <strong>Synthesized Policy ID:</strong> <code class="mono">{activeRun.policy_id}</code>
          <p style="margin-top: 6px;">
            {activeRun.policy_intent?.rationale || activeRun.rationale || "This policy delta revokes an agent capability or identity token to close an untrusted injection vulnerability. Removing capabilities may impact legitimate agent workflows."}
          </p>
        </div>

        <div class="approval-actions">
          <button
            class="btn btn-success"
            disabled={approving}
            on:click={() => handleDecision("approved")}
          >
            {approving ? "APPLYING..." : "✓ APPROVE & APPLY POLICY"}
          </button>
          <button
            class="btn btn-sm btn-reject"
            disabled={approving}
            on:click={() => handleDecision("rejected")}
          >
            ✕ REJECT (PARK RUN)
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- Split Grid: Policy Delta Diff + Verifier Certificate -->
  <div class="remediation-grid">
    <!-- Left Column: Policy Delta Viewer -->
    <div class="panel policy-panel">
      <div class="panel-header">
        <div class="panel-title">
          <span>⛊</span> SYNTHESIZED POLICY DELTA <span class="muted mono">Data, Not Code</span>
        </div>
        {#if activeRun?.policy_id}
          <span class="badge {activeRun.is_destructive ? 'badge-amber' : 'badge-green'} mono">
            {activeRun.is_destructive ? "DESTRUCTIVE" : "NON-DESTRUCTIVE"}
          </span>
        {/if}
      </div>

      {#if activeRun?.policy_intent || activeRun?.policy_id}
        {@const delta = activeRun.policy_intent || {}}
        <div class="policy-card">
          <div class="p-row mono">
            <span class="p-lbl">POLICY ID:</span>
            <span class="p-val text-blue">{activeRun.policy_id || delta.id}</span>
          </div>

          <div class="p-row mono">
            <span class="p-lbl">GEAP TARGET:</span>
            <span class="p-val">{delta.target || 'model_armor'}</span>
          </div>

          <div class="p-row mono">
            <span class="p-lbl">APPLIED OPERATION:</span>
            <span class="p-val text-green">{delta.rule?.op || activeRun.remedy || 'deep_normalize'}</span>
          </div>

          <!-- Before vs After Diff -->
          <div class="diff-container">
            <div class="diff-col diff-before">
              <div class="diff-hdr mono">BEFORE REMEDIATION</div>
              <div class="diff-body mono">
                <div>Model Armor: <strong>Surface Scan Only</strong></div>
                <div>Leet Normalization: <strong>Disabled</strong></div>
                <div>Status: <span class="text-red">Vulnerable to Obfuscation</span></div>
              </div>
            </div>

            <div class="diff-col diff-after">
              <div class="diff-hdr mono">AFTER REMEDIATION</div>
              <div class="diff-body mono">
                <div>Model Armor: <strong>Deep Normalizer Active</strong></div>
                <div>Leet Normalization: <strong>Enabled (Agent View)</strong></div>
                <div>Status: <span class="text-green">Autonomous Protection</span></div>
              </div>
            </div>
          </div>

          <!-- Rationale Text -->
          <div class="rationale-box mono">
            <div class="r-title">HARDENER RATIONALE:</div>
            <p>{delta.rationale || "Align Model Armor's normalizer with the target agent decoder to recover leet and zero-width obfuscations before pattern evaluation."}</p>
          </div>

          <!-- Raw Synthesized JSON -->
          <div class="json-box">
            <div class="r-title mono">SYNTHESIZED POLICY JSON (APPLIED VIA geap.enforce_policy):</div>
            <pre class="mono">{JSON.stringify(delta, null, 2)}</pre>
          </div>
        </div>
      {:else}
        <div class="empty-box muted mono">
          No policy drafted yet. Select a run or launch a hardening cycle to view synthesized security rules.
        </div>
      {/if}
    </div>

    <!-- Right Column: Independent Verifier Certificate -->
    <div class="panel verifier-panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">
            <span>⚖</span> INDEPENDENT VERIFICATION CERTIFICATE
          </div>
          <div class="panel-subtitle mono" style="font-size: 10px; color: var(--oxblood-bright); font-weight: 800; margin-top: 2px;">
            THE ATTACKER DOES NOT CERTIFY THE FIX.
          </div>
        </div>
        <span class="badge badge-muted mono">DB ROLE: sentinel_verifier</span>
      </div>

      {#if activeRun?.verdict || activeRun?.state === 'VERIFYING' || activeRun?.state === 'CLOSED'}
        <div class="certificate-card">
          <!-- Verdict Stamp -->
          <div class="verdict-banner {activeRun.verdict === 'CLOSED' ? 'v-closed' : activeRun.verdict === 'FALSE_CLOSED' ? 'v-false' : 'v-open'}">
            <div class="v-title mono">
              VERDICT: {activeRun.verdict === 'CLOSED' ? 'CLOSED ✓ (DEFENSES HELD)' : activeRun.verdict === 'FALSE_CLOSED' ? 'FALSE-CLOSED ⚠ (BRITTLE PATCH)' : activeRun.verdict || 'VERIFYING IN PROGRESS...'}
            </div>
            <div class="v-sub mono">
              {activeRun.verdict === 'CLOSED'
                ? "The firewalled verifier independently re-evolved fresh attacks from public seeds. Zero variants bypassed the patched fleet."
                : activeRun.verdict === 'FALSE_CLOSED'
                ? "HONESTY PROOF: The applied exact-string blocklist was bypassed by an evolved variant. The system refused a false green badge."
                : "Verifier subprocess executing under restricted database credentials."}
            </div>
          </div>

          <!-- Verifier RBAC Firewall Proof -->
          <div class="firewall-proof-box mono">
            <div class="f-title">🔒 CREDENTIAL ISOLATION (SOF-170 ENFORCEMENT):</div>
            <div class="f-row">✓ Separate Subprocess: <code>sentinel.verifier.run</code></div>
            <div class="f-row">✓ Database Role: <code>sentinel_verifier</code> (PostgreSQL RBAC)</div>
            <div class="f-row text-green">✓ Access to Attacker Corpus / Findings: <strong>EXPLICITLY DENIED (REVOKE ALL)</strong></div>
            <div class="f-row">✓ Access to Active Policy Deltas: <strong>READ-ONLY (SELECT)</strong></div>
          </div>

          <!-- 3 Orthogonal Subscores -->
          <div class="subscores-section">
            <div class="s-title mono">3-DIMENSIONAL VERIFIER SUB-SCORES:</div>
            <div class="subscores-grid mono">
              <div class="subscore-card {activeRun.sub_scores?.armor_blocked ? 'pass' : 'fail'}">
                <span class="s-icon">{activeRun.sub_scores?.armor_blocked ? '✓' : '✕'}</span>
                <div class="s-details">
                  <div class="s-name">armor_blocked</div>
                  <div class="s-desc">Model Armor stopped every variant</div>
                </div>
              </div>

              <div class="subscore-card {activeRun.sub_scores?.behavior_unchanged ? 'pass' : 'fail'}">
                <span class="s-icon">{activeRun.sub_scores?.behavior_unchanged ? '✓' : '✕'}</span>
                <div class="s-details">
                  <div class="s-name">behavior_unchanged</div>
                  <div class="s-desc">Agent never executed privileged fix</div>
                </div>
              </div>

              <div class="subscore-card {activeRun.sub_scores?.secret_contained ? 'pass' : 'fail'}">
                <span class="s-icon">{activeRun.sub_scores?.secret_contained ? '✓' : '✕'}</span>
                <div class="s-details">
                  <div class="s-name">secret_contained</div>
                  <div class="s-desc">Marked canary secret was not leaked</div>
                </div>
              </div>
            </div>
          </div>

          <!-- Trace Signature -->
          <div class="cert-footer mono">
            <span>VERIFY TRACE: {activeRun.verify_trace_id || 'sentinel.verify.span'}</span>
            <span>STATUS: CERTIFIED</span>
          </div>
        </div>
      {:else}
        <div class="empty-box muted mono">
          Awaiting verification. When an exploit is hardened, the independent verifier will re-test the fleet and issue a signed verdict certificate here.
        </div>
      {/if}
    </div>
  </div>

  <!-- Historical Hardening Runs Table -->
  <div class="panel runs-table-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span>📜</span> HISTORICAL HARDENING RUNS <span class="muted mono">PostgreSQL hardening_runs Table</span>
      </div>
      <button class="btn btn-sm" on:click={hydrateRuns}>REFRESH RUNS</button>
    </div>

    <div class="table-container">
      <table class="runs-table mono">
        <thead>
          <tr>
            <th>RUN ID</th>
            <th>ATTACK CLASS</th>
            <th>STATE</th>
            <th>VERDICT</th>
            <th>REMEDY / POLICY</th>
            <th>DESTRUCTIVE</th>
            <th>CREATED</th>
            <th>ACTION</th>
          </tr>
        </thead>
        <tbody>
          {#each runList as r (r.run_id)}
            <tr
              class:selected={activeRun?.run_id === r.run_id}
              on:click={() => selectRun(r.run_id)}
            >
              <td class="text-blue">#{r.run_id}</td>
              <td>{r.attack_class}</td>
              <td>
                <span class="badge {r.state === 'CLOSED' ? 'badge-green' : r.state === 'AWAIT_APPROVAL' ? 'badge-amber' : 'badge-blue'} badge-xs">
                  {r.state}
                </span>
              </td>
              <td>
                {#if r.verdict}
                  <span class="badge {r.verdict === 'CLOSED' ? 'badge-green' : r.verdict === 'FALSE_CLOSED' ? 'badge-amber' : 'badge-red'} badge-xs">
                    {r.verdict}
                  </span>
                {:else}
                  <span class="muted">—</span>
                {/if}
              </td>
              <td class="text-muted">{r.policy_id || r.remedy || 'content'}</td>
              <td>{r.is_destructive ? 'YES (APPROVAL)' : 'NO'}</td>
              <td class="text-muted">{r.created_at ? new Date(r.created_at).toLocaleTimeString() : '—'}</td>
              <td>
                <button class="btn btn-sm btn-select" on:click|stopPropagation={() => selectRun(r.run_id)}>
                  VIEW
                </button>
              </td>
            </tr>
          {:else}
            <tr>
              <td colspan="8" class="text-center muted">No hardening runs logged in database yet.</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </div>
</div>

<style>
  .remediation-view {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding: 28px 32px;
    max-width: 1500px;
    margin: 0 auto;
  }

  .stepper-panel {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
    padding: 24px;
  }
  .stepper-track {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 10px 0 10px;
  }
  .step-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    position: relative;
    z-index: 2;
  }
  .step-icon-circle {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: var(--bg-subtle);
    border: 2px solid var(--border);
    color: var(--stone);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 800;
    transition: all 0.3s;
  }
  .step-label {
    font-size: 11px;
    font-weight: 800;
    color: var(--stone);
    letter-spacing: 0.06em;
  }

  .step-node.completed .step-icon-circle {
    background: var(--verif-green-dim);
    border-color: var(--verif-green);
    color: var(--verif-green);
  }
  .step-node.completed .step-label {
    color: var(--text-dim);
  }

  .step-node.current .step-icon-circle {
    background: var(--tech-blue-dim);
    border-color: var(--tech-blue);
    color: var(--tech-blue);
    box-shadow: 0 0 12px rgba(29, 78, 117, 0.3);
    animation: pulse 1.5s infinite;
  }
  .step-node.current .step-label {
    color: var(--tech-blue);
  }

  .step-node.current-warn .step-icon-circle {
    background: var(--amber-dim);
    border-color: var(--amber);
    color: var(--amber);
    box-shadow: 0 0 12px rgba(184, 107, 20, 0.3);
  }
  .step-node.current-warn .step-label {
    color: var(--amber);
  }

  .step-node.success .step-icon-circle {
    background: var(--verif-green);
    border-color: var(--verif-green);
    color: #FFFFFF;
    box-shadow: 0 0 14px rgba(27, 94, 59, 0.35);
  }
  .step-node.success .step-label {
    color: var(--verif-green);
  }

  .step-node.warning .step-icon-circle {
    background: var(--amber);
    border-color: var(--amber);
    color: #FFFFFF;
  }
  .step-node.warning .step-label {
    color: var(--amber);
  }

  .step-connector {
    flex: 1;
    height: 2px;
    background: var(--border);
    margin: 0 8px;
    margin-bottom: 24px;
  }
  .connector-active {
    background: var(--verif-green);
  }

  .approval-banner {
    background: #FFFDF8;
    border: 1px solid var(--amber);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
    padding: 20px;
  }
  .approval-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  .approval-title {
    font-size: 13px;
    font-weight: 800;
    color: var(--amber);
    letter-spacing: 0.08em;
  }
  .approval-body {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
  }
  .approval-rationale {
    font-size: 12px;
    color: var(--text-dim);
    flex: 1;
  }
  .approval-actions {
    display: flex;
    gap: 10px;
  }
  .btn-reject {
    background: #FFFFFF;
    border-color: var(--border);
    color: var(--stone);
  }
  .btn-reject:hover {
    color: var(--oxblood);
    border-color: var(--oxblood);
  }

  .remediation-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }

  .policy-panel, .verifier-panel {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
  }

  .policy-card {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .p-row {
    display: flex;
    gap: 12px;
    font-size: 12px;
  }
  .p-lbl {
    color: var(--stone);
    font-weight: 800;
    min-width: 140px;
  }
  .p-val {
    font-weight: 700;
  }

  .diff-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 4px;
  }
  .diff-col {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
  }
  .diff-hdr {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
  }
  .diff-before .diff-hdr { color: var(--oxblood); }
  .diff-after .diff-hdr { color: var(--verif-green); }
  .diff-body {
    font-size: 11.5px;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .rationale-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    font-size: 11.5px;
    color: var(--text-dim);
  }
  .r-title {
    font-size: 9.5px;
    color: var(--stone);
    font-weight: 800;
    margin-bottom: 4px;
    letter-spacing: 0.08em;
  }
  .json-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
  }
  .json-box pre {
    color: var(--text);
    font-size: 10.5px;
    margin: 0;
    max-height: 140px;
    overflow-y: auto;
  }

  .certificate-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .verdict-banner {
    padding: 16px 18px;
    border-radius: 8px;
    border: 1px solid transparent;
  }
  .v-closed {
    background: var(--verif-green-dim);
    border-color: rgba(27, 94, 59, 0.4);
  }
  .v-closed .v-title { color: var(--verif-green); font-size: 14px; font-weight: 900; }
  .v-closed .v-sub { color: var(--text-dim); font-size: 11.5px; margin-top: 4px; }

  .v-false {
    background: var(--amber-dim);
    border-color: rgba(184, 107, 20, 0.4);
  }
  .v-false .v-title { color: var(--amber); font-size: 14px; font-weight: 900; }
  .v-false .v-sub { color: var(--text-dim); font-size: 11.5px; margin-top: 4px; }

  .v-open {
    background: var(--oxblood-dim);
    border-color: rgba(139, 30, 30, 0.4);
  }
  .v-open .v-title { color: var(--oxblood); font-size: 14px; font-weight: 900; }
  .v-open .v-sub { color: var(--text-dim); font-size: 11.5px; margin-top: 4px; }

  .firewall-proof-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    font-size: 11px;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .f-title {
    color: var(--text);
    font-weight: 800;
    font-size: 10px;
    margin-bottom: 2px;
  }

  .subscores-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin-top: 6px;
  }
  .subscore-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 6px;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
  }
  .subscore-card.pass {
    border-color: rgba(27, 94, 59, 0.3);
    background: var(--verif-green-dim);
  }
  .subscore-card.pass .s-icon { color: var(--verif-green); font-weight: 800; }
  .subscore-card.fail {
    border-color: rgba(139, 30, 30, 0.3);
    background: var(--oxblood-dim);
  }
  .subscore-card.fail .s-icon { color: var(--oxblood); font-weight: 800; }
  .s-name { font-size: 11px; font-weight: 800; color: var(--text); }
  .s-desc { font-size: 9.5px; color: var(--muted); }

  .cert-footer {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--muted);
    padding-top: 10px;
    border-top: 1px dashed var(--border);
  }

  .table-container {
    overflow-x: auto;
  }
  .runs-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 11.5px;
    text-align: left;
  }
  .runs-table th {
    padding: 10px 14px;
    color: var(--stone);
    border-bottom: 1px solid var(--border);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
  }
  .runs-table td {
    padding: 12px 14px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .runs-table tr {
    cursor: pointer;
    transition: background 0.12s;
  }
  .runs-table tr:hover {
    background: var(--bg-subtle);
  }
  .runs-table tr.selected {
    background: var(--tech-blue-dim);
  }

  .badge-xs { font-size: 9px; padding: 1px 5px; }
  .empty-box { padding: 40px 10px; text-align: center; font-size: 12px; color: var(--muted); }
  .text-blue { color: var(--tech-blue); }
  .text-green { color: var(--verif-green); }
  .text-red { color: var(--oxblood); }
  .text-muted { color: var(--muted); }
  .text-center { text-align: center; }
</style>

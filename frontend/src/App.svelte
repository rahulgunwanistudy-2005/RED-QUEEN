<script>
  import { onMount, onDestroy } from "svelte";
  import Icon from "./lib/Icon.svelte";
  import {
    connected, health, score, events, fleetAgents, defensePosture, findings,
    corpusStats, policiesList, lineage, selectedNode, campaignStatus,
    multimodalDemo, multimodalLoading, runs, selectedRunId, traces,
    memoryProfile, verifierIsolation, connectStream, fetchHealth, fetchFleet,
    fetchDefensePosture, fetchFindings, fetchCorpusStats, fetchPolicies,
    fetchMemoryProfile, fetchVerifierIsolation, hydrateRuns, fetchTraces,
    runCampaign, runMultimodalDemo, approveRun,
  } from "./lib/store.js";

  const NAV = [
    { id: "range", label: "Range", icon: "grid" },
    { id: "attack", label: "Attack lab", icon: "crosshair" },
    { id: "verify", label: "Proof", icon: "certificate" },
    { id: "telemetry", label: "Telemetry", icon: "pulse" },
  ];
  const ATTACK_LABELS = { prompt_injection: "Prompt injection", tool_poisoning: "Tool poisoning", multimodal: "Multimodal injection" };
  const SURFACE_LABELS = { cloud_run: "managed agent runtime", gemma: "Gemma generator" };
  const SUB_SCORES = [["armor_blocked", "Armor blocked"], ["behavior_unchanged", "Behavior held"], ["secret_contained", "Secret contained"]];

  let section = "range";
  let es;
  let attackClass = "prompt_injection";
  let targetAgent = "triage-agent";
  let remedy = "content";
  let seed = 1337;
  let campaignError = "";
  let approving = null;
  let mobileNav = false;

  $: runList = Object.values($runs).sort((a, b) => b.run_id - a.run_id);
  $: selectedRun = runList.find((r) => r.run_id === $selectedRunId) || runList[0] || null;
  $: candidateNodes = [...$lineage.nodes].sort((a, b) => (a.generation - b.generation) || String(a.id).localeCompare(String(b.id)));
  $: generations = [...new Set(candidateNodes.map((n) => n.generation))];
  $: postureScore = $score.value ?? $defensePosture.baseline_score ?? 0;
  $: realCount = Object.values($health?.use_real || {}).filter(Boolean).length;
  $: surfaceCount = Object.keys($health?.use_real || {}).length;
  $: currentSpanMax = Math.max(1, ...(($traces?.spans || []).map((s) => Number(s.started_ms || 0) + Number(s.duration_ms || 0))));

  onMount(() => {
    es = connectStream();
    Promise.all([
      fetchHealth(), fetchFleet(), fetchDefensePosture(), fetchFindings(), fetchCorpusStats(),
      fetchPolicies(), fetchMemoryProfile(), fetchVerifierIsolation(), hydrateRuns(),
    ]);
    const poll = window.setInterval(() => { fetchHealth(); fetchDefensePosture(); }, 30000);
    return () => window.clearInterval(poll);
  });
  onDestroy(() => es?.close());

  function goto(id) { section = id; mobileNav = false; }
  function fmtDate(value) {
    if (!value) return "—";
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  }
  function shortId(value, length = 10) {
    if (!value) return "—";
    const text = String(value);
    return text.length > length ? `${text.slice(0, length)}…` : text;
  }
  function verdictTone(value) {
    if (value === "CLOSED") return "good";
    if (value === "FALSE_CLOSED") return "warn";
    if (value === "STILL_OPEN") return "danger";
    return "neutral";
  }
  function surfaceMode(name, isReal) {
    if (isReal) return "GOOGLE CLOUD";
    if (name === "gemma") return "OFFLINE FALLBACK";
    if (name === "cloud_run") return "DISCLOSED SHIM";
    return "LOCAL SHIM";
  }
  function eventSummary(event) {
    if (event.type === "candidate") return `${event.attack_class || "attack"} · generation ${event.generation ?? 0} · ${event.bypass ? "bypass" : event.blocked ? "blocked" : "passed"}`;
    if (event.type === "state") return `run ${event.run_id} moved to ${event.state}`;
    if (event.type === "policy") return `${event.policy_id || "policy"} ${event.applied ? "applied" : "drafted"}`;
    if (event.type === "verdict") return `run ${event.run_id} certified ${event.verdict}`;
    if (event.type === "score") return `hardening score ${event.value} · ${event.band}`;
    if (event.type === "hello") return "event stream handshake complete";
    return Object.entries(event).filter(([k]) => !["type", "_t", "_raw"].includes(k)).slice(0, 2).map(([k, v]) => `${k}=${typeof v === "object" ? "…" : v}`).join(" · ") || "event received";
  }
  async function launchCampaign() {
    campaignError = ""; selectedNode.set(null);
    try {
      const result = await runCampaign({ attackClass, targetAgent, remedy, seed, useCorpus: true, useMemory: true, agentId: targetAgent });
      if (!result?.opened) campaignError = result?.reason || "The target resisted the campaign.";
    } catch (error) { campaignError = error.message || "Campaign failed."; }
  }
  async function loadRun(run) { selectedRunId.set(run.run_id); await fetchTraces(run.run_id); }
  async function decide(runId, decision) {
    approving = `${runId}:${decision}`;
    try { await approveRun(runId, decision); await fetchPolicies(); } finally { approving = null; }
  }
</script>

<svelte:head>
  <title>RED//QUEEN — Autonomous Security Range</title>
  <meta name="description" content="Live autonomous red-team, hardening, and independent verification control plane." />
</svelte:head>

<div class="shell">
  <aside class:open={mobileNav} class="rail">
    <button class="brand" on:click={() => goto("range")} aria-label="RED QUEEN home">
      <span class="brand-mark"><i></i><i></i></span>
      <span class="brand-copy"><strong>RED//QUEEN</strong><small>ADVERSARIAL RANGE</small></span>
    </button>
    <nav aria-label="Primary navigation">
      {#each NAV as item}
        <button class:active={section === item.id} on:click={() => goto(item.id)}>
          <Icon name={item.icon} size={17} /><span>{item.label}</span>
          {#if item.id === "telemetry" && $events.length}<b>{$events.length}</b>{/if}
        </button>
      {/each}
    </nav>
    <div class="rail-foot">
      <div class="rail-status"><span class:live={$connected}></span><div><strong>{$connected ? "Stream live" : "Reconnecting"}</strong><small>one JSON event bus</small></div></div>
      <div class="rail-version">CONTROL PLANE / 01</div>
    </div>
  </aside>

  {#if mobileNav}<button class="scrim" aria-label="Close navigation" on:click={() => mobileNav = false}></button>{/if}

  <main>
    <header class="topbar">
      <button class="mobile-menu" on:click={() => mobileNav = !mobileNav} aria-label="Open navigation"><Icon name="menu" /></button>
      <div class="page-title"><span>/{section}</span><strong>{NAV.find((n) => n.id === section)?.label}</strong></div>
      <div class="topbar-proof">
        <div class="proof-pill"><span class:ok={$health?.db}></span><small>DATABASE</small><strong>{$health?.db ? "ONLINE" : "DOWN"}</strong></div>
        <div class="proof-pill"><span class:ok={realCount > 0}></span><small>SURFACES</small><strong>{realCount}/{surfaceCount || 0} REAL</strong></div>
        <div class="proof-pill score-mini"><small>HARDENING</small><strong>{postureScore}</strong></div>
      </div>
    </header>

    <div class="workspace">
      {#if section === "range"}
        <section class="range-view view-enter">
          <div class="hero-grid">
            <div class="hero-copy">
              <div class="eyebrow"><span></span> AUTONOMOUS SELF-HARDENING RANGE</div>
              <h1>The attacker does not<br /><em>certify the fix.</em></h1>
              <p>RED//QUEEN evolves attacks against a heterogeneous Gemini fleet, hardens the boundary, then hands the result to an isolated verifier that cannot read the attacker’s corpus.</p>
              <div class="hero-actions"><button class="primary" on:click={() => goto("attack")}><Icon name="play" size={15} /> Open attack lab</button><button class="quiet" on:click={() => goto("verify")}><Icon name="certificate" size={15} /> Inspect proof</button></div>
            </div>
            <div class="score-instrument">
              <div class="instrument-head"><span>FLEET HARDENING</span><span class="signal">LIVE POSTURE</span></div>
              <div class="dial" style={`--score:${Math.min(100, Math.max(0, postureScore)) * 3.6}deg`}><div><strong>{postureScore}</strong><span>/100</span><small>{postureScore >= 80 ? "HARDENED" : postureScore >= 60 ? "EXPOSED" : "CRITICAL"}</small></div></div>
              <div class="instrument-scale"><span>0</span><i></i><i></i><i></i><i></i><i></i><span>100</span></div>
              <div class="instrument-meta"><div><small>POLICIES</small><strong>{$defensePosture.applied_deltas?.length || 0}</strong></div><div><small>FINDINGS</small><strong>{$findings.length}</strong></div><div><small>CORPUS</small><strong>{$corpusStats.total_payloads || 0}</strong></div></div>
            </div>
          </div>

          <div class="section-kicker"><span>01</span><div><strong>THE LIVE CONTROL LOOP</strong><small>Every stage maps to a working backend boundary.</small></div></div>
          <div class="loop-board">
            <div class="loop-track" aria-label="Attack and defense control loop">
              <div class="loop-node attack-node"><span>01</span><Icon name="crosshair" size={22}/><strong>EVOLVE</strong><small>Gemma + operators</small></div>
              <div class="connector"><i></i><Icon name="arrow" size={15}/></div>
              <div class="loop-node gateway-node"><span>02</span><Icon name="shield" size={22}/><strong>BREACH</strong><small>Model Armor seam</small></div>
              <div class="connector"><i></i><Icon name="arrow" size={15}/></div>
              <div class="loop-node harden-node"><span>03</span><Icon name="layers" size={22}/><strong>HARDEN</strong><small>Idempotent delta</small></div>
              <div class="connector split"><i></i><Icon name="arrow" size={15}/></div>
              <div class="loop-node verify-node"><span>04</span><Icon name="certificate" size={22}/><strong>VERIFY</strong><small>Firewalled identity</small></div>
            </div>
            <div class="firewall-band"><Icon name="lock" size={15}/><span>IDENTITY FIREWALL</span><i></i><small>verifier cannot read findings or payload corpus</small></div>
          </div>

          <div class="range-columns">
            <section class="panel fleet-panel">
              <div class="panel-head"><div><span>FLEET REGISTRY</span><small>Heterogeneous agents under test</small></div><span class="count">{$fleetAgents.length} AGENTS</span></div>
              <div class="agent-list">{#each $fleetAgents as agent}<article class="agent-row"><div class="agent-symbol" class:low={agent.risk === "low"}><Icon name="cpu" size={19}/></div><div class="agent-main"><strong>{agent.name}</strong><code>{agent.id}</code></div><div class="agent-model"><small>MODEL</small><strong>{agent.model}</strong></div><div class="risk" class:low={agent.risk === "low"}><i></i>{agent.risk}</div></article>{:else}<div class="empty-row">Registry unavailable.</div>{/each}</div>
            </section>
            <section class="panel surfaces-panel">
              <div class="panel-head"><div><span>EXECUTION SURFACES</span><small>Honest real / shim disclosure</small></div><span class="count">{$health?.status || "…"}</span></div>
              <div class="surface-grid">{#each Object.entries($health?.use_real || {}) as [name, isReal]}<div class:real={isReal} class="surface"><span></span><div><strong>{SURFACE_LABELS[name] || name.replaceAll("_", " ")}</strong><small>{surfaceMode(name, isReal)}</small></div></div>{:else}<div class="empty-row">Waiting for health posture…</div>{/each}</div>
            </section>
          </div>
        </section>

      {:else if section === "attack"}
        <section class="attack-view view-enter">
          <div class="view-heading"><div><div class="eyebrow"><span></span> RED TEAM / LIVE ORCHESTRATION</div><h2>Attack laboratory</h2><p>Configure a real campaign. Candidates arrive over the event stream as the engine mutates, scores, selects, and remembers.</p></div><div class:running={$campaignStatus.running} class="run-state"><span></span><div><small>ENGINE STATE</small><strong>{$campaignStatus.running ? `EVOLVING · GEN ${$campaignStatus.generation}` : "READY"}</strong></div></div></div>
          <div class="attack-layout">
            <aside class="campaign-console panel">
              <div class="panel-head"><div><span>CAMPAIGN CONTROL</span><small>POST /harden/campaign</small></div><Icon name="terminal"/></div>
              <label><span>ATTACK CLASS</span><select bind:value={attackClass} disabled={$campaignStatus.running}><option value="prompt_injection">Prompt injection</option><option value="tool_poisoning">Tool poisoning</option><option value="multimodal">Multimodal injection</option></select></label>
              <label><span>TARGET AGENT</span><select bind:value={targetAgent} disabled={$campaignStatus.running}>{#each $fleetAgents as agent}<option value={agent.id}>{agent.id} · {agent.model}</option>{/each}</select></label>
              <label><span>POLICY REMEDY</span><select bind:value={remedy} disabled={$campaignStatus.running}><option value="content">Deep normalization</option><option value="identity">Revoke capability</option><option value="exact">Exact blocklist</option>{#if attackClass === "multimodal"}<option value="multimodal">Multimodal guard</option>{/if}</select></label>
              <label><span>DETERMINISTIC SEED</span><input type="number" bind:value={seed} disabled={$campaignStatus.running}/></label>
              <div class="console-switches"><span><i class="on"></i> pgvector recall</span><span><i class="on"></i> Memory Bank</span></div>
              <button class="launch" on:click={launchCampaign} disabled={$campaignStatus.running}><Icon name={$campaignStatus.running ? "pulse" : "play"} size={16}/>{$campaignStatus.running ? "Campaign in progress" : "Launch live campaign"}</button>
              {#if campaignError}<div class="inline-alert">{campaignError}</div>{/if}
              <div class="campaign-metrics"><div><small>GENERATION</small><strong>{$campaignStatus.generation}<span>/{$campaignStatus.maxGen}</span></strong></div><div><small>BLOCKED</small><strong>{$campaignStatus.blocked}</strong></div><div><small>BYPASSES</small><strong class:red={$campaignStatus.bypassed > 0}>{$campaignStatus.bypassed}</strong></div></div>
            </aside>
            <div class="attack-main">
              <section class="panel lineage-panel">
                <div class="panel-head"><div><span>EVOLUTION LINEAGE</span><small>{$lineage.attackClass || attackClass} · SSE candidate events</small></div><span class="count">{candidateNodes.length} CANDIDATES</span></div>
                {#if candidateNodes.length}<div class="generation-grid">{#each generations as gen}<div class="generation-column"><header><span>GEN {String(gen).padStart(2, "0")}</span><i></i></header>{#each candidateNodes.filter((node) => node.generation === gen) as node}<button class:bypass={node.bypass} class:blocked={node.blocked} class:selected={$selectedNode?.id === node.id} class="candidate" on:click={() => selectedNode.set(node)}><span class="candidate-dot"></span><div><strong>{node.bypass ? "BYPASS" : node.blocked ? "BLOCKED" : "PASSED"}</strong><small>{shortId(node.id, 14)}</small></div><b>{Number(node.scan_score ?? 0).toFixed(2)}</b></button>{/each}</div>{/each}</div>{:else}<div class="lineage-empty"><Icon name="branch" size={34}/><strong>No campaign events yet</strong><p>Launch the campaign to watch candidates appear generation by generation. Nothing here is pre-seeded in the interface.</p></div>{/if}
              </section>
              <section class="panel inspector-panel">
                <div class="panel-head"><div><span>PAYLOAD INSPECTOR</span><small>Selected candidate from the live stream</small></div>{#if $selectedNode}<span class="count">GEN {$selectedNode.generation}</span>{/if}</div>
                {#if $selectedNode}<div class="payload-code"><div><span>candidate::{shortId($selectedNode.id, 18)}</span><span class:bypass={$selectedNode.bypass}>{$selectedNode.bypass ? "UNAUTHORIZED EXECUTION" : $selectedNode.blocked ? "INTERCEPTED" : "PASSED"}</span></div><pre>{$selectedNode.payload || $selectedNode.preview || "Payload body was not included in this stream event."}</pre></div><div class="operator-chain"><small>MUTATION CHAIN</small>{#each $selectedNode.operators || [] as op}<span>{op}</span>{:else}<span>seed payload</span>{/each}</div>{:else}<div class="inspector-empty">Select a lineage node to inspect the exact payload and operator chain.</div>{/if}
              </section>
            </div>
          </div>
          <section class="panel multimodal-panel">
            <div class="panel-head"><div><span>MULTIMODAL BLIND-SPOT PROBE</span><small>The instruction lives in pixels; the response is returned by /multimodal/demo.</small></div><button class="small-action" on:click={() => runMultimodalDemo()} disabled={$multimodalLoading}><Icon name="image" size={14}/>{$multimodalLoading ? "Scanning…" : "Run image attack"}</button></div>
            {#if $multimodalDemo?.image_b64}<div class="multimodal-result"><div class="invoice"><img src={`data:image/png;base64,${$multimodalDemo.image_b64}`} alt="Generated adversarial invoice"/><span>RENDERED ATTACK ARTIFACT</span></div><div class="mm-flow"><div><span>01</span><small>TEXT SCAN</small><strong class:bad={!$multimodalDemo.text_scan?.blocked}>{$multimodalDemo.text_scan?.blocked ? "BLOCKED" : "CLEAN / BLIND"}</strong><p>{$multimodalDemo.carrier_text}</p></div><div><span>02</span><small>VISION EXTRACTION</small><strong>{$multimodalDemo.multimodal_guard_active ? "GUARD ACTIVE" : "NOT ENFORCED"}</strong><p>{$multimodalDemo.extracted_text || "No extraction returned."}</p></div><div><span>03</span><small>AGENT OUTCOME</small><strong class:bad={$multimodalDemo.bypass}>{$multimodalDemo.scan?.blocked ? "BLOCKED AT GATEWAY" : $multimodalDemo.bypass ? "VISION AGENT HIJACKED" : "CONTAINED"}</strong><p>{$multimodalDemo.agent?.answer || "The request did not reach the agent."}</p></div></div></div>{:else}<div class="mm-empty"><div class="image-wire"><Icon name="image" size={28}/><i></i><i></i><i></i></div><div><strong>Invoice attack is ready</strong><p>Run the probe to render the real payload image and compare the text scanner, vision extraction, and target-agent result side by side.</p></div></div>{/if}
          </section>
        </section>

      {:else if section === "verify"}
        <section class="verify-view view-enter">
          <div class="view-heading"><div><div class="eyebrow green"><span></span> BLUE TEAM / INDEPENDENT EVIDENCE</div><h2>Proof, not posture.</h2><p>The hardener proposes. A separately credentialed verifier re-runs the attack and scores three orthogonal guarantees.</p></div><div class:ok={$verifierIsolation?.ok} class="isolation-badge"><Icon name="lock" size={19}/><div><small>IDENTITY FIREWALL</small><strong>{$verifierIsolation?.ok ? "ISOLATION PROVEN" : "CHECK FAILED"}</strong></div></div></div>
          <div class="verify-layout">
            <section class="panel runs-panel"><div class="panel-head"><div><span>VERIFICATION LEDGER</span><small>Persisted hardening runs</small></div><span class="count">{runList.length} RUNS</span></div><div class="run-ledger">{#each runList as run}<button class:selected={$selectedRunId === run.run_id} on:click={() => loadRun(run)}><span class="run-index">#{String(run.run_id).padStart(3,"0")}</span><div><strong>{ATTACK_LABELS[run.attack_class] || run.attack_class}</strong><small>{fmtDate(run.created_at)} · {run.state}</small></div><span class={`verdict ${verdictTone(run.verdict)}`}>{run.verdict?.replace("_", "-") || "PENDING"}</span></button>{:else}<div class="empty-ledger"><Icon name="certificate" size={30}/><strong>No certificates yet</strong><p>Complete a campaign in the Attack lab. Its real verifier result will appear here.</p></div>{/each}</div></section>
            <section class="certificate panel"><div class="certificate-rule"></div><div class="certificate-head"><div><span>RED//QUEEN</span><small>INDEPENDENT VERIFIER CERTIFICATE</small></div><Icon name="certificate" size={31}/></div>{#if selectedRun}<div class={`certificate-verdict ${verdictTone(selectedRun.verdict)}`}><small>VERDICT / RUN {selectedRun.run_id}</small><strong>{selectedRun.verdict?.replace("_", "-") || selectedRun.state}</strong><span>{selectedRun.attack_class}</span></div><div class="subscore-grid">{#each SUB_SCORES as [key, label]}<div class:pass={selectedRun.sub_scores?.[key]}><span><Icon name={selectedRun.sub_scores?.[key] ? "check" : "x"} size={15}/></span><div><small>{label}</small><strong>{selectedRun.sub_scores ? (selectedRun.sub_scores[key] ? "PASS" : "FAIL") : "PENDING"}</strong></div></div>{/each}</div><dl><div><dt>POLICY ID</dt><dd>{selectedRun.policy_id || "—"}</dd></div><div><dt>VERIFY SEED</dt><dd>{selectedRun.verify_seed ?? "—"}</dd></div><div><dt>PAYLOAD HASH</dt><dd>{shortId(selectedRun.payload_hash, 18)}</dd></div></dl>{#if selectedRun.state === "AWAIT_APPROVAL"}<div class="approval-gate"><div><strong>Human approval required</strong><p>This policy changes an identity boundary and is marked destructive.</p></div><button on:click={() => decide(selectedRun.run_id,"rejected")} disabled={approving}>Reject</button><button class="approve" on:click={() => decide(selectedRun.run_id,"approved")} disabled={approving}>Approve delta</button></div>{/if}{:else}<div class="certificate-empty"><Icon name="shield" size={42}/><strong>Awaiting independent evidence</strong><p>The interface never manufactures a passing state. A certificate is rendered only from a persisted verifier run.</p></div>{/if}</section>
          </div>
          <div class="proof-grid">
            <section class="panel isolation-panel"><div class="panel-head"><div><span>FIREWALL TRANSCRIPT</span><small>GET /verifier/isolation</small></div><span class:good={$verifierIsolation?.ok} class="count">{$verifierIsolation?.ok ? "PASS" : "FAILED"}</span></div><div class="transcript">{#each $verifierIsolation?.transcript || [] as line}<div><span class:pass={line.includes("PASS") || line.includes("OK")}></span><code>{line}</code></div>{:else}<div><code>Waiting for isolation probe…</code></div>{/each}</div></section>
            <section class="panel memory-panel"><div class="panel-head"><div><span>AGENT MEMORY</span><small>Durable risk profile</small></div><span class="count">{$memoryProfile?.backend || "…"}</span></div><div class="memory-body"><div class="memory-glyph"><Icon name="database" size={25}/><span class:known={$memoryProfile?.is_known}></span></div><div><small>PROFILE</small><strong>{$memoryProfile?.agent_id || "triage-agent"}</strong><p>{$memoryProfile?.is_known ? `${$memoryProfile.campaigns} campaigns remembered across resets.` : "No prior campaign memory for this agent."}</p></div></div><div class="weaknesses">{#each $memoryProfile?.known_weaknesses || [] as weakness}<span>{weakness}</span>{:else}<span class="muted">no known weaknesses</span>{/each}</div></section>
          </div>
        </section>

      {:else if section === "telemetry"}
        <section class="telemetry-view view-enter">
          <div class="view-heading"><div><div class="eyebrow"><span></span> OBSERVABILITY / ONE EVENT STREAM</div><h2>Telemetry evidence</h2><p>Raw control-loop events, persisted findings, and trace spans—without a second client-side model of the backend.</p></div><button class="quiet refresh" on:click={() => Promise.all([fetchFindings(), fetchPolicies(), fetchCorpusStats(), hydrateRuns()])}><Icon name="refresh" size={15}/> Refresh records</button></div>
          <div class="telemetry-stats"><div><Icon name="pulse"/><span><small>STREAM EVENTS</small><strong>{$events.length}</strong></span></div><div><Icon name="crosshair"/><span><small>FINDINGS</small><strong>{$findings.length}</strong></span></div><div><Icon name="database"/><span><small>CORPUS PAYLOADS</small><strong>{$corpusStats.total_payloads || 0}</strong></span></div><div><Icon name="shield"/><span><small>POLICY DELTAS</small><strong>{$policiesList.length}</strong></span></div></div>
          <div class="telemetry-layout">
            <section class="panel event-feed"><div class="panel-head"><div><span>LIVE EVENT BUS</span><small>/stream · newest first</small></div><span class:live={$connected} class="count">{$connected ? "CONNECTED" : "OFFLINE"}</span></div><div class="event-lines">{#each $events as event, i}<article><span class={`event-type type-${event.type}`}>{event.type || "event"}</span><div><strong>{eventSummary(event)}</strong><small>{event._t} · sequence {String($events.length-i).padStart(3,"0")}</small></div><button title="Show raw event" on:click={() => selectedNode.set(event)}><Icon name="eye" size={14}/></button></article>{:else}<div class="empty-ledger"><Icon name="pulse" size={30}/><strong>Listening for events</strong><p>The first backend event will appear here.</p></div>{/each}</div></section>
            <section class="panel trace-panel"><div class="panel-head"><div><span>TRACE WATERFALL</span><small>{selectedRun ? `run ${selectedRun.run_id}` : "Select a verification run"}</small></div><span class="count">{$traces?.spans?.length || 0} SPANS</span></div>{#if $traces?.spans?.length}<div class="waterfall">{#each $traces.spans as span}<div class="span-row"><span>{span.phase}</span><div class="span-track"><i class={`phase-${span.phase}`} style={`left:${(Number(span.started_ms || 0)/currentSpanMax)*100}%;width:${Math.max(2,(Number(span.duration_ms || 0)/currentSpanMax)*100)}%`}></i></div><code>{Number(span.duration_ms || 0).toFixed(0)}ms</code></div>{/each}</div><div class="trace-ids">{#each Object.entries($traces.trace_ids || {}) as [phase,id]}<div><small>{phase}</small><code>{shortId(id,16)}</code></div>{/each}</div>{:else}<div class="trace-empty"><Icon name="clock" size={31}/><strong>No trace selected</strong><p>Choose a run in Proof to load its attack → harden → verify spans.</p></div>{/if}</section>
          </div>
          <section class="panel findings-table"><div class="panel-head"><div><span>PERSISTED FINDINGS</span><small>Database-backed exploit evidence</small></div><span class="count">{$findings.length} ROWS</span></div><div class="table-wrap"><table><thead><tr><th>ID</th><th>ATTACK CLASS</th><th>SCAN</th><th>AGENT ACTION</th><th>OUTCOME</th><th>TRACE</th><th>TIME</th></tr></thead><tbody>{#each $findings as finding}<tr><td>#{finding.id}</td><td>{finding.attack_class}</td><td><span class:danger={!finding.scan_blocked}>{finding.scan_blocked ? "BLOCKED" : `PASSED · ${Number(finding.scan_score || 0).toFixed(2)}`}</span></td><td><code>{finding.agent_action || "—"}</code></td><td><span class:danger={finding.bypass} class:good={!finding.bypass}>{finding.bypass ? "BYPASS" : "CONTAINED"}</span></td><td><code>{shortId(finding.trace_id,12)}</code></td><td>{fmtDate(finding.created_at)}</td></tr>{:else}<tr><td colspan="7">No findings persisted yet.</td></tr>{/each}</tbody></table></div></section>
        </section>
      {/if}
    </div>
  </main>
</div>

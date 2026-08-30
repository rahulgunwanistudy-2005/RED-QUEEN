<script>
  import { onMount } from "svelte";
  import {
    traces,
    runs,
    selectedRunId,
    selectedSpan,
    fetchTraces,
    hydrateRuns,
  } from "../store.js";

  $: runList = Object.values($runs).sort((a, b) => b.run_id - a.run_id);
  $: currentRunId = $selectedRunId || (runList.length > 0 ? runList[0].run_id : null);

  const PHASE_COLORS = {
    attack: "#8B1E1E",
    harden: "#1D4E75",
    verify: "#1B5E3B",
  };

  $: spans = ($traces && $traces.spans) || [];
  $: spanMax = spans.reduce((m, s) => Math.max(m, (s.started_ms || 0) + (s.duration_ms || 0)), 1);

  function widthPct(s) {
    return Math.max(3, (s.duration_ms / spanMax) * 100);
  }
  function leftPct(s) {
    return ((s.started_ms || 0) / spanMax) * 100;
  }
  function shortId(t) {
    return t ? t.slice(0, 10) : "—";
  }

  function handleSelectRun(e) {
    const id = Number(e.target.value);
    selectedRunId.set(id);
    fetchTraces(id);
  }

  function handleSpanClick(s) {
    selectedSpan.set(s);
  }

  onMount(() => {
    hydrateRuns();
    if (currentRunId) {
      fetchTraces(currentRunId);
    }
  });
</script>

<div class="traces-view">
  <!-- Top Trace Header & Run Selector -->
  <div class="panel traces-top-panel">
    <div class="panel-header">
      <div class="panel-title">
        <span>📊</span> OPENTELEMETRY TRACE WATERFALL <span class="muted mono">GET /traces/{$traces?.run_id || ':run_id'}</span>
      </div>
      <div class="run-selector-group">
        <label class="mono select-lbl" for="run-select">SELECT HARDENING RUN:</label>
        <select id="run-select" class="input-select mono" value={currentRunId} on:change={handleSelectRun}>
          {#each runList as r}
            <option value={r.run_id}>
              Run #{r.run_id} ({r.attack_class}) — {r.verdict || r.state}
            </option>
          {:else}
            <option value="">No runs available</option>
          {/each}
        </select>
        <button class="btn btn-sm btn-secondary" on:click={() => fetchTraces(currentRunId)}>REFRESH</button>
      </div>
    </div>

    <!-- Active Run Trace Metadata -->
    {#if $traces && $traces.found}
      <div class="trace-meta-grid mono">
        <div class="meta-item">
          <span class="m-lbl">CYCLE RUN ID:</span>
          <span class="m-val text-blue">#{$traces.run_id}</span>
        </div>
        <div class="meta-item">
          <span class="m-lbl">ATTACK CLASS:</span>
          <span class="m-val">{$traces.attack_class}</span>
        </div>
        <div class="meta-item">
          <span class="m-lbl">VERDICT:</span>
          <span class="badge {$traces.verdict === 'CLOSED' ? 'badge-green' : $traces.verdict === 'FALSE_CLOSED' ? 'badge-amber' : 'badge-red'} badge-xs">
            {$traces.verdict || $traces.state}
          </span>
        </div>
        <div class="meta-item">
          <span class="m-lbl">TOTAL CYCLE LATENCY:</span>
          <span class="m-val">{spanMax.toFixed(1)} ms</span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Main Waterfall Canvas + Span Inspector Split -->
  <div class="traces-split-grid">
    <!-- Horizontal Waterfall Chart -->
    <div class="panel waterfall-panel">
      <div class="panel-header">
        <div class="panel-title">
          <span>⏱</span> CAUSAL TIMELINE WATERFALL
        </div>
        <div class="legend mono">
          <span class="legend-item"><i class="dot" style="background: {PHASE_COLORS.attack}"></i> Attack Phase</span>
          <span class="legend-item"><i class="dot" style="background: {PHASE_COLORS.harden}"></i> Harden Phase</span>
          <span class="legend-item"><i class="dot" style="background: {PHASE_COLORS.verify}"></i> Verify Phase</span>
        </div>
      </div>

      {#if $traces && $traces.found && spans.length > 0}
        <!-- Time Axis -->
        <div class="time-axis mono">
          <span>0 ms</span>
          <span>{(spanMax * 0.25).toFixed(0)} ms</span>
          <span>{(spanMax * 0.5).toFixed(0)} ms</span>
          <span>{(spanMax * 0.75).toFixed(0)} ms</span>
          <span>{spanMax.toFixed(0)} ms</span>
        </div>

        <div class="spans-waterfall">
          {#each spans as s, i}
            {@const isSelected = $selectedSpan?.name === s.name && $selectedSpan?.started_ms === s.started_ms}
            <div
              class="waterfall-row"
              class:selected={isSelected}
              on:click={() => handleSpanClick(s)}
              on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && handleSpanClick(s)}
              role="button"
              tabindex="0"
            >
              <!-- Phase Tag -->
              <div class="row-phase mono">
                <span class="phase-indicator" style="background: {PHASE_COLORS[s.phase] || '#888'}"></span>
                <span class="phase-text">{s.phase}</span>
              </div>

              <!-- Bar Track -->
              <div class="row-track">
                <div
                  class="span-bar"
                  style="left: {leftPct(s)}%; width: {widthPct(s)}%; background: {PHASE_COLORS[s.phase] || '#888'};"
                  title="{s.name} · {s.duration_ms?.toFixed(1)} ms"
                >
                  <span class="bar-title mono">
                    {s.name.replace("sentinel.", "")} · {s.duration_ms?.toFixed(1)}ms
                  </span>
                </div>
              </div>

              <!-- Trace ID Reference -->
              <div class="row-tid mono text-muted">
                {shortId(s.trace_id)}
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="empty-waterfall muted mono">
          No trace spans recorded for this cycle yet. Launch an attack or run a slice to stream causal OTel spans.
        </div>
      {/if}
    </div>

    <!-- Right Side Span Inspector -->
    <div class="panel span-inspector-panel">
      <div class="panel-header">
        <div class="panel-title">
          <span>🔍</span> SPAN ATTRIBUTE INSPECTOR
        </div>
      </div>

      {#if $selectedSpan}
        <div class="span-details mono">
          <div class="detail-row">
            <span class="d-lbl">SPAN NAME:</span>
            <span class="d-val text-blue">{$selectedSpan.name}</span>
          </div>

          <div class="detail-row">
            <span class="d-lbl">PHASE:</span>
            <span class="badge badge-{$selectedSpan.phase === 'attack' ? 'red' : $selectedSpan.phase === 'verify' ? 'green' : 'blue'} badge-xs">
              {$selectedSpan.phase?.toUpperCase()}
            </span>
          </div>

          <div class="detail-row">
            <span class="d-lbl">DURATION:</span>
            <span class="d-val"><strong>{$selectedSpan.duration_ms?.toFixed(2)} ms</strong></span>
          </div>

          <div class="detail-row">
            <span class="d-lbl">TRACE ID:</span>
            <span class="d-val">{$selectedSpan.trace_id || '—'}</span>
          </div>

          <div class="detail-row">
            <span class="d-lbl">SPAN ID:</span>
            <span class="d-val">{$selectedSpan.span_id || '—'}</span>
          </div>

          <!-- Attributes JSON -->
          <div class="attributes-section">
            <div class="attr-title">SPAN ATTRIBUTES (OPENTELEMETRY CONTEXT):</div>
            <div class="attr-box">
              <pre>{JSON.stringify($selectedSpan.attributes || {}, null, 2)}</pre>
            </div>
          </div>
        </div>
      {:else}
        <div class="empty-inspector muted mono">
          Click any span in the timeline waterfall to inspect its attributes, phase, and duration.
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .traces-view {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding: 28px 32px;
    max-width: 1500px;
    margin: 0 auto;
  }

  .traces-top-panel {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
    padding: 20px;
  }
  .run-selector-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .select-lbl {
    font-size: 10px;
    font-weight: 800;
    color: var(--stone);
    letter-spacing: 0.08em;
  }
  .input-select {
    background: #FFFFFF;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 11.5px;
  }

  .trace-meta-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 14px;
    padding: 12px 14px;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 11px;
  }
  .m-lbl {
    font-size: 9.5px;
    color: var(--stone);
    font-weight: 800;
  }
  .m-val {
    font-size: 13px;
    font-weight: 800;
  }

  .traces-split-grid {
    display: grid;
    grid-template-columns: 1fr 440px;
    gap: 24px;
  }

  .waterfall-panel, .span-inspector-panel {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
    padding: 20px;
  }
  .legend {
    display: flex;
    gap: 14px;
    font-size: 11px;
    color: var(--stone);
  }
  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }

  .time-axis {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--stone);
    padding: 0 75px 8px 80px;
    border-bottom: 1px dashed var(--border);
    margin-bottom: 14px;
    font-weight: 700;
  }

  .spans-waterfall {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .waterfall-row {
    display: grid;
    grid-template-columns: 75px 1fr 75px;
    align-items: center;
    gap: 12px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.12s;
    background: var(--bg-subtle);
    border: 1px solid var(--border-subtle);
  }
  .waterfall-row:hover {
    background: #EDE7DC;
  }
  .waterfall-row.selected {
    background: var(--oxblood-dim);
    border: 1px solid rgba(139, 30, 30, 0.3);
  }

  .row-phase {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 700;
    color: var(--text);
  }
  .phase-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .row-track {
    position: relative;
    height: 26px;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 5px;
    overflow: hidden;
  }
  .span-bar {
    position: absolute;
    top: 0;
    height: 100%;
    border-radius: 4px;
    display: flex;
    align-items: center;
    padding: 0 8px;
    opacity: 0.95;
    transition: left 0.3s, width 0.3s;
  }
  .bar-title {
    font-size: 10px;
    color: #FFFFFF;
    font-weight: 800;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .row-tid {
    font-size: 10.5px;
    text-align: right;
    color: var(--muted);
  }

  .span-details {
    display: flex;
    flex-direction: column;
    gap: 12px;
    font-size: 11.5px;
  }
  .detail-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .d-lbl {
    color: var(--stone);
    font-weight: 800;
    min-width: 110px;
  }
  .d-val {
    font-weight: 700;
    word-break: break-all;
    text-align: right;
  }

  .attributes-section {
    margin-top: 8px;
  }
  .attr-title {
    font-size: 10px;
    color: var(--stone);
    font-weight: 800;
    margin-bottom: 6px;
    letter-spacing: 0.06em;
  }
  .attr-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px;
    max-height: 240px;
    overflow-y: auto;
  }
  .attr-box pre {
    color: var(--text);
    font-size: 11px;
    margin: 0;
  }

  .empty-waterfall, .empty-inspector {
    padding: 50px 20px;
    text-align: center;
    font-size: 12px;
    color: var(--muted);
  }
  .badge-xs { font-size: 9px; padding: 1px 5px; }
  .text-blue { color: var(--tech-blue); }
  .text-muted { color: var(--muted); }
</style>

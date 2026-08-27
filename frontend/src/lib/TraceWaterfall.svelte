<script>
  // OTel trace waterfall (SOF-172). Renders the spans of ONE attack -> harden ->
  // verify cycle as a horizontal waterfall, off the /traces/{run_id} read. Each
  // phase is a bar positioned by its start offset and sized by its duration.
  import { traces } from "./store.js";

  const PHASE_COLOR = { attack: "#ff3b52", harden: "#4aa8ff", verify: "#2ecc71" };

  $: spans = ($traces && $traces.spans) || [];
  $: span_max = spans.reduce((m, s) => Math.max(m, s.started_ms + s.duration_ms), 1);
  // Give near-zero-duration spans a visible minimum width.
  function widthPct(s) {
    return Math.max(2, (s.duration_ms / span_max) * 100);
  }
  function leftPct(s) {
    return (s.started_ms / span_max) * 100;
  }
  function shortId(t) {
    return t ? t.slice(0, 8) : "—";
  }
</script>

<h2>
  TRACE WATERFALL
  <span class="muted mono">
    {$traces && $traces.found ? `/traces/${$traces.run_id}` : "/traces"}
  </span>
</h2>

{#if $traces && $traces.found}
  <div class="meta mono">
    <span>run {$traces.run_id}</span>
    <span class="ac">{$traces.attack_class}</span>
    {#if $traces.verdict}
      <span class="v v-{$traces.verdict}">{$traces.verdict.replace("_", "-")}</span>
    {/if}
  </div>
  <div class="fall">
    {#each spans as s}
      <div class="lane">
        <div class="label mono">
          <span class="dot" style="background:{PHASE_COLOR[s.phase] || '#888'}"></span>
          {s.phase}
        </div>
        <div class="track">
          <div
            class="bar"
            style="left:{leftPct(s)}%; width:{widthPct(s)}%; background:{PHASE_COLOR[s.phase] || '#888'}"
            title="{s.name} · {s.duration_ms.toFixed(1)}ms · trace {shortId(s.trace_id)}"
          >
            <span class="barlabel mono">{s.name.replace("sentinel.", "")} · {s.duration_ms.toFixed(0)}ms</span>
          </div>
        </div>
        <div class="tid mono">{shortId(s.trace_id)}</div>
      </div>
    {/each}
  </div>
{:else}
  <div class="empty muted">select a run to see its attack → harden → verify spans</div>
{/if}

<style>
  h2 {
    margin: 0 0 14px;
    font-size: 13px;
    letter-spacing: 0.16em;
    color: var(--muted);
    font-weight: 700;
  }
  .meta { display: flex; gap: 12px; align-items: center; font-size: 12px; margin-bottom: 12px; }
  .meta .ac { color: #b9c6d3; }
  .v { font-weight: 800; padding: 1px 7px; border-radius: 4px; font-size: 11px; }
  .v-CLOSED { background: #2ecc71; color: #04210f; }
  .v-FALSE_CLOSED { background: #e67e22; color: #fff; }
  .v-STILL_OPEN { background: var(--red); color: #fff; }
  .fall { display: flex; flex-direction: column; gap: 8px; }
  .lane { display: grid; grid-template-columns: 70px 1fr 68px; align-items: center; gap: 10px; }
  .label { font-size: 11px; color: #b9c6d3; display: flex; align-items: center; gap: 6px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .track {
    position: relative;
    height: 22px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 5px;
    overflow: hidden;
  }
  .bar {
    position: absolute;
    top: 0;
    height: 100%;
    border-radius: 5px;
    min-width: 3px;
    display: flex;
    align-items: center;
    padding: 0 7px;
    opacity: 0.92;
  }
  .barlabel { font-size: 10px; color: #04121f; font-weight: 700; white-space: nowrap; }
  .tid { font-size: 10.5px; color: var(--muted); text-align: right; }
  .empty { padding: 16px 4px; font-size: 12px; }
  .muted { color: var(--muted); }
</style>

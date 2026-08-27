<script>
  // Live attack-lineage tree (SOF-167). Renders candidate nodes off the SSE stream,
  // laid out by generation (columns) with parent→child edges. Blocked = muted,
  // passed-but-clean = blue, bypass = red flash + pulse. Pure client render.
  import { lineage } from "./store.js";

  const COL_W = 156;
  const ROW_H = 44;
  const PAD_X = 28;
  const PAD_Y = 34;
  const NODE_R = 9;

  $: nodes = $lineage.nodes;
  $: attackClass = $lineage.attackClass;

  $: byGen = (() => {
    const m = new Map();
    for (const n of nodes) {
      if (!m.has(n.generation)) m.set(n.generation, []);
      m.get(n.generation).push(n);
    }
    return m;
  })();

  $: pos = (() => {
    const p = {};
    for (const [g, col] of byGen) {
      col.forEach((n, i) => {
        p[n.id] = { x: PAD_X + g * COL_W, y: PAD_Y + i * ROW_H, node: n };
      });
    }
    return p;
  })();

  $: maxGen = nodes.reduce((a, n) => Math.max(a, n.generation), 0);
  $: maxCol = [...byGen.values()].reduce((a, c) => Math.max(a, c.length), 1);
  $: width = PAD_X * 2 + maxGen * COL_W + 60;
  $: height = PAD_Y + maxCol * ROW_H + 10;

  $: edges = nodes
    .filter((n) => n.parent_id && pos[n.parent_id])
    .map((n) => ({ from: pos[n.parent_id], to: pos[n.id], bypass: n.bypass }));

  $: bypassed = nodes.some((n) => n.bypass);
  $: winGen = bypassed ? Math.min(...nodes.filter((n) => n.bypass).map((n) => n.generation)) : null;

  const state = (n) => (n.bypass ? "bypass" : n.blocked ? "blocked" : "passed");
</script>

<div class="wrap">
  <div class="head">
    <span class="lbl">ATTACK LINEAGE</span>
    {#if attackClass}
      <span class="ac mono">{attackClass}</span>
    {/if}
    {#if bypassed}
      <span class="win">⚠ BYPASS @ gen {winGen}</span>
    {:else if nodes.length}
      <span class="holding">🛡 defenses holding</span>
    {/if}
  </div>

  {#if nodes.length === 0}
    <div class="empty mono">
      run <span class="cmd">python -m sentinel.redteam --both</span> to watch it evolve
    </div>
  {:else}
    <div class="scroll">
      <svg viewBox="0 0 {width} {height}" width={width} height={height}>
        {#each edges as e}
          <line
            x1={e.from.x} y1={e.from.y} x2={e.to.x} y2={e.to.y}
            class:bypass={e.bypass}
            class="edge"
          />
        {/each}
        {#each Object.values(pos) as p}
          <g class="node {state(p.node)}" transform="translate({p.x},{p.y})">
            <circle r={NODE_R} />
            <text x={NODE_R + 6} y="4" class="mono cap">
              g{p.node.generation}·{(p.node.operators || []).length}op{p.node.origin === "corpus" ? " ↺" : ""}
            </text>
            <title>{p.node.id}
risk={p.node.scan_score} · {state(p.node)}
ops: {(p.node.operators || []).join(", ") || "—"}
{p.node.preview || ""}</title>
          </g>
        {/each}
      </svg>
    </div>
    <div class="legend mono">
      <span class="k blocked"><i></i>blocked</span>
      <span class="k passed"><i></i>passed</span>
      <span class="k bypass"><i></i>bypass</span>
      <span class="k muted">↺ = used corpus ancestor</span>
    </div>
  {/if}
</div>

<style>
  .wrap { display: flex; flex-direction: column; gap: 12px; }
  .head { display: flex; align-items: center; gap: 12px; }
  .lbl { font-size: 13px; letter-spacing: 0.16em; color: var(--muted); font-weight: 700; }
  .ac { color: var(--blue); font-size: 12px; }
  .win { color: var(--red); font-weight: 700; font-size: 12px; letter-spacing: 0.04em; }
  .holding { color: #2ecc71; font-size: 12px; }
  .empty { color: var(--muted); font-size: 12px; padding: 24px 4px; }
  .cmd { color: var(--blue); }
  .scroll { overflow: auto; max-width: 100%; max-height: 46vh; }

  .edge { stroke: #24333f; stroke-width: 1.5; }
  .edge.bypass { stroke: var(--red); stroke-width: 2; }

  .node circle { stroke-width: 2; }
  .node .cap { fill: #7d8fa1; font-size: 10px; }
  .node.blocked circle { fill: #1a2530; stroke: #3a4a58; }
  .node.passed circle { fill: #16344e; stroke: var(--blue); }
  .node.bypass circle { fill: var(--red); stroke: #ff8593; animation: pulse 1s ease-in-out infinite; }
  .node.bypass .cap { fill: var(--red); }

  @keyframes pulse {
    0%, 100% { opacity: 1; filter: drop-shadow(0 0 0 rgba(255,59,82,0)); }
    50% { opacity: 0.85; filter: drop-shadow(0 0 6px rgba(255,59,82,0.9)); }
  }

  .legend { display: flex; gap: 16px; font-size: 11px; color: var(--muted); flex-wrap: wrap; }
  .k { display: inline-flex; align-items: center; gap: 6px; }
  .k i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
  .k.blocked i { background: #1a2530; border: 2px solid #3a4a58; }
  .k.passed i { background: #16344e; border: 2px solid var(--blue); }
  .k.bypass i { background: var(--red); border: 2px solid #ff8593; }
</style>

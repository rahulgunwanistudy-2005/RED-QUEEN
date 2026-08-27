<script>
  import { onMount, onDestroy } from "svelte";
  import { score, events, connected, connectStream, runSlice } from "./lib/store.js";
  import ScoreDial from "./lib/ScoreDial.svelte";
  import LineageTree from "./lib/LineageTree.svelte";

  let es;
  let running = false;

  onMount(() => {
    es = connectStream();
  });
  onDestroy(() => es && es.close());

  async function trigger() {
    running = true;
    try {
      await runSlice();
    } finally {
      running = false;
    }
  }
</script>

<header>
  <div class="brand">
    <span class="shield">🛡</span>
    <div>
      <h1>SENTINEL<span class="ev"> EVOLUTION</span></h1>
      <p class="tag">
        <span class="red">RED-TEAM</span> · self-hardening agent-security range ·
        <span class="blue">BLUE-TEAM</span>
      </p>
    </div>
  </div>
  <div class="status" class:on={$connected}>
    <span class="dot"></span>{$connected ? "STREAM LIVE" : "OFFLINE"}
  </div>
</header>

<main>
  <section class="panel dialpanel">
    <h2>HARDENING SCORE</h2>
    <ScoreDial value={$score.value} band={$score.band} />
    {#if $score.bypass === true}
      <div class="verdict breach">⚠ BYPASS — injection reached the agent</div>
    {:else if $score.bypass === false}
      <div class="verdict held">✓ DEFENSES HELD</div>
    {:else}
      <div class="verdict idle">awaiting first attempt…</div>
    {/if}
    <button on:click={trigger} disabled={running}>
      {running ? "RUNNING…" : "RUN THIN SLICE"}
    </button>
  </section>

  <section class="panel lineagepanel">
    <LineageTree />
  </section>

  <section class="panel streampanel">
    <h2>EVENT STREAM <span class="muted mono">/stream</span></h2>
    <div class="log mono">
      {#each $events as e}
        <div class="row">
          <span class="type type-{e.type}">{e.type}</span>
          <span class="body">{JSON.stringify(e)}</span>
        </div>
      {:else}
        <div class="row muted">no events yet</div>
      {/each}
    </div>
  </section>
</main>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 28px;
    border-bottom: 1px solid var(--border);
  }
  .brand {
    display: flex;
    gap: 14px;
    align-items: center;
  }
  .shield {
    font-size: 34px;
    filter: drop-shadow(0 0 10px rgba(74, 168, 255, 0.5));
  }
  h1 {
    margin: 0;
    font-size: 22px;
    letter-spacing: 0.18em;
    font-weight: 800;
  }
  .ev {
    color: var(--blue);
  }
  .tag {
    margin: 2px 0 0;
    font-size: 12px;
    letter-spacing: 0.06em;
    color: var(--muted);
  }
  .red {
    color: var(--red);
    font-weight: 700;
  }
  .blue {
    color: var(--blue);
    font-weight: 700;
  }
  .status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    letter-spacing: 0.12em;
    color: var(--muted);
  }
  .status .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #55606b;
  }
  .status.on {
    color: #2ecc71;
  }
  .status.on .dot {
    background: #2ecc71;
    box-shadow: 0 0 8px #2ecc71;
  }
  main {
    display: grid;
    grid-template-columns: 340px 1fr;
    gap: 20px;
    padding: 24px 28px;
  }
  .lineagepanel {
    min-width: 0;
  }
  .streampanel {
    grid-column: 1 / -1;
  }
  @media (max-width: 860px) {
    main {
      grid-template-columns: 1fr;
    }
  }
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
  }
  h2 {
    margin: 0 0 16px;
    font-size: 13px;
    letter-spacing: 0.16em;
    color: var(--muted);
    font-weight: 700;
  }
  .dialpanel {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .verdict {
    margin: 18px 0;
    font-size: 13px;
    font-weight: 600;
    text-align: center;
  }
  .verdict.breach {
    color: var(--red);
  }
  .verdict.held {
    color: #2ecc71;
  }
  .verdict.idle {
    color: var(--muted);
  }
  button {
    background: linear-gradient(180deg, #ff3b52, #cc2038);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 11px 18px;
    font-weight: 700;
    letter-spacing: 0.1em;
    font-size: 12px;
    cursor: pointer;
    width: 100%;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .log {
    max-height: 60vh;
    overflow: auto;
    font-size: 12px;
  }
  .row {
    display: flex;
    gap: 10px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    word-break: break-all;
  }
  .type {
    flex: 0 0 auto;
    color: var(--blue);
    font-weight: 700;
  }
  .type-score {
    color: #f1c40f;
  }
  .body {
    color: #b9c6d3;
  }
  .muted {
    color: var(--muted);
  }
</style>

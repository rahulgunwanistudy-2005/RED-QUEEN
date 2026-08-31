<script>
  import {
    viewMode,
    activeTab,
    connected,
    score,
    campaignStatus,
    eventDrawerOpen,
    events,
    judgeMode,
    cinemaMode,
    cinematicPlaying,
    cinematicStep,
    runSlice,
  } from "../store.js";
  import ScoreDial from "./ScoreDial.svelte";

  let sliceRunning = false;

  async function handleThinSlice() {
    sliceRunning = true;
    try {
      await runSlice();
    } finally {
      sliceRunning = false;
    }
  }

  function startJudgeDemo() {
    cinemaMode.set(true);
    cinematicStep.set(0);
    cinematicPlaying.set(true);
  }

  const tabs = [
    { id: "fleet", label: "Fleet & Posture", icon: "🛡" },
    { id: "attacks", label: "Attack Engine", icon: "⚔" },
    { id: "remediation", label: "Remediation & Verifier", icon: "🔧" },
    { id: "traces", label: "OTel Traces", icon: "📊" },
  ];
</script>

<header class="app-header">
  <div class="header-left">
    <!-- Brand / Return to Intro -->
    <div
      class="brand"
      on:click={() => viewMode.set("landing")}
      on:keydown={(e) => (e.key === "Enter" || e.key === " ") && viewMode.set("landing")}
      role="button"
      tabindex="0"
    >
      <div class="shield-logo">🛡</div>
      <div class="brand-text">
        <div class="title serif-display">
          RED//<span class="highlight">QUEEN</span>
        </div>
        <div class="subtitle mono">
          <span class="oxblood-tag">RED-TEAM</span> · AUTONOMOUS RANGE · <span class="green-tag">VERIFIER</span>
        </div>
      </div>
    </div>

    <!-- Navigation Tabs -->
    <nav class="nav-tabs">
      <button
        class="nav-tab nav-landing-tab"
        class:active={$viewMode === "landing"}
        on:click={() => viewMode.set("landing")}
      >
        <span class="tab-icon">✦</span>
        <span class="tab-label">Product Story</span>
      </button>

      <div class="tab-divider"></div>

      {#each tabs as t}
        <button
          class="nav-tab"
          class:active={$viewMode === "control_plane" && $activeTab === t.id}
          on:click={() => {
            activeTab.set(t.id);
            viewMode.set("control_plane");
          }}
        >
          <span class="tab-icon">{t.icon}</span>
          <span class="tab-label">{t.label}</span>
          {#if t.id === "attacks" && $campaignStatus.running}
            <span class="pulse-dot"></span>
          {/if}
        </button>
      {/each}
    </nav>
  </div>

  <div class="header-right">
    <!-- Judge Demo Mode CTA -->
    <button
      class="btn btn-sm btn-judge"
      on:click={startJudgeDemo}
      title="Launch 45-second full cinematic judge walkthrough"
    >
      <span class="judge-icon">▶</span>
      <span>45s JUDGE EXPERIENCE</span>
    </button>

    <!-- Quick Thin Slice CTA -->
    <button
      class="btn btn-sm btn-slice"
      on:click={handleThinSlice}
      disabled={sliceRunning}
      title="Execute reference vertical slice (Single unhardened injection)"
    >
      <span class="slice-icon">{sliceRunning ? "⚡" : "⚡"}</span>
      <span>{sliceRunning ? "RUNNING..." : "DEMO SLICE"}</span>
    </button>

    <!-- Mini Score Summary -->
    <div class="mini-score-widget">
      <ScoreDial value={$score.value} band={$score.band} size={100} showBand={false} />
      <div class="score-meta">
        <span class="score-lbl mono">HARDENING SCORE</span>
        <span class="score-badge badge badge-{$score.band === 'green' ? 'green' : $score.band === 'amber' ? 'amber' : 'red'} mono">
          {$score.value != null ? `${$score.value}/100` : "INITIALIZING"}
        </span>
      </div>
    </div>

    <!-- Live Event Drawer Toggle -->
    <button
      class="btn btn-sm btn-drawer"
      class:active={$eventDrawerOpen}
      on:click={() => eventDrawerOpen.update((v) => !v)}
      title="Toggle real-time SSE event console"
    >
      <span class="terminal-icon">⌨</span>
      <span class="mono">EVENTS</span>
      <span class="event-count mono">{$events.length}</span>
    </button>

    <!-- SSE Connection Status Indicator -->
    <div class="stream-status" class:connected={$connected}>
      <span class="status-indicator"></span>
      <span class="status-text mono">
        {$connected ? "LIVE" : "CONNECTING"}
      </span>
    </div>
  </div>
</header>

<style>
  .app-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 24px;
    background: rgba(250, 248, 245, 0.95);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(10px);
    box-shadow: var(--shadow-subtle);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 24px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }
  .shield-logo {
    font-size: 24px;
  }
  .brand-text .title {
    font-size: 14.5px;
    font-weight: 900;
    letter-spacing: 0.12em;
    color: var(--text);
  }
  .highlight {
    color: var(--oxblood);
  }
  .brand-text .subtitle {
    font-size: 9px;
    color: var(--muted);
    letter-spacing: 0.08em;
    font-weight: 700;
    margin-top: 1px;
  }
  .oxblood-tag {
    color: var(--oxblood);
    font-weight: 800;
  }
  .green-tag {
    color: var(--verif-green);
    font-weight: 800;
  }

  .nav-tabs {
    display: flex;
    align-items: center;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px;
    gap: 2px;
  }
  .nav-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: none;
    color: var(--stone);
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.04em;
    cursor: pointer;
    transition: all 0.15s ease;
    position: relative;
  }
  .nav-tab:hover {
    color: var(--text);
    background: rgba(0, 0, 0, 0.04);
  }
  .nav-tab.active {
    background: #FFFFFF;
    color: var(--text);
    box-shadow: var(--shadow-subtle);
  }
  .nav-landing-tab.active {
    color: var(--oxblood);
    font-weight: 800;
  }
  .tab-divider {
    width: 1px;
    height: 16px;
    background: var(--border);
    margin: 0 4px;
  }
  .tab-icon {
    font-size: 12px;
  }
  .pulse-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--oxblood);
    box-shadow: 0 0 6px var(--oxblood);
    animation: pulse 1s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(1.3); }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .btn-judge {
    background: var(--oxblood);
    border-color: var(--oxblood);
    color: #FFFFFF;
    font-weight: 800;
  }
  .btn-judge:hover {
    background: var(--oxblood-hover);
  }
  .judge-icon {
    font-size: 10px;
  }

  .btn-slice {
    background: #FFFFFF;
    border: 1px solid var(--border);
    color: var(--text);
    box-shadow: var(--shadow-subtle);
  }
  .btn-slice:hover:not(:disabled) {
    background: var(--bg-subtle);
    border-color: var(--border-focus);
    color: var(--oxblood);
  }
  .slice-icon {
    color: var(--amber);
  }

  .mini-score-widget {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 10px;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 6px;
    box-shadow: var(--shadow-subtle);
  }
  .score-meta {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }
  .score-lbl {
    font-size: 8.5px;
    color: var(--muted);
    letter-spacing: 0.08em;
    font-weight: 700;
  }
  .score-badge {
    font-size: 10px;
    padding: 1px 5px;
  }

  .btn-drawer {
    background: #FFFFFF;
    border: 1px solid var(--border);
    color: var(--stone);
    box-shadow: var(--shadow-subtle);
  }
  .btn-drawer.active {
    background: var(--text);
    border-color: var(--text);
    color: #FFFFFF;
  }
  .event-count {
    background: rgba(0, 0, 0, 0.06);
    padding: 1px 5px;
    border-radius: 8px;
    font-size: 9.5px;
  }

  .stream-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    font-weight: 700;
    color: var(--stone);
    padding-left: 2px;
  }
  .status-indicator {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--stone-light);
  }
  .stream-status.connected {
    color: var(--verif-green);
  }
  .stream-status.connected .status-indicator {
    background: var(--verif-green);
    box-shadow: 0 0 6px var(--verif-green);
  }
</style>

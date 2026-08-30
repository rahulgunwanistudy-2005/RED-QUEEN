<script>
  import { onMount, onDestroy } from "svelte";
  import {
    viewMode,
    activeTab,
    connectStream,
    hydrateRuns,
    fetchFleet,
    fetchDefensePosture,
    fetchFindings,
    fetchCorpusStats,
  } from "./lib/store.js";

  import Header from "./lib/components/Header.svelte";
  import EventDrawer from "./lib/components/EventDrawer.svelte";
  import JudgeGuide from "./lib/components/JudgeGuide.svelte";
  import CinematicJudgeTheater from "./lib/components/CinematicJudgeTheater.svelte";
  import CinematicLanding from "./lib/landing/CinematicLanding.svelte";
  import FleetView from "./lib/views/FleetView.svelte";
  import AttacksView from "./lib/views/AttacksView.svelte";
  import RemediationView from "./lib/views/RemediationView.svelte";
  import TracesView from "./lib/views/TracesView.svelte";

  let es;

  onMount(() => {
    es = connectStream();
    hydrateRuns();
    fetchFleet();
    fetchDefensePosture();
    fetchFindings();
    fetchCorpusStats();
  });

  onDestroy(() => {
    if (es) {
      es.close();
    }
  });
</script>

<div class="app-shell" class:landing-mode={$viewMode === "landing"}>
  {#if $viewMode === "landing"}
    <CinematicLanding />
  {:else}
    <Header />

    <main class="main-content">
      {#if $activeTab === "fleet"}
        <FleetView />
      {:else if $activeTab === "attacks"}
        <AttacksView />
      {:else if $activeTab === "remediation"}
        <RemediationView />
      {:else if $activeTab === "traces"}
        <TracesView />
      {/if}
    </main>

    <EventDrawer />
  {/if}

  <!-- Persistent Interactive Judge Guide Overlay -->
  <JudgeGuide />

  <!-- 38s Fullscreen Video-Like Judge Theater Overlay -->
  <CinematicJudgeTheater />
</div>

<style>
  .app-shell {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    background: var(--bg);
    transition: background 0.3s ease;
  }

  .app-shell.landing-mode {
    background: var(--parchment);
  }

  .main-content {
    flex: 1;
    padding-bottom: 60px;
  }
</style>

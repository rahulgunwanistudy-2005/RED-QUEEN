<script>
  import { onMount, onDestroy } from "svelte";
  import {
    cinemaMode,
    cinematicStep,
    cinematicPlaying,
    cinemaSpeed,
    cinemaElapsed,
    viewMode,
    activeTab,
  } from "../store.js";
  import SecurityOrganism from "../three/SecurityOrganism.svelte";

  const BEATS = [
    {
      time: "00:00 - 00:04",
      stage: "01 · THE THREAT",
      headline: "THE ATTACK EVOLVES.",
      tagline: "Autonomous Agent Vulnerability",
      what: "A baseline unmutated prompt injection arrives at the enterprise perimeter targeting triage-agent.",
      how: "Ingress received via ADK Gateway; evaluated against initial Model Armor surface scan rules.",
      telemetry: {
        attackClass: "prompt_injection",
        generation: "Gen 00 (Seed Vector)",
        operator: "none (raw baseline)",
        similarity: "1.000 (Seed)",
        subsystem: "sentinel.redteam.seed",
        dbRole: "sentinel_app",
      },
      tab: "attacks",
    },
    {
      time: "00:04 - 00:08",
      stage: "02 · THE PERIMETER",
      headline: "SO DOES THE DEFENSE.",
      tagline: "Google Cloud Model Armor & Gateway",
      what: "Enterprise defense perimeter initializes. Google Cloud Model Armor and Agent Gateway shield customer-facing agents.",
      how: "Gateway inspects inbound tickets against pattern filters and verifies capability tokens for bound tools.",
      telemetry: {
        attackClass: "perimeter_inspection",
        generation: "Gen 00",
        operator: "model_armor.scan()",
        similarity: "0.950 (Normal Inbound)",
        subsystem: "sentinel.gateway.handle_request",
        dbRole: "sentinel_app",
      },
      tab: "fleet",
    },
    {
      time: "00:08 - 00:12",
      stage: "03 · PROACTIVE PROBING",
      headline: "RED//QUEEN DOESN'T WAIT FOR AN INCIDENT.",
      tagline: "Continuous Proactive Red Teaming",
      what: "The automated red-team range launches continuous adversarial probing across prompt injection and tool poisoning vectors.",
      how: "Systematically tests triage-agent capabilities: read_ticket, run_privileged_fix, and export_secrets.",
      telemetry: {
        attackClass: "prompt_injection & tool_poisoning",
        generation: "Gen 01",
        operator: "seed_perturbation",
        similarity: "0.892 (Target Agent)",
        subsystem: "sentinel.redteam.loop.evolve",
        dbRole: "sentinel_redteam",
      },
      tab: "attacks",
    },
    {
      time: "00:12 - 00:16",
      stage: "04 · EVOLUTIONARY SEARCH",
      headline: "IT MANUFACTURES THE NEXT ATTACK.",
      tagline: "4 Mutation Operators + pgvector Memory",
      what: "The attack engine applies 4 evolutionary mutation operators to generate non-trivial bypass candidates.",
      how: "Executes paraphrase_override, obfuscate_tool, soften_directive, and obfuscate_target with cosine similarity memory.",
      telemetry: {
        attackClass: "prompt_injection",
        generation: "Gen 02 → Gen 03",
        operator: "obfuscate_tool (Leet + Separators)",
        similarity: "0.874 (Cosine Memory Match)",
        subsystem: "sentinel.redteam.operators",
        dbRole: "sentinel_redteam (pgvector)",
      },
      tab: "attacks",
    },
    {
      time: "00:16 - 00:20",
      stage: "05 · THE DECODER GAP",
      headline: "UNTIL ONE GETS THROUGH.",
      tagline: "LLM Semantic Decoder Gap Exploitation",
      what: "An evolved variant bypasses the surface normalizer by exploiting the target LLM semantic decoder gap.",
      how: "The target agent decodes the leet obfuscation, causing execution flow redirection into privileged tools.",
      telemetry: {
        attackClass: "prompt_injection",
        generation: "Gen 03 (Candidate #91F8)",
        operator: "paraphrase_override",
        similarity: "0.861 (Bypass Risk 0.94)",
        subsystem: "sentinel.target.agent",
        dbRole: "triage-agent-sa",
      },
      tab: "attacks",
    },
    {
      time: "00:20 - 00:25",
      stage: "06 · BREACH CLIMAX",
      headline: "BYPASS FOUND.",
      tagline: "Unauthorized Action Coerced · Score: 41/100 (RED)",
      what: "Unauthorized privileged tool execution occurs (run_privileged_fix). Hardening score drops to 41/100.",
      how: "Breach finding recorded with full OpenTelemetry causal trace context linking payload hash to agent action.",
      telemetry: {
        attackClass: "prompt_injection",
        generation: "Gen 03",
        operator: "EXPLOIT CONFIRMED ⚡",
        similarity: "Score: 41/100 (RED)",
        subsystem: "sentinel.findings.record",
        dbRole: "sentinel_app",
      },
      tab: "remediation",
    },
    {
      time: "00:25 - 00:29",
      stage: "07 · THE PHILOSOPHY",
      headline: "THE ATTACKER DOES NOT CERTIFY THE FIX.",
      tagline: "Strict Domain Separation",
      what: "Self-judging red teams produce false safety. Red//Queen enforces absolute domain separation for verification.",
      how: "A firewalled verifier subprocess operates with zero access to the attacker's mutation corpus.",
      telemetry: {
        attackClass: "verification_domain",
        generation: "Isolated Phase",
        operator: "firewall_enforce",
        similarity: "Corpus Access: REVOKED",
        subsystem: "sentinel.verifier.run",
        dbRole: "sentinel_verifier (Restricted)",
      },
      tab: "remediation",
    },
    {
      time: "00:29 - 00:33",
      stage: "08 · INDEPENDENT VERIFIER",
      headline: "INDEPENDENT VERIFICATION.",
      tagline: "PostgreSQL RBAC sentinel_verifier",
      what: "The verifier independently re-evolves attacks from public seeds to independently prove the vulnerability.",
      how: "Subprocess executes under dedicated PostgreSQL RBAC credentials (sentinel_verifier) ensuring mathematical credibility.",
      telemetry: {
        attackClass: "verification_subsystem",
        generation: "Independent Re-derive",
        operator: "verify_from_seed",
        similarity: "RBAC: sentinel_verifier",
        subsystem: "sentinel.verifier.run.verify",
        dbRole: "sentinel_verifier (SELECT only)",
      },
      tab: "remediation",
    },
    {
      time: "00:33 - 00:37",
      stage: "09 · BOUNDARY HARDENING",
      headline: "CHANGE THE BOUNDARY.",
      tagline: "Model Armor deep_normalize Policy Delta",
      what: "The hardening engine synthesizes an idempotent policy delta: Model Armor deep_normalize, closing the decoder gap.",
      how: "GEAP policy engine applies the rule delta without modifying agent code or triggering service downtime.",
      telemetry: {
        attackClass: "policy_hardening",
        generation: "Policy Delta V17",
        operator: "deep_normalize",
        similarity: "Rule: Model Armor Normalizer",
        subsystem: "sentinel.harden.synthesize",
        dbRole: "sentinel_app",
      },
      tab: "remediation",
    },
    {
      time: "00:37 - 00:41",
      stage: "10 · ADVERSARIAL RE-TEST",
      headline: "ATTACK IT AGAIN.",
      tagline: "Boundary Deflection & Shatter Sparks",
      what: "The verifier launches a fresh evolutionary campaign against the patched fleet. The evolved attack is intercepted.",
      how: "Deep normalizer recovers leet characters before rule evaluation; attack particles shatter against reinforced boundary.",
      telemetry: {
        attackClass: "retest_campaign",
        generation: "Gen 01..03 (Post-Patch)",
        operator: "perimeter_intercept",
        similarity: "Blocked: 100% of Variants",
        subsystem: "sentinel.verifier.run.retest",
        dbRole: "sentinel_verifier",
      },
      tab: "remediation",
    },
    {
      time: "00:41 - 00:45",
      stage: "11 · PROOF OF CLOSURE",
      headline: "CLOSED. PROVED.",
      tagline: "3/3 Sub-Scores PASS · Score: 96/100 (GREEN)",
      what: "Verification certificate signed with 3/3 orthogonal sub-scores passing. Hardening score rises to 96/100 (GREEN).",
      how: "Armor Blocked: PASS · Behavior Unchanged: PASS · Secret Contained: PASS. Causal OTel trace recorded.",
      telemetry: {
        attackClass: "certified_verdict",
        generation: "TERMINAL",
        operator: "CLOSED ✓",
        similarity: "Score: 96/100 (GREEN)",
        subsystem: "sentinel.verdict.signed",
        dbRole: "sentinel_verifier (Certified)",
      },
      tab: "traces",
    },
  ];

  let intervalId;
  const TOTAL_DURATION = 45; // 45 seconds total
  const STEP_DURATION = 4.09; // seconds per step

  $: currentBeat = BEATS[$cinematicStep] || BEATS[0];
  $: progressPct = Math.min(100, (($cinematicStep * STEP_DURATION + ($cinemaElapsed % STEP_DURATION)) / TOTAL_DURATION) * 100);

  // Web Audio SFX Synthesizer
  let audioCtx = null;
  let sfxEnabled = false;

  function initAudio() {
    if (!audioCtx && typeof window !== "undefined") {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        audioCtx = new AudioContext();
      }
    }
  }

  function playBeatSFX(step) {
    if (!sfxEnabled || !audioCtx) return;
    try {
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (step === 5) {
        // Climax Breach sound
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(120, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(40, audioCtx.currentTime + 0.6);
        gain.gain.setValueAtTime(0.22, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.6);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.6);
      } else if (step >= 10) {
        // Final Proved sound
        osc.type = "sine";
        osc.frequency.setValueAtTime(440, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(880, audioCtx.currentTime + 0.8);
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.8);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.8);
      } else {
        // Subtle beat tick
        osc.type = "sine";
        osc.frequency.setValueAtTime(300 + step * 25, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.12);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.12);
      }
    } catch {
      // Audio fallback
    }
  }

  function toggleSFX() {
    initAudio();
    sfxEnabled = !sfxEnabled;
    if (sfxEnabled) {
      playBeatSFX($cinematicStep);
    }
  }

  function startTheater() {
    cinemaElapsed.set(0);
    cinematicStep.set(0);
    cinematicPlaying.set(true);
    playBeatSFX(0);
  }

  function exitTheater() {
    cinematicPlaying.set(false);
    cinemaMode.set(false);
  }

  function exploreInControlPlane(tab) {
    cinemaMode.set(false);
    cinematicPlaying.set(false);
    activeTab.set(tab);
    viewMode.set("control_plane");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  onMount(() => {
    startTheater();
    intervalId = setInterval(() => {
      if ($cinematicPlaying) {
        cinemaElapsed.update((e) => e + 0.1 * $cinemaSpeed);
        if ($cinemaElapsed >= ($cinematicStep + 1) * (STEP_DURATION / $cinemaSpeed)) {
          if ($cinematicStep < BEATS.length - 1) {
            cinematicStep.update((s) => {
              const next = s + 1;
              playBeatSFX(next);
              return next;
            });
          } else {
            cinematicStep.set(0);
            cinemaElapsed.set(0);
            playBeatSFX(0);
          }
        }
      }
    }, 100);
  });

  onDestroy(() => {
    if (intervalId) clearInterval(intervalId);
    if (audioCtx) {
      audioCtx.close();
    }
  });
</script>

{#if $cinemaMode}
  <div class="theater-overlay" class:breach-climax={$cinematicStep === 5} class:proved-climax={$cinematicStep >= 10}>
    <!-- Top Ultra-Minimal Progress Indicator & Controls -->
    <div class="theater-topbar">
      <div class="tt-left mono">
        <span class="tt-logo">🛡</span>
        <span class="tt-title">RED//QUEEN // 45s AUTONOMOUS CINEMATIC WALKTHROUGH</span>
      </div>

      <!-- Linear Micro Progress Timeline -->
      <div class="tt-timeline">
        <div class="tt-timeline-fill" style="width: {progressPct}%;"></div>
      </div>

      <div class="tt-right mono">
        <span class="tt-timecode">{(($cinematicStep * STEP_DURATION)).toFixed(1)}s / {TOTAL_DURATION}s</span>

        <button class="btn btn-sm btn-sfx" on:click={toggleSFX} title="Toggle Cinematic SFX">
          {sfxEnabled ? "🔊 SFX ON" : "🔇 SFX OFF"}
        </button>

        <button class="btn btn-sm btn-exit" on:click={exitTheater}>
          ✕ EXIT THEATER
        </button>
      </div>
    </div>

    <!-- Main Viewport: The 3D Security Organism in full view with floating, translucent cards -->
    <div class="theater-stage">
      <!-- Full Viewport 3D Security Organism (Unobstructed Canvas) -->
      <div class="organism-cinema-viewport">
        <SecurityOrganism width="100%" height="100%" interactive={true} />
      </div>

      <!-- Floating Animated Cinema Cards (Arranged cleanly in left/corner space) -->
      <div class="cinema-floating-cards" key={$cinematicStep}>
        <!-- Card 1: Top Stage Pill -->
        <div class="cinema-card card-stage mono anim-slide-down">
          <span class="stage-dot">●</span>
          <span class="stage-title">{currentBeat.stage}</span>
          <span class="stage-sep">|</span>
          <span class="stage-tagline">{currentBeat.tagline}</span>
        </div>

        <!-- Card 2: Bold Headline Typography with blur-to-focus transition -->
        <div class="cinema-card card-headline anim-scale-up">
          <h1 class="headline-text serif-display">{currentBeat.headline}</h1>
        </div>

        <!-- Card 3: Frosted Glass Explainer Card (What & How) -->
        <div class="cinema-card card-explainer anim-slide-up">
          <div class="explainer-block">
            <div class="exp-lbl mono">WHAT IS HAPPENING:</div>
            <div class="exp-text editorial-serif">{currentBeat.what}</div>
          </div>

          <div class="explainer-divider"></div>

          <div class="explainer-block">
            <div class="exp-lbl mono">HOW IT WORKS (UNDER THE HOOD):</div>
            <div class="exp-subtext editorial-serif">{currentBeat.how}</div>
          </div>
        </div>

        <!-- Card 4: Floating Live Telemetry HUD Card (Bottom-Right/Left) -->
        <div class="cinema-card card-telemetry mono anim-slide-right">
          <div class="tel-row">
            <span class="t-k">ATTACK VECTOR:</span>
            <span class="t-v text-oxblood">{currentBeat.telemetry.attackClass}</span>
          </div>
          <div class="tel-row">
            <span class="t-k">LINEAGE GEN:</span>
            <span class="t-v">{currentBeat.telemetry.generation}</span>
          </div>
          <div class="tel-row">
            <span class="t-k">MUTATION:</span>
            <span class="t-v text-oxblood">{currentBeat.telemetry.operator}</span>
          </div>
          <div class="tel-row">
            <span class="t-k">DB RBAC:</span>
            <span class="t-v text-green">{currentBeat.telemetry.dbRole}</span>
          </div>
          <div class="tel-row tel-module">
            <span class="t-k">MODULE:</span>
            <code>{currentBeat.telemetry.subsystem}</code>
          </div>

          <button class="btn btn-sm btn-inspect-live" on:click={() => exploreInControlPlane(currentBeat.tab)}>
            EXPLORE IN {currentBeat.tab.toUpperCase()} VIEW →
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .theater-overlay {
    position: fixed;
    inset: 0;
    background: #FAF8F5;
    z-index: 150;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    transition: box-shadow 0.4s ease;
  }

  .theater-overlay.breach-climax {
    box-shadow: inset 0 0 100px rgba(139, 30, 30, 0.3);
  }

  .theater-overlay.proved-climax {
    box-shadow: inset 0 0 100px rgba(27, 94, 59, 0.22);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: scale(0.99); }
    to { opacity: 1; transform: scale(1); }
  }

  /* Ultra-Minimal Top Bar */
  .theater-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 32px;
    background: rgba(255, 255, 255, 0.88);
    border-bottom: 1px solid var(--border);
    backdrop-filter: blur(12px);
    z-index: 20;
    gap: 20px;
  }
  .tt-left {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 900;
    color: var(--text);
    letter-spacing: 0.08em;
    white-space: nowrap;
  }
  .tt-logo {
    font-size: 16px;
  }

  .tt-timeline {
    flex: 1;
    max-width: 400px;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
    position: relative;
  }
  .tt-timeline-fill {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: var(--oxblood);
    border-radius: 2px;
    transition: width 0.1s linear;
  }

  .tt-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .tt-timecode {
    font-size: 11px;
    color: var(--stone);
    font-weight: 800;
  }
  .btn-sfx {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    color: var(--stone);
    font-size: 10.5px;
    font-weight: 800;
  }
  .btn-exit {
    background: transparent;
    border: 1px solid var(--oxblood);
    color: var(--oxblood);
    font-size: 10.5px;
    font-weight: 800;
  }
  .btn-exit:hover {
    background: var(--oxblood);
    color: #FFFFFF;
  }

  /* Main Viewport Stage */
  .theater-stage {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  .organism-cinema-viewport {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    z-index: 1;
  }

  /* Floating Cinema Cards Architecture (Positioned in Clear Blank Zones) */
  .cinema-floating-cards {
    position: absolute;
    inset: 0;
    z-index: 10;
    pointer-events: none;
    padding: 32px 48px;
    display: grid;
    grid-template-columns: 520px 1fr 340px;
    grid-template-rows: auto 1fr auto;
    gap: 16px;
    align-items: flex-start;
  }

  .cinema-card {
    pointer-events: auto;
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.08);
  }

  /* Card 1: Top Stage Pill */
  .card-stage {
    grid-column: 1;
    grid-row: 1;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 800;
    border-radius: 20px;
    width: fit-content;
    box-shadow: var(--shadow-subtle);
  }
  .stage-dot {
    color: var(--oxblood);
    font-size: 12px;
  }
  .stage-title {
    color: var(--oxblood);
    letter-spacing: 0.08em;
  }
  .stage-sep {
    color: var(--border);
  }
  .stage-tagline {
    color: var(--stone);
  }

  /* Card 2: Big Bold Headline */
  .card-headline {
    grid-column: 1;
    grid-row: 2;
    background: transparent;
    border: none;
    box-shadow: none;
    backdrop-filter: none;
    margin-top: 8px;
  }
  .headline-text {
    font-size: 42px;
    font-weight: 900;
    line-height: 1.05;
    color: var(--text);
    letter-spacing: -0.02em;
    text-shadow: 0 2px 14px rgba(255, 255, 255, 0.9);
  }

  /* Card 3: Frosted Glass Explainer Card */
  .card-explainer {
    grid-column: 1;
    grid-row: 3;
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 12px;
  }
  .explainer-block {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .exp-lbl {
    font-size: 9.5px;
    font-weight: 800;
    color: var(--stone);
    letter-spacing: 0.08em;
  }
  .exp-text {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.45;
  }
  .exp-subtext {
    font-size: 13.5px;
    color: var(--text-dim);
    line-height: 1.45;
  }
  .explainer-divider {
    height: 1px;
    background: var(--border-subtle);
  }

  /* Card 4: Floating Live Telemetry HUD Card */
  .card-telemetry {
    grid-column: 3;
    grid-row: 3;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 10.5px;
    margin-bottom: 12px;
  }
  .tel-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .t-k {
    color: var(--stone);
    font-weight: 800;
    font-size: 9px;
  }
  .t-v {
    font-weight: 800;
  }
  .text-oxblood { color: var(--oxblood); }
  .text-green { color: var(--verif-green); }
  .tel-module {
    flex-direction: column;
    gap: 2px;
    padding-top: 4px;
    border-top: 1px dashed var(--border);
  }
  .tel-module code {
    background: var(--bg-subtle);
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 10px;
    border: 1px solid var(--border);
    word-break: break-all;
  }

  .btn-inspect-live {
    margin-top: 6px;
    background: var(--text);
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 800;
    padding: 6px 10px;
    border-radius: 5px;
    text-align: center;
    border: none;
    cursor: pointer;
  }
  .btn-inspect-live:hover {
    background: var(--oxblood);
  }

  /* Creative Staggered Animation Keyframes */
  .anim-slide-down {
    animation: slideDown 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .anim-scale-up {
    animation: scaleUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) 0.08s both;
  }
  .anim-slide-up {
    animation: slideUp 0.42s cubic-bezier(0.16, 1, 0.3, 1) 0.16s both;
  }
  .anim-slide-right {
    animation: slideRight 0.45s cubic-bezier(0.16, 1, 0.3, 1) 0.24s both;
  }

  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-16px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes scaleUp {
    from { opacity: 0; transform: scale(0.96) translateY(10px); filter: blur(6px); }
    to { opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(20px); filter: blur(4px); }
    to { opacity: 1; transform: translateY(0); filter: blur(0); }
  }

  @keyframes slideRight {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
  }
</style>

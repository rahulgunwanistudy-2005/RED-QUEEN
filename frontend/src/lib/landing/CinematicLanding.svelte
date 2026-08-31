<script>
  import { onMount, onDestroy } from "svelte";
  import {
    viewMode,
    activeTab,
    cinematicStep,
    cinematicPlaying,
    judgeMode,
    cinemaMode,
    score,
    connected,
  } from "../store.js";
  import SecurityOrganism from "../three/SecurityOrganism.svelte";

  const BEATS = [
    {
      time: "00:00 - 00:04",
      stage: "01. HOOK",
      headline: "THE ATTACK EVOLVES.",
      sub: "A single unmutated baseline injection arrives at the perimeter. The threat landscape is quiet, but adversarial pressure is mounting.",
      hud: "RED TEAM / GENERATION 00 · SEED PAYLOAD",
      tech: "sentinel.redteam.seed",
      tab: "attacks",
      loopIndex: 0,
    },
    {
      time: "00:04 - 00:08",
      stage: "02. DEFENSE",
      headline: "SO DOES THE DEFENSE.",
      sub: "The enterprise fleet perimeter activates. Google Cloud Model Armor and the ADK Agent Gateway inspect all inbound customer tickets and tool payloads.",
      hud: "AGENT FLEET · MODEL ARMOR · GATEWAY SHIELD",
      tech: "sentinel.gateway.handle_request",
      tab: "fleet",
      loopIndex: 0,
    },
    {
      time: "00:08 - 00:13",
      stage: "03. INCIDENT",
      headline: "RED//QUEEN DOESN'T WAIT FOR AN INCIDENT.",
      sub: "Red team vectors begin continuous automated probing across prompt injection and tool poisoning attack classes.",
      hud: "PROBING: PROMPT_INJECTION & TOOL_POISONING",
      tech: "sentinel.redteam.loop.evolve",
      tab: "attacks",
      loopIndex: 1,
    },
    {
      time: "00:13 - 00:18",
      stage: "04. EVOLUTION",
      headline: "IT MANUFACTURES THE NEXT ATTACK.",
      sub: "The attack engine applies 4 mutation operators (paraphrase_override, obfuscate_tool, soften_directive, obfuscate_target) with pgvector memory retrieval.",
      hud: "MUTATION LINEAGE: GEN 01 → GEN 02 → GEN 03",
      tech: "sentinel.redteam.operators",
      tab: "attacks",
      loopIndex: 2,
    },
    {
      time: "00:18 - 00:22",
      stage: "05. PENETRATION",
      headline: "UNTIL ONE GETS THROUGH.",
      sub: "An evolved variant bypasses the surface normalizer. The target triage agent is coerced into executing unauthorized privileged tooling.",
      hud: "ADVERSARY EXPLOITING DECODER GAP",
      tech: "sentinel.target.agent",
      tab: "attacks",
      loopIndex: 3,
    },
    {
      time: "00:22 - 00:25",
      stage: "06. BYPASS",
      headline: "BYPASS FOUND.",
      sub: "The exploit lands. Unauthorized privileged action is recorded in findings with causal OpenTelemetry trace evidence. Risk score drops to 41/100.",
      hud: "⚠ BYPASS DETECTED · RISK SCORE DROPS (41/100)",
      tech: "sentinel.findings.record",
      tab: "remediation",
      loopIndex: 3,
    },
    {
      time: "00:25 - 00:28",
      stage: "07. PHILOSOPHY",
      headline: "THE ATTACKER DOES NOT CERTIFY THE FIX.",
      sub: "Self-evaluating red teams create dangerous illusions of safety. Red//Queen enforces an independent verifier operating in an isolated security domain.",
      hud: "INDEPENDENT DOMAIN · ROLE ISOLATION",
      tech: "sentinel.verifier.run",
      tab: "remediation",
      loopIndex: 4,
    },
    {
      time: "00:28 - 00:31",
      stage: "08. VERIFICATION",
      headline: "INDEPENDENT VERIFICATION.",
      sub: "An isolated subprocess under dedicated PostgreSQL RBAC credentials (sentinel_verifier) independently validates the breach from public seeds.",
      hud: "INDEPENDENT VERIFIER · DB ROLE: sentinel_verifier",
      tech: "sentinel.verifier.run.verify",
      tab: "remediation",
      loopIndex: 4,
    },
    {
      time: "00:31 - 00:34",
      stage: "09. HARDENING",
      headline: "CHANGE THE BOUNDARY.",
      sub: "The hardening engine synthesizes an idempotent policy delta: Model Armor deep_normalize, closing the semantic decoder gap without code redeployment.",
      hud: "SYNTHESIZING POLICY DELTA · DEEP_NORMALIZE",
      tech: "sentinel.harden.synthesize",
      tab: "remediation",
      loopIndex: 5,
    },
    {
      time: "00:34 - 00:37",
      stage: "10. RE-TEST",
      headline: "ATTACK IT AGAIN.",
      sub: "The verifier launches a fresh evolutionary campaign against the patched fleet. The evolved attack hits the reinforced perimeter and is blocked.",
      hud: "RE-TEST AGAINST PATCHED FLEET · INTERCEPTED",
      tech: "sentinel.verifier.run.retest",
      tab: "remediation",
      loopIndex: 6,
    },
    {
      time: "00:37 - 00:40",
      stage: "11. PROVED",
      headline: "CLOSED. PROVED.",
      sub: "The verification certificate is signed with 3 orthogonal sub-scores. Hardening score rises to 96/100 (GREEN).",
      hud: "VERDICT: CLOSED ✓ · DEFENSES SECURED",
      tech: "sentinel.verdict.signed",
      tab: "traces",
      loopIndex: 7,
    },
  ];

  let timerInterval;
  let activeLoopStage = 0;

  const loopStages = [
    { name: "1. DISCOVER", desc: "Catalog agent tools, identity tokens, and trust boundaries.", comp: "sentinel.platform.geap.registry_list", step: 0 },
    { name: "2. ATTACK", desc: "Seed adversarial prompt injection and MCP tool poisoning vectors.", comp: "sentinel.redteam.seed", step: 2 },
    { name: "3. EVOLVE", desc: "Evolve candidate variants across generations with pgvector cosine memory.", comp: "sentinel.redteam.loop", step: 3 },
    { name: "4. BYPASS", desc: "Measure perimeter leakage and unauthorized privileged tool calls.", comp: "sentinel.target.agent", step: 5 },
    { name: "5. VERIFY", desc: "Independent firewalled subprocess re-derives the failure from public seeds.", comp: "sentinel.verifier.run", step: 7 },
    { name: "6. HARDEN", desc: "Synthesize minimal policy deltas (deep_normalize, capability revocation).", comp: "sentinel.harden.synthesize", step: 8 },
    { name: "7. RE-TEST", desc: "Stress-test the patched system with mutated adversarial variants.", comp: "sentinel.verifier.retest", step: 9 },
    { name: "8. PROVE CLOSED", desc: "Issue certified verdict with 3-dimensional orthogonal sub-scores.", comp: "sentinel.harden.machine", step: 10 },
  ];

  function togglePlay() {
    cinematicPlaying.update((p) => !p);
  }

  function setStep(idx) {
    cinematicStep.set(idx);
    activeLoopStage = BEATS[idx].loopIndex;
  }

  function nextStep() {
    cinematicStep.update((s) => {
      const next = (s + 1) % BEATS.length;
      activeLoopStage = BEATS[next].loopIndex;
      return next;
    });
  }

  function prevStep() {
    cinematicStep.update((s) => {
      const prev = (s - 1 + BEATS.length) % BEATS.length;
      activeLoopStage = BEATS[prev].loopIndex;
      return prev;
    });
  }

  function handleLoopSelect(idx, step) {
    activeLoopStage = idx;
    cinematicStep.set(step);
  }

  function enterRange(tab = "fleet") {
    activeTab.set(tab);
    viewMode.set("control_plane");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startJudgeDemo() {
    cinemaMode.set(true);
    cinematicStep.set(0);
    cinematicPlaying.set(true);
  }

  onMount(() => {
    timerInterval = setInterval(() => {
      if ($cinematicPlaying) {
        nextStep();
      }
    }, 4500);
  });

  onDestroy(() => {
    if (timerInterval) clearInterval(timerInterval);
  });
</script>

<div class="landing-page">
  <!-- Top Editorial Header -->
  <header class="landing-header">
    <div class="brand-block">
      <span class="brand-shield">🛡</span>
      <div>
        <div class="brand-title serif-display">RED//QUEEN</div>
        <div class="brand-sub mono">AUTONOMOUS RED-TEAM RANGE · ENTERPRISE AGENT SECURITY</div>
      </div>
    </div>

    <div class="header-actions">
      <div class="stream-pill mono" class:connected={$connected}>
        <span class="dot"></span>
        {$connected ? "STREAM LIVE" : "CONNECTING..."}
      </div>

      <button class="btn btn-secondary btn-sm" on:click={startJudgeDemo}>
        ▶ 45s JUDGE EXPERIENCE
      </button>

      <button class="btn btn-primary btn-sm" on:click={() => enterRange("fleet")}>
        ENTER THE RANGE →
      </button>
    </div>
  </header>

  <!-- 1. Top Section: Attention-Grabbing Hook & Value Proposition -->
  <section class="hook-section">
    <div class="hook-container">
      <div class="hook-badge mono">
        <span class="badge-dot">●</span> AUTONOMOUS AGENT SECURITY CONTROL LOOP
      </div>

      <h1 class="hook-headline serif-display">
        THE ATTACK <span class="oxblood-text">EVOLVES.</span><br />
        SO DOES <span class="green-text">THE DEFENSE.</span>
      </h1>

      <p class="hook-lead editorial-serif">
        Red//Queen continuously attacks your AI agent fleet, discovers adaptive prompt and tool bypasses, independently verifies failures under isolated database roles, and synthesizes hardened boundaries until the exploit is proven closed.
      </p>

      <div class="hook-cta-row">
        <button class="btn btn-primary btn-hero" on:click={startJudgeDemo}>
          ▶ START 45s CINEMATIC EXPERIENCE
        </button>
        <button class="btn btn-secondary btn-hero" on:click={() => enterRange("fleet")}>
          EXPLORE LIVE AGENT FLEET →
        </button>
      </div>

      <!-- 4 Pinteresty Architecture Pillars -->
      <div class="pillars-grid">
        <div class="pillar-card">
          <div class="p-icon">🧬</div>
          <div class="p-title serif-display">Adversarial Evolution</div>
          <div class="p-sub mono">4 Mutation Operators · pgvector</div>
          <p class="p-desc">Generates multi-generation injection variants using cosine similarity memory to explore decoder bypasses.</p>
        </div>

        <div class="pillar-card">
          <div class="p-icon">⚖</div>
          <div class="p-title serif-display">Independent Verifier</div>
          <div class="p-sub mono">DB Role: sentinel_verifier</div>
          <p class="p-desc">The attacker never certifies the fix. A firewalled subprocess with zero corpus access re-proves the failure.</p>
        </div>

        <div class="pillar-card">
          <div class="p-icon">🛡</div>
          <div class="p-title serif-display">Boundary Hardening</div>
          <div class="p-sub mono">Model Armor · Identity Scopes</div>
          <p class="p-desc">Synthesizes idempotent policy deltas (deep_normalize, capability revocation) without code redeployment.</p>
        </div>

        <div class="pillar-card">
          <div class="p-icon">🎯</div>
          <div class="p-title serif-display">Mathematical Proof</div>
          <div class="p-sub mono">3 Orthogonal Sub-Scores</div>
          <p class="p-desc">Re-tests patched fleet against new mutations. Refuses false-closed badges unless exploit fails completely.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- 2. Scroll Section: 3D Hero + Interactive Technical Narrative -->
  <section id="hero-3d-section" class="hero-3d-section">
    <div class="section-container">
      <div class="section-tag mono">02 / THE 3D SECURITY ORGANISM & STORY</div>
      
      <div class="hero-split-grid">
        <!-- Left Side: Technical Narrative & Interactive Step Controller -->
        <div class="hero-narrative-col">
          <div class="narrative-card">
            <!-- Timeline Scrub Header -->
            <div class="timeline-meta-bar">
              <div class="tm-left mono">
                <span class="step-badge">{BEATS[$cinematicStep].stage}</span>
                <span class="time-readout">{BEATS[$cinematicStep].time}</span>
              </div>
              <div class="tm-controls">
                <button class="btn btn-sm btn-secondary" on:click={prevStep} title="Previous beat">◀</button>
                <button class="btn btn-sm btn-oxblood" on:click={togglePlay}>
                  {$cinematicPlaying ? "PAUSE" : "PLAY"}
                </button>
                <button class="btn btn-sm btn-secondary" on:click={nextStep} title="Next beat">▶</button>
              </div>
            </div>

            <!-- 11-Beat Scrub Bar -->
            <div class="beats-track">
              {#each BEATS as b, i}
                <button
                  class="beat-node"
                  class:active={$cinematicStep === i}
                  on:click={() => setStep(i)}
                  title={b.headline}
                >
                  <span class="beat-num mono">{i + 1}</span>
                </button>
              {/each}
            </div>

            <!-- Active Beat Content -->
            <div class="active-beat-content">
              <h2 class="beat-headline serif-display">{BEATS[$cinematicStep].headline}</h2>
              <p class="beat-sub editorial-serif">{BEATS[$cinematicStep].sub}</p>

              <div class="beat-hud-box mono">
                <div class="hud-item">
                  <span class="lbl">TECHNICAL HUD:</span>
                  <span class="val text-oxblood">{BEATS[$cinematicStep].hud}</span>
                </div>
                <div class="hud-item">
                  <span class="lbl">BACKEND MODULE:</span>
                  <code>{BEATS[$cinematicStep].tech}</code>
                </div>
              </div>

              <div class="beat-actions">
                <button class="btn btn-primary btn-sm" on:click={() => enterRange(BEATS[$cinematicStep].tab)}>
                  INSPECT IN {BEATS[$cinematicStep].tab.toUpperCase()} VIEW →
                </button>
              </div>
            </div>

            <!-- Interactive 8-Stage Loop Selector -->
            <div class="loop-selector-block">
              <div class="ls-title mono">CONTROL LOOP STAGES (CLICK TO DRIVE 3D CAMERA):</div>
              <div class="loop-chips-grid">
                {#each loopStages as stage, idx}
                  <button
                    class="loop-chip mono"
                    class:active={activeLoopStage === idx}
                    on:click={() => handleLoopSelect(idx, stage.step)}
                  >
                    <span class="idx">0{idx + 1}</span>
                    <span class="name">{stage.name.split(". ")[1]}</span>
                  </button>
                {/each}
              </div>
            </div>
          </div>
        </div>

        <!-- Right Side: 3D Security Organism Scene -->
        <div class="hero-3d-col">
          <div class="organism-wrapper">
            <SecurityOrganism width="100%" height="600px" interactive={true} />
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 3. Problem Section: The Adaptive Threat -->
  <section class="narrative-section">
    <div class="section-container">
      <div class="section-tag mono">03 / THE ADAPTIVE THREAT</div>
      <h2 class="section-headline serif-display">
        Static defenses defend against yesterday's attack.
      </h2>
      <div class="problem-grid">
        <div class="problem-card">
          <div class="card-num mono">01</div>
          <h4 class="card-title serif-display">The Single Filter Fallacy</h4>
          <p>
            Agent attacks mutate. A static regex or exact-match blocklist that intercepts one naive injection fails when adversaries apply leet obfuscations, directive softening, or tool poisoning.
          </p>
        </div>

        <div class="problem-card">
          <div class="card-num mono">02</div>
          <h4 class="card-title serif-display">The Self-Judging Attacker</h4>
          <p>
            Standard benchmarks let red-team agents evaluate their own success. Red//Queen enforces an independent verifier operating under a firewalled database role (<code>sentinel_verifier</code>) with zero access to the attacker corpus.
          </p>
        </div>

        <div class="problem-card">
          <div class="card-num mono">03</div>
          <h4 class="card-title serif-display">The False Closure Trap</h4>
          <p>
            Brittle patches create a false sense of security. Red//Queen's verifier explicitly tests for <code>FALSE_CLOSED</code> states, refusing to issue a passing certificate unless the fix withstands newly evolved variants.
          </p>
        </div>
      </div>
    </div>
  </section>

  <!-- 4. Proof Section -->
  <section class="narrative-section section-proof">
    <div class="section-container">
      <div class="section-tag mono">04 / PHILOSOPHICAL & TECHNICAL PROOF</div>
      <h2 class="section-headline serif-display">
        "THE ATTACKER DOES NOT CERTIFY THE FIX."
      </h2>

      <div class="proof-card">
        <p class="proof-statement editorial-serif">
          Red//Queen does not claim protection based on heuristics or self-judging agents. Every patch is independently re-tested against a newly evolved adversary before an official verification certificate is signed.
        </p>

        <div class="proof-metrics-grid mono">
          <div class="pm-box">
            <span class="pm-title">ARMOR BLOCKED</span>
            <span class="pm-val">100% OF RE-TEST VARIANTS</span>
            <span class="pm-sub">Decodes leet & zero-width tokens</span>
          </div>

          <div class="pm-box">
            <span class="pm-title">BEHAVIOR UNCHANGED</span>
            <span class="pm-val">ZERO ESCALATIONS</span>
            <span class="pm-sub">Agent answers safely without tool abuse</span>
          </div>

          <div class="pm-box">
            <span class="pm-title">SECRET CONTAINED</span>
            <span class="pm-val">CANARY PROTECTED</span>
            <span class="pm-sub">Zero exfiltration through sinks</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Grand Finale CTA -->
  <section class="landing-cta-section">
    <div class="section-container">
      <h2 class="cta-headline serif-display">
        Experience the Autonomous Range
      </h2>
      <p class="cta-sub editorial-serif">
        Inspect live agent capabilities, launch real evolutionary attack campaigns, review destructive approval gates, and analyze OpenTelemetry trace waterfalls.
      </p>
      <div class="cta-buttons">
        <button class="btn btn-primary btn-hero" on:click={() => enterRange("fleet")}>
          LAUNCH RED//QUEEN CONTROL PLANE →
        </button>
      </div>
    </div>
  </section>
</div>

<style>
  .landing-page {
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  .landing-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 40px;
    border-bottom: 1px solid var(--border);
    background: rgba(250, 248, 245, 0.92);
    backdrop-filter: blur(10px);
    position: sticky;
    top: 0;
    z-index: 50;
  }

  .brand-block {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand-shield {
    font-size: 26px;
  }
  .brand-title {
    font-size: 15px;
    font-weight: 900;
    letter-spacing: 0.12em;
    color: var(--text);
  }
  .brand-sub {
    font-size: 9.5px;
    color: var(--muted);
    letter-spacing: 0.08em;
    font-weight: 700;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .stream-pill {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 700;
    color: var(--stone);
    padding: 4px 10px;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 20px;
    box-shadow: var(--shadow-subtle);
  }
  .stream-pill .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--stone);
  }
  .stream-pill.connected {
    color: var(--verif-green);
    border-color: rgba(27, 94, 59, 0.3);
  }
  .stream-pill.connected .dot {
    background: var(--verif-green);
    box-shadow: 0 0 6px var(--verif-green);
  }

  /* 1. Hook Section */
  .hook-section {
    padding: 70px 40px 60px 40px;
    max-width: 1400px;
    margin: 0 auto;
    text-align: center;
  }
  .hook-container {
    max-width: 1100px;
    margin: 0 auto;
  }
  .hook-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #FFFFFF;
    border: 1px solid var(--border);
    padding: 5px 14px;
    border-radius: 20px;
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: 0.1em;
    color: var(--stone);
    margin-bottom: 24px;
    box-shadow: var(--shadow-subtle);
  }
  .badge-dot {
    color: var(--oxblood);
  }

  .hook-headline {
    font-size: 58px;
    line-height: 1.06;
    font-weight: 900;
    letter-spacing: -0.02em;
    color: var(--text);
    margin-bottom: 24px;
  }
  .oxblood-text {
    color: var(--oxblood);
    font-style: italic;
  }
  .green-text {
    color: var(--verif-green);
  }

  .hook-lead {
    font-size: 20px;
    line-height: 1.6;
    color: var(--text-dim);
    max-width: 860px;
    margin: 0 auto 36px auto;
  }

  .hook-cta-row {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-bottom: 54px;
  }
  .btn-hero {
    padding: 14px 30px;
    font-size: 12px;
    letter-spacing: 0.08em;
  }

  /* Pinteresty Pillars Grid */
  .pillars-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    text-align: left;
  }
  .pillar-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 24px;
    box-shadow: var(--shadow-card);
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .pillar-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-elevated);
  }
  .p-icon {
    font-size: 24px;
    margin-bottom: 12px;
  }
  .p-title {
    font-size: 17px;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 4px;
  }
  .p-sub {
    font-size: 10px;
    font-weight: 700;
    color: var(--oxblood);
    margin-bottom: 10px;
    letter-spacing: 0.05em;
  }
  .p-desc {
    font-size: 12.5px;
    line-height: 1.55;
    color: var(--text-dim);
  }

  /* 2. Scroll 3D Section */
  .hero-3d-section {
    padding: 80px 40px;
    border-top: 1px solid var(--border);
    background: var(--bg-subtle);
  }
  .section-container {
    max-width: 1400px;
    margin: 0 auto;
  }
  .section-tag {
    font-size: 11px;
    font-weight: 800;
    color: var(--oxblood);
    letter-spacing: 0.12em;
    margin-bottom: 20px;
  }

  .hero-split-grid {
    display: grid;
    grid-template-columns: 1.05fr 1fr;
    gap: 36px;
    align-items: center;
  }

  .narrative-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 32px;
    box-shadow: var(--shadow-elevated);
  }

  .timeline-meta-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .step-badge {
    background: var(--text);
    color: #FFFFFF;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.08em;
  }
  .time-readout {
    font-size: 11px;
    color: var(--muted);
    font-weight: 700;
    margin-left: 8px;
  }
  .tm-controls {
    display: flex;
    gap: 6px;
  }

  .beats-track {
    display: grid;
    grid-template-columns: repeat(11, 1fr);
    gap: 4px;
    margin-bottom: 24px;
  }
  .beat-node {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px 0;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .beat-node:hover {
    background: #EDE7DC;
  }
  .beat-node.active {
    background: var(--oxblood);
    border-color: var(--oxblood);
    color: #FFFFFF;
  }
  .beat-num {
    font-size: 10px;
    font-weight: 800;
  }

  .active-beat-content {
    margin-bottom: 28px;
  }
  .beat-headline {
    font-size: 26px;
    font-weight: 900;
    color: var(--text);
    margin-bottom: 10px;
  }
  .beat-sub {
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-dim);
    margin-bottom: 20px;
  }

  .beat-hud-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 14px 18px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 20px;
  }
  .hud-item {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
  }
  .hud-item .lbl {
    color: var(--muted);
    font-weight: 700;
  }
  .hud-item .val {
    font-weight: 800;
  }
  .text-oxblood {
    color: var(--oxblood);
  }
  .hud-item code {
    background: rgba(0, 0, 0, 0.05);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    color: var(--text);
  }

  /* Loop Selector */
  .loop-selector-block {
    padding-top: 20px;
    border-top: 1px solid var(--border-subtle);
  }
  .ls-title {
    font-size: 9.5px;
    font-weight: 800;
    color: var(--muted);
    letter-spacing: 0.08em;
    margin-bottom: 10px;
  }
  .loop-chips-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }
  .loop-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 10px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s;
  }
  .loop-chip:hover, .loop-chip.active {
    background: var(--text);
    border-color: var(--text);
    color: #FFFFFF;
  }
  .loop-chip.active .idx {
    color: var(--oxblood-bright);
  }
  .loop-chip .idx {
    color: var(--muted);
    font-size: 9px;
  }

  .organism-wrapper {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow-elevated);
    overflow: hidden;
  }

  /* Narrative Sections */
  .narrative-section {
    padding: 80px 40px;
    border-top: 1px solid var(--border);
  }
  .section-headline {
    font-size: 38px;
    font-weight: 900;
    color: var(--text);
    margin-bottom: 36px;
  }

  .problem-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
  }
  .problem-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 28px;
    box-shadow: var(--shadow-card);
  }
  .card-num {
    font-size: 13px;
    font-weight: 900;
    color: var(--oxblood);
    margin-bottom: 12px;
  }
  .card-title {
    font-size: 18px;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 10px;
  }
  .problem-card p {
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--text-dim);
  }

  /* Section Proof */
  .section-proof {
    background: var(--bg-subtle);
  }
  .proof-card {
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 40px;
    box-shadow: var(--shadow-elevated);
  }
  .proof-statement {
    font-size: 22px;
    line-height: 1.6;
    color: var(--text);
    margin-bottom: 36px;
    max-width: 960px;
  }
  .proof-metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
  .pm-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .pm-title {
    font-size: 10px;
    font-weight: 800;
    color: var(--muted);
    letter-spacing: 0.08em;
  }
  .pm-val {
    font-size: 14px;
    font-weight: 900;
    color: var(--verif-green);
  }
  .pm-sub {
    font-size: 11px;
    color: var(--text-dim);
  }

  /* CTA Section */
  .landing-cta-section {
    padding: 90px 40px;
    text-align: center;
    background: #FFFFFF;
    border-top: 1px solid var(--border);
  }
  .cta-headline {
    font-size: 40px;
    font-weight: 900;
    margin-bottom: 16px;
  }
  .cta-sub {
    font-size: 18px;
    color: var(--text-dim);
    max-width: 720px;
    margin: 0 auto 36px auto;
    line-height: 1.6;
  }

  @media (max-width: 1024px) {
    .hook-headline { font-size: 42px; }
    .pillars-grid { grid-template-columns: repeat(2, 1fr); }
    .hero-split-grid { grid-template-columns: 1fr; }
    .problem-grid, .proof-metrics-grid { grid-template-columns: 1fr; }
  }
</style>

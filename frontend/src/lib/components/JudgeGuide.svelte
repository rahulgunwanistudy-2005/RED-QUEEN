<script>
  import {
    judgeMode,
    judgeStep,
    viewMode,
    activeTab,
    cinematicStep,
    cinematicPlaying,
  } from "../store.js";

  const JUDGE_STAGES = [
    {
      step: 1,
      title: "01 · THE PROBLEM & HOOK",
      narrative: "AI Agents are vulnerable to mutating adversarial attacks. Static filters fail against obfuscations.",
      actionLabel: "WATCH 3D CINEMATIC",
      tab: "landing",
      cinStep: 0,
    },
    {
      step: 2,
      title: "02 · FLEET CAPABILITY BOUNDARY",
      narrative: "Inspect triage-agent (gemini-2.0-flash), its bound tools (run_privileged_fix, export_secrets), and Model Armor perimeter.",
      actionLabel: "OPEN FLEET VIEW",
      tab: "fleet",
      cinStep: 1,
    },
    {
      step: 3,
      title: "03 · ADVERSARIAL EVOLUTION",
      narrative: "Red//Queen's red-team evolves multi-generation attack variants using 4 mutation operators and pgvector memory.",
      actionLabel: "OPEN ATTACK ENGINE",
      tab: "attacks",
      cinStep: 3,
    },
    {
      step: 4,
      title: "04 · BYPASS CLIMAX & TRACE",
      narrative: "An evolved variant bypasses the normalizer, coercing unauthorized execution. Score drops to 41/100 with OTel trace evidence.",
      actionLabel: "INSPECT BYPASS",
      tab: "attacks",
      cinStep: 5,
    },
    {
      step: 5,
      title: "05 · POLICY DELTA & APPROVAL",
      narrative: "Red//Queen synthesizes an idempotent policy delta (Model Armor deep_normalize) and gates destructive actions for human approval.",
      actionLabel: "OPEN REMEDIATION",
      tab: "remediation",
      cinStep: 8,
    },
    {
      step: 6,
      title: "06 · INDEPENDENT VERIFIER & PROOF",
      narrative: "The attacker does not certify the fix. An isolated DB role (sentinel_verifier) re-tests and signs a 3/3 orthogonal passing certificate.",
      actionLabel: "INSPECT CERTIFICATE & TRACES",
      tab: "traces",
      cinStep: 10,
    },
  ];

  $: current = JUDGE_STAGES[$judgeStep] || JUDGE_STAGES[0];

  function next() {
    judgeStep.update((s) => Math.min(JUDGE_STAGES.length - 1, s + 1));
  }

  function prev() {
    judgeStep.update((s) => Math.max(0, s - 1));
  }

  function triggerAction() {
    if (current.tab === "landing") {
      viewMode.set("landing");
      cinematicStep.set(current.cinStep);
      cinematicPlaying.set(true);
      setTimeout(() => {
        const el = document.getElementById("hero-3d-section");
        if (el) el.scrollIntoView({ behavior: "smooth" });
      }, 50);
    } else {
      activeTab.set(current.tab);
      viewMode.set("control_plane");
      cinematicStep.set(current.cinStep);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function closeJudgeMode() {
    judgeMode.set(false);
  }
</script>

{#if $judgeMode}
  <div class="judge-guide-modal panel">
    <div class="jg-header">
      <div class="jg-title mono">
        <span class="jg-badge">⚖ 45s JUDGE EXPERIENCE</span>
        <span class="jg-step-count">STAGE {$judgeStep + 1} / {JUDGE_STAGES.length}</span>
      </div>
      <button class="btn-close" on:click={closeJudgeMode} title="Exit Judge Mode">✕</button>
    </div>

    <div class="jg-body">
      <div class="jg-stage-title serif-display">{current.title}</div>
      <p class="jg-narrative editorial-serif">{current.narrative}</p>
    </div>

    <div class="jg-footer">
      <div class="jg-nav-btns">
        <button class="btn btn-sm btn-secondary" on:click={prev} disabled={$judgeStep === 0}>◀ PREV</button>
        <button class="btn btn-sm btn-secondary" on:click={next} disabled={$judgeStep === JUDGE_STAGES.length - 1}>NEXT ▶</button>
      </div>

      <button class="btn btn-sm btn-primary jg-action-btn" on:click={triggerAction}>
        {current.actionLabel} →
      </button>
    </div>
  </div>
{/if}

<style>
  .judge-guide-modal {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 440px;
    background: #FFFFFF;
    border: 1.5px solid var(--oxblood);
    border-radius: 10px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.16);
    z-index: 100;
    padding: 18px 22px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    animation: slideIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .jg-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .jg-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .jg-badge {
    background: var(--oxblood);
    color: #FFFFFF;
    font-size: 9.5px;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: 0.08em;
  }
  .jg-step-count {
    font-size: 10px;
    color: var(--muted);
    font-weight: 800;
  }

  .btn-close {
    background: transparent;
    border: none;
    color: var(--stone);
    font-size: 14px;
    cursor: pointer;
    padding: 2px 6px;
  }
  .btn-close:hover {
    color: var(--oxblood);
  }

  .jg-stage-title {
    font-size: 15px;
    font-weight: 900;
    color: var(--text);
    margin-bottom: 4px;
  }
  .jg-narrative {
    font-size: 13.5px;
    line-height: 1.5;
    color: var(--text-dim);
  }

  .jg-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 10px;
    border-top: 1px solid var(--border-subtle);
  }
  .jg-nav-btns {
    display: flex;
    gap: 6px;
  }
  .jg-action-btn {
    font-size: 10.5px;
    font-weight: 800;
  }
</style>

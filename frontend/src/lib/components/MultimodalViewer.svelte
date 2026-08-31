<script>
  import { multimodalDemo, multimodalLoading, campaignStatus, runMultimodalDemo, runCampaign } from "../store.js";

  let revealed = false;
  let hardening = false;

  $: demo = $multimodalDemo;
  $: hasResult = demo && !demo.error;
  $: guardActive = hasResult && demo.multimodal_guard_active;
  $: bypassed = hasResult && demo.bypass;
  $: blocked = hasResult && demo.scan?.blocked;

  async function runAttack() {
    revealed = false;
    await runMultimodalDemo();
    revealed = true;
  }

  async function hardenGuard() {
    hardening = true;
    try {
      await runCampaign({ attackClass: "multimodal", remedy: "multimodal", useMemory: true });
      await runMultimodalDemo(); // re-probe under the new posture -> now BLOCKED
    } finally {
      hardening = false;
    }
  }
</script>

<div class="mm panel">
  <div class="mm-head">
    <div class="panel-title">
      <span>🖼</span> MULTIMODAL INJECTION · THE INVISIBLE PAYLOAD
      <span class="muted mono">attack_class=multimodal · Gemini vision</span>
    </div>
    <div class="mm-actions">
      {#if hasResult}
        {#if blocked}
          <span class="badge badge-green mono">🛡 BLOCKED BY MULTIMODAL GUARD</span>
        {:else if bypassed}
          <span class="badge badge-red mono pulse-badge">⚠ VISION AGENT HIJACKED</span>
        {/if}
      {/if}
      <button class="btn btn-primary btn-sm" on:click={runAttack} disabled={$multimodalLoading || hardening}>
        {$multimodalLoading ? "⏳ RUNNING…" : "▶ RUN MULTIMODAL ATTACK"}
      </button>
      <button class="btn btn-sm btn-harden" on:click={hardenGuard} disabled={hardening || $multimodalLoading || !hasResult}>
        {hardening ? "⏳ HARDENING…" : "🛡 HARDEN (MULTIMODAL GUARD)"}
      </button>
    </div>
  </div>

  {#if !hasResult}
    <div class="mm-empty">
      <div class="mm-empty-icon">🧾</div>
      <p>
        An ordinary invoice — with a hidden instruction painted into the pixels. Click
        <strong>RUN MULTIMODAL ATTACK</strong> to feed it to the real Gemini vision agent. A
        <em>text</em> guardrail is blind to pixels, so it slips straight through and hijacks
        the agent. Then <strong>HARDEN</strong> to switch on the distinct multimodal guard and
        watch the same payload get blocked.
      </p>
    </div>
  {:else if demo.error}
    <div class="mm-empty"><p class="text-red mono">error: {demo.error}</p></div>
  {:else}
    <div class="mm-grid">
      <!-- LEFT: the rendered invoice + reveal toggle -->
      <div class="mm-image-col">
        <div class="mm-image-frame" class:revealed>
          <img src={`data:image/png;base64,${demo.image_b64}`} alt="attack invoice" />
          {#if revealed}
            <div class="mm-highlight">
              <div class="mm-highlight-tag mono">HIDDEN INSTRUCTION IN PIXELS ↓</div>
            </div>
          {/if}
        </div>
        <label class="mm-toggle mono">
          <input type="checkbox" bind:checked={revealed} />
          <span>{revealed ? "Hide" : "Reveal"} the hidden instruction</span>
        </label>
      </div>

      <!-- RIGHT: the reveal flow -->
      <div class="mm-flow">
        <div class="mm-step">
          <div class="mm-step-lbl mono">1 · TEXT GUARDRAIL SAW (the carrier)</div>
          <div class="mm-box carrier mono">{demo.carrier_text}</div>
          <div class="mm-verdict {demo.text_scan?.blocked ? 'v-block' : 'v-blind'} mono">
            {demo.text_scan?.blocked ? "BLOCKED" : "CLEAN · a text defense is blind to pixels"}
          </div>
        </div>

        <div class="mm-step">
          <div class="mm-step-lbl mono">2 · HIDDEN INSTRUCTION (in the image)</div>
          <div class="mm-box hidden-txt mono" class:masked={!revealed}>
            {revealed ? demo.overlay_text : "•••••••  toggle reveal to expose  •••••••"}
          </div>
        </div>

        <div class="mm-step">
          <div class="mm-step-lbl mono">3 · MULTIMODAL GUARD · VISION EXTRACTION
            <span class="badge {guardActive ? 'badge-green' : 'badge-muted'} badge-xs">{guardActive ? "ACTIVE" : "inactive"}</span>
          </div>
          <div class="mm-box extracted mono">{demo.extracted_text?.slice(0, 320) || "—"}</div>
          <div class="mm-verdict {blocked ? 'v-block' : 'v-blind'} mono">
            {guardActive ? (blocked ? "MATCH · hidden instruction recovered → BLOCKED" : "clean") : "guard not yet applied — extraction bypassed"}
          </div>
        </div>

        <div class="mm-step">
          <div class="mm-step-lbl mono">4 · TARGET AGENT OUTCOME</div>
          {#if blocked}
            <div class="mm-outcome ok mono">
              <strong>🛡 request blocked at the gateway</strong> — the agent never saw the image.
            </div>
          {:else if demo.agent}
            <div class="mm-outcome {bypassed ? 'bad' : 'ok'} mono">
              <div>action: <strong class={bypassed ? "text-red" : "text-blue"}>{demo.agent.action}</strong></div>
              <div>privileged executed: <strong class={bypassed ? "text-red" : "text-green"}>{String(demo.agent.privileged_executed)}</strong></div>
              <div class="mm-agent-answer">{demo.agent.answer}</div>
              <div class="mm-backend">backend: {demo.agent.backend}</div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .mm {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-card);
    padding: 20px;
  }
  .mm-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-subtle);
  }
  .mm-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .btn-harden {
    border: 1px solid var(--verif-green);
    color: var(--verif-green);
    background: #fff;
  }
  .btn-harden:disabled { opacity: 0.45; }

  .mm-empty {
    padding: 28px 24px;
    display: flex;
    align-items: center;
    gap: 20px;
    color: var(--text-dim);
    font-size: 13px;
    line-height: 1.6;
  }
  .mm-empty-icon { font-size: 46px; }

  .mm-grid {
    display: grid;
    grid-template-columns: minmax(320px, 460px) 1fr;
    gap: 24px;
    align-items: start;
  }

  .mm-image-col { display: flex; flex-direction: column; gap: 10px; }
  .mm-image-frame {
    position: relative;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    background: var(--bg-subtle);
    box-shadow: var(--shadow-card);
    transition: box-shadow 0.2s;
  }
  .mm-image-frame.revealed { box-shadow: 0 0 0 2px var(--oxblood); }
  .mm-image-frame img { display: block; width: 100%; height: auto; }
  .mm-highlight {
    position: absolute;
    left: 0; right: 0;
    bottom: 5%;
    height: 22%;
    background: linear-gradient(90deg, rgba(139,0,0,0.16), rgba(139,0,0,0.05));
    border-top: 2px dashed var(--oxblood);
    border-bottom: 2px dashed var(--oxblood);
    display: flex;
    align-items: flex-start;
    justify-content: flex-end;
    animation: mm-pulse 1.4s ease-in-out infinite;
  }
  .mm-highlight-tag {
    background: var(--oxblood);
    color: #fff;
    font-size: 9px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 0 0 0 6px;
    letter-spacing: 0.05em;
  }
  @keyframes mm-pulse { 0%,100% { opacity: 0.55; } 50% { opacity: 1; } }

  .mm-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-dim);
    cursor: pointer;
  }

  .mm-flow { display: flex; flex-direction: column; gap: 12px; }
  .mm-step { display: flex; flex-direction: column; gap: 5px; }
  .mm-step-lbl {
    font-size: 10px;
    font-weight: 800;
    color: var(--stone);
    letter-spacing: 0.07em;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mm-box {
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 11.5px;
    line-height: 1.5;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 120px;
    overflow-y: auto;
  }
  .mm-box.carrier { border-left: 3px solid var(--tech-blue); }
  .mm-box.hidden-txt { border-left: 3px solid var(--oxblood); color: var(--oxblood); }
  .mm-box.hidden-txt.masked { color: var(--muted); letter-spacing: 0.1em; }
  .mm-box.extracted { border-left: 3px solid var(--stone); }

  .mm-verdict { font-size: 10.5px; font-weight: 700; padding: 2px 2px; }
  .v-blind { color: var(--tech-blue); }
  .v-block { color: var(--verif-green); }

  .mm-outcome {
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 11.5px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .mm-outcome.bad { background: rgba(139,0,0,0.06); border: 1px solid var(--oxblood); }
  .mm-outcome.ok { background: rgba(20,120,70,0.06); border: 1px solid var(--verif-green); }
  .mm-agent-answer { color: var(--text-dim); font-style: italic; margin-top: 4px; }
  .mm-backend { color: var(--muted); font-size: 10px; margin-top: 2px; }

  .text-red { color: var(--oxblood); }
  .text-green { color: var(--verif-green); }
  .text-blue { color: var(--tech-blue); }
  .pulse-badge { animation: mm-pulse 1.2s infinite; }
  .badge-xs { font-size: 9px; padding: 1px 5px; }

  @media (max-width: 900px) {
    .mm-grid { grid-template-columns: 1fr; }
  }
</style>

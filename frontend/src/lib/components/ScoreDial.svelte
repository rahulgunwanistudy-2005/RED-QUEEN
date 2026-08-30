<script>
  // Semicircular Hardening Score Gauge (0..100)
  export let value = null;
  export let band = "unknown";
  export let size = 180;
  export let showBand = true;

  const R = 76;
  const CX = 90;
  const CY = 86;
  const CIRC = Math.PI * R;

  $: pct = value == null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  $: dash = `${pct * CIRC} ${CIRC}`;
  $: color =
    band === "green"
      ? "#1B5E3B"
      : band === "amber"
      ? "#B86B14"
      : band === "red"
      ? "#8B1E1E"
      : "#9C9486";
  $: label = value == null ? "—" : value;
</script>

<div class="score-dial" style="width: {size}px; --dial-color: {color};">
  <svg viewBox="0 0 180 105" width="100%" height="100%">
    <!-- Background Track Arc -->
    <path
      d="M 14 86 A {R} {R} 0 0 1 166 86"
      fill="none"
      stroke="#E5DFD5"
      stroke-width="12"
      stroke-linecap="round"
    />
    <!-- Active Score Arc -->
    <path
      d="M 14 86 A {R} {R} 0 0 1 166 86"
      fill="none"
      stroke={color}
      stroke-width="12"
      stroke-linecap="round"
      stroke-dasharray={dash}
      style="transition: stroke-dasharray 0.7s cubic-bezier(0.4, 0, 0.2, 1), stroke 0.5s ease"
    />
    <!-- Center Numerical Value -->
    <text x="90" y="74" text-anchor="middle" class="val mono">{label}</text>
    <text x="90" y="94" text-anchor="middle" class="unit mono">/ 100</text>
  </svg>
  {#if showBand}
    <div class="band-tag mono" style="color: {color}">
      <span class="dot" style="background: {color}; box-shadow: 0 0 8px {color};"></span>
      {band ? band.toUpperCase() : "UNKNOWN"}
    </div>
  {/if}
</div>

<style>
  .score-dial {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }
  .val {
    fill: var(--dial-color);
    font-size: 34px;
    font-weight: 800;
  }
  .unit {
    fill: var(--muted);
    font-size: 11px;
    letter-spacing: 0.1em;
    font-weight: 600;
  }
  .band-tag {
    margin-top: -2px;
    font-size: 11px;
    letter-spacing: 0.16em;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
</style>

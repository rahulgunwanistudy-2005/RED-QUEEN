<script>
  // Hardening Score dial: 0..100, red -> amber -> green semicircular gauge.
  export let value = null;
  export let band = "unknown";

  const R = 90;
  const CX = 110;
  const CY = 110;
  const CIRC = Math.PI * R; // half-circle arc length

  $: pct = value == null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  $: dash = `${pct * CIRC} ${CIRC}`;
  $: color =
    band === "green" ? "#2ecc71" : band === "amber" ? "#f1c40f" : band === "red" ? "#ff3b52" : "#5a6b7b";
  $: label = value == null ? "—" : value;
</script>

<div class="dial" style="--dial: {color}">
  <svg viewBox="0 0 220 130" width="100%" height="100%">
    <path
      d="M 20 110 A {R} {R} 0 0 1 200 110"
      fill="none"
      stroke="#1c2733"
      stroke-width="16"
      stroke-linecap="round"
    />
    <path
      d="M 20 110 A {R} {R} 0 0 1 200 110"
      fill="none"
      stroke={color}
      stroke-width="16"
      stroke-linecap="round"
      stroke-dasharray={dash}
      style="transition: stroke-dasharray .6s ease, stroke .6s ease"
    />
    <text x="110" y="96" text-anchor="middle" class="value">{label}</text>
    <text x="110" y="120" text-anchor="middle" class="unit">/ 100</text>
  </svg>
  <div class="band">{band.toUpperCase()}</div>
</div>

<style>
  .dial {
    width: 260px;
    max-width: 100%;
    text-align: center;
  }
  .value {
    fill: var(--dial);
    font-size: 44px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
  }
  .unit {
    fill: #6b7d8f;
    font-size: 13px;
    letter-spacing: 0.08em;
  }
  .band {
    margin-top: 10px;
    font-size: 13px;
    letter-spacing: 0.22em;
    font-weight: 700;
    color: var(--dial);
  }
</style>

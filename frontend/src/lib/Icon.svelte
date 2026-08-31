<script>
  export let name;
  export let size = 18;
  export let strokeWidth = 1.7;
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === "grid"}
    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
  {:else if name === "crosshair"}
    <circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/>
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>
  {:else if name === "shield"}
    <path d="M12 3 20 6v5c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10V6l8-3Z"/><path d="m8.8 12 2 2 4.5-5"/>
  {:else if name === "pulse"}
    <path d="M3 12h4l2.2-5 4.2 10 2.2-5H21"/>
  {:else if name === "terminal"}
    <rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M12.5 15H17"/>
  {:else if name === "database"}
    <ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>
  {:else if name === "cpu"}
    <rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/>
    <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>
  {:else if name === "lock"}
    <rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>
  {:else if name === "play"}
    <path d="m8 5 11 7-11 7V5Z"/>
  {:else if name === "image"}
    <rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 20"/>
  {:else if name === "branch"}
    <circle cx="6" cy="5" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="19" r="2"/>
    <path d="M6 7v10M8 9c5 0 4-3 8-3"/>
  {:else if name === "certificate"}
    <circle cx="12" cy="10" r="7"/><path d="m8.5 16-1 6 4.5-2 4.5 2-1-6M9 10l2 2 4-4"/>
  {:else if name === "layers"}
    <path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/>
  {:else if name === "clock"}
    <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>
  {:else if name === "arrow"}
    <path d="M5 12h14M14 7l5 5-5 5"/>
  {:else if name === "chevron"}
    <path d="m9 18 6-6-6-6"/>
  {:else if name === "check"}
    <path d="m5 12 4 4L19 6"/>
  {:else if name === "x"}
    <path d="m6 6 12 12M18 6 6 18"/>
  {:else if name === "refresh"}
    <path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 9a7 7 0 0 1 11.8-2L20 9M4 15l2.1 2a7 7 0 0 0 11.8-2"/>
  {:else if name === "eye"}
    <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>
  {:else if name === "menu"}
    <path d="M4 7h16M4 12h16M4 17h16"/>
  {/if}
</svg>

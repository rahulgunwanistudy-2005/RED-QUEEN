<script>
  import { events, eventDrawerOpen, eventFilter } from "../store.js";

  let searchQuery = "";
  let expandedEvent = null;

  const filters = [
    { id: "all", label: "ALL" },
    { id: "score", label: "SCORE" },
    { id: "candidate", label: "ATTACK" },
    { id: "state", label: "STATE" },
    { id: "policy", label: "POLICY" },
    { id: "approval", label: "APPROVAL" },
    { id: "verdict", label: "VERDICT" },
    { id: "corpus", label: "CORPUS" },
  ];

  $: filteredEvents = $events.filter((e) => {
    if ($eventFilter !== "all" && e.type !== $eventFilter) return false;
    if (!searchQuery) return true;
    const s = searchQuery.toLowerCase();
    return JSON.stringify(e).toLowerCase().includes(s);
  });

  function toggleExpand(index) {
    expandedEvent = expandedEvent === index ? null : index;
  }

  function getBadgeClass(type) {
    if (type === "candidate") return "badge-oxblood";
    if (type === "verdict") return "badge-green";
    if (type === "policy") return "badge-blue";
    if (type === "approval") return "badge-amber";
    if (type === "score") return "badge-amber";
    return "badge-muted";
  }

  function formatEventSummary(e) {
    if (e.type === "candidate") {
      const flag = e.bypass ? "⚡ BYPASS CONFIRMED" : e.blocked ? "🛡 BLOCKED" : "passed";
      const ops = (e.operators || []).join(", ") || "none";
      return `Gen ${e.generation} [${e.id}] ${flag} · risk=${e.scan_score} · ops=[${ops}]`;
    }
    if (e.type === "state") {
      return `Phase: ${e.phase || '—'} -> STATE: ${e.state} (Run ${e.run_id || '—'}) ${e.note ? '— ' + e.note : ''}`;
    }
    if (e.type === "policy") {
      return `Policy ${e.policy_id} ${e.applied ? 'APPLIED (idempotent)' : 'DRAFTED'} · target=${e.target || '—'} · destructive=${e.is_destructive}`;
    }
    if (e.type === "verdict") {
      return `VERDICT [Run ${e.run_id}]: ${e.verdict} · armor_blocked=${e.sub_scores?.armor_blocked} · behavior_ok=${e.sub_scores?.behavior_unchanged}`;
    }
    if (e.type === "approval") {
      return `⏸ AWAIT_APPROVAL for Run ${e.run_id} [${e.policy_id}] · ${e.rationale || e.note || 'Approval required'}`;
    }
    if (e.type === "score") {
      return `Score Update: ${e.value}/100 (${e.band?.toUpperCase()}) · bypass=${e.bypass}`;
    }
    if (e.type === "corpus") {
      return `Corpus Memory: Gen ${e.generation} retrieved ancestors [${(e.used_ancestors || []).join(', ')}]`;
    }
    return JSON.stringify(e);
  }
</script>

{#if $eventDrawerOpen}
  <div class="event-drawer">
    <div class="drawer-header">
      <div class="drawer-title">
        <span class="terminal-icon">⌨</span>
        <span class="title-text mono">LIVE EVENT BUS LOG <span class="stream-endpoint">/stream (SSE)</span></span>
        <span class="count-badge mono">{filteredEvents.length} events</span>
      </div>

      <!-- Filters & Search -->
      <div class="drawer-controls">
        <div class="filter-group">
          {#each filters as f}
            <button
              class="filter-btn mono"
              class:active={$eventFilter === f.id}
              on:click={() => eventFilter.set(f.id)}
            >
              {f.label}
            </button>
          {/each}
        </div>

        <input
          type="text"
          class="search-input mono"
          placeholder="Filter event payload / trace ID..."
          bind:value={searchQuery}
        />

        <button
          class="btn btn-sm btn-clear mono"
          on:click={() => events.set([])}
          title="Clear local event buffer"
        >
          CLEAR
        </button>

        <button
          class="btn btn-sm btn-close"
          on:click={() => eventDrawerOpen.set(false)}
          title="Close drawer"
        >
          ✕
        </button>
      </div>
    </div>

    <div class="drawer-body mono">
      {#each filteredEvents as e, i}
        <div
          class="event-row"
          class:expanded={expandedEvent === i}
          on:click={() => toggleExpand(i)}
          on:keydown={(ev) => (ev.key === "Enter" || ev.key === " ") && toggleExpand(i)}
          role="button"
          tabindex="0"
        >
          <div class="event-line">
            <span class="timestamp">{e._t || "—"}</span>
            <span class="badge {getBadgeClass(e.type)}">{e.type.toUpperCase()}</span>
            <span class="event-summary">{formatEventSummary(e)}</span>
            <span class="expand-hint">{expandedEvent === i ? "▲ JSON" : "▼ JSON"}</span>
          </div>

          {#if expandedEvent === i}
            <div class="json-payload">
              <pre>{JSON.stringify(e, null, 2)}</pre>
            </div>
          {/if}
        </div>
      {:else}
        <div class="empty-events muted">
          No events matching filter. Trigger an attack or thin slice to watch events stream in real-time.
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .event-drawer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 290px;
    background: #FFFFFF;
    border-top: 1px solid var(--border);
    box-shadow: 0 -8px 30px rgba(0, 0, 0, 0.12);
    z-index: 90;
    display: flex;
    flex-direction: column;
    animation: slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes slideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }

  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 18px;
    background: var(--bg-subtle);
    border-bottom: 1px solid var(--border);
  }
  .drawer-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .terminal-icon {
    color: var(--oxblood);
  }
  .title-text {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: var(--text);
  }
  .stream-endpoint {
    color: var(--muted);
    font-weight: normal;
  }
  .count-badge {
    background: #FFFFFF;
    color: var(--stone);
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 10px;
    border: 1px solid var(--border);
  }

  .drawer-controls {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .filter-group {
    display: flex;
    background: #FFFFFF;
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 2px;
    gap: 1px;
  }
  .filter-btn {
    background: transparent;
    border: none;
    color: var(--stone);
    font-size: 9.5px;
    padding: 3px 8px;
    border-radius: 3px;
    cursor: pointer;
    font-weight: 700;
    letter-spacing: 0.05em;
  }
  .filter-btn:hover {
    color: var(--text);
  }
  .filter-btn.active {
    background: var(--text);
    color: #FFFFFF;
  }

  .search-input {
    background: #FFFFFF;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 11px;
    width: 220px;
  }

  .btn-clear {
    background: transparent;
    color: var(--stone);
    border: 1px solid var(--border);
  }
  .btn-clear:hover {
    color: var(--oxblood);
    border-color: var(--oxblood);
  }

  .btn-close {
    background: transparent;
    border: none;
    color: var(--stone);
    font-size: 13px;
    cursor: pointer;
    padding: 4px 8px;
  }
  .btn-close:hover {
    color: var(--text);
  }

  .drawer-body {
    flex: 1;
    overflow-y: auto;
    padding: 8px 18px;
    font-size: 11px;
    background: #FFFFFF;
  }

  .event-row {
    padding: 5px 8px;
    border-bottom: 1px solid var(--border-subtle);
    border-radius: 3px;
    cursor: pointer;
    transition: background 0.1s;
  }
  .event-row:hover {
    background: var(--bg-subtle);
  }
  .event-row.expanded {
    background: var(--oxblood-dim);
    border: 1px solid rgba(139, 30, 30, 0.2);
  }

  .event-line {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .timestamp {
    color: var(--muted);
    font-size: 10px;
    min-width: 65px;
  }
  .event-summary {
    color: var(--text);
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .expand-hint {
    color: var(--muted);
    font-size: 10px;
  }

  .json-payload {
    margin-top: 6px;
    padding: 8px 12px;
    background: var(--bg-subtle);
    border: 1px solid var(--border);
    border-radius: 4px;
    overflow-x: auto;
  }
  .json-payload pre {
    color: var(--text);
    font-size: 10.5px;
    margin: 0;
  }

  .empty-events {
    padding: 32px 0;
    text-align: center;
    color: var(--muted);
    font-size: 12px;
  }
</style>

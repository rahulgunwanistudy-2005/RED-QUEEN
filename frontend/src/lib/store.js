import { writable, get, derived } from "svelte/store";

// --- Global Core State ---
export const connected = writable(false);
export const viewMode = writable("landing"); // 'landing' | 'control_plane'
export const activeTab = writable("fleet"); // 'fleet' | 'attacks' | 'remediation' | 'traces'
export const score = writable({ value: null, band: "unknown", bypass: null, attack_class: null });
export const events = writable([]); // Array of raw events { type, ... , _t }
export const health = writable(null);
export const memoryProfile = writable(null);
export const verifierIsolation = writable(null);

// --- Cinematic Timeline & Judge Mode State ---
export const cinematicStep = writable(0); // 0..10 narrative beats
export const cinematicPlaying = writable(false);
export const cinematicProgress = writable(0); // 0..100%
export const judgeMode = writable(false); // Guided Judge Demo Walkthrough
export const judgeStep = writable(0); // 0..8 Demo Stages
export const cinemaMode = writable(false); // 30-40s Fullscreen Video-Like Experience
export const cinemaSpeed = writable(1.0); // 1.0x | 1.5x
export const cinemaElapsed = writable(0); // in seconds

// --- Fleet & Defense Posture ---
export const fleetAgents = writable([]);
export const defensePosture = writable({
  armor_threshold: 0.45,
  baseline_score: 41,
  deep_normalize: false,
  blocklist_count: 0,
  blocklist_hashes: [],
  lowered_threshold: null,
  revoked_tokens: [],
  applied_deltas: [],
});
export const findings = writable([]);
export const gatewayResult = writable(null);
export const gatewayLoading = writable(false);

// --- Attack Engine & Lineage ---
export const lineage = writable({
  attackClass: "prompt_injection",
  nodes: [],
  corpusAncestors: [],
});
export const selectedNode = writable(null);
export const campaignStatus = writable({
  running: false,
  generation: 0,
  maxGen: 6,
  blocked: 0,
  bypassed: 0,
  bestScanScore: 1.0,
  startTime: null,
  elapsedSec: 0,
});
export const corpusStats = writable({
  total_payloads: 0,
  total_bypasses: 0,
  recent_ancestors: [],
});

// --- Multimodal Viewer (SOF-173/176) ---
export const multimodalDemo = writable(null); // {image_b64, overlay_text, carrier_text, extracted_text, text_scan, scan, multimodal_guard_active, agent, bypass}
export const multimodalLoading = writable(false);

// --- Remediation & Verification ---
export const runs = writable({}); // { [run_id]: RunObject }
export const selectedRunId = writable(null);
export const policiesList = writable([]);

// --- Observability & Traces ---
export const traces = writable(null);
export const selectedSpan = writable(null);

// --- Event Stream Drawer Console ---
export const eventDrawerOpen = writable(false);
export const eventFilter = writable("all");

// --- Helper Functions & State Upserts ---
function upsertRun(id, patch) {
  if (id == null) return;
  runs.update((m) => {
    const prev = m[id] || { run_id: id };
    const next = { ...prev, ...patch };
    return { ...m, [id]: next };
  });
}

// --- SSE EventStream Manager ---
let eventSource = null;

export function connectStream() {
  if (eventSource) {
    try {
      eventSource.close();
    } catch {}
  }

  const es = new EventSource("/stream");
  eventSource = es;

  es.onopen = () => {
    connected.set(true);
  };

  es.onmessage = (e) => {
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }

    const timestamp = new Date().toLocaleTimeString();
    events.update((list) => [{ ...data, _t: timestamp, _raw: e.data }, ...list].slice(0, 250));

    // Event Dispatching
    if (data.type === "score") {
      score.set({
        value: data.value,
        band: data.band,
        bypass: data.bypass,
        attack_class: data.attack_class,
      });
      if (data.generation != null) {
        campaignStatus.update((c) => ({ ...c, generation: data.generation }));
      }
    } else if (data.type === "candidate") {
      lineage.update((l) => {
        const fresh = data.generation === 0 || (data.attack_class && data.attack_class !== l.attackClass);
        const prevNodes = fresh ? [] : l.nodes.filter((n) => n.id !== data.id);
        return {
          attackClass: data.attack_class || l.attackClass,
          nodes: [...prevNodes, data],
          corpusAncestors: l.corpusAncestors,
        };
      });

      campaignStatus.update((c) => ({
        ...c,
        generation: Math.max(c.generation, data.generation || 0),
        blocked: c.blocked + (data.blocked ? 1 : 0),
        bypassed: c.bypassed + (data.bypass ? 1 : 0),
        bestScanScore: Math.min(c.bestScanScore, data.scan_score ?? 1.0),
      }));
    } else if (data.type === "corpus") {
      lineage.update((l) => ({
        ...l,
        corpusAncestors: data.used_ancestors || [],
      }));
    } else if (data.type === "state" && data.run_id != null) {
      upsertRun(data.run_id, {
        state: data.state,
        attack_class: data.attack_class,
        note: data.note,
      });
    } else if (data.type === "policy" && data.run_id != null) {
      upsertRun(data.run_id, {
        policy_id: data.policy_id,
        target: data.target,
        is_destructive: data.is_destructive,
        rule: data.rule,
        rationale: data.rationale,
        applied: data.applied || false,
      });
      fetchDefensePosture();
    } else if (data.type === "approval" && data.run_id != null) {
      upsertRun(data.run_id, {
        state: "AWAIT_APPROVAL",
        awaiting: true,
        policy_id: data.policy_id,
        rule: data.rule,
        rationale: data.rationale,
      });
    } else if (data.type === "verdict" && data.run_id != null) {
      upsertRun(data.run_id, {
        verdict: data.verdict,
        sub_scores: data.sub_scores,
        attack_class: data.attack_class,
        policy_id: data.policy_id,
        awaiting: false,
      });
      selectedRunId.set(data.run_id);
      fetchTraces(data.run_id);
      fetchDefensePosture();
      fetchCorpusStats();
    }
  };

  es.onerror = () => {
    connected.set(false);
  };

  return es;
}

// --- API Client Methods ---

export async function fetchFleet() {
  try {
    const res = await fetch("/registry");
    if (!res.ok) throw new Error("Failed to fetch registry");
    const data = await res.json();
    fleetAgents.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return [];
  }
}

export async function fetchHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("Failed to fetch health");
    const data = await res.json();
    health.set(data);
    return data;
  } catch (err) {
    console.error(err);
    health.set({ status: "unreachable", db: false, error: err.message });
    return null;
  }
}

export async function fetchMemoryProfile(agentId = "triage-agent") {
  try {
    const res = await fetch(`/memory/profile?agent_id=${encodeURIComponent(agentId)}`);
    if (!res.ok) throw new Error("Failed to fetch memory profile");
    const data = await res.json();
    memoryProfile.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return null;
  }
}

export async function fetchVerifierIsolation() {
  try {
    const res = await fetch("/verifier/isolation");
    if (!res.ok) throw new Error("Failed to verify isolation");
    const data = await res.json();
    verifierIsolation.set(data);
    return data;
  } catch (err) {
    console.error(err);
    verifierIsolation.set({ ok: false, transcript: [err.message] });
    return null;
  }
}

export async function fetchDefensePosture() {
  try {
    const res = await fetch("/defense/posture");
    if (!res.ok) throw new Error("Failed to fetch defense posture");
    const data = await res.json();
    defensePosture.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return null;
  }
}

export async function fetchFindings() {
  try {
    const res = await fetch("/findings");
    if (!res.ok) throw new Error("Failed to fetch findings");
    const data = await res.json();
    findings.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return [];
  }
}

export async function fetchCorpusStats() {
  try {
    const res = await fetch("/corpus/stats");
    if (!res.ok) throw new Error("Failed to fetch corpus stats");
    const data = await res.json();
    corpusStats.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return null;
  }
}

export async function fetchPolicies() {
  try {
    const res = await fetch("/policies");
    if (!res.ok) throw new Error("Failed to fetch policies");
    const data = await res.json();
    policiesList.set(data);
    return data;
  } catch (err) {
    console.error(err);
    return [];
  }
}

export async function sendGatewayRequest(ticketId, content, authorized = false) {
  gatewayLoading.set(true);
  try {
    const res = await fetch("/gateway/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_id: ticketId, content, authorized }),
    });
    const data = await res.json();
    gatewayResult.set(data);
    return data;
  } catch (err) {
    gatewayResult.set({ error: err.message });
    return null;
  } finally {
    gatewayLoading.set(false);
  }
}

export async function runMultimodalDemo(overlay = null) {
  multimodalLoading.set(true);
  try {
    const res = await fetch("/multimodal/demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(overlay ? { overlay } : {}),
    });
    if (!res.ok) throw new Error("multimodal demo failed");
    const data = await res.json();
    multimodalDemo.set(data);
    return data;
  } catch (err) {
    multimodalDemo.set({ error: err.message });
    return null;
  } finally {
    multimodalLoading.set(false);
  }
}

// Memory-aware full campaign (SOF-174): reads the agent's Memory Bank profile,
// warm-starts from any recalled exploit, harden->verify, updates the profile.
export async function runCampaign({
  attackClass = "prompt_injection",
  seed = 1337,
  remedy = "content",
  useCorpus = true,
  useMemory = true,
  agentId = "triage-agent",
} = {}) {
  campaignStatus.set({
    running: true, generation: 0, maxGen: 6, blocked: 0, bypassed: 0,
    bestScanScore: 1.0, startTime: Date.now(), elapsedSec: 0,
  });
  try {
    const res = await fetch("/harden/campaign", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        attack_class: attackClass, seed: Number(seed), remedy,
        use_corpus: useCorpus, use_memory: useMemory, agent_id: agentId,
      }),
    });
    const data = await res.json();
    if (data.run_id) selectedRunId.set(data.run_id);
    await hydrateRuns();
    await fetchDefensePosture();
    await fetchCorpusStats();
    await fetchMemoryProfile(agentId);
    return data;
  } finally {
    campaignStatus.update((c) => ({ ...c, running: false }));
  }
}

export async function runSlice() {
  const res = await fetch("/slice/run", { method: "POST" });
  const data = await res.json();
  fetchFindings();
  return data;
}

export async function hardenRun({
  attackClass = "prompt_injection",
  seed = 1337,
  remedy = "content",
  useCorpus = true,
} = {}) {
  campaignStatus.set({
    running: true,
    generation: 0,
    maxGen: 6,
    blocked: 0,
    bypassed: 0,
    bestScanScore: 1.0,
    startTime: Date.now(),
    elapsedSec: 0,
  });

  try {
    const res = await fetch("/harden/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        attack_class: attackClass,
        seed: Number(seed),
        remedy,
        use_corpus: useCorpus,
      }),
    });
    const data = await res.json();
    if (data.run_id) {
      selectedRunId.set(data.run_id);
    }
    await hydrateRuns();
    await fetchFindings();
    await fetchDefensePosture();
    await fetchCorpusStats();
    return data;
  } finally {
    campaignStatus.update((c) => ({ ...c, running: false }));
  }
}

export async function approveRun(runId, decision = "approved") {
  const res = await fetch("/harden/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, decision }),
  });
  const data = await res.json();
  await hydrateRuns();
  await fetchDefensePosture();
  if (data.run_id) {
    await fetchTraces(data.run_id);
  }
  return data;
}

export async function fetchTraces(runId) {
  if (!runId) return null;
  try {
    const res = await fetch(`/traces/${runId}`);
    const data = await res.json();
    traces.set(data);
    if (data.spans && data.spans.length > 0) {
      selectedSpan.set(data.spans[0]);
    }
    return data;
  } catch (err) {
    console.error(err);
    traces.set(null);
    return null;
  }
}

export async function hydrateRuns() {
  try {
    const res = await fetch("/harden/runs");
    if (!res.ok) return;
    const rows = await res.json();
    runs.update((m) => {
      const next = { ...m };
      for (const r of rows) {
        next[r.run_id] = {
          ...next[r.run_id],
          ...r,
          awaiting: r.state === "AWAIT_APPROVAL" && (!r.approval || r.approval === "none"),
        };
      }
      return next;
    });

    const currentSelected = get(selectedRunId);
    if (rows.length > 0 && (currentSelected == null || !rows.find((r) => r.run_id === currentSelected))) {
      selectedRunId.set(rows[0].run_id);
      fetchTraces(rows[0].run_id);
    }
  } catch (err) {
    console.error(err);
  }
}

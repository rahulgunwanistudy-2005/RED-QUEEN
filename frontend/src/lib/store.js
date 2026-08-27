import { writable, get } from "svelte/store";

// One store for the whole app. The client models no server internals — it just
// reflects the JSON events arriving on /stream.
export const score = writable({ value: null, band: "unknown", bypass: null });
export const events = writable([]);
export const connected = writable(false);

// Attack-lineage tree (SOF-167): candidate events accumulate into a per-campaign
// node list. A generation-0 candidate (or a switch of attack_class) starts a fresh
// campaign. Pure client state off the existing stream — no new endpoints.
export const lineage = writable({ attackClass: null, nodes: [] });

// M2 (SOF-172): hardening runs keyed by run_id — state, drafted/applied policy, the
// firewalled verifier's verdict + orthogonal sub-scores, and approval status. Fed by
// the state/policy/approval/verdict events on the same stream. `selectedRun` drives
// the trace waterfall; `traces` holds the spans fetched for it.
export const runs = writable({}); // { [run_id]: {...} }
export const selectedRun = writable(null);
export const traces = writable(null);

function upsertRun(id, patch) {
  runs.update((m) => {
    const prev = m[id] || { run_id: id };
    return { ...m, [id]: { ...prev, ...patch } };
  });
}

export function connectStream() {
  const es = new EventSource("/stream");
  es.onopen = () => connected.set(true);
  es.onmessage = (e) => {
    let data;
    try {
      data = JSON.parse(e.data);
    } catch {
      return;
    }
    events.update((list) => [{ ...data, _t: Date.now() }, ...list].slice(0, 100));
    if (data.type === "score") {
      score.set({ value: data.value, band: data.band, bypass: data.bypass });
    } else if (data.type === "candidate") {
      lineage.update((l) => {
        const fresh = data.generation === 0 || data.attack_class !== l.attackClass;
        const nodes = fresh ? [] : l.nodes;
        return { attackClass: data.attack_class, nodes: [...nodes, data] };
      });
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
        applied: data.applied || undefined,
      });
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
      selectedRun.set(data.run_id);
      fetchTraces(data.run_id);
    }
  };
  es.onerror = () => connected.set(false);
  return es;
}

export async function runSlice() {
  const res = await fetch("/slice/run", { method: "POST" });
  return res.json();
}

// --- M2 harden + verify controls (SOF-172) ---------------------------------

export async function hardenRun({ attackClass = "prompt_injection", seed = 1337, remedy = "content" } = {}) {
  const res = await fetch("/harden/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attack_class: attackClass, seed, remedy, use_corpus: true }),
  });
  return res.json();
}

export async function approveRun(runId, decision = "approved") {
  const res = await fetch("/harden/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, decision }),
  });
  return res.json();
}

export async function fetchTraces(runId) {
  try {
    const res = await fetch(`/traces/${runId}`);
    const data = await res.json();
    traces.set(data);
    return data;
  } catch {
    return null;
  }
}

export async function hydrateRuns() {
  try {
    const res = await fetch("/harden/runs");
    const rows = await res.json();
    runs.update((m) => {
      const next = { ...m };
      for (const r of rows) {
        next[r.run_id] = { ...next[r.run_id], ...r, awaiting: r.state === "AWAIT_APPROVAL" };
      }
      return next;
    });
    if (rows.length && get(selectedRun) == null) {
      selectedRun.set(rows[0].run_id);
      fetchTraces(rows[0].run_id);
    }
  } catch {
    /* server not up yet */
  }
}

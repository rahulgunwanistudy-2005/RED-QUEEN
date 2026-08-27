import { writable } from "svelte/store";

// One store for the whole app. The client models no server internals — it just
// reflects the JSON events arriving on /stream.
export const score = writable({ value: null, band: "unknown", bypass: null });
export const events = writable([]);
export const connected = writable(false);

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
    }
  };
  es.onerror = () => connected.set(false);
  return es;
}

export async function runSlice() {
  const res = await fetch("/slice/run", { method: "POST" });
  return res.json();
}

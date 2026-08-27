import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// One app, one stream. The Svelte dev server proxies every backend call to the
// FastAPI control plane (SOF-158/160/161) so the client only ever talks to /.
const API = process.env.SENTINEL_SERVER_URL || "http://localhost:8099";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: Number(process.env.PORT) || 5173,
    proxy: {
      "/health": API,
      "/registry": API,
      "/events": API,
      "/slice": API,
      "/harden": API,
      "/traces": API,
      "/stream": { target: API, changeOrigin: true, ws: false },
    },
  },
});

// The News Universe (docs/decisions/news-map.md, "The universe"): a
// static site. In development, /api/map and /api/account go to the
// backend named by UNIVERSE_BACKEND (the real one, or the preview's stub:
// scripts/preview_universe.py). In production Caddy does the same
// (docker/caddy/Caddyfile), so the pages and the API share one origin and
// the session cookie works as it does on the newsroom's site.
import { defineConfig } from "astro/config";

const backend = process.env.UNIVERSE_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  output: "static",
  server: { port: 4321, host: "127.0.0.1" },
  vite: {
    server: {
      proxy: {
        "/api/map": { target: backend, changeOrigin: true, rewrite: (path) => path.replace(/^\/api\/map/, "/map") },
        "/api/account": { target: backend, changeOrigin: true, rewrite: (path) => path.replace(/^\/api\/account/, "/account") },
      },
    },
  },
});

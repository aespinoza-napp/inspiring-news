/** @type {import('next').NextConfig} */
const nextConfig = {
  // `next build` also writes .next/standalone: a server.js with only the
  // node_modules it traces as used. docker/frontend.Dockerfile ships that
  // and nothing else, so the production image carries no npm and no
  // devDependencies. `npm run dev` is unaffected; `next start` still works
  // but warns that it is not the standalone server.
  output: "standalone",
  // Where the build goes. `.next` everywhere but scripts/e2e.py, which
  // builds into `.next-e2e`: building into `.next` while `npm run dev`
  // served from it replaced the dev server's files under it, and every
  // page then answered 500 ("Cannot find module './1682.js'") until it was
  // restarted (2026-11-03, twice).
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

module.exports = nextConfig;

/** @type {import('next').NextConfig} */
const nextConfig = {
  // `next build` also writes .next/standalone: a server.js with only the
  // node_modules it traces as used. docker/frontend.Dockerfile ships that
  // and nothing else, so the production image carries no npm and no
  // devDependencies. `npm run dev` is unaffected; `next start` still works
  // but warns that it is not the standalone server.
  output: "standalone",
};

module.exports = nextConfig;

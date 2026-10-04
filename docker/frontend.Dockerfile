# Build context is `frontend/` (see docker-compose.prod.yml), so every
# COPY path below is relative to the frontend directory.
#
# Three stages, so the image that runs holds Next's standalone server
# (next.config.js, `output: "standalone"`) and nothing else: no npm, no
# TypeScript, no devDependencies, no source.

# Node 22: the maintenance LTS line. 20, which the dev machine runs,
# left support in April 2026. Next 14.2 needs >= 18.17.
FROM node:22.20-alpine3.22 AS deps

WORKDIR /app

# Its own layer: only re-runs when the lockfile changes. `npm ci`, not
# `install`: the lockfile is the record, and a drifted one should fail
# the build rather than be rewritten inside it.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund


FROM node:22.20-alpine3.22 AS build

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# No BACKEND_URL or STORAGE_API_KEY at build time, on purpose: both are
# read by the server routes at request time (process.env), never inlined.
# Every route that calls the backend is dynamic - it reads the request or
# fetches with cache: "no-store" - so the build never calls it.
RUN npm run build


FROM node:22.20-alpine3.22

WORKDIR /app

# HOSTNAME: Docker sets it to the container id, and the standalone
# server binds to whatever it names - the container's own address, not
# 0.0.0.0, so neither the healthcheck on 127.0.0.1 nor Caddy across the
# compose network would reach it.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# server.js and the traced node_modules, then the static assets, which
# the standalone output deliberately leaves out (a CDN would serve them).
# There is no public/ directory to copy.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static

# The image's own unprivileged user. Nothing here writes outside /app.
USER node

EXPOSE 3000

CMD ["node", "server.js"]

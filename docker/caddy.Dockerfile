# The one door from the internet (docker-compose.gcp.yml): Caddy, with
# the readers' universe built into it (universe/, a static Astro +
# three.js site; docs/decisions/news-map.md, "The universe").
#
# Build context is `universe/`. The site is static: it reads /api/map and
# /api/account from its own origin at run time, which the Caddyfile sends
# to the backend, so nothing here needs the API, a key or the network
# beyond npm. Built on the VM with the rest of the stack ("push, then
# reset the VM"), never pushed to a registry.

FROM node:22.20-alpine3.22 AS universe

WORKDIR /universe

# Dependencies first, so a change to the site alone reuses this layer.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build


FROM caddy:2.10.2

# Read-only for the server: Caddy only serves it (file_server).
COPY --from=universe /universe/dist /srv/universe

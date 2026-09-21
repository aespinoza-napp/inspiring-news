#!/usr/bin/env bash
#
# Brings up the whole app for local development: the docker-compose
# stack (backend, inference, searxng, neo4j) plus the frontend dev
# server. Not part of scripts/check.sh - that's verification, this is
# "I want to click around in the browser."
#
# Usage:
#   ./scripts/dev.sh          bring up docker services + frontend (foreground)
#   ./scripts/dev.sh docker   docker services only, detached
#   ./scripts/dev.sh stop     stop the docker services (frontend is Ctrl+C'd, not this)
#
# What this does NOT start: Ollama. It runs on the host, outside
# compose (see docker/README.md and CLAUDE.md's LLMClient note) - on
# Windows/Mac it's normally already running as a background app once
# installed. This script only checks it's reachable and warns if not.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
TARGET="${1:-all}"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m! %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

check_config() {
  [ -f "$ROOT/backend/.env" ] || die "backend/.env is missing - copy backend/.env-example first, then edit it (see docker/README.md)."
  [ -f "$ROOT/docker/searxng/settings.yml" ] || die "docker/searxng/settings.yml is missing - copy docker/searxng/settings.yml.example first (see docker/README.md)."
}

start_docker() {
  step "Starting docker services (backend, inference, searxng, neo4j)"
  # --build every time, not just on first run: backend/inference have no
  # live source mount, so source is baked into the image at build time.
  # A plain `up -d` silently keeps serving the old image forever once
  # one exists - Docker's layer cache makes a no-op rebuild fast, so
  # this costs seconds, not minutes, when nothing actually changed.
  ( cd "$ROOT" && docker compose --env-file "$ROOT/backend/.env" -f "$COMPOSE_FILE" up -d --build ) || die "docker compose up failed"

  step "Waiting for backend to be healthy"
  # inference's own healthcheck can legitimately take minutes on a cold
  # model-cache volume (first-ever run only) - see docker-compose.yml's
  # comment on the inference service. Everything after that is fast.
  if timeout 600 bash -c 'until curl -sf http://localhost:8000/docs >/dev/null 2>&1; do sleep 2; done'; then
    ok "backend is up (http://localhost:8000)"
  else
    warn "backend did not come up within 10 minutes - check: docker compose --env-file backend/.env -f docker/docker-compose.yml logs backend"
  fi
}

check_ollama() {
  step "Checking Ollama (LLM verification)"
  if curl -sf -m 3 http://localhost:11434/api/version >/dev/null 2>&1; then
    ok "Ollama is reachable on localhost:11434"
  else
    warn "Ollama is not reachable on localhost:11434 - fact-check claims will come back"
    warn "\"LLM verification unavailable\". Install it, then 'ollama pull llama3.1' once."
  fi
}

start_frontend() {
  step "Starting frontend (http://localhost:3000) - Ctrl+C to stop"
  [ -f "$ROOT/frontend/.env.local" ] || warn "frontend/.env.local is missing - copy frontend/.env.local.example first."
  ( cd "$ROOT/frontend" && npm run dev )
}

case "$TARGET" in
  all)
    check_config
    start_docker
    check_ollama
    start_frontend
    ;;
  docker)
    check_config
    start_docker
    check_ollama
    ok "Docker services are up. Run 'cd frontend && npm run dev' separately, or './scripts/dev.sh' for both."
    ;;
  stop)
    step "Stopping docker services"
    ( cd "$ROOT" && docker compose --env-file "$ROOT/backend/.env" -f "$COMPOSE_FILE" down ) || die "docker compose down failed"
    ok "Stopped. (Named volumes - the vector store, cache and lake - are kept; 'docker compose down -v' would delete those too.)"
    ;;
  *)
    echo "Unknown target '$TARGET'. Use: all | docker | stop" >&2
    exit 2
    ;;
esac

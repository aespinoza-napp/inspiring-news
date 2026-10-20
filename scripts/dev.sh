#!/usr/bin/env bash
#
# Brings up the whole app for local development: the docker-compose
# stack (backend, inference, searxng, neo4j) plus the frontend dev
# server. Not part of scripts/check.sh - that's verification, this is
# "I want to click around in the browser."
#
# Usage:
#   ./scripts/dev.sh                 a menu in a terminal (Enter = everything);
#                                    'all' when there is no terminal
#   ./scripts/dev.sh all             docker services + frontend (foreground)
#   ./scripts/dev.sh docker          docker services only, detached
#   ./scripts/dev.sh status          what is running, and whether it answers
#   ./scripts/dev.sh logs [SERVICE]  follow the logs (all services, or one)
#   ./scripts/dev.sh restart [SVC]   rebuild and restart (all, or one)
#   ./scripts/dev.sh init            write .env_global into every component's settings
#   ./scripts/dev.sh stop            stop the docker services (frontend is Ctrl+C'd, not this)
#
# What this does NOT start: Ollama. It runs on the host, outside
# compose (see docker/README.md and CLAUDE.md's LLMClient note) - on
# Windows/Mac it's normally already running as a background app once
# installed. This script only checks it's reachable and warns if not.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
TARGET="${1:-}"
COMPOSE=(docker compose --env-file "$ROOT/backend/.env" -f "$COMPOSE_FILE")

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m! %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

check_config() {
  # Every start: shared values from .env_global into each component's
  # file, secrets generated on first run (scripts/init_env.sh).
  step "Settings from .env_global"
  "$ROOT/scripts/init_env.sh" || die "scripts/init_env.sh failed"
  [ -f "$ROOT/backend/.env" ] || die "backend/.env is missing - copy backend/.env-example first, then edit it (see docker/README.md)."
  grep -Eq '^SEARXNG_SECRET=.+' "$ROOT/backend/.env" || die "backend/.env has no SEARXNG_SECRET - generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" (see docker/README.md)."
}

start_docker() {
  step "Starting docker services (backend, inference, searxng, neo4j)"
  # --build every time, not just on first run: backend/inference have no
  # live source mount, so source is baked into the image at build time.
  # A plain `up -d` silently keeps serving the old image forever once
  # one exists - Docker's layer cache makes a no-op rebuild fast, so
  # this costs seconds, not minutes, when nothing actually changed.
  # Only while that cache survives, though: on 2026-10-09 a no-op
  # rebuild took 291s, because the cache sat at Docker's 20GB cap and
  # had evicted the dependency layers. See docker/README.md's
  # "Slow rebuilds".
  ( cd "$ROOT" && "${COMPOSE[@]}" up -d --build ) || die "docker compose up failed"

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
    warn "\"LLM verification unavailable\". Install it, then 'ollama pull llama3.2:3b' once."
  fi
}

probe() {
  # name, url: one line saying whether it answers.
  if curl -sf -m 3 "$2" >/dev/null 2>&1; then ok "$1  $2"; else warn "$1 not answering  $2"; fi
}

show_status() {
  step "Docker services"
  if [ ! -f "$ROOT/backend/.env" ]; then
    warn "backend/.env is missing - nothing can have been started by this script yet."
  else
    ( cd "$ROOT" && "${COMPOSE[@]}" ps ) || warn "docker compose ps failed - is Docker running?"
  fi
  step "Endpoints"
  probe "backend " http://localhost:8000/docs
  probe "frontend" http://localhost:3000
  probe "neo4j   " http://localhost:7474
  probe "ollama  " http://localhost:11434/api/version
}

show_logs() {
  # Ctrl+C stops following; the services keep running.
  ( cd "$ROOT" && "${COMPOSE[@]}" logs -f --tail 100 ${1:+"$1"} )
}

restart_services() {
  check_config
  step "Rebuilding and restarting ${1:-every service}"
  ( cd "$ROOT" && "${COMPOSE[@]}" up -d --build --force-recreate ${1:+"$1"} ) || die "docker compose up failed"
  ok "Restarted. './scripts/dev.sh status' to check, './scripts/dev.sh logs ${1:-}' to watch."
}

menu() {
  printf '\n\033[1minspiring-news - dev\033[0m\n\n'
  printf '  1) start everything (docker + frontend)   [Enter]\n'
  printf '  2) docker services only (detached)\n'
  printf '  3) status\n'
  printf '  4) logs\n'
  printf '  5) restart a service\n'
  printf '  6) stop docker services\n'
  printf '  7) settings: write .env_global into every component\n'
  printf '  q) quit\n\n'
  read -rp 'Choice: ' choice
  case "${choice:-1}" in
    1) TARGET=all ;;
    2) TARGET=docker ;;
    3) TARGET=status ;;
    4) read -rp 'Service (blank = all: backend, inference, searxng, neo4j): ' SERVICE; TARGET=logs ;;
    5) read -rp 'Service (blank = all: backend, inference, searxng, neo4j): ' SERVICE; TARGET=restart ;;
    6) TARGET=stop ;;
    7) TARGET=init ;;
    q|Q) exit 0 ;;
    *) die "Unknown choice '$choice'" ;;
  esac
}

start_frontend() {
  step "Starting frontend (http://localhost:3000) - Ctrl+C to stop"
  [ -f "$ROOT/frontend/.env.local" ] || warn "frontend/.env.local is missing - copy frontend/.env.local.example first."
  ( cd "$ROOT/frontend" && npm run dev )
}

SERVICE="${2:-}"
if [ -z "$TARGET" ]; then
  if [ -t 0 ]; then menu; else TARGET=all; fi
fi

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
  init)
    "$ROOT/scripts/init_env.sh"
    ;;
  status)
    show_status
    ;;
  logs)
    show_logs "$SERVICE"
    ;;
  restart)
    restart_services "$SERVICE"
    ;;
  stop)
    step "Stopping docker services"
    ( cd "$ROOT" && "${COMPOSE[@]}" down ) || die "docker compose down failed"
    ok "Stopped. (Named volumes - the vector store, cache and lake - are kept; 'docker compose down -v' would delete those too.)"
    ;;
  *)
    echo "Unknown target '$TARGET'. Use: all | docker | init | status | logs [SERVICE] | restart [SERVICE] | stop" >&2
    exit 2
    ;;
esac

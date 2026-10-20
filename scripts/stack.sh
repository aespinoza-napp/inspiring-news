#!/usr/bin/env bash
#
# One machine, several jobs, not enough memory for all of them at once.
# Brings up what one activity needs, stops what it does not, and keeps
# exactly one language model in Ollama's memory - the one the activity
# calls - pulling it first if it is missing.
#
#   ./scripts/stack.sh status            what runs, what is loaded, what is free
#   ./scripts/stack.sh analyse           discover, analyse, follow the Live screen
#   ./scripts/stack.sh write [MODEL]     write, review and rewrite drafts
#   ./scripts/stack.sh eval [MODEL]      the evaluation harness (its own container)
#   ./scripts/stack.sh label             the labeller's Today batch: no model at all
#   ./scripts/stack.sh idle              everything stopped, every model unloaded
#
# What each needs (docs/decisions/deployment.md, "Models in memory"):
#
#   activity  searxng inference neo4j backend  model in Ollama
#   analyse      x        x       x      x     LLM_MODEL (the verifier)
#   write        x        x              x     WRITER_LLM_MODEL, else LLM_MODEL
#   eval         x        x                    MODEL, else LLM_MODEL
#   label        x        x              x     none
#
# The writer does not need the graph, and the harness needs neither the
# graph nor the API: it runs in a one-off container of its own
# (docker-compose.eval.yml). Neo4j holds ~1 GB, inference ~2-5 GB, and a
# 7-9B writer at a 16k context ~6-7 GB - beside a 3B verifier at ~3 GB,
# more than a 16 GB machine has to spare.
#
# Before loading a model the script checks that the host has the model's
# size plus a margin free, and refuses otherwise rather than let the
# operating system swap. Ollama runs on the host here (dev); in
# production it is a container, which unloads the idle model by itself
# (OLLAMA_MAX_LOADED_MODELS=1, docker-compose.prod.yml).
#
# Env: OLLAMA_URL (default: LLM_BASE_URL from backend/.env without /v1,
# with host.docker.internal read as localhost), KEEP_ALIVE (default 30m:
# how long the loaded model stays after its last call), MARGIN_GB (1.5).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"
COMPOSE=(docker compose -f "$ROOT/docker/docker-compose.yml" --env-file "$ENV_FILE")
KEEP_ALIVE="${KEEP_ALIVE:-30m}"
MARGIN_GB="${MARGIN_GB:-1.5}"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
warn() { printf '\033[33m! %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

setting() {
  # The last value backend/.env gives a key, quotes and comments stripped.
  [ -f "$ENV_FILE" ] || return 0
  grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- | sed -e 's/[[:space:]]*#.*$//' -e 's/^"//' -e 's/"$//'
}

ollama_url() {
  if [ -n "${OLLAMA_URL:-}" ]; then echo "$OLLAMA_URL"; return; fi
  local base
  base="$(setting LLM_BASE_URL)"
  base="${base:-http://localhost:11434/v1}"
  base="${base%/}"; base="${base%/v1}"
  echo "${base/host.docker.internal/localhost}"
}

OLLAMA="$(ollama_url)"

# ----------------------------------------------------------------------
# Memory
# ----------------------------------------------------------------------

free_gb() {
  # Memory the host can give a new process without swapping. On Windows,
  # what Docker Desktop's VM took (inference, Neo4j) counts as used even
  # after its containers stop, until `wsl --shutdown`: on 2026-10-19 the
  # guard refused a 3.7 GB writer at 4.8 GB free, rightly.
  # Git Bash on Windows has a /proc/meminfo too, without MemAvailable:
  # MemFree there (what Windows calls free physical memory).
  if [ -r /proc/meminfo ]; then
    awk '/^MemAvailable:/ {a = $2} /^MemFree:/ {f = $2} END {printf "%.1f", (a ? a : f) / 1048576}' /proc/meminfo
  elif command -v powershell >/dev/null 2>&1; then
    powershell -NoProfile -Command \
      "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB, 1)" \
      2>/dev/null | tr -d '\r' | tr ',' '.'
  elif command -v vm_stat >/dev/null 2>&1; then
    vm_stat | awk '/Pages free|Pages inactive/ {gsub(/\./, "", $NF); pages += $NF} END {printf "%.1f", pages * 4096 / 1073741824}'
  else
    echo ""
  fi
}

# ----------------------------------------------------------------------
# Ollama: the native API (the backend speaks its OpenAI one)
# ----------------------------------------------------------------------

ollama_up() { curl -sf -m 3 "$OLLAMA/api/version" >/dev/null; }

# Python on Windows ends its lines with CRLF: a model name read back with
# its "\r" is a model Ollama does not have, so every unload in the first
# trial (2026-10-19) failed and every "already loaded" missed. `tr` strips it.

loaded() {
  # Models in memory now, one per line.
  curl -sf -m 5 "$OLLAMA/api/ps" | python -c \
    "import json,sys; [print(m['name']) for m in json.load(sys.stdin).get('models', [])]" 2>/dev/null \
    | tr -d '\r'
}

size_gb() {
  # A pulled model's size on disk in GB, or nothing when it is not pulled.
  curl -sf -m 5 "$OLLAMA/api/tags" | python -c "
import json, sys
want = sys.argv[1] if ':' in sys.argv[1] else sys.argv[1] + ':latest'
for m in json.load(sys.stdin).get('models', []):
    if m['name'] == want:
        print(round(m['size'] / 1e9, 1))
" "$1" 2>/dev/null | tr -d '\r'
}

unload() {
  # Up to two minutes: a model still answering a call unloads after it.
  # The first trial (2026-10-19) gave this 30 s, met a model Ollama
  # showed as "Stopping..." behind an evaluation run's last call, gave
  # up, and then measured memory the model still held.
  if ! curl -sf -m 120 "$OLLAMA/api/generate" -d "{\"model\": \"$1\", \"keep_alive\": 0}" >/dev/null; then
    warn "could not unload $1"
    return
  fi
  local waited=0
  while loaded | grep -qx -e "$1" -e "$1:latest" && [ $waited -lt 60 ]; do
    sleep 2; waited=$((waited + 2))
  done
  ok "unloaded $1"
}

unload_all_but() {
  local keep="${1:-}" name
  while read -r name; do
    [ -n "$name" ] || continue
    if [ "$name" = "$keep" ] || [ "$name" = "$keep:latest" ]; then continue; fi
    unload "$name"
  done < <(loaded)
}

ensure_model() {
  # Pulled (pulling it if not), the others unloaded, then loaded - if
  # the host has room for it.
  local model="$1" size free need
  ollama_up || die "Ollama does not answer at $OLLAMA - start it (ollama serve, or the desktop app)."

  size="$(size_gb "$model")"
  if [ -z "$size" ]; then
    step "Pulling $model (not on this machine yet)"
    ollama pull "$model" || die "could not pull $model"
    size="$(size_gb "$model")"
  fi

  unload_all_but "$model"

  if loaded | grep -qx -e "$model" -e "$model:latest"; then
    ok "$model already loaded"
    return
  fi

  free="$(free_gb)"
  if [ -n "$free" ] && [ -n "$size" ]; then
    need="$(python -c "print(round($size * 1.2 + $MARGIN_GB, 1))")"
    if python -c "import sys; sys.exit(0 if $free >= $need else 1)"; then
      ok "$free GB free, $model needs ~$need GB"
    else
      die "$model needs ~$need GB and $free GB are free. Stop something first (./scripts/stack.sh idle), or set MARGIN_GB."
    fi
  else
    warn "could not tell how much memory is free; loading $model anyway"
  fi

  step "Loading $model (kept for $KEEP_ALIVE after its last call)"
  curl -sf -m 600 "$OLLAMA/api/generate" -d "{\"model\": \"$model\", \"keep_alive\": \"$KEEP_ALIVE\"}" >/dev/null \
    && ok "$model loaded" || die "Ollama could not load $model"
}

# ----------------------------------------------------------------------
# Containers
# ----------------------------------------------------------------------

services() {
  # Exactly these compose services up, every other one stopped.
  local wanted=("$@") all running svc keep
  mapfile -t all < <("${COMPOSE[@]}" config --services 2>/dev/null)
  for svc in "${all[@]}"; do
    keep=0
    for w in "${wanted[@]}"; do [ "$svc" = "$w" ] && keep=1; done
    if [ $keep = 0 ]; then
      running="$("${COMPOSE[@]}" ps -q "$svc" 2>/dev/null)"
      if [ -n "$running" ]; then
        "${COMPOSE[@]}" stop "$svc" >/dev/null 2>&1 && ok "stopped $svc"
      fi
    fi
  done
  if [ ${#wanted[@]} -gt 0 ]; then
    step "Starting ${wanted[*]}"
    # --no-deps: only what the activity asked for. Until 2026-10-20 the
    # backend depended on neo4j in compose, and a plain `up` started the
    # graph for writing too - the first trial did; that dependency is
    # gone (the graph write is fail-soft), and this keeps any other one
    # from pulling in a service the activity does not need.
    "${COMPOSE[@]}" up -d --no-deps "${wanted[@]}" || die "docker compose up failed"
  fi
}

status() {
  step "Containers"
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null \
    || warn "Docker is not running"
  step "Ollama at $OLLAMA"
  if ollama_up; then
    curl -sf -m 5 "$OLLAMA/api/ps" | python -c "
import json, sys
models = json.load(sys.stdin).get('models', [])
for m in models:
    vram = m.get('size_vram', 0)
    where = 'GPU' if vram and vram >= m['size'] else ('CPU' if not vram else 'GPU+CPU')
    print(f\"  {m['name']}: {m['size'] / 1e9:.1f} GB ({where}), until {m.get('expires_at', '?')[:19]}\")
print('  nothing loaded' if not models else '', end='')
"
  else
    warn "not answering"
  fi
  step "Host"
  echo "  $(free_gb) GB free"
}

# ----------------------------------------------------------------------

[ -f "$ENV_FILE" ] || die "backend/.env is missing - copy backend/.env-example first."

VERIFIER="$(setting LLM_MODEL)"; VERIFIER="${VERIFIER:-llama3.2:3b}"
WRITER="$(setting WRITER_LLM_MODEL)"; WRITER="${WRITER:-$VERIFIER}"

case "${1:-status}" in
  status)
    status ;;
  analyse|analyze)
    services searxng inference neo4j backend
    ensure_model "$VERIFIER"
    status ;;
  write)
    services searxng inference backend
    ensure_model "${2:-$WRITER}"
    status ;;
  eval)
    services searxng inference
    ensure_model "${2:-$VERIFIER}"
    echo
    echo "Then, from docker/: docker compose -f docker-compose.yml -f docker-compose.eval.yml \\"
    echo "  --env-file ../backend/.env run --rm --no-deps -T backend python -m src.evaluation.cli run ..."
    status ;;
  label)
    services searxng inference backend
    if ollama_up; then unload_all_but ""; fi
    status ;;
  idle|stop)
    services
    if ollama_up; then unload_all_but ""; fi
    status ;;
  *)
    sed -n '2,20p' "$0"; exit 2 ;;
esac

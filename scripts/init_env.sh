#!/usr/bin/env bash
#
# Sets up every component's settings from one file, .env_global.
#
#   ./scripts/init_env.sh
#
# 1. Creates .env_global from .env_global.example if it is missing.
# 2. Fills NEO4J_PASSWORD and SEARXNG_SECRET if they are empty - from an
#    existing backend/.env, else newly generated - and writes them back
#    into .env_global so reruns keep the same value.
# 3. Creates backend/.env and frontend/.env.local from their examples if
#    missing, then sets only the shared keys in them. Other lines - the
#    thresholds, anything edited by hand - are left as they are.
#
# Safe to run any number of times; ./scripts/dev.sh runs it on every
# start. awk rather than sed -i or python: it behaves the same on Linux,
# macOS and Git Bash on Windows.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL="$ROOT/.env_global"
BACKEND_ENV="$ROOT/backend/.env"
FRONTEND_ENV="$ROOT/frontend/.env.local"

warn() { printf '\033[33m! %s\033[0m\n' "$1"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

# The last value a file gives a key, quotes and trailing comments stripped
# (the same reading as scripts/stack.sh's `setting`).
get_key() {
  [ -f "$1" ] || return 0
  grep -E "^$2=" "$1" | tail -1 | cut -d= -f2- | sed -e 's/[[:space:]]*#.*$//' -e 's/^"//' -e 's/"$//'
}

# set_key FILE KEY VALUE: replace every active KEY= line; failing that,
# uncomment the first "# KEY=" line in its place; failing that, append.
# The value goes through ENVIRON, not -v, so backslashes stay literal.
set_key() {
  local file="$1" key="$2" tmp
  tmp="$(mktemp)"
  K="$key" V="$3" awk '
    BEGIN { k = ENVIRON["K"]; v = ENVIRON["V"]; done = 0 }
    { lines[NR] = $0 }
    index($0, k "=") == 1 { lines[NR] = k "=" v; done = 1 }
    END {
      if (!done) {
        for (i = 1; i <= NR; i++) {
          if (lines[i] ~ "^#[[:space:]]*" k "=") { lines[i] = k "=" v; done = 1; break }
        }
      }
      for (i = 1; i <= NR; i++) print lines[i]
      if (!done) print k "=" v
    }
  ' "$file" > "$tmp" && cat "$tmp" > "$file"
  rm -f "$tmp"
}

# unset_key FILE KEY: comment out every active KEY= line. For keys where
# an empty value is wrong rather than "off" - an empty STORAGE_API_KEY
# matches no request at all (backend/.env-example).
unset_key() {
  local file="$1" tmp
  tmp="$(mktemp)"
  K="$2" awk 'index($0, ENVIRON["K"] "=") == 1 { $0 = "# " $0 } { print }' "$file" > "$tmp" && cat "$tmp" > "$file"
  rm -f "$tmp"
}

# set_or_unset FILE KEY VALUE: empty means "not set" for optional keys.
set_or_unset() {
  if [ -n "$3" ]; then set_key "$1" "$2" "$3"; else unset_key "$1" "$2"; fi
}

new_secret() {
  # 32 random bytes as hex; od and /dev/urandom exist everywhere bash does.
  head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
}

# ----------------------------------------------------------------------
# 1-2. The global file and its secrets
# ----------------------------------------------------------------------

if [ ! -f "$GLOBAL" ]; then
  cp "$ROOT/.env_global.example" "$GLOBAL" || die "could not create .env_global"
  ok "created .env_global from .env_global.example"
fi

for key in NEO4J_PASSWORD SEARXNG_SECRET; do
  # An existing backend/.env wins over a new secret: its Neo4j volume was
  # created with that password, and would refuse a fresh one.
  existing="$(get_key "$BACKEND_ENV" "$key")"
  if [ -z "$(get_key "$GLOBAL" "$key")" ] && [ -n "$existing" ]; then
    set_key "$GLOBAL" "$key" "$existing"
    ok "kept $key from backend/.env (saved in .env_global)"
  elif [ -z "$(get_key "$GLOBAL" "$key")" ]; then
    set_key "$GLOBAL" "$key" "$(new_secret)"
    ok "generated $key (saved in .env_global)"
  fi
done

NEO4J_PASSWORD="$(get_key "$GLOBAL" NEO4J_PASSWORD)"
SEARXNG_SECRET="$(get_key "$GLOBAL" SEARXNG_SECRET)"
STORAGE_API_KEY="$(get_key "$GLOBAL" STORAGE_API_KEY)"
BACKEND_URL="$(get_key "$GLOBAL" BACKEND_URL)"
LLM_BASE_URL="$(get_key "$GLOBAL" LLM_BASE_URL)"
LLM_API_KEY="$(get_key "$GLOBAL" LLM_API_KEY)"
LLM_MODEL="$(get_key "$GLOBAL" LLM_MODEL)"
WRITER_LLM_MODEL="$(get_key "$GLOBAL" WRITER_LLM_MODEL)"
CORRECTOR_LLM_MODEL="$(get_key "$GLOBAL" CORRECTOR_LLM_MODEL)"

# ----------------------------------------------------------------------
# 3. The component files
# ----------------------------------------------------------------------

if [ ! -f "$BACKEND_ENV" ]; then
  cp "$ROOT/backend/.env-example" "$BACKEND_ENV" || die "could not create backend/.env"
  ok "created backend/.env from backend/.env-example"
else
  # Neo4j keeps the password it was created with; a new one here would
  # only lock the backend out of an existing database.
  old="$(get_key "$BACKEND_ENV" NEO4J_PASSWORD)"
  if [ -n "$old" ] && [ "$old" != "$NEO4J_PASSWORD" ]; then
    warn "NEO4J_PASSWORD changes from what backend/.env had. An existing neo4j-data volume"
    warn "keeps the old one: recreate the volume, or put the old value in .env_global."
  fi
fi

set_key      "$BACKEND_ENV" NEO4J_PASSWORD  "$NEO4J_PASSWORD"
set_key      "$BACKEND_ENV" SEARXNG_SECRET  "$SEARXNG_SECRET"
set_or_unset "$BACKEND_ENV" STORAGE_API_KEY "$STORAGE_API_KEY"
[ -n "$LLM_BASE_URL" ] && set_key "$BACKEND_ENV" LLM_BASE_URL "$LLM_BASE_URL"
[ -n "$LLM_API_KEY" ]  && set_key "$BACKEND_ENV" LLM_API_KEY  "$LLM_API_KEY"
[ -n "$LLM_MODEL" ]    && set_key "$BACKEND_ENV" LLM_MODEL    "$LLM_MODEL"
set_or_unset "$BACKEND_ENV" WRITER_LLM_MODEL    "$WRITER_LLM_MODEL"
set_or_unset "$BACKEND_ENV" CORRECTOR_LLM_MODEL "$CORRECTOR_LLM_MODEL"
ok "backend/.env is up to date"

if [ ! -f "$FRONTEND_ENV" ]; then
  cp "$ROOT/frontend/.env.local.example" "$FRONTEND_ENV" || die "could not create frontend/.env.local"
  ok "created frontend/.env.local from frontend/.env.local.example"
fi

[ -n "$BACKEND_URL" ] && set_key "$FRONTEND_ENV" BACKEND_URL "$BACKEND_URL"
set_or_unset "$FRONTEND_ENV" STORAGE_API_KEY "$STORAGE_API_KEY"
ok "frontend/.env.local is up to date"

# The labeller reads its settings from the environment, not a file.
if [ -n "$STORAGE_API_KEY" ]; then
  warn "The labeller needs the key in its environment: STORAGE_API_KEY=... python labeller/app.py"
fi

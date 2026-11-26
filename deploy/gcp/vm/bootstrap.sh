#!/usr/bin/env bash
# Brings the production stack up on a Google Cloud VM. Run as root by the
# instance's startup script (deploy/gcp/startup.sh.tftpl) on every boot,
# after it has cloned or updated the repository - so this must be safe to
# run again on a machine where it already ran.
#
#   bootstrap.sh              install, render backend/.env, start the stack
#   bootstrap.sh render-env F write the .env alone, to F (what
#                             ./scripts/check.sh gcp tests against Floci)
#
# Configuration comes from the environment the startup script sets:
#   PROJECT_ID       the Google Cloud project holding the secrets
#   SECRET_PREFIX    prefix of the four secrets' names (Terraform's `name`)
#   LLM_MODEL        the Ollama model to pull and verify with
#   SITE_ADDRESS     Caddy's site address: a domain, or ":80" without one
#   UNIVERSE_ADDRESS the universe's site address: a domain, an sslip.io
#                    name, or http://<ip>
#   STACK            "full" (everything, the local LLM included) or "lite"
#                    (the universe and /discover, Groq as the LLM:
#                    docker/docker-compose.lite.yml)
#   SEED_BUCKET      the bucket scripts/gcp_seed.sh uploads to; on a
#                    first boot, its seed fills the graph, the lake and
#                    the photos before the stack starts
#   SECRET_MANAGER_ENDPOINT  default https://secretmanager.googleapis.com;
#                    the emulator's address under test
#   SECRET_MANAGER_TOKEN     skips the metadata server (the emulator
#                    accepts anything)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SECRET_MANAGER_ENDPOINT="${SECRET_MANAGER_ENDPOINT:-https://secretmanager.googleapis.com}"
STORAGE_ENDPOINT="${STORAGE_ENDPOINT:-https://storage.googleapis.com}"
STACK="${STACK:-full}"
METADATA="http://metadata.google.internal/computeMetadata/v1"

log() { echo "[bootstrap] $*"; }

token() {
  if [ -n "${SECRET_MANAGER_TOKEN:-}" ]; then
    echo "$SECRET_MANAGER_TOKEN"
    return
  fi
  # The VM's own service account, which Terraform granted
  # secretAccessor on exactly these secrets and nothing else.
  curl -fsS -H "Metadata-Flavor: Google" "$METADATA/instance/service-accounts/default/token" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
}

# A secret's latest version, decoded. REST rather than gcloud: the same
# call then works against Floci in the check, where gcloud is not around.
secret() {
  curl -fsS -H "Authorization: Bearer $(token)" \
    "$SECRET_MANAGER_ENDPOINT/v1/projects/$PROJECT_ID/secrets/$SECRET_PREFIX-$1/versions/latest:access" \
    | python3 -c 'import base64, json, sys; print(base64.b64decode(json.load(sys.stdin)["payload"]["data"]).decode())'
}

# One that may not exist: Groq's key is created only when given
# (deploy/gcp/main.tf). Empty when it is not there.
optional_secret() {
  secret "$1" 2>/dev/null || true
}

# backend/.env from the committed example, with the secrets and the
# deployment's own values replacing whatever the example says. The
# example's other values are the defaults the stack was measured with.
render_env() {
  local out="$1"
  local keys="NEO4J_PASSWORD|SEARXNG_SECRET|STORAGE_API_KEY|SITE_PASSWORD_HASH|LLM_MODEL|SITE_ADDRESS|UNIVERSE_ADDRESS|GROQ_API_KEY|GRAPH_ENABLED|LAKE_ENABLED"

  local neo4j searxng storage site_hash groq
  neo4j="$(secret neo4j-password)"
  searxng="$(secret searxng-secret)"
  storage="$(secret storage-api-key)"
  site_hash="$(secret site-password-hash)"
  groq="$(optional_secret groq-api-key)"

  umask 077
  {
    grep -Ev "^($keys)=" "$REPO_DIR/backend/.env-example"
    echo
    echo "# Rendered by deploy/gcp/vm/bootstrap.sh from Secret Manager - edits are overwritten on boot."
    echo "NEO4J_PASSWORD=$neo4j"
    echo "SEARXNG_SECRET=$searxng"
    echo "STORAGE_API_KEY=$storage"
    # Single-quoted: a bcrypt hash is full of `$`, and compose expands
    # `$x` in an unquoted .env value - the hash Caddy got would be
    # mangled, and no password would ever match it.
    echo "SITE_PASSWORD_HASH='$site_hash'"
    echo "LLM_MODEL=${LLM_MODEL:?LLM_MODEL is not set}"
    echo "SITE_ADDRESS=${SITE_ADDRESS:-:80}"
    echo "UNIVERSE_ADDRESS=${UNIVERSE_ADDRESS:-http://universe.invalid}"
    # Groq first (src/services/llms.py); with the lite stack, Groq alone.
    if [ -n "$groq" ]; then
      echo "GROQ_API_KEY=$groq"
    fi
    echo "GRAPH_ENABLED=true"
    echo "LAKE_ENABLED=true"
  } > "$out.tmp"
  mv "$out.tmp" "$out"
}

install_docker() {
  if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    return
  fi
  log "installing Docker Engine and the compose plugin"
  apt-get update -q
  apt-get install -y -q ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_ops_agent() {
  if ! systemctl list-unit-files google-cloud-ops-agent.service >/dev/null 2>&1 \
     || ! systemctl is-enabled google-cloud-ops-agent >/dev/null 2>&1; then
    log "installing the Ops Agent"
    curl -fsSL https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh -o /tmp/add-ops-agent-repo.sh
    bash /tmp/add-ops-agent-repo.sh --also-install
  fi
  # Ours replaces the default: container logs with the backend's JSON
  # parsed into fields, and /metrics into Cloud Monitoring.
  if ! cmp -s "$REPO_DIR/deploy/gcp/vm/ops-agent.yaml" /etc/google-cloud-ops-agent/config.yaml; then
    cp "$REPO_DIR/deploy/gcp/vm/ops-agent.yaml" /etc/google-cloud-ops-agent/config.yaml
    systemctl restart google-cloud-ops-agent
  fi
}

compose() {
  cd "$REPO_DIR/docker"
  local files=(-f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gcp.yml)
  if [ "$STACK" = "lite" ]; then
    files+=(-f docker-compose.lite.yml)
  fi
  # -p: a fixed project name, so volume names do not depend on the
  # checkout's directory name.
  docker compose -p inspiring-news "${files[@]}" --env-file ../backend/.env "$@"
}

# ---------------------------------------------------------------------
# The seed: what a new VM starts from instead of an empty graph and lake
# (scripts/gcp_seed.sh uploads it from the dev machine). The universe
# shows the graph's articles with the import's photos, and /discover
# carries on with the judgements, rounds and feedback the lake holds.
#
# Restored only into what does not exist yet - a volume that compose has
# not created, a photo folder with nothing in it - so a seed uploaded
# after the stack ran can never overwrite what the VM itself wrote.
# ---------------------------------------------------------------------

PROJECT=inspiring-news

# One object of the seed bucket, through Cloud Storage's JSON API with
# the VM's token (objectViewer on that bucket only), into a file.
object() {
  local name
  name="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=""))' "$1")"
  curl -fsS -H "Authorization: Bearer $(token)" \
    "$STORAGE_ENDPOINT/storage/v1/b/$SEED_BUCKET/o/$name?alt=media" -o "$2"
}

# A volume as compose would have made it: with its labels, compose
# takes it as its own instead of warning that it was created outside.
new_volume() {
  docker volume create --label "com.docker.compose.project=$PROJECT" \
    --label "com.docker.compose.volume=$1" "${PROJECT}_$1" >/dev/null
}

has_volume() {
  docker volume inspect "${PROJECT}_$1" >/dev/null 2>&1
}

seed() {
  if [ -z "${SEED_BUCKET:-}" ]; then
    return
  fi

  local dir manifest
  dir="$(mktemp -d)"
  manifest="$dir/manifest.json"

  if ! object seed/manifest.json "$manifest" 2>/dev/null; then
    log "no seed in gs://$SEED_BUCKET (scripts/gcp_seed.sh): the graph and the lake start empty"
    rm -rf "$dir"
    return
  fi

  field() { python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$manifest" "$1"; }

  if ! has_volume neo4j-data; then
    log "seed: the graph, from $(field createdAt)"
    mkdir -p "$dir/dump"
    object "$(field neo4j)" "$dir/dump/neo4j.dump"
    new_volume neo4j-data
    # The image the stack runs (docker-compose.yml), so the dump is loaded
    # by the version that will open it. Its entrypoint owns /data for the
    # neo4j user before it runs the command.
    # A load that fails takes its volume with it, so the next boot tries
    # again instead of finding a volume and starting an empty graph.
    docker run --rm -v "${PROJECT}_neo4j-data:/data" -v "$dir/dump:/dumps:ro" neo4j:5 \
      neo4j-admin database load neo4j --from-path=/dumps --overwrite-destination=true \
      || { docker volume rm "${PROJECT}_neo4j-data" >/dev/null; exit 1; }
  fi

  if ! has_volume backend-data; then
    log "seed: the lake, the vector store and the drafts"
    object "$(field backend)" "$dir/backend-data.tar.gz"
    new_volume backend-data
    docker run --rm -v "${PROJECT}_backend-data:/data" -v "$dir:/seed:ro" alpine:3.20 \
      tar -xzf /seed/backend-data.tar.gz --numeric-owner -C /data \
      || { docker volume rm "${PROJECT}_backend-data" >/dev/null; exit 1; }
  fi

  # The import's photos: a bind mount of the checkout (docker-compose.yml),
  # gitignored, so a fresh clone has an empty folder there.
  local photos
  photos="$REPO_DIR/$(field photosPath)"
  case "$photos" in
    "$REPO_DIR"/backend/data/imports/*) ;;
    *) log "seed: photosPath is not under backend/data/imports - not restored"; photos="" ;;
  esac
  if [ -n "$photos" ] && [ -z "$(ls -A "$photos" 2>/dev/null)" ]; then
    log "seed: the universe's photos"
    object "$(field photos)" "$dir/map-images.tar.gz"
    mkdir -p "$photos"
    tar -xzf "$dir/map-images.tar.gz" -C "$photos"
  fi

  rm -rf "$dir"
}

up() {
  compose up -d --build --remove-orphans
}

# What a person following the first boot needs next, at the end of the
# journal: which containers are up, and where the site is.
summary() {
  compose ps --format 'table {{.Service}}\t{{.Status}}'
  if [ "${SITE_ADDRESS:-:80}" = ":80" ]; then
    log "no domain: only http://<external_ip>/healthz and /reader are public; the rest of the UI is behind 'terraform output ui_tunnel'"
  else
    log "site: https://$SITE_ADDRESS/ (user editor, 'terraform output -raw site_password'); health: https://$SITE_ADDRESS/healthz"
  fi
  case "${UNIVERSE_ADDRESS:-}" in
    ""|http://universe.invalid) ;;
    http://*) log "universe: $UNIVERSE_ADDRESS/ (plain HTTP: readers can browse, not sign in)" ;;
    *) log "universe: https://$UNIVERSE_ADDRESS/" ;;
  esac
}

case "${1:-}" in
  render-env)
    render_env "${2:?usage: bootstrap.sh render-env <file>}"
    ;;
  "")
    install_docker
    install_ops_agent
    log "rendering backend/.env from Secret Manager"
    render_env "$REPO_DIR/backend/.env"
    seed
    log "starting the $STACK stack (the first boot builds the images and downloads the models: ~10GB with the local LLM, ~7GB without)"
    up
    summary
    log "done"
    ;;
  *)
    echo "usage: bootstrap.sh [render-env <file>]" >&2
    exit 2
    ;;
esac

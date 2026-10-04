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
#   SECRET_MANAGER_ENDPOINT  default https://secretmanager.googleapis.com;
#                    the emulator's address under test
#   SECRET_MANAGER_TOKEN     skips the metadata server (the emulator
#                    accepts anything)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SECRET_MANAGER_ENDPOINT="${SECRET_MANAGER_ENDPOINT:-https://secretmanager.googleapis.com}"
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

# backend/.env from the committed example, with the secrets and the
# deployment's own values replacing whatever the example says. The
# example's other values are the defaults the stack was measured with.
render_env() {
  local out="$1"
  local keys="NEO4J_PASSWORD|SEARXNG_SECRET|STORAGE_API_KEY|SITE_PASSWORD_HASH|LLM_MODEL|SITE_ADDRESS|GRAPH_ENABLED|LAKE_ENABLED"

  local neo4j searxng storage site_hash
  neo4j="$(secret neo4j-password)"
  searxng="$(secret searxng-secret)"
  storage="$(secret storage-api-key)"
  site_hash="$(secret site-password-hash)"

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
  # -p: a fixed project name, so volume names do not depend on the
  # checkout's directory name.
  docker compose -p inspiring-news \
    -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gcp.yml \
    --env-file ../backend/.env "$@"
}

up() {
  compose up -d --build --remove-orphans
}

# What a person following the first boot needs next, at the end of the
# journal: which containers are up, and where the site is.
summary() {
  compose ps --format 'table {{.Service}}\t{{.Status}}'
  if [ "${SITE_ADDRESS:-:80}" = ":80" ]; then
    log "no domain: only http://<external_ip>/healthz is public; the UI is behind 'terraform output ui_tunnel'"
  else
    log "site: https://$SITE_ADDRESS/ (user editor, 'terraform output -raw site_password'); health: https://$SITE_ADDRESS/healthz"
  fi
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
    log "starting the stack (the first boot builds the images and downloads ~10GB of models)"
    up
    summary
    log "done"
    ;;
  *)
    echo "usage: bootstrap.sh [render-env <file>]" >&2
    exit 2
    ;;
esac

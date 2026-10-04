#!/usr/bin/env bash
#
# The Google Cloud deployment, checked without a Google Cloud account:
# `./scripts/check.sh gcp` runs this. Needs Docker and nothing else -
# Terraform and the emulator run in containers.
#
# 1. The three compose files merge (base + prod + gcp).
# 2. deploy/gcp applies to Floci (floci-gcp, a local Google Cloud
#    emulator: https://floci.io) - every API call Terraform makes, with
#    the provider real deploys use.
# 3. The VM's bootstrap renders backend/.env from the secrets Terraform
#    just created, through Secret Manager's REST API, and the key it gets
#    is the key Terraform generated.
# 4. A second plan is empty: what was applied is what the code says.
# 5. Everything is destroyed again.
#
# What it cannot check: Floci manages VMs but runs no guest, so whether
# the VM boots, installs Docker and starts the stack is only known on a
# real one (docs/decisions/deployment.md, "What Floci does not prove").

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Pinned. Compute Engine is only in floci-gcp's nightlies so far (the
# 0.9.0 release has none); bump to a release once one carries it.
FLOCI_IMAGE="floci/floci-gcp:nightly-09302026"
TERRAFORM_IMAGE="hashicorp/terraform:1.16"

RUN_ID="inspiring-gcp-check-$$"
NETWORK="$RUN_ID"
FLOCI="$RUN_ID-floci"

# Docker Desktop on Windows needs a Windows path for a bind mount, and
# Git Bash must not rewrite the container-side paths.
export MSYS_NO_PATHCONV=1
host_path() { (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

cleanup() {
  docker rm -f "$FLOCI" >/dev/null 2>&1 || true
  docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "-- compose: base + prod + gcp merge"
(
  # A copy of docker/ beside a throwaway backend/.env: only that the three
  # files merge is checked, and compose reads the backend's env_file
  # whether or not it is asked to - which would make this check depend
  # on whoever runs it having one.
  scratch="$(mktemp -d)"
  cp -r "$ROOT/docker" "$scratch/docker"
  mkdir -p "$scratch/backend"
  # The hash in the form bootstrap.sh writes it: single-quoted, so the
  # `$`s survive compose's interpolation. Unquoted, compose reads
  # `$abc...` as a variable and Caddy gets "$2a$10" (tried 2026-10-02).
  # `config` prints a literal `$` as `$$`, its own escape.
  hash='$2a$10$abcdefghijklmnopqrstuuJ8GzbS7m0r0b3RqnSPdnqN0mE3JbV0G'
  printf "NEO4J_PASSWORD=x\nSEARXNG_SECRET=x\nSTORAGE_API_KEY=x\nLLM_MODEL=x\nSITE_PASSWORD_HASH='%s'\n" "$hash" > "$scratch/backend/.env"
  cd "$scratch/docker"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gcp.yml \
    --env-file ../backend/.env config > "$scratch/merged.yml"
  escaped="$(printf '%s' "$hash" | sed 's/\$/$$/g')"
  grep -qF "SITE_PASSWORD_HASH: $escaped" "$scratch/merged.yml" \
    && ! grep "SITE_PASSWORD_HASH:" "$scratch/merged.yml" | grep -vqF "$escaped" \
    || { echo "compose mangled SITE_PASSWORD_HASH on its way to Caddy"; exit 1; }
  echo "merged; Caddy gets the password hash intact"
  rm -rf "$scratch"
)

echo "-- starting $FLOCI_IMAGE"
docker network create "$NETWORK" >/dev/null
docker run -d --name "$FLOCI" --network "$NETWORK" --network-alias floci-gcp \
  -e FLOCI_GCP_SERVICES_COMPUTE_REGIONS=europe-southwest1,europe-west1 \
  "$FLOCI_IMAGE" >/dev/null

echo "-- terraform against the emulator"
docker run --rm --network "$NETWORK" \
  -v "$(host_path "$ROOT")":/repo:ro \
  -v inspiring-tf-plugins:/plugins -e TF_PLUGIN_CACHE_DIR=/plugins \
  -e GOOGLE_OAUTH_ACCESS_TOKEN=floci \
  --entrypoint sh "$TERRAFORM_IMAGE" -euc '
    apk add -q bash curl python3 py3-bcrypt >/dev/null

    # A copy: init writes .terraform/ and the state next to the module,
    # and the checkout is mounted read-only.
    cp -r /repo/deploy/gcp /work && cd /work

    terraform fmt -check -recursive
    terraform init -input=false -no-color >/dev/null
    terraform validate -no-color
    terraform apply -auto-approve -input=false -no-color -var-file=emulator.tfvars >/dev/null
    echo "applied: $(terraform state list | wc -l) resources"

    # The VM side, against the secrets that now exist.
    mkdir -p /tmp/repo/backend
    cp -r /repo/deploy /tmp/repo/deploy
    cp /repo/backend/.env-example /tmp/repo/backend/
    # The VM clones on Linux and gets LF; a Windows checkout from before
    # .gitattributes pinned *.sh to LF hands this container CRLF, which
    # bash here rejects on line one.
    tr -d "\r" < /repo/deploy/gcp/vm/bootstrap.sh > /tmp/repo/deploy/gcp/vm/bootstrap.sh
    PROJECT_ID=floci-local SECRET_PREFIX=inspiring-news LLM_MODEL=llama3.2:3b SITE_ADDRESS=:80 \
    SECRET_MANAGER_ENDPOINT=http://floci-gcp:4588 SECRET_MANAGER_TOKEN=floci \
      bash /tmp/repo/deploy/gcp/vm/bootstrap.sh render-env /tmp/rendered.env

    rendered="$(grep "^STORAGE_API_KEY=" /tmp/rendered.env | cut -d= -f2-)"
    [ "$rendered" = "$(terraform output -raw storage_api_key)" ] \
      || { echo "rendered STORAGE_API_KEY is not the one Terraform generated"; exit 1; }
    for key in NEO4J_PASSWORD SEARXNG_SECRET STORAGE_API_KEY SITE_PASSWORD_HASH; do
      [ "$(grep -c "^$key=." /tmp/rendered.env)" = 1 ] || { echo "$key missing or repeated"; exit 1; }
    done

    # The hash the VM renders accepts the password Terraform hands the
    # person (terraform output site_password) - the one check that the
    # site can be logged into at all, short of a real VM. No single
    # quote in the Python: this whole script is one single-quoted string.
    SITE_PASSWORD="$(terraform output -raw site_password)" python3 -c "
import bcrypt, os
quote = chr(39)
line = [l.rstrip() for l in open(\"/tmp/rendered.env\") if l.startswith(\"SITE_PASSWORD_HASH=\")][0]
value = line.split(\"=\", 1)[1]
assert value[0] == quote == value[-1], \"SITE_PASSWORD_HASH is not single-quoted: compose would expand its dollar signs\"
assert bcrypt.checkpw(os.environ[\"SITE_PASSWORD\"].encode(), value[1:-1].encode()), \"the rendered hash does not accept site_password\"
"
    echo "rendered backend/.env: secrets match, the site password opens the rendered hash"

    # 0: no changes. 2 would mean the emulator handed back something the
    # code does not describe - drift a real apply would show too.
    terraform plan -detailed-exitcode -input=false -no-color -var-file=emulator.tfvars >/dev/null
    echo "second plan: no changes"

    terraform destroy -auto-approve -input=false -no-color -var-file=emulator.tfvars >/dev/null
    echo "destroyed"
  '

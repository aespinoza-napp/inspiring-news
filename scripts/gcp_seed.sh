#!/usr/bin/env bash
#
# The seed a new Google Cloud VM starts from, made from this machine's
# Docker stack and uploaded to the deployment's private bucket. The VM's
# first boot restores it before the stack starts (deploy/gcp/vm/bootstrap.sh,
# seed), so the universe opens on the graph's articles with their photos
# and /discover carries on with the rounds, judgements and feedback the lake
# holds - instead of an empty graph and an empty lake.
#
#   ./scripts/gcp_seed.sh <bucket>          build it and upload it
#                                           (terraform output -raw seed_bucket)
#   ./scripts/gcp_seed.sh --local <dir>     build it into <dir>, upload nothing
#
# What goes in:
#
#   neo4j.dump            the positive graph (neo4j-admin database dump)
#   backend-data.tar.gz   from the backend's volume: the lake (records, rounds,
#                         judgements, feedback, journal), the vector store, the
#                         drafts and the imports' snapshots - not the analysis
#                         cache, and not users.db: readers' accounts on this
#                         machine are test accounts, never deployed
#   map-images.tar.gz     the WordPress import's photos (gitignored; the
#                         universe serves them)
#   manifest.json         what the VM reads first: names, sizes, sha256, when
#
# Neo4j and the backend are stopped while they are copied - a dump needs the
# database closed, and the lake and the vector store are copied as they are on
# disk - and started again after, if they were running. Needs Docker, and for
# an upload gcloud signed in (`gcloud auth login`).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The dev stack's compose project: docker/docker-compose.yml, run from docker/.
PROJECT="${LOCAL_PROJECT:-docker}"

# Where docker-compose.yml mounts the photos from (/app/data/map-images).
# backend/tests/test_deployment_config.py holds the two together.
PHOTOS_PATH="backend/data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images"

# The backend volume's folders that are the record. The rest is a cache,
# local accounts, or a mount point the VM fills from git.
BACKEND_KEEP="lake vector_db drafts imports"

log() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

BUCKET=""
OUT=""

case "${1:-}" in
  --local) OUT="${2:?usage: gcp_seed.sh --local <dir>}" ;;
  ""|-h|--help) sed -n '3,30p' "$0"; exit 2 ;;
  *) BUCKET="$1" ;;
esac

if [ -n "$BUCKET" ]; then
  command -v gcloud >/dev/null || die "gcloud is not installed: https://cloud.google.com/sdk/docs/install"
  OUT="$(mktemp -d)"
  trap 'rm -rf "$OUT"' EXIT
fi

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

for volume in neo4j-data backend-data; do
  docker volume inspect "${PROJECT}_$volume" >/dev/null 2>&1 \
    || die "no volume ${PROJECT}_$volume: is this the machine whose stack holds the data? (LOCAL_PROJECT=...)"
done

[ -n "$(ls -A "$ROOT/$PHOTOS_PATH" 2>/dev/null)" ] \
  || die "no photos in $PHOTOS_PATH: python3 scripts/wordpress_images.py <the export's .xml>"

# Stopped while copied, and started again whatever happens after.
stopped=()
restart() {
  if [ ${#stopped[@]} -gt 0 ]; then
    log "starting ${stopped[*]} again"
    docker start "${stopped[@]}" >/dev/null
  fi
}
trap 'restart; [ -z "$BUCKET" ] || rm -rf "$OUT"' EXIT

for service in neo4j backend; do
  container="$(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$service")"
  if [ -n "$container" ]; then
    log "stopping $service while it is copied"
    # Two minutes, not docker's 10 s: Neo4j killed before its clean
    # shutdown leaves an active transaction log, and the dump refuses it
    # ("Active logical log detected", tried 2026-11-26).
    docker stop --time 120 "$container" >/dev/null
    stopped+=("$container")
  fi
done

log "the graph: neo4j-admin database dump"
# The neo4j user inside the image writes the dump into this folder.
chmod 0777 "$OUT"
docker run --rm -v "${PROJECT}_neo4j-data:/data" -v "$OUT:/dumps" neo4j:5 \
  neo4j-admin database dump neo4j --to-path=/dumps --overwrite-destination=true

log "the backend's record: $BACKEND_KEEP"
docker run --rm -v "${PROJECT}_backend-data:/data:ro" -v "$OUT:/out" alpine:3.20 sh -c '
  cd /data
  keep=""
  for folder in '"$BACKEND_KEEP"'; do [ -e "$folder" ] && keep="$keep $folder"; done
  tar -czf /out/backend-data.tar.gz --numeric-owner $keep
'

restart
stopped=()

log "the photos: $PHOTOS_PATH"
tar -czf "$OUT/map-images.tar.gz" -C "$ROOT/$PHOTOS_PATH" .

revision="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
python3 - "$OUT" "$PHOTOS_PATH" "$revision" <<'PY'
import hashlib, json, os, sys
from datetime import datetime, timezone

out, photos_path, revision = sys.argv[1:]

def entry(name):
    path = os.path.join(out, name)
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return {"object": f"seed/{name}", "bytes": os.path.getsize(path), "sha256": digest.hexdigest()}

files = {key: entry(name) for key, name in (("neo4j", "neo4j.dump"), ("backend", "backend-data.tar.gz"), ("photos", "map-images.tar.gz"))}

manifest = {
    "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "codeRevision": revision,
    # What bootstrap.sh reads: each part's object, and where the photos go.
    "neo4j": files["neo4j"]["object"],
    "backend": files["backend"]["object"],
    "photos": files["photos"]["object"],
    "photosPath": photos_path,
    "files": files,
}

with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=1)

for key, item in files.items():
    print(f"  {item['object']:<28} {item['bytes'] / 1e6:8.1f} MB")
PY

if [ -z "$BUCKET" ]; then
  log "built in $OUT; nothing uploaded"
  exit 0
fi

log "uploading to gs://$BUCKET/seed/"
# The manifest last: until it is there, a booting VM sees no seed rather
# than half of one.
gcloud storage cp "$OUT/neo4j.dump" "$OUT/backend-data.tar.gz" "$OUT/map-images.tar.gz" "gs://$BUCKET/seed/"
gcloud storage cp "$OUT/manifest.json" "gs://$BUCKET/seed/manifest.json"

log "done: a VM booting for the first time restores it before the stack starts"

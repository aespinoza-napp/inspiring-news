#!/usr/bin/env bash
#
# The whole pipeline in AVeriTeC's web condition, one run per switch that
# changes what is searched (docs/decisions/evaluation.md, "One benchmark for
# every approach"; experiments/averitec/protocol.md, "web").
#
#   ./scripts/bench_averitec_web.sh N [N ...]      e.g. 10, or 10 20 30 40
#
# The first N claims of the balanced dev sample, the verifier comparison's
# claims (scripts/bench_averitec_verifiers.sh), with the 3B and live SearXNG
# through the temporal gate. Four plans: plain (averitec_web.json),
# restatement (averitec_web_restatement.json), the checkable plan and
# questions. For each N the four run one after another, so they search at
# about the same hour, and they share one search cache, so a query two plans
# both ask gets the same answer (SearXNG answers identical queries
# differently run to run). Each run resumes: give ten new claims at a time.
#
# Two searched runs still differ by the web: compare plans on the same
# claims and say so. A run counts only if its report's temporal audit says
# Held. Search with today's engines (docker/searxng/settings.yml, changed
# 23 Nov): no searched run from before compares.
#
# Needs SearXNG on :8080 (the dev stack), inference/ on the host and Ollama.

set -uo pipefail

[[ $# -ge 1 ]] || { echo "usage: bench_averitec_web.sh N [N ...]" >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

DATA=data/evaluation/averitec/averitec_dev_balanced.jsonl
TH=data/evaluation/thresholds
CACHE=data/evaluation/experiments/averitec/searches-dev-balanced.jsonl
LOGS=data/evaluation/experiments/averitec/logs-web-balanced
mkdir -p "$LOGS"

# Restatement off unless the plan's file turns it on (backend/.env has it on).
export CLAIM_RESTATEMENT=off CLAIM_MAX_CONCURRENCY=2 INFERENCE_TIMEOUT=120
export INFERENCE_URL="${INFERENCE_URL:-http://localhost:8001}"
export LLM_BASE_URL=http://localhost:11434/v1 LLM_TIMEOUT=180 LLM_MAX_CONCURRENCY=1

curl -s -m 20 -o /dev/null "http://localhost:8080/search?q=test&format=json" || {
  echo "SearXNG is not answering on :8080" >&2
  exit 1
}

for N in "$@"; do
  for plan in web web_restatement web_checkable web_questions; do
    echo "== $plan, first $N claims, $(date -Is), load $(cut -d' ' -f1-3 /proc/loadavg)"
    uv run python -m src.evaluation.cli run --dataset "$DATA" --thresholds "$TH/averitec_$plan.json" \
      --label web-gate --search-cache "$CACHE" --model llama3.2:3b-bench --limit "$N" \
      2>&1 | tee -a "$LOGS/$plan.log"
  done
done

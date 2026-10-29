#!/usr/bin/env bash
#
# The verifier on Groq's hosted models, on the same evidence as the local
# ones: each replays the searched baseline (cli run --replay), so its
# verdicts pair claim by claim with bench_models.sh's.
#
#   ./scripts/bench_groq.sh [BASELINE_RUN_DIR] [LIMIT]
#
# BASELINE_RUN_DIR defaults to the newest llama3.2:3b-bench run that kept
# its evidence; LIMIT to all 69 train claims (no screen first: on the free
# plan a run costs nothing, only ~40 minutes of its rate limit).
#
# Which models (29 Oct 2026, from the key's own /models listing): the
# three the developer key reaches that judge text. llama-3.1-8b-instant
# and llama-3.3-70b-versatile ("Contact Sales") answer model_not_found;
# whisper, orpheus and the prompt guards are not language models for this;
# gpt-oss-safeguard-20b classifies against a safety policy; allam-2-7b is
# Arabic first.
#
#   openai/gpt-oss-120b   Apache 2.0, reasons by default (Groq: medium)
#   openai/gpt-oss-20b    Apache 2.0; ~13 GB at MXFP4, so the one of the
#                         three this laptop could also serve itself
#   qwen/qwen3.8-27b      preview: may be withdrawn at short notice
#
# What leaves the machine: each claim and the text of its evidence pages,
# all of them public web pages, to api.groq.com.
#
# Not run beside bench_models.sh: the ranker still embeds every source in
# the local inference/ (bge-m3 on this CPU), and every local model's time
# would then include it.
#
# Env: GROQ_API_KEY (default: read from .env_global at the repo root).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$ROOT/backend/data/evaluation/experiments/models/logs}"
MODELS=(openai/gpt-oss-120b openai/gpt-oss-20b qwen/qwen3.8-27b)

if [[ -z "${GROQ_API_KEY:-}" ]]; then
  GROQ_API_KEY="$(grep '^GROQ_API_KEY=' "$ROOT/.env_global" | cut -d= -f2- | tr -d '"')"
fi
[[ -n "$GROQ_API_KEY" ]] || { echo "no GROQ_API_KEY in the environment or .env_global" >&2; exit 1; }

# The provider is configuration, never a flag (cli.py): base URL and key.
export LLM_BASE_URL=https://api.groq.com/openai/v1
export LLM_API_KEY="$GROQ_API_KEY"
# gpt-oss cannot be told not to think; "low" is its least, the nearest to
# the local models' thinking off. Its reasoning counts against max_tokens,
# and at the per-source verifier's 160 it came back empty 9 calls in 20
# even at "low" (2026-10-29): LLM_REASONING_TOKENS gives it room above
# every cap. qwen3.8-27b answered without reasoning tokens.
export LLM_REASONING_EFFORT='{"openai/gpt-oss-120b":"low","openai/gpt-oss-20b":"low"}'
export LLM_REASONING_TOKENS='{"openai/gpt-oss-120b":2048,"openai/gpt-oss-20b":2048}'
# The key is on Groq's free plan (no card): 1,000 requests a day and
# 8,000 tokens a minute per model, read from its x-ratelimit headers on
# 29 Oct; a claim is ~3,500 tokens. One claim and one call at a time, and
# what still meets the limit waits out its retry-after (LLMClient), so a
# run is ~35-45 min a model rather than 10, and loses no source to it.
export LLM_MAX_CONCURRENCY=1
export LLM_TIMEOUT=180
export INFERENCE_TIMEOUT=120
export CLAIM_MAX_CONCURRENCY=1
export INFERENCE_URL="${INFERENCE_URL:-http://localhost:8001}"

cd "$ROOT/backend"
mkdir -p "$LOG_DIR"

baseline="${1:-}"
if [[ -z "$baseline" ]]; then
  baseline="$(dirname "$(ls -t data/evaluation/runs/manual-train/llama3.2-3b-bench/*/evidence.jsonl | head -1)")"
fi
limit="${2:-69}"

curl -s -m 5 -o /dev/null "$INFERENCE_URL/" || {
  echo "inference/ is not answering at $INFERENCE_URL: cd inference && uv run uvicorn src.main:app --port 8001" >&2
  exit 1
}

for m in "${MODELS[@]}"; do
  printf '\n\033[1m==> verifier %s (Groq): replaying %s, first %s train claims\033[0m\n' "$m" "$baseline" "$limit"
  uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train \
    --model "$m" --replay "$baseline" --limit "$limit" 2>&1 | tee "$LOG_DIR/verifier-groq-${m//\//-}.log" || true
done

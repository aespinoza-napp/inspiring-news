#!/usr/bin/env bash
#
# Every verifier on AVeriTeC's balanced dev sample, on fixed evidence
# (docs/decisions/evaluation.md, "One benchmark for every approach").
#
#   ./scripts/bench_averitec_verifiers.sh N [GROQ_MODEL]
#
# The first N claims of averitec_dev_balanced.jsonl (labels interleaved, so
# any N is balanced). The 3B's knowledge-store run makes the evidence;
# MiniCheck, the 9B and one Groq model replay it, so the four differ by their
# reading alone. Each run resumes, so N=20 after N=10 adds ten claims: the
# author's rule is ten new claims at a time (experiments/averitec/protocol.md).
#
# On the claims both have, the store run gives back 49e4c76106c6's evidence
# and verdicts (9 of 9 on 23 Nov): the store is fixed and BM25 deterministic.
#
# Restatement off for all four (backend/.env turns it on for the app): the
# protocol judges the claim's text alone. One claim and one call at a time.
# GROQ_MODEL defaults to openai/gpt-oss-120b, chosen by the 23 Nov screen
# (experiments/models/results.md); Groq runs on the free plan only.
#
# Needs inference/ on the host (cd inference && uv run uvicorn src.main:app
# --port 8001; it serves MiniCheck's /grounding), Ollama with the -bench
# copies, and GROQ_API_KEY in .env_global. Seconds are only comparable on a
# quiet machine: check uptime first, and don't run check.sh beside it.

set -uo pipefail

N="${1:?usage: bench_averitec_verifiers.sh N [GROQ_MODEL]}"
GROQ_MODEL="${2:-openai/gpt-oss-120b}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

DATA=data/evaluation/averitec/averitec_dev_balanced.jsonl
STORE=data/evaluation/averitec/raw/dev_knowledge_store.zip
TH=data/evaluation/thresholds
LOGS=data/evaluation/experiments/verifier/logs-balanced
mkdir -p "$LOGS"

export CLAIM_RESTATEMENT=off CLAIM_MAX_CONCURRENCY=1 INFERENCE_TIMEOUT=120
export INFERENCE_URL="${INFERENCE_URL:-http://localhost:8001}"
local_llm=(env LLM_BASE_URL=http://localhost:11434/v1 LLM_TIMEOUT=180 LLM_MAX_CONCURRENCY=1)
cli=(uv run python -m src.evaluation.cli)

curl -s -m 5 -o /dev/null "$INFERENCE_URL/" || {
  echo "inference/ is not answering at $INFERENCE_URL" >&2
  exit 1
}
echo "start $(date -Is): load $(cut -d' ' -f1-3 /proc/loadavg)"

step_log="$(mktemp)"
"${local_llm[@]}" "${cli[@]}" run --dataset "$DATA" --knowledge-store "$STORE" \
  --thresholds "$TH/averitec_store.json" --model llama3.2:3b-bench --label knowledge-store --limit "$N" \
  2>&1 | tee "$step_log" | tee -a "$LOGS/3b-store.log"
BASE="$(grep -o 'in data/evaluation/runs/[^ ]*' "$step_log" | tail -1 | cut -c4-)"
rm -f "$step_log"
[[ -n "$BASE" && -f "$BASE/evidence.jsonl" ]] || { echo "no evidence from the store run" >&2; exit 1; }
echo "evidence: $BASE"

"${local_llm[@]}" "${cli[@]}" run --dataset "$DATA" --replay "$BASE" \
  --thresholds "$TH/averitec_store_minicheck.json" --model minicheck-ft5 --label replay-store --limit "$N" \
  2>&1 | tee -a "$LOGS/minicheck.log"

# Thinking off, as scripts/bench_models.sh runs it. Without it the 9B spent
# all 160 tokens of every per-source answer reasoning and answered nothing:
# 35 of 35 calls cut, every verdict invalid (23 Nov, the first try).
"${local_llm[@]}" LLM_REASONING_EFFORT='{"qwen3.5:9b-bench":"none"}' "${cli[@]}" run --dataset "$DATA" --replay "$BASE" \
  --thresholds "$TH/averitec_store.json" --model qwen3.5:9b-bench --label replay-store --limit "$N" \
  2>&1 | tee -a "$LOGS/9b.log"

# Groq: the settings scripts/bench_groq.sh uses (gpt-oss reasons at "low",
# with room above every answer cap; rate limits are waited out).
key="$(grep '^GROQ_API_KEY=' "$ROOT/.env_global" | cut -d= -f2- | tr -d '"')"
[[ -n "$key" ]] || { echo "no GROQ_API_KEY in .env_global" >&2; exit 1; }
env LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_API_KEY="$key" LLM_TIMEOUT=180 LLM_MAX_CONCURRENCY=1 \
  LLM_REASONING_EFFORT='{"openai/gpt-oss-120b":"low","openai/gpt-oss-20b":"low"}' \
  LLM_REASONING_TOKENS='{"openai/gpt-oss-120b":2048,"openai/gpt-oss-20b":2048}' \
  "${cli[@]}" run --dataset "$DATA" --replay "$BASE" \
  --thresholds "$TH/averitec_store.json" --model "$GROQ_MODEL" --label replay-store --limit "$N" \
  2>&1 | tee -a "$LOGS/groq-${GROQ_MODEL//\//-}.log"

echo "end $(date -Is): load $(cut -d' ' -f1-3 /proc/loadavg)"

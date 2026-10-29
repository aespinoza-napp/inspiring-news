#!/usr/bin/env bash
#
# The model benchmark of 29 Oct 2026: every role's candidates, from the
# models this machine has pulled, one after another.
#
#   ./scripts/bench_models.sh all                  everything below, in order
#   ./scripts/bench_models.sh models               create the -bench copies
#   ./scripts/bench_models.sh baseline             the searched 3B run the verifiers replay
#   ./scripts/bench_models.sh verifier BASELINE_RUN_DIR [LIMIT]
#   ./scripts/bench_models.sh writer
#   ./scripts/bench_models.sh reviewer
#
# Which models, and why the others are left out, was agreed before any
# result was read (docs/decisions/evaluation.md, "Choosing the models"):
#
#   verifier  llama3.2:3b (baseline) qwen3.5:9b granite3.3:8b gemma4:e4b
#   writer    qwen3.5:4b (baseline)  qwen3.5:9b qwen3:8b gemma4:e4b
#   reviewer  qwen3.5:9b (baseline)  llama3.2:3b granite3.3:8b phi4-mini gemma4:e4b
#
# Every model is served as a "-bench" copy (same weights, no download):
# 10 threads, because Ollama's default spreads over the 165U's two
# low-power cores and halves the answer speed (performance.md, section 5),
# and a 16k context, because the CPU's default 4k silently cuts a writer's
# or reviewer's prompt (writing.md, "The model"). The run directories say
# -bench, so a time measured here is never mistaken for one at defaults.
#
# One at a time, on purpose, though the laptop has 62 GB: memory is not
# what limits it. Answering is bound by memory bandwidth and the 15 W
# package, so two models at once each run at about half speed - no
# wall-clock gain - and every time recorded becomes the other model's
# waiting too (evaluation.md: the first 3B runs, 133 s a claim, shared the
# CPU with another run and are not quoted).
#
# The verifier is compared on fixed evidence: each candidate replays
# BASELINE_RUN_DIR's retrieval (cli run --replay), so only the reading
# differs. LIMIT (default 20) screens on the first train claims; run it
# again without a limit, or with 69, and the same run resumes.
#
# Env: LOG_DIR (default: backend/data/evaluation/experiments/models/logs).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$ROOT/backend/data/evaluation/experiments/models/logs}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"

VERIFIERS=(qwen3.5:9b granite3.3:8b gemma4:e4b)
WRITERS=(qwen3.5:4b qwen3.5:9b qwen3:8b gemma4:e4b)
REVIEWERS=(qwen3.5:9b llama3.2:3b granite3.3:8b phi4-mini:latest gemma4:e4b)
ALL=(llama3.2:3b qwen3.5:4b qwen3.5:9b qwen3:8b granite3.3:8b gemma4:e4b phi4-mini:latest)

# llama3.2:3b -> llama3.2:3b-bench; phi4-mini:latest -> phi4-mini:bench
bench_name() {
  local base="${1%%:*}" tag="${1#*:}"
  if [[ "$tag" == latest ]]; then echo "$base:bench"; else echo "$base:$tag-bench"; fi
}

# Production's LLM limits (docker-compose.eval.yml), with a timeout an 8B
# answer on this CPU fits in: a timed-out call is a lost verdict, not a
# slow one. Thinking off for every model that thinks (Qwen3, Qwen3.5 and
# Gemma 4; checked 29 Oct: no reasoning tokens with "none").
export LLM_TIMEOUT="${LLM_TIMEOUT:-600}"
export LLM_MAX_CONCURRENCY=1
export INFERENCE_TIMEOUT=120
export CLAIM_MAX_CONCURRENCY=2
export INFERENCE_URL="${INFERENCE_URL:-http://localhost:8001}"
efforts=""
for m in qwen3.5:4b qwen3.5:9b qwen3:8b gemma4:e4b; do
  efforts+="\"$(bench_name "$m")\":\"none\","
done
export LLM_REASONING_EFFORT="{${efforts%,}}"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# A loaded model holds memory but no CPU; unloading between models keeps
# the next one's first call from sharing the machine with a dying one.
unload() { curl -s "$OLLAMA_URL/api/generate" -d "{\"model\":\"$1\",\"keep_alive\":0}" >/dev/null || true; }

require_pulled() {
  if ! ollama list | awk 'NR>1 {print $1}' | grep -qx "$1"; then
    echo "skipped: $1 is not pulled on this machine" >&2
    return 1
  fi
}

mkdir -p "$LOG_DIR"
cd "$ROOT/backend"

# The harness on the host needs both: compose does not publish
# inference's port, and the eval container cannot reach a host Ollama that
# listens on 127.0.0.1 only.
require_services() {
  curl -s -m 5 -o /dev/null "$INFERENCE_URL/" || {
    echo "inference/ is not answering at $INFERENCE_URL:" >&2
    echo "  cd inference && uv run uvicorn src.main:app --port 8001" >&2
    exit 1
  }
  curl -sf -m 20 -o /dev/null "http://localhost:8080/search?q=test&format=json" || {
    echo "SearXNG is not answering at localhost:8080:" >&2
    echo "  docker compose -f docker/docker-compose.yml --env-file backend/.env up -d searxng" >&2
    exit 1
  }
}

BASELINE_MODEL="$(bench_name llama3.2:3b)"

# The run key is the same for the same settings, so a second call resumes
# the first instead of searching again.
baseline_run() {
  require_services
  step "baseline $BASELINE_MODEL: searching, all 69 train claims"
  uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train \
    --model "$BASELINE_MODEL" 2>&1 | tee -a "$LOG_DIR/baseline-$BASELINE_MODEL.log"
  unload "$BASELINE_MODEL"
}

baseline_dir() {
  local file
  file="$(ls -t data/evaluation/runs/manual-train/"${BASELINE_MODEL/:/-}"/*/evidence.jsonl | head -1)"
  dirname "$file"
}

case "${1:-}" in
  all)
    "$ROOT/scripts/bench_models.sh" models
    baseline_run
    # Not with set -e's abort: a phase that fails leaves the next to run.
    "$ROOT/scripts/bench_models.sh" verifier "$(baseline_dir)" "${2:-20}" || true
    "$ROOT/scripts/bench_models.sh" writer || true
    "$ROOT/scripts/bench_models.sh" reviewer || true ;;

  baseline)
    baseline_run ;;

  models)
    dir="$(mktemp -d)"
    for m in "${ALL[@]}"; do
      require_pulled "$m" || continue
      printf 'FROM %s\nPARAMETER num_thread 10\nPARAMETER num_ctx 16384\n' "$m" > "$dir/Modelfile"
      ollama create "$(bench_name "$m")" -f "$dir/Modelfile" >/dev/null && echo "created $(bench_name "$m")"
    done
    rm -rf "$dir" ;;

  verifier)
    baseline="${2:?the searched baseline run directory, with its evidence.jsonl}"
    limit="${3:-20}"
    require_services
    for m in "${VERIFIERS[@]}"; do
      require_pulled "$m" || continue
      b="$(bench_name "$m")"
      step "verifier $b: replaying $baseline, first $limit train claims"
      uv run python -m src.evaluation.cli run --dataset data/evaluation/manual --split train \
        --model "$b" --replay "$baseline" --limit "$limit" 2>&1 | tee "$LOG_DIR/verifier-$b.log"
      unload "$b"
    done ;;

  writer)
    for m in "${WRITERS[@]}"; do
      require_pulled "$m" || continue
      b="$(bench_name "$m")"
      step "writer $b: one draft in en, es and ca"
      # Nothing of it is stored by the script itself: the log is the record.
      uv run python ../scripts/try_writer_model.py --model "$b" \
        --language en --language es --language ca 2>&1 | tee "$LOG_DIR/writer-$b.log"
      unload "$b"
    done ;;

  reviewer)
    for m in "${REVIEWERS[@]}"; do
      require_pulled "$m" || continue
      b="$(bench_name "$m")"
      # The planted-defect benchmark first: it holds the 95% format gate,
      # so a model that fails it is read as failing before the drafts.
      step "reviewer $b: the writing benchmark (planted defects)"
      uv run python -m src.evaluation.cli writing run --model "$b" 2>&1 | tee "$LOG_DIR/writing-$b.log"
      step "reviewer $b: the seeded drafts"
      uv run python ../scripts/try_reviewer_model.py --model "$b" \
        --json "$LOG_DIR/reviewer-$b.json" 2>&1 | tee "$LOG_DIR/reviewer-$b.log"
      unload "$b"
    done ;;

  *)
    sed -n '2,40p' "$ROOT/scripts/bench_models.sh"; exit 2 ;;
esac

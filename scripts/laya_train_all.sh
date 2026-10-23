#!/usr/bin/env bash
# Fine-tune Laya on every decision that has labels here, then answer each
# decision's test set with the result and score it. The settings are the
# rule's (backend/data/evaluation/experiments/laya/rule.md, "The training
# settings"); change them there first, not only here.
#
#   ./scripts/laya_train_all.sh [decision ...]     # default: all three
#
# CPU-heavy for hours: do not run it beside an evaluation run whose
# response times are being measured.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAYA="$ROOT/backend/data/evaluation/experiments/laya"
CHECKPOINTS="$ROOT/inference/checkpoints"
DECISIONS=("${@:-worth_offering topic_group checkable_claim}")

for decision in ${DECISIONS[@]}; do
  extra=()
  [ "$decision" = "topic_group" ] && extra+=(--shuffle-options)

  echo "==> $decision: training"
  (cd "$ROOT/inference" && uv run laya-train \
      --data "$LAYA/data/${decision}_train.jsonl" \
      --base multilingual --loss rlcd \
      --epochs 8 --micro-batch 8 --grad-accum 2 --seed 0 --device cpu \
      "${extra[@]}" \
      --out "$CHECKPOINTS/$decision")

  echo "==> $decision: answering the test set"
  (cd "$ROOT/inference" && uv run python -m src.decisions predict \
      --checkpoint "$decision" \
      --data "$LAYA/data/${decision}_test.jsonl" \
      --out "$LAYA/predictions/${decision}_finetuned.jsonl")

  echo "==> $decision: score"
  (cd "$ROOT/backend" && uv run python -m src.evaluation.decisions score \
      --decision "$decision" \
      --predictions "$LAYA/predictions/${decision}_finetuned.jsonl" \
      | tee "$LAYA/predictions/${decision}_finetuned.score.json")
done

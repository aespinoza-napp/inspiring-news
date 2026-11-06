#!/usr/bin/env bash
# The fact-checker, part by part, against Claude's own blind checks.
# A thin wrapper over backend/src/evaluation/troubleshoot.py, run from anywhere:
#
#   ./scripts/troubleshoot.sh prepare --batch 20261105-next20            # claims 21-40 of the train run, blind
#   ./scripts/troubleshoot.sh agent   --batch 20261105-next20 --stage 01 --dry-run   # see the claude commands first
#   ./scripts/troubleshoot.sh agent   --batch 20261105-next20 --stage 01            # plan (blind) -> numbers -> analysis
#   ./scripts/troubleshoot.sh agent   --batch 20261105-next20 --stage 01 --implement
#   ./scripts/troubleshoot.sh status  --batch 20261105-next20
#   ./scripts/troubleshoot.sh all     --batch 20261105-next20            # stages 01-05 in order, analysis only
#   ./scripts/troubleshoot.sh preflight                                  # cost and services, before anything else
#   ./scripts/troubleshoot.sh loop    --batch 20261105-next20 --holdout 20261105-hold20 --stage 01   # rounds until nothing improves
#
# docs/troubleshooting/fact-checking/README.md ("Running it") explains each step.
set -euo pipefail

cd "$(dirname "$0")/../backend"

if [[ "${1:-}" == "all" ]]; then
  shift
  for stage in 01 02 03 04 05; do
    uv run python -m src.evaluation.troubleshoot agent --stage "$stage" "$@"
  done
  exit 0
fi

exec uv run python -m src.evaluation.troubleshoot "$@"

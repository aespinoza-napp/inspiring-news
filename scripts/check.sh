#!/usr/bin/env bash
#
# The one verification command. `make check`, or ./scripts/check.sh.
#
# It exists so nobody - human or agent - has to rediscover that the slow
# model-stack tests are excluded by a registered `slow` marker (not a
# flag to remember), that a growing set of backend tests need the
# inference/ service reachable and skip - rather than fail - when it
# isn't (see backend/tests/conftest.py's require_inference), or that the
# frontend is typechecked from a different directory.
#
# One command means one habit and one unambiguous answer to "am I done".
#
# Usage:
#   ./scripts/check.sh            backend + inference + frontend
#   ./scripts/check.sh fast       invariants only - seconds, no models
#   ./scripts/check.sh backend    backend only
#   ./scripts/check.sh inference  inference only - real models, no mocks
#   ./scripts/check.sh frontend   frontend only
#   ./scripts/check.sh labeller   the fact labeller - stdlib only, no venv
#   ./scripts/check.sh slow       the slow model-stack tests, only
#   ./scripts/check.sh graph      the graph against a real Neo4j - fails,
#                                 not skips, when it is not running
#   ./scripts/check.sh gcp        the Google Cloud deployment against Floci,
#                                 a local emulator - needs Docker only

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

# The `slow` marker is excluded by pyproject's addopts, so no flag to
# remember here. `./scripts/check.sh slow` runs those instead.
PYTEST_ARGS=(-q)

failures=0

step() {
  printf '\n\033[1m==> %s\033[0m\n' "$1"
}

fail() {
  printf '\033[31m✗ %s\033[0m\n' "$1"
  failures=$((failures + 1))
}

pass() {
  printf '\033[32m✓ %s\033[0m\n' "$1"
}

run_fast() {
  step "Invariants (the rules from CLAUDE.md, as tests)"
  if (cd "$ROOT/backend" && uv run pytest tests/test_invariants.py -q); then
    pass "invariants"
  else
    fail "invariants"
  fi
}

run_backend() {
  step "Backend tests"
  if (cd "$ROOT/backend" && uv run pytest "${PYTEST_ARGS[@]}"); then
    pass "backend tests"
  else
    fail "backend tests"
  fi
}

run_slow() {
  step "Slow tests (full model stack over data/raw)"
  if (cd "$ROOT/backend" && uv run pytest -m slow -q); then
    pass "slow tests"
  else
    fail "slow tests"
  fi
}

# Not part of `all`, like `slow`: it needs a running Neo4j, and a check
# that fails on every machine without one trains people to ignore it.
# Asked for explicitly, a missing Neo4j is a failure - the old
# test_connection.py skipped, so it passed whether a database existed or
# not.
run_graph() {
  step "Graph tests (a real Neo4j at NEO4J_URI)"
  if (cd "$ROOT/backend" && uv run pytest -m neo4j -q); then
    pass "graph tests"
  else
    fail "graph tests"
  fi
}

# Not part of `all` either: it needs Docker and pulls two images. The
# Terraform in deploy/gcp/ applied to Floci (a local Google Cloud
# emulator), the VM's .env rendered from the secrets it created, then
# destroyed. See deploy/gcp/emulator-check.sh for what it cannot prove.
run_gcp() {
  step "Google Cloud deployment against Floci (deploy/gcp/)"
  if "$ROOT/deploy/gcp/emulator-check.sh"; then
    pass "gcp deployment (emulated)"
  else
    fail "gcp deployment (emulated)"
  fi
}

run_inference() {
  step "Inference service tests (real models, no mocks)"
  if (cd "$ROOT/inference" && uv run pytest -q); then
    pass "inference tests"
  else
    fail "inference tests"
  fi
}

run_frontend() {
  step "Frontend typecheck"
  if (cd "$ROOT/frontend" && npx tsc --noEmit); then
    pass "frontend typecheck"
  else
    fail "frontend typecheck"
  fi
}

# Plain `python`, not uv: the labeller has no dependencies on purpose, so
# the test must not lean on a virtualenv either.
run_labeller() {
  step "Fact labeller tests (standard library only)"
  if (cd "$ROOT" && python -m unittest -q labeller/test_app.py); then
    pass "labeller tests"
  else
    fail "labeller tests"
  fi
}

case "$TARGET" in
  fast)      run_fast ;;
  slow)      run_slow ;;
  graph)     run_graph ;;
  gcp)       run_gcp ;;
  backend)   run_backend ;;
  inference) run_inference ;;
  frontend)  run_frontend ;;
  labeller)  run_labeller ;;
  all)       run_backend; run_inference; run_frontend; run_labeller ;;
  *)
    echo "Unknown target '$TARGET'. Use: all | fast | slow | graph | gcp | backend | inference | frontend | labeller" >&2
    exit 2
    ;;
esac

printf '\n'

if [ "$failures" -gt 0 ]; then
  printf '\033[31m%d check(s) failed.\033[0m\n' "$failures"
  exit 1
fi

printf '\033[32mAll checks passed.\033[0m\n'

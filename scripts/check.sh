#!/usr/bin/env bash
#
# The one verification command. `make check`, or ./scripts/check.sh.
#
# It exists so nobody - human or agent - has to rediscover that pytest
# needs --ignore=tests/nlp/test_all_news.py (that module reads real
# scraped articles nothing in the suite populates, so it fails on a clean
# checkout for reasons unrelated to your change), or that the frontend is
# typechecked from a different directory.
#
# One command means one habit and one unambiguous answer to "am I done".
#
# Usage:
#   ./scripts/check.sh            backend + frontend
#   ./scripts/check.sh fast       invariants only - seconds, no models
#   ./scripts/check.sh backend    backend only
#   ./scripts/check.sh frontend   frontend only

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

# Excluded from routine runs: depends on backend/data/raw already holding
# real scraped articles, which nothing in the current suite creates.
PYTEST_ARGS=(--ignore=tests/nlp/test_all_news.py -q)

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

run_frontend() {
  step "Frontend typecheck"
  if (cd "$ROOT/frontend" && npx tsc --noEmit); then
    pass "frontend typecheck"
  else
    fail "frontend typecheck"
  fi
}

case "$TARGET" in
  fast)     run_fast ;;
  backend)  run_backend ;;
  frontend) run_frontend ;;
  all)      run_backend; run_frontend ;;
  *)
    echo "Unknown target '$TARGET'. Use: all | fast | backend | frontend" >&2
    exit 2
    ;;
esac

printf '\n'

if [ "$failures" -gt 0 ]; then
  printf '\033[31m%d check(s) failed.\033[0m\n' "$failures"
  exit 1
fi

printf '\033[32mAll checks passed.\033[0m\n'

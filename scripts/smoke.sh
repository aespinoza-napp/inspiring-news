#!/usr/bin/env bash
# Smoke-test a running backend: it is up, every dependency answers, the
# API key is on and accepted, the open routes are open, and the image is
# the current one. With --claim, one real claim gets a real verdict.
#
#   scripts/smoke.sh [base-url] [api-key] [--claim]
#
# base-url defaults to http://127.0.0.1:8000, the key to $STORAGE_API_KEY.
# The deployment runbook runs it through the VM's SSH tunnel
# (docs/decisions/deployment.md, "The first real deploy", step 7):
#
#   scripts/smoke.sh http://127.0.0.1:8000 "$(terraform output -raw storage_api_key)"
#
# Only curl and grep, on purpose: it runs from Git Bash on Windows, which
# has neither python3 nor jq.
#
# Read-only without --claim: the one write it attempts, a job with no
# URL, is refused before anything runs (401 with the key on, 422 without).
# --claim costs a live search and one LLM call - about a minute on the
# production CPU - and leaves a job in the journal.
#
# Exit status: the number of checks that failed; 0 means all passed.

set -uo pipefail

BASE="http://127.0.0.1:8000"
KEY="${STORAGE_API_KEY:-}"
CLAIM=0
positional=0

for arg in "$@"; do
  case "$arg" in
    --claim) CLAIM=1 ;;
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)
      positional=$((positional + 1))
      if [ "$positional" -eq 1 ]; then BASE="${arg%/}"; else KEY="$arg"; fi
      ;;
  esac
done

if [ -t 1 ]; then GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'; else GREEN=""; RED=""; DIM=""; OFF=""; fi

FAILED=0
BODY_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE"' EXIT

ok()   { printf '%sok%s    %s\n' "$GREEN" "$OFF" "$1"; }
fail() { printf '%sFAIL%s  %s\n' "$RED" "$OFF" "$1"; FAILED=$((FAILED + 1)); }
note() { printf '%s      %s%s\n' "$DIM" "$1" "$OFF"; }

# request METHOD PATH [key|nokey] [json-body] [timeout] -> STATUS, BODY
request() {
  local method="$1" path="$2" auth="${3:-nokey}" body="${4:-}" timeout="${5:-20}"
  local args=(-sS -m "$timeout" -o "$BODY_FILE" -w '%{http_code}' -X "$method")

  if [ "$auth" = key ] && [ -n "$KEY" ]; then args+=(-H "X-API-Key: $KEY"); fi
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' --data "$body"); fi

  STATUS="$(curl "${args[@]}" "$BASE$path" 2>/dev/null)" || STATUS="${STATUS:-000}"
  BODY="$(cat "$BODY_FILE" 2>/dev/null)"
}

echo "Smoke test of $BASE"

# --- 1. Up, and every dependency an analysis needs -------------------

request GET /healthz

case "$STATUS" in
  200)
    ok "/healthz: every dependency answers"
    ;;
  503)
    down="$(grep -o '"[A-Za-z_]*":{"ok":false' <<<"$BODY" | cut -d'"' -f2 | paste -sd, -)"
    fail "/healthz: 503, not answering: ${down:-see the body}"
    note "$BODY"
    ;;
  000)
    fail "/healthz: no answer from $BASE - is it running, and is the tunnel open?"
    exit "$FAILED"
    ;;
  *)
    fail "/healthz: HTTP $STATUS"
    note "$BODY"
    ;;
esac

# --- 2. Metrics -------------------------------------------------------

request GET /metrics

if [ "$STATUS" = 200 ] && grep -q '^# TYPE inspiring_' <<<"$BODY"; then
  ok "/metrics: Prometheus counters served"
else
  fail "/metrics: HTTP $STATUS, or no inspiring_* metric in it"
fi

# --- 3. The key -------------------------------------------------------
#
# A job with no URL: refused by the key (401) when it is on, by
# validation (422) when it is off. Nothing runs either way.

request POST /analyze/jobs nokey '{}'

if [ -n "$KEY" ]; then

  case "$STATUS" in
    401) ok "the key is on: a request without it is refused (401)" ;;
    422) fail "the key is OFF: a request without it reached validation (422) - every endpoint is open" ;;
    *)   fail "a request without the key: expected 401, got HTTP $STATUS" ;;
  esac

  request GET /scraper/stats key

  case "$STATUS" in
    200) ok "the key is accepted (/scraper/stats: 200)" ;;
    401) fail "the key given is refused (/scraper/stats: 401) - wrong key for this server" ;;
    *)   fail "/scraper/stats with the key: HTTP $STATUS" ;;
  esac

else

  case "$STATUS" in
    422) ok "no key given, and this server asks for none (the local default)" ;;
    401) fail "this server wants a key: pass it as the second argument or STORAGE_API_KEY" ;;
    *)   fail "a request without the key: HTTP $STATUS" ;;
  esac

fi

# --- 4. What is open by design ----------------------------------------

request GET /reader/articles

if [ "$STATUS" = 200 ] && grep -q '"items"' <<<"$BODY"; then
  total="$(grep -o '"total":[0-9]*' <<<"$BODY" | head -1 | cut -d: -f2)"
  ok "/reader/articles: open, ${total:-?} published article(s)"
else
  fail "/reader/articles: HTTP $STATUS without its key - the reader view should be open"
fi

request GET /analyze/jobs/00000000-0000-4000-8000-000000000000

if [ "$STATUS" = 404 ]; then
  ok "polling a job by id: open (an unknown id is 404)"
else
  fail "polling an unknown job id: expected 404, got HTTP $STATUS"
fi

# --- 5. The image is the current one ----------------------------------
#
# /evaluation/summary is the newest route: a 404 here is an image built
# before it, which is what a stack that was not rebuilt serves.

request GET /evaluation/summary key

case "$STATUS" in
  200) ok "/evaluation/summary: served (the image has the newest routes)" ;;
  401) fail "/evaluation/summary: 401 - refused without the right key" ;;
  404) fail "/evaluation/summary: 404 - this backend's image predates it; rebuild it" ;;
  *)   fail "/evaluation/summary: HTTP $STATUS" ;;
esac

# --- 6. Optional: one real claim --------------------------------------

if [ "$CLAIM" = 1 ]; then

  echo "Verifying one claim (a live search and one LLM call; up to 10 minutes)..."

  request POST /verify-claim key \
    '{"claim": "The Great Barrier Reef lies off the coast of Queensland, Australia."}' 600

  if [ "$STATUS" != 200 ]; then
    fail "/verify-claim: HTTP $STATUS"
    note "$BODY"
  else
    verdict="$(grep -o '"verdict":"[A-Z_]*"' <<<"$BODY" | head -1 | cut -d'"' -f4)"
    evidence="$(grep -o '"evidenceCount":[0-9]*' <<<"$BODY" | head -1 | cut -d: -f2)"

    if grep -q '"llmUnreachable":true' <<<"$BODY"; then
      fail "/verify-claim: the LLM was unreachable - check LLM_TIMEOUT and LLM_MAX_CONCURRENCY for a CPU"
    elif grep -q '"searchUnavailable":true' <<<"$BODY"; then
      fail "/verify-claim: the web search failed - read SearXNG's unresponsive_engines before anything else"
    elif [ "${evidence:-0}" -eq 0 ]; then
      fail "/verify-claim: $verdict with no evidence - the search answered but found nothing usable"
    else
      ok "/verify-claim: $verdict, from $evidence source(s)"
    fi
  fi

fi

echo
if [ "$FAILED" -eq 0 ]; then
  printf '%sAll checks passed.%s\n' "$GREEN" "$OFF"
else
  printf '%s%d check(s) failed.%s\n' "$RED" "$FAILED" "$OFF"
fi

exit "$FAILED"

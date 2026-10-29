#!/bin/sh
#
# Every model the backend is configured to call, in the ollama-models
# volume before the backend starts (docker-compose.prod.yml, ollama-pull).
# A no-op for a model already there: `ollama pull` only fetches what
# changed. Before 2026-10-19 only LLM_MODEL was pulled, so a writer
# configured in backend/.env met a missing model on its first draft.
#
#   LLM_MODEL            the verifier (required)
#   WRITER_LLM_MODEL     the writer; when WRITER_LLM_BASE is set, the name
#                        the long-context variant below is served as
#   WRITER_LLM_BASE      a model to serve with WRITER_NUM_CTX tokens of
#                        context: Ollama's 4k default cuts a draft's prompt
#                        without a word (docs/decisions/writing.md)
#   WRITER_NUM_CTX       16384 unless set; the reviewer's too
#   CORRECTOR_LLM_MODEL  the reviewer, when it is not LLM_MODEL; when
#                        CORRECTOR_LLM_BASE is set, the name its
#                        long-context variant is served as
#   CORRECTOR_LLM_BASE   as WRITER_LLM_BASE, for the reviewer: a review
#                        reads the draft and up to 14,000 characters of its
#                        sources, past 4k tokens as surely as a draft does
#                        (2026-10-19: qwen3.5:9b recommended as reviewer;
#                        2026-10-29: gemma4:e4b, evaluation.md)
#   OLLAMA_NUM_THREAD    threads for those two variants; unset is Ollama's
#                        own choice. On the dev laptop's hybrid CPU that
#                        choice spread onto two low-power cores, and 10
#                        threads wrote a draft in 298 s against 381 s
#                        (docs/decisions/performance.md). Measure on the
#                        machine before setting: scripts/bench_ollama.py
#   OLLAMA_NUM_BATCH     their prompt batch; unset is Ollama's 512. 128
#                        where an integrated GPU serves the Qwen 3.5 models,
#                        which crash it at 512 (vk::DeviceLostError)
#
# Ollama holds one of them in memory at a time (OLLAMA_MAX_LOADED_MODELS=1
# on the ollama service): pulled is on disk, not resident.

set -eu

pull() {
  [ -n "$1" ] || return 0
  echo "ollama-pull: $1"
  ollama pull "$1"
}

# The writer and the corrector are optional: a model that cannot be had
# is reported, and the backend still starts - verification does not need
# it, and a draft then fails saying which model is missing.
optional() {
  pull "$1" || echo "ollama-pull: WARNING - could not pull $1; drafts that need it will fail"
}

# serve_long NAME BASE: BASE pulled, then served as NAME with the long
# context. The variant is a Modelfile over the same weights: no download
# beyond the base model's own.
serve_long() {
  optional "$2"
  printf 'FROM %s\nPARAMETER num_ctx %s\n' "$2" "${WRITER_NUM_CTX:-16384}" > /tmp/Modelfile
  [ -z "${OLLAMA_NUM_THREAD:-}" ] || printf 'PARAMETER num_thread %s\n' "$OLLAMA_NUM_THREAD" >> /tmp/Modelfile
  [ -z "${OLLAMA_NUM_BATCH:-}" ] || printf 'PARAMETER num_batch %s\n' "$OLLAMA_NUM_BATCH" >> /tmp/Modelfile
  echo "ollama-pull: $1 from $2, ${WRITER_NUM_CTX:-16384} tokens of context"
  ollama create "$1" -f /tmp/Modelfile \
    || echo "ollama-pull: WARNING - could not create $1; drafts that need it will fail"
}

pull "${LLM_MODEL:?LLM_MODEL is required}"

if [ -n "${WRITER_LLM_BASE:-}" ]; then
  serve_long "${WRITER_LLM_MODEL:?WRITER_LLM_BASE needs WRITER_LLM_MODEL, the name to serve it as}" "$WRITER_LLM_BASE"
else
  optional "${WRITER_LLM_MODEL:-}"
fi

if [ -n "${CORRECTOR_LLM_BASE:-}" ]; then
  serve_long "${CORRECTOR_LLM_MODEL:?CORRECTOR_LLM_BASE needs CORRECTOR_LLM_MODEL, the name to serve it as}" "$CORRECTOR_LLM_BASE"
elif [ "${CORRECTOR_LLM_MODEL:-}" != "$LLM_MODEL" ] && [ "${CORRECTOR_LLM_MODEL:-}" != "${WRITER_LLM_MODEL:-}" ]; then
  optional "${CORRECTOR_LLM_MODEL:-}"
fi

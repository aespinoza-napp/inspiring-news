# Tests

Mirrors `src/` roughly by subsystem: `nlp/`, `scraper/`, `fact_checker/` (further split into
`ranking/`, `retrieval/`, `validators/`, `verification/` — matching `src/services/fact_checker/`
exactly), `services/`, `database/`.

## Shared fixtures & fakes

- **`factories.py`** — `create_article`, `create_claim`, `create_evidence`: fully-populated model
  instances for tests that just need *a* valid one, with `**kwargs` overrides for what they care about.
- **`builders/source_builder.py`** — same idea for `NewsSource`.
- **`fact_checker/fakes.py`** — a fake for every external dependency the fact-checker touches
  (embeddings, SearXNG, the scraper, the LLM client, source repository, plus `FakeEvidenceRetriever`/
  `FakeRanker` for orchestrator-level tests). This is why `uv run pytest` needs no live SearXNG/LLM/Qdrant.
- **`conftest.py`**'s `repository` fixture spins up a temporary on-disk Qdrant database for tests that
  need one, rather than mocking the client.

## A rule that matters

**No test module should call its own test function at module level** (`test_something()` as a bare
statement outside `if __name__ == "__main__"`) — that runs the test's side effects, including writes,
during pytest *collection*, before pytest controls execution at all. This has bitten twice already
(`test_scraper.py` did live network scraping just by being imported; `test_pipeline.py` silently
overwrote a committed fixture on every collection). Both are fixed — don't reintroduce the pattern in a
new test file.

## Pre-existing failures

A handful of tests fail against a clean `main` regardless of what you're working on — see `CLAUDE.md`'s
"Tests" section under Backend for the current list and why, and verify against a clean checkout before
assuming a change of yours broke one of them.

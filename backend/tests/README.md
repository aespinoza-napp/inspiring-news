# Tests

Mirrors `src/` by subsystem: `processors/nlp/`, `services/` (including `services/scraper/` and
`services/fact_checker/`, further split into `ranking/`, `retrieval/`, `validators/`, `verification/` —
matching `src/services/fact_checker/` exactly), `api/`, `database/`, `repositories/`, `config/`.

## Shared fixtures & fakes

- **`factories.py`** — `create_article`, `create_claim`, `create_evidence`: fully-populated model
  instances for tests that just need *a* valid one, with `**kwargs` overrides for what they care about.
- **`builders/source_builder.py`** — same idea for `NewsSource`.
- **`services/fact_checker/fakes.py`** — a fake for every external dependency the fact-checker touches
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

## What runs, what skips

`./scripts/check.sh` from the repo root is the definition of "done". As of 2026-09-21 the backend suite
is green: 504 passed, 11 skipped, 2 deselected. The skips need something running — the `inference/`
service (`require_inference`) or Neo4j — and the two deselected carry the `slow` marker (the whole corpus
through the real models; `./scripts/check.sh slow`).

There are no known failing tests. If one fails, it is yours until shown otherwise.

Two fixtures worth knowing: `create_article()`'s default URL is the same for every article, and a stored
article at the same URL is *the same article*, not a duplicate — a test that needs a different article
must give it a different `url`. And `TestClient(app)` does not run the app's lifespan unless used as a
context manager, which is what keeps the job journal out of the real lake during tests.

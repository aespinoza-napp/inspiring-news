---
name: debug-verdict
description: Diagnose why a claim or article got a wrong or suspicious verdict in the fact-checking pipeline, such as everything UNVERIFIED, a true claim marked FALSE, irrelevant sources or bad search queries. Use when a verdict looks wrong or someone asks why it is not working.
---

# Why did this claim get this verdict?

Work from the run's own record, upstream first. A verdict can only be as good as the
stage before it, and "the LLM is broken" has usually been wrong here.

## 1. Get the record

The job's events hold every query, source, stance and quote:
`curl -s localhost:8000/analyze/jobs/<job id>`. In the app, `/live?job=<id>` shows
the same, and `/trace?q=<url or id>` shows the whole journey. Read the code revision
and thresholds there: the run may not be the pipeline you think
(`FACT_CHECK_PROFILE`, `backend/.env`).

## 2. Go down this list and stop at the first that fits

| What you see | What it means | Where to look |
|---|---|---|
| `llmUnreachable`, "not checked" | The model was not reached | `/healthz`, Ollama bind address, `docker/README.md` |
| `searchUnavailable`, or results from a failed route | Search failed or answered off-subject | `/scraper` source probe, `search.py` `MIN_QUERY_COVERAGE` |
| Queries missing the claim's subject | Query building | `retrieval/query_builder.py`, `terms.py` |
| Sources about something else | Engines, not the model | Measure engines (below) |
| Good sources, all cut | Pertinence gate | `evidence_ranked.cut` reasons, `docs/decisions/retrieval.md` |
| Copies rejected, nothing left | Honest UNVERIFIED | `fact_checker/independence.py` |
| Right sources, wrong stance | The 3B's reading | Compare each quote with the claim |
| Only the article verdict looks wrong | Worst-claim-wins | `foundVerdict`, the per-claim verdicts |

## 3. Measuring engines

Count **on-topic** results, never results: ten results about the query's first word
once read as a healthy search. Test real claim queries, a few seconds apart, because
bursts get an engine suspended and then your measurement is the cause.

SearXNG ignores an engine name it does not have enabled and answers with its defaults,
so identical results across engines mean the name was not applied. To try a list,
run a throwaway container on another port with its own settings file, and remove it.

## 4. Reporting

Quote the evidence: the query, the source, the stance, the quote. Separate what you
measured from what you infer. If the cause is the model reading correct evidence
badly, say so; that is a known limit (`docs/decisions/evaluation.md`), not a bug to
patch for one article. To change the pipeline, use the `fact-check-change` skill.

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
| The claim starts or ends mid-quote (a `»` with no `«`) | The splitter cut a quotation | `processors/nlp/claims.py` `_inside_quote` |
| An opinion or a quote judged FALSE by facts about its story | Judged as a fact, not as who said it | `claim_restated.kind`, `opinion_claims` |
| A source's text has `Ã`, `Â`, `â€` | A page decoded with the wrong charset | `scraper/fetcher.py` `decoded` |

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

## A claim searched without its referent (2026-11-10)

Symptom: sources "found" but about something else, or 0 results, on a sentence
that starts with a verb or a pronoun ("tienen...", "la iniciativa...", "según
explica el especialista..."). Look at the queries on the Live screen: if the
subject's name (a project, a person) is in none of them, the referent was lost.
Check the `claim_restated` event: `standalone` should carry the name from the
passage before the sentence. If it is "checked as written" with a note, read why.

## Replaying one claim of a job by hand (2026-11-17)

Before you change anything, reproduce the verdict with the real model on the job's own
sources. Write a short script in the scratchpad and run it from `backend/` with
`PYTHONPATH=. uv run python <script> <job.json>`. It loads the job (`curl -s -H "X-API-Key:
$KEY" localhost:8000/analyze/jobs/<id>`, the key is in `backend/.env`), builds an `Evidence`
from each source in `claim_checked.evidence`, fetches the pages again with
`EvidenceScraper().enrich(...)`, and calls `LLMVerifier().verify(claim, evidence,
context=ArticleContext(title=...), thresholds=PipelineThresholds(verifier_answer="per_source"),
language=...)`. Try one condition at a time. To see what the model was actually shown for a
source, call `LLMVerifier()._excerpter(claim, context, thresholds, language)(page_text)`. The
3B is noisy, so one try per condition is a diagnosis, not a measurement. Do not run
`./scripts/check.sh` at the same time: on a shared CPU the inference tests then hang.

## An opinion or a quote marked FALSE (2026-11-17)

Symptom: "What is checked: An opinion said by X". The sources are about the right story, and
their "contradicts" quotes state a fact about it (a place, a range, a figure) that says nothing
about whether X said it. The Victoria colombiana case: "Creemos que lo sabemos todo...»,
confesó Magdalena al diario The Guardian" came back FALSE because two pages said the
waterlily's natural range does not reach the Inírida. Check, in order:

1. **Is the claim the whole quote?** If it starts after the opening `«` it was cut by the
   splitter. Read the article around it. Fixed in `ClaimExtractor._inside_quote`.
2. **Did the restater give a speaker?** `claim_restated.restatement.speaker`. With
   `opinion_claims: attribution` (the default) the verifier asks whether the speaker said it,
   and a `contradicts` needs a quote naming them. With no speaker, or with
   `claim_restatement` off, the old path still runs.
3. **Does any source actually carry the quote?** Search the fetched pages for a few words of
   it. If one does and the model said `silent`, look at its excerpt (above), and at encoding
   first.

## Mojibake in a source (2026-11-17)

Symptom: `Ã³`, `Ã±`, or a vanished `í` (`muchÃsimas`) in an excerpt. The page was UTF-8,
served with no charset (radiomatik.com sends bare `text/plain`), and requests read it as
Latin-1. The 3B then called "silent" the very source that settled the claim.
`fetcher.decoded` now tries UTF-8 first. If it reappears, check the response's content-type
with `curl -sI <url>` and find which path decoded the page without going through
`decoded`.

## Recording what you fixed

Each fix found through this skill goes into it as a row in the table above and a dated
section below, so the next diagnosis starts from it. It also gets a section in
`docs/fact-checking-changes.md`.

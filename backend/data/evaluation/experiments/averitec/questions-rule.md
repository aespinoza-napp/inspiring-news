# Asking questions before searching: the experiment's rule

Written 2026-11-06, before the question plan existed as code and before any
verdict under it. The literature behind it is in the thesis
(`docs/final_document/chapters/02-state-of-the-art/01-automated-fact-checking/04-what-to-search.tex`)
and `docs/troubleshooting/fact-checking/01-what-to-look-for.md`.

## The question

Does a claim searched by at most three questions, each carrying the claim's
subject and one decisive detail of its rule-based checkable point, find
evidence that a verdict can rest on more often than the queries the pipeline
builds now - and how do its questions and answers score against AVeriTeC's?

## What is built

`query_plan: questions` beside `sentence` and `checkable`, off by default.

- One model call per claim (the verifier's model) writes up to three questions
  from the claim's text and its checkable point's details. Nothing else goes in
  the prompt: no speaker, place or date, as in every AVeriTeC condition.
- Each question is held to the claim without a model. Rejected: one with a figure
  the claim does not state; one that does not carry the claim's subject (a name or
  subject word of the checkable point, else its first terms); one that carries no
  decisive detail (a figure, identifier, date or name, else a term); one that
  repeats a kept question.
- Each kept question is one search query: its subject, its detail and its own key
  words. Three questions, three queries: the same number of searches as now.
- No question kept, or a deadline, or the model down: the checkable plan, as it is,
  with a note.
- A question's answer is the passage of the first judged source its query found;
  none found is "No answer could be found." No extra model call.
- **The checkable point is not changed** by any of this: it stays as it is
  (`finding_closing`, `counted`), the baseline.

## Train, first

AVeriTeC's train split, the first 100 claims in the file's order (hash order, so
a fixed random sample), live web through the temporal gate (`averitec_web.json`'s
settings), `llama3.2:3b-bench`, no second look. Two searched conditions:

| Name | Thresholds |
|---|---|
| `train-checkable` | `averitec_web_checkable.json`: the web settings + `query_plan: checkable`, `checkable_terms: finding_closing`, `checkable_figures: counted` |
| `train-questions` | `averitec_web_questions.json`: the same + `query_plan: questions` |

Searched runs differ by 6-9 points on their own, so 100 claims cannot show a small
gain. Train decides only whether the plan, as built, goes to dev:

1. Both runs' temporal audits say **Held**, or the run is void and re-run.
2. At least 80 of 100 claims keep at least one question. If not, the prompt or the
   checks are fixed **on train only** and `train-questions` is run again; at most two
   such fixes, each recorded below with its numbers.
3. `train-questions` is not more than 10 points below `train-checkable` in accuracy
   (paired point estimate), and its searches fail no more than 10 points more often.
   A guard against a broken plan, not evidence of a gain.

If 2 or 3 still fails after two fixes, the plan is **not adopted**, and dev is run
anyway only because the comparison with the literature was asked for; the report
says so first.

## Dev, then

Added to `protocol.md`'s conditions, same rules (dev not tuned on; any late source
voids a run): `store-questions` (knowledge store) and `web-questions` (live web),
the 500 dev claims, with `averitec_store_questions.json` / `averitec_web_questions.json`.
Compared with the protocol's `store` and `web` (the sentence plan) on the same
claims - the comparison the protocol already makes. The checkable plan is not run on
dev: the machine's time (about 17 h per 500-claim condition) is the reason.

## What is reported, whatever it says

Everything `protocol.md` lists, and beside accuracy:

- **Q-only** and **Q+A**: the Hungarian METEOR match of the run's questions (and
  question + answer) with the gold ones, as AVeriTeC's official scorer computes it
  (`src/evaluation/averitec_score.py`, a re-implementation; its differences from the
  official script are listed there).
- **AVeriTeC score**: accuracy counting a claim right only when its Q+A match is
  above 0.25 (and the other reporting levels). The sentence and checkable plans have
  no questions: their Q-only, Q+A and AVeriTeC score are 0 by construction, and are
  reported as "no questions", not as a result.
- The published figures beside them, each with its split: ClaimCheck (dev, accuracy),
  InFact and HerO (the shared task's test set; the dev figures where the paper gives
  them). A dev figure is never compared with a test figure without saying so.

## What this does not say

English only, AVeriTeC's claims (politics and health, 2019-2020); a 3B model where
the published systems use 4B to GPT-4o; three questions where InFact asks ten. The
answer is a passage, not a written answer, which lowers Q+A by construction.
Nothing here changes the application's defaults.

## Corrections and fixes on train

*(each dated, with its numbers, before the run it leads to)*

**2026-11-06, before any searched run: three fixes to the questions, read from the
question step alone** (no search, no verdict) on the first 10 train claims, the same
claims each time. `llama3.2:3b-bench`. Claims keeping at least one question:

| Version | Kept | What was wrong |
|---|---:|---|
| v1, as first built | 9 of 10 | The subject was the checkable point's first names, which hold phrases GLiNER or a capital letter took for names ("Presidential candidate", "Walmart Tweeted", "ghee", "hot milk"): the Biden questions said "a Presidential candidate" and passed. The prompt's own example ("Which source counts...") came back as "What document or study says that...", and "What document study" reached the query. Near-duplicates left one question on Nigeria and South Africa. "Ryan Zinke" did not count as naming "US Interior Secretary Ryan Zinke". |
| v2 | 6 of 10 | Subject = the claim's first real name (every word capitalised, or an acronym, from GLiNER's entities and the point's names); a name counts when its core is named (not a title, not a numeral); the prompt names the subject and asks about the fact, never which source says it, each question on a different detail; question words left out of the query; a repeat is the same detail in mostly the same words. Too strict: the first name was "US" for Zinke and "Mumbai" for Nanavati Hospital, so good questions were refused. And "Presidential candidate" still passed, through a bug that skipped lowercase title words. |
| v3 | 10 of 10 | Any of the claim's names will do; only lowercase joiners ("of", "de") are skipped in a name; a date ("November 1st 2019") is not a name. The queries then lost repeated words and took the names from the same list the check uses. |

The checkable point was not changed by any of these: the helpers were added beside it
(`checkable.is_proper`, `proper_names`, `names_in`), and `checkable_point` is as it was.

**2026-11-06, the first searched runs on those 10 claims, and why they cannot decide
anything.** Live web, `averitec_web_*.json`, `llama3.2:3b-bench`:

| Run | Right of 10 | Sources taking a side |
|---|---:|---:|
| `train-checkable` (`08a0e658a528`) | 5 | 21 of 43 |
| `train-questions`, v3 (`130164923684`) | 8 | 18 of 44 |
| `train-questions-v4` (`13cc53557bb6`) | 3 | 8 of 34 |

v4 changed two things: an answer only from a source taking a side (supports or
contradicts), and the claim's first name leading every query. But identical queries
in v3 and v4 ("Boracay photos taken", the Biden queries but for one repeated word)
found sources taking a side in v3 and none in v4, an hour apart: the drop is mostly
SearXNG answering the same query differently, not the change. One part of it was the
change: Zinke's query led with the point's "US Interior Secretary Ryan Zinke" and
found nothing, where v3's "special flag Ryan Zinke ordered raised" found five sources.
Fixed: a name is searched as the question writes it.

So plans are compared on train **through one search cache** from here on
(`cli run --search-cache`, `src/evaluation/search_cache.py`): a query asked before is
answered as it was, and only a changed query reaches SearXNG. None of these figures is a
result: 10 claims, and the accuracy is not the rule's measure (rule 3 is a guard).
v3's Q-only 0.286, Q+A 0.156, AVeriTeC score 0.10 at 0.25 (train gold) are a first look.

**2026-11-06, through one search cache** (`data/evaluation/experiments/averitec/searches-train10.jsonl`),
the same 10 claims:

| Run | Right | Candidates | Judged sources | Taking a side | Searches answered from the cache |
|---|---:|---:|---:|---:|---:|
| `cache-checkable-v5` (`caeca8f8da38`) | 4 | 634 | 43 | 20 | 0 of 30 (it filled it) |
| `cache-questions-v5` (`b74e86798dbd`) | 5 | 369 | 25 | 9 | 0 of 25 |
| `cache-questions-v6` (`469933d58a92`) | 5 | 620 | 38 | 14 | 34 of 35 |

v5 had too few candidates: the questions' queries are specific, return fewer pages, and
the temporal gate removes most of what any query returns (Biden: 48 candidates, 47 cut, 37
of them for a date after the claim). v6 searches the checkable plan's anchor query first,
then the questions (`plan_questions`): the pool is back (620 against 634), and with 34 of
35 searches recorded, v6 differs from v5 by that one change. Nigeria's Not Enough
Evidence, the gold label, is the one verdict the change turned right (and Russia's
Conflicting went from UNVERIFIED to FALSE, wrong either way).

What limits both plans now is the search itself, not the plan: in the cache's 49
answers DuckDuckGo, Startpage, Mojeek and Google returned nothing, and the results came
from Crossref (603), arXiv (490), Yahoo (343), Brave (66) and Semantic Scholar (36). With
the news pages cut by the gate, the papers fill the evidence and say nothing on the claim.
Not changed here: the engines are every run's, so it is a search change of its own
(`docker/searxng/settings.yml`), to propose and measure apart.

**2026-11-06, without the scholarly engines** (`search_science_engines: drop`, now in
`averitec_web_checkable.json` and `averitec_web_questions.json`), measured on its own: the same
10 claims through the same cache (all but 6 of 59 searches recorded; the 6 had failed before
and were asked again).

| Run | Right | Judged sources | Papers among them | Taking a side | Median s per claim | Model calls |
|---|---:|---:|---:|---:|---:|---:|
| `cache-checkable-v5` (`caeca8f8da38`), with them | 4 | 43 | 23 | 20 | 95 | 43 |
| `cache-checkable-v7-noscience` (`adbbde6c99a5`) | 5 | 24 | 0 | 18 | 48 | 24 |
| `cache-questions-v6` (`469933d58a92`), with them | 5 | 38 | 20 | 14 | 99 | 48 |
| `cache-questions-v7-noscience` (`ac5a2987583d`) | 5 | 19 | 0 | 11 | 60 | 29 |

No detectable difference in accuracy on 10 claims; the papers took no side and only cost the
verifier's time. Kept for AVeriTeC's web runs. What both plans lack now is news from before the
claim: Boracay, Nanavati Hospital and Walmart still end with sources that say nothing.

# 1. Knowing what to look for

**The part:** before searching, deciding which detail of the sentence would
settle it, and what kind of source would. In the pipeline there is no such step
by default. `claim_restatement: standalone` (off, 3 Nov) is the nearest: it
restates the sentence as one checkable statement. Every query is otherwise
built from the sentence's own words (`retrieval/query_builder.py`, `terms.py`).

## Finding (4 Nov 2026, 20 train claims)

For every claim, Claude first wrote down the point and what would settle it
(`backend/data/evaluation/experiments/claude-search/plan.jsonl`). In 16 of 20
the decisive detail was a **figure, a date or a named place**, and in 9 the
settling source was a **primary one** that could be named in advance:

| Claim | What would settle it | Primary source named in advance | Found there |
|---|---|---|---|
| fact037 | 212 travel-related dengue cases in Florida so far in 2026 | Florida Health's weekly arbovirus report | yes, week 37 |
| fact038 | Arctic minimum on 12 September | NSIDC | yes |
| fact020 | Jire carried Jimato 68 days | the Bossou study (Current Biology) | yes |
| fact063 | clean power met China's 2025 demand growth | Ember's report | yes |
| fact065 | Calvo de Mora is director general of Macán | the winery's site | yes |
| fact081 | 11-set in 2012, 13-set in 2014 | Mamakani and Ruskey's papers | yes |
| fact082 | Dzoba used AI for the 17-set diagram | his preprint / repository | yes |
| fact012 | Roe's statement | the University of Oslo release | yes |
| fact049 | fewer than 0.001% of brain cells | the Shah lab's paper | the paper yes, the figure no |

The pipeline's queries for the same claims name neither the figure nor the
source type (see [02-queries.md](02-queries.md)). fact037's three queries do
not contain "dengue" or "212" at all.

## Why it matters

What the claim turns on decides everything after it. A search that does not
carry the figure finds pages on the subject, ranking keeps the most similar
titles, and the verifier is then asked about pages that cannot settle the point.
Five of the pipeline's 11 wrong verdicts here came from sources that were on
the subject and silent or off the point (fact010, fact011, fact049, fact081,
fact082).

## Built (2026-11-04), not yet measured

`query_plan: checkable` (`fact_checker/retrieval/checkable.py`): the checkable
point read from the sentence with no model, and recorded in
`searching_web.checkablePoint`:
- figures with their scale, identifiers (SE-20) and times kept whole;
- day-month dates;
- multi-word names;
- the assertion's words without filler.

On these 20 claims it now finds 212 (fact037), 0.001 per cent (fact049),
138,000 and 23,000 (fact016), SE-20 and 25 millones (fact010), 11-set and 2012
(fact081), and 12 September (fact038). `docs/fact-checking-changes.md` (12).

### The subject the sentence never says (built the same day)

"There have been a total of 212 known travel-related cases in Florida" never
says dengue. Everything after it depends on that word: without it the search
returns Florida tourism and a 2010 cholera story. Two causes:

- **The harness never had the headline.** It passed only the article's URL. It
  now takes each custom-set article's headline from the labeller's batches
  (`evaluation/queue/`, frozen when the fact was labelled), with the site's name
  stripped. All 69 train claims have one. It goes in
  `ArticleContext.search_title`, read by the search alone: `title` is also in
  the verifier's prompt, and a search change must not change what the model
  reads.
- **The app's rule was all or nothing.** `terms.subject_terms` restores the
  article's subject (the headline's words its keywords hold) only when the
  sentence names *none* of them. fact037 names Florida, so even the app, with
  the whole article, would have lost "dengue". Under `checkable`,
  `checkable.lost_subject` brings back each subject word the sentence lacks.
  `subject_terms` keeps its rule for the sentence plan and the ranker.

Where there are no keywords (the harness, `/verify-claim`), the subject is the
headline's words that **the article's other sentences repeat**
(`checkable.title_subject`), as keywords would. Tried on the headline alone, a
third of the train claims got its framing ("querida suegra tengo gusto",
"oddest even odder thought"). With the repetition test:
- fact037, fact138 and fact174 get "Dengue fever";
- fact020 "chimpanzee mothers", replacing the stories about human infants its
  query found;
- fact009 "Starship", whose sentence says only "La nave";
- fact063 and fact064 "Chinese Industry", fact122 "Jupiter".

22 of 69 get no subject rather than a wrong one. A few weak ones remain ("old
London", "Questions"). The article's other sentences can include test-half
claims' text, the article's words and never a label, as the app has the whole
article.

fact037's queries are now `Florida Dengue fever counties "212" 2026` /
`Florida Dengue fever "212" travel related cases` / `Florida Dengue fever
"212" 2026 travel related cases`.

What it does not do yet: name the **kind of source** that would settle the
claim (an official report, the study, the organisation's own site).

## What to try

- `claim_restatement: standalone`, measured as a searched try: it restates, but
  is not told to name the decisive detail.
- A "checkable point" field in the restatement: the figure, date or name, and
  the kind of source that would hold it (official report, the study, the
  organisation's own site). Code on the search side, so a searched try.

## Against the literature (2026-11-06)

The rule-based checkable point is **kept as it is, as the baseline** that a
question-based plan is measured against. The papers, and where this stage sits
among them, are in the thesis: `docs/final_document/chapters/02-state-of-the-art/
01-automated-fact-checking/04-what-to-search.tex`; the five rounds are in its
results (`07-results/07-pre-verdict-stages.tex`, "Knowing what to look for"),
and the planned question plan in `09-conclusions/04-future-work/02-further-work.tex`
("Asking questions before searching").

- **Questions first:** QABriefs (Fan et al. 2020), literal vs implied subquestions
  (Chen et al. 2022: >70% literal, 18% implied recovered), Varifocal (Ousidhoum
  et al. 2022), FACTIFY-5WQA (Rani et al. 2023); AVeriTeC's evidence is
  question-answer pairs, and InFact (10 questions, model-written queries per
  question) and HerO (open 8B) led its 2024 shared task.
- **Splitting the claim:** ProgramFC, FActScore, Factcheck-Bench; with pre-claim
  web evidence, Chen et al. 2024 (evidence covers some aspects, rarely all).
  Contested: Wanner et al. 2024 (the score depends on the decomposition method),
  Hu et al. 2025 (helps weak verifiers, adds noise, more sub-claims eventually hurt).
- **Standing alone:** decontextualisation (Choi et al. 2021); molecular rather
  than atomic facts (Gunjal & Durrett 2024) - the dengue case is exactly this.
- **Small models:** ClaimCheck (Qwen3-4B plans the queries; 76.4% on AVeriTeC dev).

What a question plan would add here: the kind of source, the official AVeriTeC
score (it needs question-answer pairs), and a question per figure for the altered
detail. The plan to try: `query_plan: questions` beside the others, at most three
questions, each carrying the subject and one decisive detail of this checkable
point, tried on AVeriTeC train first.

## Experiments

One file per batch in [experiments/01-what-to-look-for/](experiments/01-what-to-look-for/README.md), run by
`scripts/troubleshoot.sh agent --stage 01` ([README.md](README.md), "Running it").

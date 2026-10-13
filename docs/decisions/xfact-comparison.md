# Our pipeline on X-Fact, beside the X-Fact paper

> Linked from `docs/decisions/evaluation.md` §Pilot. Read it before
> quoting an x-fact number in the paper, or putting one next to Gupta &
> Srikumar's.

**Status, 2026-10-13: measured.** The 64-claim pilot and the 165 Spanish
rows of X-Fact's in-domain test split were run end to end through the
harness, with `llama3.2:3b`; every number below is in a committed report
under `backend/data/evaluation/reports/`, next to the manifest that
produced it.

Nothing was trained. The verdict model is a zero-shot LLM reading
evidence the pipeline retrieved from the open web that day; there are no
weights to fit and no x-fact row was used to tune anything. "Training" in
the X-Fact sense, fine-tuning mBERT on 19,079 claims, has no counterpart
here. What was run is the pipeline's own `check_claim` over x-fact rows,
through the evaluation harness (`evaluation.md`), scored against
x-fact's labels.

## The paper's numbers

Read from the paper itself on 2026-10-13, not quoted from memory: Gupta &
Srikumar, *X-FACT: A New Benchmark Dataset for Multilingual Fact
Checking*, ACL-IJCNLP 2021 (short papers), pp. 675-682,
<https://aclanthology.org/2021.acl-short.86.pdf> (arXiv 2106.09248).
Every number is **macro-F1 in percent, the mean of four runs (seeds
1-4), standard deviation in parentheses**, over X-Fact's seven labels
(*true, mostly true, partly true/misleading, mostly false, false,
complicated/hard to categorise, other*). The paper reports no accuracy
and no per-language score.

**Table 3** (mBERT-base fine-tuned on X-Fact's train split; English is
not in it):

| Model | α1 in-domain | α2 out-of-domain | α3 zero-shot |
|---|---|---|---|
| Majority (always *false*) | 6.9 | 10.6 | 7.6 |
| Claim-Only | 38.2 (0.9) | 16.2 (0.9) | 14.7 (0.6) |
| Claim-Only + Meta | 39.4 (0.9) | 15.4 (0.8) | 16.7 (1.1) |
| Attn-EA (Random): the evidence model fed random snippets | 37.5 (0.8) | 16.3 (0.5) | 14.9 (1.2) |
| Attn-EA: claim + top-5 Google snippets | 38.9 (0.2) | 15.7 (0.1) | 16.5 (0.7) |
| **Attn-EA + Meta** (the paper's best) | **41.9 (1.2)** | 15.4 (1.5) | 16.0 (0.3) |

**Table 4** (the same two models with 12,311 English PolitiFact claims
from MultiFC added to training; both get worse):

| Model | α1 | α2 | α3 |
|---|---|---|---|
| Claim-Only + Meta | 37.1 (2.7) | 14.5 (0.5) | 14.4 (0.3) |
| Attn-EA + Meta | 38.0 (4.5) | 14.7 (2.6) | 14.3 (1.9) |

What the settings are (Tables 2 and 6): α1 is the training languages
*and* sources (3,826 claims, 12 languages; Spanish is there, as
chequeado.com); α2 is the same languages from other sources (2,368
claims, 4 languages, no Spanish); α3 is languages never seen in training
(3,381 claims, 12 languages, no Spanish or English). "Meta" is language,
site, claimant, claim date and review date as text. The evidence is the
**snippets of the top five Google results for the claim, collected when
the dataset was built**; the paper's own check of 100 Hindi α1 claims
found the snippets sufficient for 45% of them and the full pages for 83%
(§3.2). There is no uniform-random baseline in the paper: "Attn-EA
(Random)" is the evidence model fed random snippets, and the majority
baseline is the only label-prior baseline.

## Our numbers

Accuracy and macro-F1 with percentile 95% bootstrap intervals over
claims (10,000 resamples, seed 2026). Macro-F1 is over the five verdicts
the gold labels contain (three for English). Every claim of both runs
was scored: none was set apart at report time.

| Run | n | Accuracy [95% CI] | Macro-F1 ×100 [95% CI] |
|---|---|---|---|
| **Pilot, all** | 64 | 29.7% [18.8, 40.6] | 16.8 [10.4, 23.4] |
| Pilot, English (PolitiFact, `train` rows, 3 classes) | 24 | 41.7% [20.8, 62.5] | 35.8 [15.7, 55.4] |
| Pilot, Spanish (Chequeado, 31 `train` / 2 `dev` / 7 `test`) | 40 | 22.5% [10.0, 35.0] | 13.0 [6.1, 19.6] |
| Pilot, without `verdictLeak` claims | 55 | 27.3% [16.4, 40.0] | 16.1 |
| Pilot, without either leak flag | 43 | 23.3% [11.6, 37.2] | 15.3 [7.1, 23.8] |
| **Spanish `test` split (α1, Spanish only)** | 165 | 19.4% [13.3, 25.5] | 11.1 [7.9, 14.2] |
| Closed-book, pilot: same model, claim only, no evidence | 64 | 18.8% [9.4, 28.1] | 6.3 [3.4, 8.8] |
| Closed-book, Spanish `test` (1 claim unanswered: the model looped) | 164 | 16.5% [11.0, 22.6] | 8.4 [4.9, 12.7] |

Baselines on our own sets, computed from the label counts, not run:

| Set | Majority class: accuracy / macro-F1 ×100 | Uniform random over 5 verdicts: accuracy / expected macro-F1 ×100 |
|---|---|---|
| Pilot (balanced by construction: three labels tie at 16) | 25.0 / 8.0 | 20.0 / ≈19.5 |
| Pilot, English | 33.3 / 16.7 | 20.0 / ≈25.0 |
| Pilot, Spanish | 20.0 / 6.7 | 20.0 / ≈20.0 |
| Spanish `test` (majority `TRUE`, 50 of 165) | 30.3 / 9.3 | 20.0 / ≈19.2 |

Spanish `test` report:
`backend/data/evaluation/reports/xfact_es_test/llama3.2-3b/a6f2e3c8a401/`;
pilot: `.../xfact_en_es_pilot/llama3.2-3b/e6fe23310930/`.

Read plainly:

- **On X-Fact's own Spanish test rows the pipeline does not beat
  chance.** Accuracy 19.4% is below always answering the majority class
  (30.3%); kappa is -0.002 [-0.060, 0.055]; macro-F1 11.1 is above the
  majority's 9.3 and below a uniform guess's expected ≈19.2. It answers
  `FALSE` to 107 of 165 (gold: 24) and `MISLEADING` never (gold: 48, the
  second-largest class). Beside the paper's α1 rows it is 27 points
  below Claim-Only (38.2) and 31 below the best (41.9), before any of
  the caveats below; it does not reach α2 or α3 (14.3-16.7) either.
  And here the evidence buys nothing measurable: paired over 164 claims,
  +3.0 accuracy points [-3.0, +9.1] and +2.7 macro-F1 [-2.1, +6.9] over
  the same model closed-book, which answers `FALSE` to 155 of 164.
- **On the pilot the pipeline is barely above chance.** Cohen's kappa
  against gold is 0.07 [-0.03, 0.18]; its interval includes 0. Its
  macro-F1 (16.8) is below what a uniform random guess would be expected
  to score on a balanced set (≈19.5), because it answers `FALSE` to 43 of
  64 claims (gold has 16) and never says `MISLEADING`. Spanish macro-F1
  (13.0) sits between the paper's majority baseline (6.9) and its α2/α3
  rows (14-17), far below its α1 rows (37-42).
- **The evidence does help, measurably.** Paired over the same 64
  claims, the pipeline beats the same model without evidence by +10.9
  accuracy points [+3.1, +20.3] and +10.4 macro-F1 points [+4.5, +16.8];
  8 claims only the pipeline got right, 1 only the closed-book model did.
  Closed-book, `llama3.2:3b` answers `FALSE` to 60 of 64 claims: the
  pipeline's lean towards `FALSE` is the model's prior showing through.
- **English looks better and means less.** 7 of its 10 right answers
  are `FALSE` on the 8 `FALSE` rows (on Spanish, 7 of 9), and 9 of the
  24 English claims had PolitiFact's own verdict page among their
  evidence (below). There is no paper number to put beside it at all.

## Why the two are not directly comparable

None of these is a detail; several move the number by more than its
interval.

1. **Labels: their 7, our 5.** We score `TRUE`, `PARTIALLY_TRUE`,
   `MISLEADING`, `FALSE`, `UNVERIFIED` (`backend/data/evaluation/README.md`).
   *mostly false* and *false* are merged into `FALSE`, *mostly true*
   becomes `PARTIALLY_TRUE`, *other* is dropped. A merged class is
   easier to hit, and macro-F1 averages over fewer classes (5 for
   Spanish, 3 for English, against their 7), so the same system would
   score differently on each scale.
2. **English is not part of X-Fact's evaluation.** English exists only
   in the `x-fact-including-en` variant's training file: no dev or test
   split, no published score. Its rows keep PolitiFact's six-point scale,
   which has no *partly true/misleading* and no *complicated*, so English
   has no `MISLEADING` and no `UNVERIFIED`. And PolitiFact's *half true*
   maps to `PARTIALLY_TRUE`, while X-Fact's master mapping folds *half
   true* into *partly true/misleading* for every other language, which we
   map to `MISLEADING`: the same verdict lands in two classes depending
   on the row's language. The paper's only English result is that adding
   it to training *hurts* (Table 4).
3. **The pilot is not a test split, and not a random sample.** Its 64
   rows were drawn 8 per language-label bucket, preferring dev and test
   rows: 24 English (all `train`), 40 Spanish (31 `train`, 2 `dev`, 7
   `test`). Its label distribution is flat by construction, where the
   paper's test sets have *false* as their most frequent label; macro-F1
   on a balanced sample and on a skewed one are different quantities.
   Only the Spanish `test` run is drawn the way α1 is, and only for one
   of α1's twelve languages.
4. **64 or 165 claims against thousands.** Each paper number is a mean
   over 4 training runs on 3,826 (α1) test claims, and its standard
   deviation (0.1 to 4.5 points) is the spread between seeds, not a
   sampling interval. Ours is one deterministic run with a bootstrap
   interval over claims 13 to 40 points wide. A difference smaller than
   our interval is not a difference.
5. **Supervised against zero-shot.** mBERT was fine-tuned for ten epochs
   on 19,079 X-Fact claims and picked on the dev set: it learned the
   label distribution, each source's habits and, as the paper shows
   (Claim-Only beats Majority by 31 points on α1), strong claim-only
   cues. Our model has never seen an x-fact label. α3 (~15-17), where
   the supervised models meet unseen data too, is in that respect the
   fairer row, though Spanish is not in it.
6. **Their evidence was frozen in 2021; ours is the live web of
   2026-10-13.** Their five snippets were collected when the dataset was
   built, from Google. Ours are what SearXNG's answering engines returned
   that day (Bing and Yep for the web, Wikipedia and four academic
   indexes; Google and Brave were refusing SearXNG), scraped in full and
   filtered by the pertinence gate. "Time elapsed" below is about what
   that does.
7. **Metadata.** Their best model reads the claimant, the site and both
   dates. The pipeline gets the claim text alone, as `/verify-claim`
   does: the closest paper rows are those without "+ Meta".
8. **Out-of-context quotes.** Chequeado's claims are quotes stripped of
   speaker, place and moment ("Cayó 21% en tres años y medio"). A
   supervised model can learn that such quotes are usually *false*; a
   retrieval pipeline first has to find what the sentence is about, and
   without a date or a speaker it often cannot. `xf-65610a4bdaa1`
   ("Tenemos una deuda del 40% del PBI...", an Argentine statement) was
   judged `TRUE` from Bolivia's central bank.

## Time elapsed

The claims were made between 2008 and 2018 (English) and, for Chequeado,
on dates X-Fact did not record; the dataset was published in 2021; the
web was searched on 2026-10-13; the model's pretraining data stops in
December 2023 (Meta's Llama 3.2 model card). Six effects follow. Numbers
are the pilot's (`time_elapsed.json` beside its report) unless marked;
the Spanish `test` run's are in its own `time_elapsed.json` and quoted
where they add something.

### (a) Verdict leakage: the fact-check itself is now on the web

- **PolitiFact's own verdict page was ranked for 9 of the 24 English
  claims (38%)** and cited for 8. In every case it was the fact-check of
  that exact claim. Four of the nine came from `staging.politifact.com`,
  PolitiFact's staging server, which search engines index; the harness's
  subdomain rule caught them.
- **Chequeado's never was, for any of the 40 Spanish claims**, although
  every one of those rows lists Chequeado's verdict page and all 42 of
  those pages still answer (link rot, below). No Chequeado URL appeared
  even among the candidates. Two exact quotes sent to SearXNG by hand
  returned dictionaries and unrelated news from Bing and Yep: with Google
  refusing SearXNG, the engines left do not surface Chequeado. The leak
  the roadmap expected on the Spanish rows did not happen; on English it
  did. The Spanish `test` run confirms it: Chequeado was ranked for 0 of
  165 claims, and was a candidate for 2.
- **It inflates less than feared with this model.** Accuracy was 4 of 9
  (44%) on leaked claims against 15 of 55 (27%) on the rest; with the
  verdict in hand the 3B model still read the page as evidence, not as a
  ruling. `xf-f4007ef26c2c` (rated *false*) came back `TRUE` because the
  PolitiFact page "confirms" the figure the claim quotes;
  `xf-b374ee0b0585` (rated *true*) came back `FALSE`. A stronger model
  would read the ruling, and the leak would then decide the verdict.
- Other fact-check pages were ranked for 3 more claims (factcheck.org,
  maldita.es, and a congressional committee's "fact check" page), plus
  an unrelated Snopes check beside PolitiFact's for `xf-3005b1d6af1b`:
  12 claims in all with some fact-check among their evidence, 41.7%
  accurate against 26.9%. In the Spanish `test` run no claim's own
  verdict was found; the script's fact-check heuristic flagged 6 claims
  there, for factchequeado, RTVE and El País pages checking other claims
  and one Mexican vehicle-inspection ("verificación") page.

### (b) Temporal leakage: evidence from after the claim

- **16 of the 20 claims whose flag can be decided (80%) cited a source
  published after the claim** (`temporalLeak`); 4 did not; 44 are
  undetermined, because every Spanish row has `claimDate: none` and some
  cited sources carry no date. 38 more ranked-but-uncited sources over 19
  claims were newer than their claim.
- Accuracy was 50.0% (8 of 16) on flagged claims and 25.0% (1 of 4) on
  clear ones: the newer sources include the fact-checks of (a). Without
  either flag the pilot drops from 29.7% to 23.3% [11.6, 37.2].
- The custom set's Rule 3 forbids the annotator any evidence newer than
  the article; the pipeline has no such rule and searches without a date
  limit. On x-fact that difference is the norm, not the exception.

### (c) Drift: what was true then is not what is true now

- **20 of 64 claims pin themselves to their own present** (a heuristic
  over the claim text): 12 by relative time ("hoy", "now", "este año",
  "los últimos dos años", "lleva 8 años") and 9 by records or rankings
  ("de la historia", "the first time in history", "top five worst").
  Every relative-time Spanish claim is unresolvable as stated: X-Fact
  has no date for it, so "hoy" means 2026 to a search engine.
- No accuracy penalty shows at this size (35% on them against 27%; on
  the Spanish `test` split 36 of 165 are flagged, 33% against 16%), but
  the failure is visible claim by claim. `xf-be54e83dc79f`, "La
  Asignación Universal por Hijo hoy tiene 4 millones de beneficiarios"
  (gold `TRUE`), was checked against articles from August and September
  2026, not against the figures of the year it was said, and came back
  `FALSE` on a 2026 figure of "unas 2,5 millones" (families, where the
  claim counted children): "hoy" was read as today.
  `xf-653d580b47ae` (three cities among the five worst for asthma, 2012,
  gold `TRUE`) came back `TRUE`, from the 2024 and 2026 rankings: right
  for the wrong year. `xf-6de0b294b07b` ("1 de cada 2 niños es pobre",
  gold `TRUE`) came back `FALSE` on a Colombian figure, beside a 2026
  Argentine one: no date, no country, today's web.
- Drift cannot be measured without a dated, re-labelled copy of each
  claim, which X-Fact does not have; the heuristic finds the claims that
  announce their dependence on time, not every claim whose statistic has
  since been revised.

### (d) Link rot: the references are going

Measured on the pilot's 305 reference links on 2026-10-13
(`scripts/check_reference_links.py`, `reference_links.json`): one
request per host at a time, HEAD first, social media not requested.

- **All 120 English references are `<LINK NOT AVAILABLE>`**: X-Fact
  shipped PolitiFact's rows without them. English reference recall
  cannot be measured at all.
- Of 185 distinct Spanish links, 73 are on chequeado.com. **The 42
  verdict articles all still answer**; 14 of its 31 listing and
  source-profile pages return 404 (the site was reorganised).
- Of the 112 links elsewhere, 43 are Twitter, Facebook, Reddit or
  YouTube posts, which a status code cannot vouch for and which no web
  search returns. Of the 69 requested: 42 answer, 9 answer at a new
  address, **14 are gone** (6 return 404, 6 no longer resolve or time
  out, `telam.com.ar` among them, 2 redirect to the home page) and 4
  refused us. 5 of the 14 lost ones are in the Wayback Machine.
- 29 of the 40 Spanish claims still have at least one live reference off
  Chequeado; 4 have none left. The pipeline found **no reference link at
  all** (0% at every depth, 38 claims) and a reference *domain* among
  the candidates for 10.5%, ranked for 5.3%. Link rot is part of that
  zero; social posts and search engines that no longer reach the 2017
  web are the larger part.

### (e) Search engines favour the recent

- Of the 235 ranked sources with a date, **124 (53%) were published
  after X-Fact was built** (mid-2021), **95 (40%) after the model's
  cutoff** (December 2023), and **54 (23%) in 2026**, the year of the
  search: the most common year of all. The median ranked source is from
  2022; the median cited one from 2020.
- For the dated English claims (2008-2018): of 86 dated ranked sources,
  15 predate the claim, 12 appeared within a year after it and 59 more
  than a year after; the median source is 6.8 years newer than the
  claim. The evidence of the claim's own moment, what PolitiFact read
  then, is the minority of what search returns now.
- The Spanish `test` run, all undated claims: of 667 dated ranked
  sources, 364 (55%) postdate the dataset, 281 (42%) the model's cutoff,
  and 166 (25%) are from 2026, again the commonest year.
- Dates are the extractor's (`publishedAt`); a page's modified date can
  pass for its publication date, so these shares lean recent if
  anything.

### (f) The model's own memory

- `llama3.2:3b`'s pretraining stops in December 2023, after every pilot
  claim and every fact-check of it: the verdicts may be in its weights.
  Measured with `scripts/closed_book_probe.py` (the same client, the
  same five verdict definitions, the claim text alone):
- **No sign of remembered verdicts.** The model said it recalled a
  published fact-check for 0 of 64 claims, and closed-book it answers
  `FALSE` to 60 of 64: 18.8% accuracy, macro-F1 6.3, below the
  majority baseline's 8.0. Its 12 right answers are gold-`FALSE` claims
  its prior happens to fit. None of the pipeline's explanations cites a
  fact-check from memory: the two that name PolitiFact cite its page
  among the evidence.
- The Spanish `test` split says the same: a recalled fact-check for 0
  of 164, `FALSE` for 155, 16.5% accuracy and macro-F1 8.4.
- A 3B model is the weakest case for this effect. A larger model, or one
  trained later, should be probed the same way before its x-fact
  numbers are read.

## Recommendation: excluding fact-checker domains at retrieval time

`evaluation.md` left this open until the pilot measured it. Measured: the
row's own fact-checker was ranked for 9 of 64 pilot claims (all
English), cited for 8, and any fact-checker for 12.

**Recommended, for benchmark runs on fact-checker datasets only:** a
per-run `evidence_exclude_domains` in `PipelineThresholds` (its own goal,
its own cache bump), set for x-fact runs to the row's own site *and its
subdomains* (`staging.politifact.com`) plus the IFCN fact-checkers that
publish in English and Spanish, with `verdictLeak` still reported so
that a miss in the exclusion list shows. Without it, an x-fact number
measures lookup as much as verification, and the better the model, the
more it measures lookup: this model got only 4 of 9 leaked claims right,
a stronger one would read the ruling.

**Not recommended for production or the custom set.** A published
fact-check is legitimate, high-value evidence for a claim in today's
news, and the custom set's claims are new: a fact-check of one is not
the gold label leaking, it is the evidence a journalist would use. Keep
the exclusion a per-run threshold, off by default, and report both
numbers when it is used.

## Reproducing

```bash
cd docker   # the pilot and the Spanish test split, resumable
docker compose -f docker-compose.yml -f docker-compose.eval.yml --env-file ../backend/.env \
  run --rm --no-deps -T backend python -m src.evaluation.cli run \
  --dataset data/evaluation/xfact_en_es_pilot.jsonl --model llama3.2:3b   # or xfact_es_test.jsonl
cd ../backend
uv run python -m src.evaluation.cli report --run data/evaluation/runs/<set>/llama3.2-3b/<key> \
  --prices data/evaluation/prices.json
uv run python ../scripts/check_reference_links.py data/evaluation/xfact_en_es_pilot.jsonl \
  data/evaluation/reports/xfact_en_es_pilot/reference_links.json
LLM_TIMEOUT=180 uv run python ../scripts/closed_book_probe.py <set> llama3.2:3b \
  data/evaluation/reports/<set>/closed_book_llama3.2-3b.json
uv run python ../scripts/xfact_time_elapsed.py data/evaluation/runs/<set>/llama3.2-3b/<key> \
  data/evaluation/reports/<set>/llama3.2-3b/<key>/time_elapsed.json \
  [--links ...reference_links.json] --closed-book ...closed_book_llama3.2-3b.json
python scripts/extract_xfact_split.py backend/data/evaluation/xfact_en_es.jsonl es test \
  backend/data/evaluation/xfact_es_test.jsonl
```

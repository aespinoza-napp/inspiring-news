# The whole pipeline in AVeriTeC's web condition, on the balanced sample

Run 2026-11-24, 18:09-20:03. Each plan that changes what is searched
(`docs/decisions/evaluation.md`, "One benchmark for every approach") was run
through the whole pipeline, with live SearXNG behind the temporal gate. All
four plans ran on the same 40 claims as the verifier comparison
(`experiments/verifier/averitec-balanced.md`). Dev is read, never tuned on
(`protocol.md`): nothing here adopts a plan.

## Setup

- **Claims:** the first 40 of `averitec_dev_balanced.jsonl`, ten of each label.
  Always answering Refuted gets 10 (25.0%, macro-F1 0.100).
- **Model:** `llama3.2:3b-bench`, the pipeline's verifier, with one model call
  at a time and two claims at once.
- **Plans:** plain (`averitec_web.json`), restatement
  (`averitec_web_restatement.json`), the checkable plan
  (`averitec_web_checkable.json`) and questions (`averitec_web_questions.json`).
  Every plan drops undated sources and the scholarly engines, fetches up to 30
  pages, and takes no second look.
- **How:** `scripts/bench_averitec_web.sh 10 20 30 40`. For each ten claims the
  four plans ran one after another and shared one search cache
  (`searches-dev-balanced.jsonl`, 270 searches). A query two plans both asked
  got the same answer, so they differ by what they asked, not by the web's mood.
  Pages were still fetched live.
- **Engines:** today's allowlist (23 Nov). At 18:08 a test search was answered
  by Yahoo, Yandex and PrivacyWall; DuckDuckGo was refusing searches as a bot
  (CAPTCHA) and PubMed timed out. No searched run from before 23 Nov compares.

Every run's temporal audit says **Held**. Every claim was searched (no failed
search, no unreachable model, no invalid answer). 95-97.5% of claims reached
the model with at least one ranked source.

## Results

| Plan | Run | Right of 40 (by ten) | Accuracy [95% CI] | Macro-F1 | Kappa vs gold [95% CI] | Wrong and definite | UNVERIFIED | vs plain [95% CI] | Only it / only plain right | Whole claim s (median) | Model calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| plain | `840326b34ddb` | 11 (1, 4, 4, 2) | 27.5% [15.0, 42.5] | 0.228 | +0.033 [-0.128, +0.203] | 24 | 7 | | | 68.9 | 131 |
| restatement | `a526f686af92` | 10 (1, 4, 4, 1) | 25.0% [12.5, 40.0] | 0.207 | 0.000 [-0.163, +0.167] | 24 | 8 | -2.5 pts [-7.5, 0.0] | 0 / 1 | 77.8 | 133 |
| **checkable** | `e73baa3ba438` | **15 (2, 4, 5, 4)** | **37.5% [22.5, 52.5]** | **0.315** | **+0.167 [-0.004, +0.340]** | **19** | 11 | **+10.0 pts [0.0, +22.5]** | **5 / 1** | 79.1 | 132 |
| questions | `87c5eba33005` | 12 (2, 4, 4, 2) | 30.0% [17.5, 45.0] | 0.240 | +0.067 [-0.086, +0.231] | 21 | 10 | +2.5 pts [-10.0, +15.0] | 4 / 3 | 93.9 | 184 |
| *fixed evidence, for reference* | `1ee9810b5fa1` | 10 (3, 1, 3, 3) | 25.0% [12.5, 40.0] | 0.228 | 0.000 | 27 | 7 | | | 43.4 | 193 |

Per-class F1 (Supported / Refuted / Not Enough Evidence / Conflicting):

| Plan | Supported | Refuted | NEE | Conflicting |
|---|---|---|---|---|
| plain | 0.320 | 0.357 | 0.235 | 0 |
| restatement | 0.250 | 0.357 | 0.222 | 0 |
| checkable | 0.316 | 0.467 | 0.476 | 0 |
| questions | 0.222 | 0.438 | 0.300 | 0 |

"Wrong and definite" is a wrong TRUE or FALSE answer. Plain against the
fixed-evidence run, paired: +2.5 points [-12.5, +17.5], with 5 claims right
only on the web and 4 only on the store.

**Did the search find the annotators' sources?** Rarely. The page the
annotators used was among a claim's search results for 5-8% of claims under
every plan. It was never among the sources ranked for the model. Its site
appeared among the search results for 28-33% of claims, among the ranked
sources for 3-5%, and among the cited ones for 2.6%. A claim reached the model
with 3.4-3.6 ranked sources on the web, against 4.8 from the knowledge store.

## What 40 claims say

- **The checkable plan is the only one that changed anything.** It got 15 right
  against plain's 11, right on 5 claims plain got wrong and wrong on 1 plain got
  right. It also answered with confidence and wrongly less often (19 against 24)
  and said UNVERIFIED more (11 against 7). But its interval starts at 0
  ([0.0, +22.5]), so the resampling does not rule the difference out. This is
  dev, which is not tuned on: the plan becomes a candidate for train
  (`protocol.md`: anything that changes the pipeline is tried on train first).
- **Questions before the search changed nothing measurable**: +2.5 points
  [-10, +15], right on 4 claims plain missed and wrong on 3 plain got. It costs
  a model call per claim (184 calls against 131) and about 25 s of median
  claim time. It kept 2-3 questions for 38 claims; for the other 2 no
  question held to the claim, and it searched by the checkable plan.
- **Restatement was never applied, so it was not measured.** The restatement
  reads the claim in its article, from the headline and the opening.
  AVeriTeC's claims come with no article. Every one of the 40 came back
  "No article to read it in: checked as written", so this run is the plain plan
  again: 39 of 40 verdicts the same, and the one that differs comes from a page
  fetched live. Its search took 0 s at the median because every query it asked
  was already in the cache from the plain run. Measuring the restatement needs
  claims that come with their article: the custom set, or the app's own runs.
- **The web does no better than the knowledge store**: 11 against 10, both at
  always-Refuted's 10. With step 8's result (gpt-oss-120b 18 of 40 on the
  store's sources), the verifier is the first bottleneck. The search is the
  second: it almost never reaches the annotators' own sources.
- **Untested:** gpt-oss-120b with the checkable plan.

## Time

The four plans of each batch ran back to back on an otherwise quiet laptop:
load 0.25 at the start, nothing else running. The load of 11-16 during the run
was the run's own inference service ranking pages. A batch of ten claims took
5-9 minutes per plan, and the whole run 1 h 54 min, against the roadmap's
estimate of 6 hours. The median claim spent 3-4 s searching (except
restatement, which hit the cache), 2-3 s fetching pages and 6-10 s ranking; the
rest was the model.

Reports: `cli report`, each plan with `--compare` against plain, and plain
against the fixed-evidence run `1ee9810b5fa1`, in
`reports/averitec_dev_balanced/llama3.2-3b-bench/`.

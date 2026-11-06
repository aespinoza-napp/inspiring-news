# 4. Ranking

**The part:** the candidates are cut in two steps before the model reads them.

1. **The pre-rank funnel** keeps the best `max_evidence_per_claim` (5) by a
   first score, inside retrieval, before pages are read
   (`evidence_prerank: embedding`, over titles and snippets).
2. **`EvidenceRanker.rank`** then scores the kept pages (semantic, lexical,
   recency, reliability). It drops a second source from the same domain, and the
   **pertinence gate** (`evidence_min_pertinence`) cuts one that is on the
   subject but does not address the claim.

## Finding (4 Nov 2026, 20 train claims)

Two failures, in opposite directions:

**The right source is cut for a similar title.** fact082 (Chris Dzoba used AI
to find a 17-set Venn diagram): `github.com/dzoba` was a candidate, the
repository that holds the result, and was cut by the funnel at rank 6 of 12
(score 0.35). The five kept were his profile pages, buymeacoffee.com, me.sh,
appshunter.io and ticalc.org twice (relevance 0.48-0.53), because their titles
are his name. All five were "silent", and the verdict UNVERIFIED (gold TRUE).
The funnel scores how much a page is *about the entity*, not whether it
holds *the claim*.

**Pages that cannot answer pass the gate.** Kept and sent to the model, every
one "silent":

| Claim | Kept |
|---|---|
| fact016 (Book Bunk's figures) | bookshop.org, barnesandnoble.com, gutenberg.org, apps.apple.com |
| fact064 (8 of 11 sectors) | lnzonelink.com, abc-directory.com, theglobaltradelinks.com, Wikipedia |
| fact081 (11- and 13-set diagrams) | medium.com, simple.wikipedia.org, en.wikipedia.org, math.libretexts.org |

Each costs one model call under `verifier_answer: per_source`. On this laptop
that was about 5 calls and ~48 s of a claim's ~93 s, in the first 15 claims of
the 4 Nov baseline, before the CPU contention. None can change the verdict. Two failures are cheap to try: the gate's threshold, and the funnel's
size.

## Numbers

- Cut by the funnel: 3-14 of each claim's 13-24 candidates, every claim.
- Cut as "same domain as a higher-ranked source": 0-8 a claim. For fact011,
  7 more abc.es pages, the article's own site.
- Cut by the pertinence gate ("on-topic but does not address the claim"): 1-2
  on 4 of 20 claims (fact016, fact020, fact049, fact062). It rarely fires at
  the default threshold.

## What to try

- **Raise `evidence_min_pertinence`** (a replay): the silent pages above should
  go, saving calls. Watch confidently wrong and the number of claims left with
  too little evidence: the gate trades a wrong verdict for an honest
  UNVERIFIED.
- **`ranking_text: passages`** (a replay): the ranker judges the sentences the
  verifier will read, not the page's head. The campaign's first try.
- **A funnel that reads the snippet's figures and key terms**, not only the
  title (`evidence_prerank`; code inside retrieval, so a searched try).

## Experiments

One file per batch in [experiments/04-ranking/](experiments/04-ranking/README.md), run by
`scripts/troubleshoot.sh agent --stage 04` ([README.md](README.md), "Running it").

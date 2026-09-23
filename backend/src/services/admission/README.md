# Admission

Decides whether an enriched article is worth fact-checking at all. A module of its own, run by
`AnalysisService` **before** the fact-checker (`src/services/fact_checker/`), which no longer knows
it exists.

```
extract -> enrich -> admission -> fact-check -> store
                        |
                        +-- rejected: no search, no LLM call; stored with its reasons
```

| Piece | File | Question it answers | Needs |
|---|---|---|---|
| Topic filter | `topic_filter.py` (`TopicFilter.accepts`) | Is it about something this publication covers? | Nothing - reads the article's topic predictions |
| Positive impact | `positive_impact.py` (`PositiveImpactScorer.score`) | How constructive, inspiring and hopeful is it (0-1), and does that clear the run's minimum? | Sentiment and quality only |
| Duplicate detection | `duplicate_detector.py` (`DuplicateDetector.check` / `.remember`) | Is the same story already stored, from any outlet? | The shared `VectorRepository` |
| Composition | `admission_filter.py` (`AdmissionFilter.admit` / `.remember`) | All three, with every reason it was turned away | The above |

Why apart from fact-checking: these three judge an *article* - its topics, its tone, its neighbours in
the vector store - and none needs evidence, a web search or an LLM. The fact-checker judges *claims*
and needs all three. Separated, each can be called and replaced on its own: the corrector scores
positive impact on text that is never fact-checked, and `/verify-claim` checks a claim that has no
article to admit.

Things that must stay true:

- **All three checks always run**, even after one fails, so `AdmissionResult.reason` names every
  reason (`topic_not_relevant,not_positive_impact,duplicate_article`) - the lake stores them as
  `rejection_reasons`.
- **`remember` runs after the fact-check, never at admission.** The same Qdrant collection is the
  internal corpus `EvidenceRetriever` searches; stored earlier, the article is found as evidence for
  its own claims. `AnalysisService._check` owns that order.
- **Duplicates are matched excluding the article's own URL.** Extraction mints a new id every run, so
  re-analysing a URL would otherwise match its stored copy at similarity 1.0.
  `docs/decisions/incidents.md`.
- **The phase literals are unchanged** - `validating`, `validated`, `skipped` - because the frontend's
  `PhaseStepper` matches them.
- Thresholds (`topic_min_confidence`, `positive_impact_min_score`,
  `positive_impact_hard_fail_enabled`, `duplicate_threshold`, `relatedness_threshold`) are per call,
  like everywhere else (`docs/decisions/thresholds.md`).

The report keeps its admission fields (`topic_ok`, `positive_ok`, `duplicate`, `impact_score`,
`impact_reasons`, `failed_stage = admission_filter`) so the stored records and the `/analyze` response
did not change shape; `AnalysisService` fills them from `AdmissionResult`.

Tests: `backend/tests/services/admission/`.

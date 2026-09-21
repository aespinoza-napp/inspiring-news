# Components

Small, mostly presentational React components shared across the pages. No component
library — plain `.tsx` + the hand-written classes in `src/app/globals.css`.

| Component | Renders |
|---|---|
| `NavLinks.tsx` | The nav (Analyzer, Live, Claim Check, Enrichment, Corrector), highlighting the active route |
| `PhaseStepper.tsx` | The job-level 6-stage progress timeline (Fetch → Enrich → Validate → Fact-check → Store → Done), driven by `useAnalysisJob`'s phase-event list. Also exports `CheckIcon`, reused by `StageTimeline` |
| `StageTimeline.tsx` | The **per-claim** analog: a compact 7-dot stepper over the fact-checker's `PipelineStage`s, with a hover description and inline text for whichever stage a claim reached or stopped at. Used both per-claim and for the article-level admission-gate failure |
| `SourcesPlot.tsx` | Per-claim horizontal bar chart of every source touched (cited, ranked-but-ignored, cut at ranking, cut at retrieval) on a single-hue ordinal ramp — see the component's own doc comment for why ordinal rather than a status/red-green scheme |
| `ScoreBar.tsx` | Generic labeled horizontal score bar (0–100), reused for topics, sentiment, quality scores, and the corrector's metric cards |
| `LiveTrace.tsx` | The `/live` view of one run: per claim, the SearXNG queries, every source found with the engines behind it, the rating each received (relevance and its three factors; an unrated domain says "unrated" rather than showing the default), and the verdict with each source's stance. Built from `lib/liveTrace.ts`; only `http(s)` URLs become links |
| `TopicKeywords.tsx` | The defining keywords of each matched topic (tabs for the top 5), closest to the article first, from `TopicPrediction.keywords`. Scored by embedding similarity, so it works for Spanish articles; "2×" marks words that also appear literally. Bars are scaled to that topic's own keywords |
| `VerdictBadge.tsx` | A claim's `TRUE`/`PARTIALLY_TRUE`/`FALSE`/`MISLEADING`/`UNVERIFIED` badge — distinct "not checked" styling for claims that never reached verification at all |

`StageTimeline` and `SourcesPlot` both expect the richer per-claim fields on `ClaimResult`
(`reachedStage`, `stageNote`, `rejectedSources`, `evidence`) — see `src/lib/types.ts` and the
fact-checker's own README (`backend/src/services/fact_checker/README.md`) for where that data comes
from.

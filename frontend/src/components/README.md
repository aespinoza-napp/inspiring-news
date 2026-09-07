# Components

Small, mostly presentational React components shared between `/` and `/corrector`. No component
library — plain `.tsx` + the hand-written classes in `src/app/globals.css`.

| Component | Renders |
|---|---|
| `NavLinks.tsx` | The Analyzer / Corrector nav, highlighting the active route |
| `PhaseStepper.tsx` | The job-level 5-stage progress timeline (Fetch → Enrich → Validate → Fact-check → Done), driven by `useAnalysisJob`'s phase-event list. Also exports `CheckIcon`, reused by `StageTimeline` |
| `StageTimeline.tsx` | The **per-claim** analog: a compact 7-dot stepper over the fact-checker's `PipelineStage`s, with a hover description and inline text for whichever stage a claim reached or stopped at. Used both per-claim and for the article-level admission-gate failure |
| `SourcesPlot.tsx` | Per-claim horizontal bar chart of every source touched (cited, ranked-but-ignored, cut at ranking, cut at retrieval) on a single-hue ordinal ramp — see the component's own doc comment for why ordinal rather than a status/red-green scheme |
| `ScoreBar.tsx` | Generic labeled horizontal score bar (0–100), reused for topics, sentiment, quality scores, and the corrector's metric cards |
| `VerdictBadge.tsx` | A claim's `TRUE`/`FALSE`/`MISLEADING`/`UNVERIFIED` badge — distinct "not checked" styling for claims that never reached verification at all |

`StageTimeline` and `SourcesPlot` both expect the richer per-claim fields on `ClaimResult`
(`reachedStage`, `stageNote`, `rejectedSources`, `evidence`) — see `src/lib/types.ts` and the
fact-checker's own README (`backend/src/services/fact_checker/README.md`) for where that data comes
from.

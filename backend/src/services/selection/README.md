# Selection

Between discovery and analysis: a **candidate round** lists what the
sources of up to three topic groups published, a person or the AI
chooses at most twenty, and only those become analysis jobs. Run by
`/discover` and `POST /ingest/rounds/*`; the reasons are in
`docs/decisions/selection.md`.

```
groups -> IngestionService.discover_candidates -> ranked best first,
                                                    |  at the round's topic emphasis
                         round: the best 20 shown (candidates), the rest
                         kept (reserve); show_more -> up to 40 shown
                                                    |
              AISelector (LLM, titles + summaries) -+-> picks, scores, reasons
                                                    |
                            person ticks <= 20 -----+-> queue -> analysis jobs
```

| Piece | File | What it does |
|---|---|---|
| Mission screen | `mission_screen.py` (`MissionScreen`) | Leaves out what is not an article (podcasts, roundups, quizzes, galleries, advisories, promotions, shopping: `FORMATS`, a positive outlet's too) and candidates nearer politics, crime, disasters, war, celebrity, sport or service pages than any topic, before the per-source cap; run by `IngestionService` for rounds and `POST /ingest`, and by the labelling batch. `assess` also returns each candidate's reading (its nearness to `IMPACT` included), positive outlets' too |
| Ranking | `ranking.py` (`weights`, `score`, `rank`, `ordered`: `best_first`, `fitting_first`, `one_per_story`) | Scores each candidate from its own positive-impact reading and how well it fits the round's groups - the two splitting 0.6 by the round's **topic emphasis** (0 all positive impact, 1 all topic; `DEFAULT_TOPIC_EMPHASIS` 0.6, so 0.24 and 0.36) - its source's record in this round's screen (0.25) and its reliability rating (0.15); `discover_candidates` returns them best first, those nearer another group's topics after the rest (`otherGroup`), each story once before any story twice (`sameStoryAs`), and records how (`ranking`) |
| Rounds | `rounds.py` (`SelectionRounds`) | Every round, one JSON file each under `lake/stats/selection/` once `src/main.py` attaches the folder; the last 50 also in memory |
| AI selection | `ai_selector.py` (`AISelector`) | Scores candidates 0-10 against `DEFINITION`, ten per LLM call, and picks the best at `DEFAULT_MIN_SCORE` or more |
| The step | `selection_service.py` (`SelectionService`) | Creates a round (the best `LISTED` shown), shows more on request (up to `MAX_LISTED`), runs the AI selection in a background thread (one at a time), queues a selection and records who chose it |

Things that must stay true:

- **Nothing but the round's shown candidates can be queued**, at most
  `MAX_SELECTED`, and a round only once. The reserve is neither
  choosable nor read by the AI until `show_more` brings it into view -
  never while the AI is reading the list.
- **The ranking reads nothing new.** It works from the screen's own pass
  and the source configuration; a round where `inference/` was
  unreachable is ranked by its sources alone (`rank.news: null`), never
  dropped or left unsorted.
- **The topic emphasis is per call and per round.** It comes with the
  request (`topicEmphasis`), goes down as an argument (`create_round` ->
  `discover_candidates` -> `rank`), and never onto an instance: these
  services are shared by every request. None means the default. It is a
  request parameter like `groups`, not a `PipelineThresholds` field
  (`docs/decisions/selection.md`, "Positive impact or the topic").
- **No topic signal, no emphasis.** With no group asked for, or nothing
  read, a round is ranked at `WITHOUT_TOPIC` (0) whatever was asked, and
  `ranking.topicEmphasis.applied` is null - it must not look as if the
  topic had been weighed.
- **The weights sum to 1 at every emphasis**: the emphasis only moves
  weight between the story's two parts. A round records the four it used
  (`ranking.weights`) and the emphasis asked for, applied and the default.
- **The AI selection is not told the emphasis**, by decision: it reads a
  list the emphasis already made topic-first, and judges positive impact
  within it.
- **`selectedBy` and the agreement counts are computed here**, from the
  AI's recorded proposal - never taken from the client. They are what
  `src/evaluation/experiments.py selection` reports.
- **An unreachable model fails the selection** (`status: failed`) rather
  than returning picks from part of the list.
- **An unreachable `inference/` leaves nothing out** and the round says
  `screen.status: unavailable` - a screen that did not run must not look
  like one that passed everything.
- **Batches keep their order** (`bounded_map`): batch k's answer is
  matched to batch k's candidates by number. Anything the model got wrong
  - a number outside the list, an item scored twice, a score that is not
  a number - is left unscored, never guessed.
- The LLM call goes through `LLMClient.complete_json`, so the LLM permit
  is held around the leaf call only; its timeout is
  `AI_SELECTION_TIMEOUT`, not `LLM_TIMEOUT`.

Tests: `backend/tests/services/selection/`.

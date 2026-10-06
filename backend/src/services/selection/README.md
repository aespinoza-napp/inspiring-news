# Selection

Between discovery and analysis: a **candidate round** lists what the
sources of up to three topic groups published, a person or the AI
chooses at most twenty, and only those become analysis jobs. Run by
`/discover` and `POST /ingest/rounds/*`; the reasons are in
`docs/decisions/selection.md`.

```
groups -> IngestionService.discover_candidates -> round (candidates)
                                                    |
              AISelector (LLM, titles + summaries) -+-> picks, scores, reasons
                                                    |
                            person ticks <= 20 -----+-> queue -> analysis jobs
```

| Piece | File | What it does |
|---|---|---|
| Mission screen | `mission_screen.py` (`MissionScreen`) | Leaves out candidates nearer politics, crime, disasters, war, celebrity, sport or service pages than any topic, before the per-source cap; run by `IngestionService` for rounds and `POST /ingest` |
| Rounds | `rounds.py` (`SelectionRounds`) | Every round, one JSON file each under `lake/stats/selection/` once `src/main.py` attaches the folder; the last 50 also in memory |
| AI selection | `ai_selector.py` (`AISelector`) | Scores candidates 0-10 against `DEFINITION`, ten per LLM call, and picks the best at `DEFAULT_MIN_SCORE` or more |
| The step | `selection_service.py` (`SelectionService`) | Creates a round, runs the AI selection in a background thread (one at a time), queues a selection and records who chose it |

Things that must stay true:

- **Nothing but the round's own candidates can be queued**, at most
  `MAX_SELECTED`, and a round only once.
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

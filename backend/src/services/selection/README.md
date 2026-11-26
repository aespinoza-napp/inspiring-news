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
                                                    |
          person records <= 5 (blind or not) -------+-> AI asked for <= 5 -> comparison
                                                         + both sides' photos kept
```

| Piece | File | What it does |
|---|---|---|
| Mission screen | `mission_screen.py` (`MissionScreen`) | Leaves out what is not an article (podcasts, roundups, quizzes, galleries, advisories, promotions, shopping: `FORMATS`, a positive outlet's too) and candidates nearer politics, crime, disasters, war, celebrity, sport or service pages than any topic, before the per-source cap; run by `IngestionService` for rounds and `POST /ingest`, and by the labelling batch. `assess` also returns each candidate's reading (its nearness to `IMPACT` included), positive outlets' too |
| Ranking | `ranking.py` (`weights`, `score`, `rank`, `ordered`: `best_first`, `fitting_first`, `one_per_story`) | Scores each candidate from its own positive-impact reading and how well it fits the round's groups - the two splitting 0.6 by the round's **topic emphasis** (0 all positive impact, 1 all topic; `DEFAULT_TOPIC_EMPHASIS` 0.6, so 0.24 and 0.36) - its source's record in this round's screen (0.25) and its reliability rating (0.15); `discover_candidates` returns them best first, those nearer another group's topics after the rest (`otherGroup`), each story once before any story twice (`sameStoryAs`), and records how (`ranking`) |
| Rounds | `rounds.py` (`SelectionRounds`) | Every round, one JSON file each under `lake/stats/selection/` once `src/main.py` attaches the folder; the last 50 also in memory |
| AI selection | `ai_selector.py` (`AISelector`) | Scores candidates 0-10 against `DEFINITION`, ten per LLM call, and picks the best at `DEFAULT_MIN_SCORE` or more |
| The step | `selection_service.py` (`SelectionService`) | Creates a round (the best `LISTED` shown), shows more on request (up to `MAX_LISTED`), runs the AI selection in a background thread (one at a time), queues a selection and records who chose it; records a person's own choice of at most `COMPARED` (5) to compare with the AI's (`record_person_selection`, `compare`, `kappa`) |
| Feedback | `feedback.py` (`SelectionFeedback`, `Feedback`) | What the person marked not for us and what they chose, per edition (`lake/stats/selection/feedback/examples.json`): a marked article never offered again, a blocked site left out, stories like the marked ones lowered from 3 + 3 examples by a share of their *lean* (nearer the marked average than the chosen one), left out over a lean of 0.08 from 40 + 20 |
| Judgements | `judgements.py` (`SelectionJudgements`, `build_dataset`) | Every judgement made here as one dataset in the lake (`lake/judgements/`): `events.jsonl` appended as each is made (sent, recorded, not for us, undone, forgotten, unblocked, the AI's scores, and the list each was made from), `dataset.jsonl` and `dataset.csv` rebuilt from it alone - one row per shown candidate of a judged round, labelled chosen / not_for_us / not_chosen. The rounds from before it backfilled once at startup; `GET /ingest/judgements[/events\|/dataset]` |
| Reasons | `reasons.py` (`reasons_for`, `cleaned`, `reject_reasons_for`) | Why a person may say they chose a story, per edition (several at once): offered by `GET /ingest/sources` as `pickReasons`, kept as codes on a recorded choice and on what is sent; an unknown code is refused |
| Photos | `photos.py` (`PhotoKeeper`) | Copies the photos of a compared round's picks beside it (`lake/stats/selection/photos/<id>/`), through the URL guard, kept only when their bytes are a JPEG, PNG, GIF, WebP or AVIF of 5 MB at most |

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
- **Nothing is queued or recorded while the AI reads the round** (409),
  and the AI is not started on a round being sent: its picks would land
  on a selection recorded as the person's alone.
- **A person's recorded choice is at most `COMPARED`, once, and its
  `blind` is worked out here** (no finished AI proposal at that moment).
  From then on `more` is refused, so the AI reads the list the person
  chose from, and is asked for at most `COMPARED` too.
- **The person's feedback is per call and per edition.** `create_round`
  builds it and passes it down (`discover_candidates(feedback=)` ->
  `rank(feedback=)`), never onto an instance; nothing taught, nothing
  asked of `inference/`. It only lowers the story part, so the weights
  still sum to 1; leaving out waits for `LEAVE_OUT_MINIMUM`. A marked
  candidate stays in its round's list and cannot be queued or recorded.
- **A judgement is logged after its round is saved, and fail-soft**
  (`judgements.py`): `events.jsonl` is only ever appended to, and the
  dataset is rebuilt from it alone. Nothing the step decides reads it.
- **A candidate's `image` is a link, never fetched at discovery.** Only a
  compared pick's photo is copied, and only what its bytes prove is an
  image.
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

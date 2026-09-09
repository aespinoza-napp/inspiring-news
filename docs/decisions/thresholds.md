# Thresholds

> Extracted from CLAUDE.md so it is read when you work on thresholds
> and not on every session. Referenced from CLAUDE.md's Navigation table.


Every tunable threshold lives in `src/config/thresholds.py`, not in the
component that uses it:

- `PipelineThresholds` — the *effective* set for one run. Every field
  defaults from `settings` (i.e. from `.env`).
- `ThresholdOverrides` — the *request* shape, every field optional.
- `PipelineThresholds.resolve(overrides)` merges them: whatever the
  caller set wins, everything else falls back to the environment.

Callers send overrides on the `thresholds` field of `POST /analyze` and
`POST /analyze/jobs`; anything omitted uses the configured default. Jobs
resolve on the request thread, so a bad value is a 422 on the POST rather
than a job that is accepted and then fails where only polling reveals it.
`ThresholdOverrides` is `extra="forbid"` and range-bounded, so a typo'd
knob or a nonsensical value is rejected instead of silently ignored.

**Never write `MIN_X = settings.MIN_X` in a class body.** That is
evaluated once when the module is first imported, which freezes the value
for the life of the process — it is why `ClaimSelector.MAX_CLAIMS`,
`ConfidenceScorer.MIN_EVIDENCE`, `DuplicateValidator.DUPLICATE_THRESHOLD`
and friends could not be overridden at all, and why the tests for them had
to reach in and reassign the attribute (so they never covered the path a
real caller takes). Thresholds are passed **per call** —
`validate(article, thresholds)`, `process(text, threshold)`,
`select(claims, thresholds)`, `run(article, thresholds=...)` — because the
components are long-lived singletons (see `container.py`) shared by every
request, so a per-run value cannot live on the instance. `None` everywhere
means "use the defaults", so every one of those parameters is optional and
existing call sites keep working.

Two consequences worth knowing:

- **The analysis cache keys on the thresholds too** (only those differing
  from the defaults, so a plain run still keys on the URL alone). The same
  URL under a different admission bar is a different analysis; serving the
  default run's cached answer would make it look like the override had
  been applied when it never was.
- **The lake records them.** `Lineage.threshold_overrides` carries exactly
  what a run changed, so a stored record's numbers stay reproducible — the
  same article yields a different verdict under a different bar.

Ranking and confidence *weights* (`RANKING_*`, `CONFIDENCE_*`) are
deliberately environment-only, not per-request: each group must sum to
1.0, and letting a caller set one member alone would silently produce a
scoring function that no longer normalises.


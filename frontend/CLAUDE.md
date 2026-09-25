# Frontend

Loaded when working under `frontend/`. Nothing here needs the backend's
fact-checking history — that is the point of the split.

```bash
npm install
npm run dev      # http://localhost:3000
npm run build
npx tsc --noEmit # or ./scripts/check.sh frontend from the repo root
```

`npm run lint` is not configured (it drops into the ESLint setup prompt).
The typecheck is the gate.

## Shape

Seven pages. Every one talks to the backend **only** through the
server-side route handlers in `src/app/api/`, which keeps `BACKEND_URL`
off the client. See `.env.local.example` — it is `http://127.0.0.1:8000`,
not `localhost`, because Node can resolve `localhost` to the IPv6
loopback first and fail to reach uvicorn's IPv4-only default.

| Page | What it does |
|---|---|
| `/` (`app/page.tsx`) | Paste article URLs; each gets a `JobCard` driven by `lib/useAnalysisJob.ts`. Shows the topic radar next to the *topic's own keywords* (`TopicKeywords`), not the article's yake keywords. Claims appear as rows the moment they are selected and each fills in with its own verdict as it finishes — it folds events with `lib/liveTrace.ts`, the same fold `/live` uses, rather than matching the phase literals a second time |
| `/live` | A second screen: every job the backend is running or ran recently, from any client. Per claim: the SearXNG queries, every source found and the engines behind it, the rating each received, and the verdict — filling in as events arrive. `lib/useLiveJobs.ts` polls `GET /api/jobs`; `lib/liveTrace.ts` folds events into that view |
| `/claim` | One claim → verdict, evidence, sources rejected, and the LLM's pre-recalibration answer |
| `/enrich` | URL and/or text → what was extracted (title, author, date, body, each tagged typed-in / extracted / missing), then topics, keywords, entities, claims, sentiment, quality, embedding shape |
| `/corrector` | Text → the 7 corrector metrics |
| `/scraper` | A **source health panel** (`components/SourceProbePanel.tsx`: starts `POST /api/scraper/probe`, polls `GET` every 2s only while it runs; up / degraded / down per source, feed vs topic-page links, a sample of extractions, and a banner when SearXNG's engines are down). An **ingest panel** (`components/IngestPanel.tsx`: pick sources and articles per source; the button states the most analyses it can queue; shows the last run). Then every page fetch the backend has made, per domain: requests, success rate, why the rest failed (too short / no content / HTTP error / timeout / connection / blocked), last request and last failure. Below that, the articles actually stored in the lake per domain (scraped vs unique, title/author/date coverage, what became of them) and a per-day chart (`components/DailyBars.tsx`). Polls `GET /api/scraper/stats` and `/api/scraper/articles` every 10s, `cache: "no-store"` like the job routes |
| `/sources` | A health check of every source YAML, disabled ones included: discovery (links found, via feed or homepage, or why none), then 1-5 sample articles each run through the real extraction cascade - outcome, strategy, title / author / date (a missing one shown as **missing**), body length, time. Verdict per source: working / partial / broken; a Re-check button per source. Nothing is stored or analysed. `POST /api/sources/check`, behind the storage key |

`lib/types.ts` mirrors the backend's response shapes exactly — keep it in
sync when a backend response changes.

## Two things that must not be removed

Both are real incidents; `docs/decisions/incidents.md` has the detail.

1. **`src/app/api/jobs/[jobId]/route.ts` must keep `cache: "no-store"`.**
   Next.js 14 caches server-side `fetch()` GETs by default, so every
   1-second poll after the first was served a stale response. The UI sat
   on the first phase forever while the backend had already finished.
2. **In `useAnalysisJob.ts`, the `setInterval` after the first
   `await pollOnce(...)` must stay guarded by `cancelled`.** Otherwise a
   cleanup firing while that poll is in flight leaks an interval nothing
   will ever clear.

Neither is covered by a test. They are held in place by comments.

The same two rules apply to the Live screen: `app/api/jobs/route.ts`'s GET
is `cache: "no-store"`, and `useLiveJobs` reschedules its timer only behind
`cancelled`.

## Per-claim events interleave

The backend fact-checks an article's claims **concurrently**, so one
claim can be judged while another is still searching. Anything reading
`PhaseEvent[]` has to be order-insensitive per claim. Two things from the
backend make that workable, and both must keep being used:

- **`claims_selected` carries the whole claim set** (`claims: [{index,
  text, anchorScore}]`) before any claim has been checked. Create the
  rows from it. Rows created from whichever per-claim event arrived first
  reshuffle themselves as the run progresses.
- **Every per-claim event carries `claimIndex`** as well as `claim`.
  `liveTrace.ts` reads the index first and falls back to the text,
  because runs replayed out of the journal may predate the index.

See `docs/decisions/concurrency.md`.

## PhaseStepper

`components/PhaseStepper.tsx` renders the job's phase events as six
stages: Fetch → Enrich → Validate → Fact-check → Store → Done. It matches
backend phase names as **string literals**, so a renamed phase silently
breaks a stage. The Store stage tracks staged writes: `storing` /
`stored_layer` fire per layer (four writes in a clean run — raw,
processed, processed again with the report, exploitation) and the final
`stored` event carries the editorial outcome.

It works from the *set* of phases seen and counts `claim_checked` events,
which is why concurrent claims did not break it. Its one ordered read is
the status line: while claims are in flight that becomes "checking N
claims, M done", because there the last event belongs to whichever claim
emitted most recently and describes nothing.

## The Live screen

`lib/liveTrace.ts` is a pure fold from `PhaseEvent[]` to a per-claim trace.
It matches phase names as string literals against the backend, like
`PhaseStepper`, and is deliberately tolerant: a missing field leaves a gap
rather than throwing, because the events also come out of the journal and a
viewer that crashes on one odd event shows nothing for a run still going.

Source URLs come from web search results, so `components/LiveTrace.tsx`
only turns `http(s)` URLs into links (`safeHref`). Keep it that way.
`reliabilityKnown: false` is rendered as "unrated" — it is the default for
an unrated domain, not a rating.

## Design system

A single hand-written `src/app/globals.css`: CSS variables, light/dark
via `prefers-color-scheme`, `prefers-reduced-motion` respected. **No UI
library, no Tailwind**, and no dependencies beyond `next`/`react`/
`react-dom`. Keep it that way unless there is a real reason not to.

## Known gap

Per-run thresholds are plumbed but unreachable: `useAnalysisJob` accepts
`ThresholdOverrides` and no page passes any, and `StorageInfo` /
`ResolvedThresholds` are declared and never rendered. The backend feature
is complete; the UI for it does not exist.

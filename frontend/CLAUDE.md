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

Four pages. Every one talks to the backend **only** through the
server-side route handlers in `src/app/api/`, which keeps `BACKEND_URL`
off the client. See `.env.local.example` — it is `http://127.0.0.1:8000`,
not `localhost`, because Node can resolve `localhost` to the IPv6
loopback first and fail to reach uvicorn's IPv4-only default.

| Page | What it does |
|---|---|
| `/` (`app/page.tsx`) | Paste article URLs; each gets a `JobCard` driven by `lib/useAnalysisJob.ts` |
| `/claim` | One claim → verdict, evidence, sources rejected, and the LLM's pre-recalibration answer |
| `/enrich` | Text → topics, keywords, entities, claims, sentiment, quality, embedding shape |
| `/corrector` | Text → the 7 corrector metrics |

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

## PhaseStepper

`components/PhaseStepper.tsx` renders the job's phase events as six
stages: Fetch → Enrich → Validate → Fact-check → Store → Done. It matches
backend phase names as **string literals**, so a renamed phase silently
breaks a stage. The Store stage tracks staged writes: `storing` /
`stored_layer` fire per layer (four writes in a clean run — raw,
processed, processed again with the report, exploitation) and the final
`stored` event carries the editorial outcome.

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

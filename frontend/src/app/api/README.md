# API routes (server-side proxy)

Thin proxies to the backend — every one just forwards the request to `BACKEND_URL` and relays the
response. Their only real job is keeping `BACKEND_URL` off the client (see `CLAUDE.md`). None of these
contain business logic; if something looks wrong in a response, the bug is almost certainly in the
backend (`backend/src/api/routes.py`), not here.

| Route | Backend endpoint | Used by |
|---|---|---|
| `analyze/route.ts` | `POST /analyze` | Not currently used by either page — the synchronous, blocks-until-done endpoint. Kept for direct API use |
| `jobs/route.ts` | `POST /analyze/jobs` | `useAnalysisJob` — starts a background job, returns `{ jobId }` immediately |
| `jobs/route.ts` (GET) | `GET /analyze/jobs` | `useLiveJobs` (the `/live` page) — every job running or recent. **Also `cache: "no-store"`.** |
| `jobs/batch/route.ts` | `POST` / `GET /analyze/jobs/batch` | `useBatchAnalysisJobs` — the Analyzer's bulk mode |
| `jobs/[jobId]/route.ts` | `GET /analyze/jobs/{jobId}` | `useAnalysisJob` — polled every second for progress. **Must keep `cache: "no-store"`** on its `fetch()` — see `CLAUDE.md`, this bit the project once already (stale cached responses made the UI look permanently stuck) |
| `correct/route.ts` | `POST /correct` | `/corrector` page |
| `verify-claim/route.ts` | `POST /verify-claim` | `/claim` page |
| `enrich/route.ts` | `POST /enrich` | `/enrich` page |
| `graph/[...path]/route.ts` | `GET /graph/{schema,presets,articles,related}`, `POST /graph/{query,sync}` | `/graph` page. An allowlist, not a blind catch-all. GETs are `cache: "no-store"` |

**Every route sends the API key.** Each file has a `headers(json)` that adds `X-API-Key` from
`STORAGE_API_KEY` when the server has one, and every `fetch()` passes `headers: headers(...)`. The
backend requires the key on everything but `/healthz`, `/metrics` and polling a job by id once it
is set, and production always sets it; the key is sent to the open ones too, so closing them later
is a backend-only change. A new route that skips it works on a laptop with no key and answers 401
on the server. `backend/tests/api/test_api_key.py` reads these files and fails on a route that does
not follow the pattern.

All of them use `127.0.0.1`, never `localhost`, for `BACKEND_URL`'s default — see the comment in
`analyze/route.ts` for why (Node can resolve `localhost` to the IPv6 loopback first, which fails
against uvicorn's IPv4-only default).

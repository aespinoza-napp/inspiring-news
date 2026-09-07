# API routes (server-side proxy)

Thin proxies to the backend — every one just forwards the request to `BACKEND_URL` and relays the
response. Their only real job is keeping `BACKEND_URL` off the client (see `CLAUDE.md`). None of these
contain business logic; if something looks wrong in a response, the bug is almost certainly in the
backend (`backend/src/api/routes.py`), not here.

| Route | Backend endpoint | Used by |
|---|---|---|
| `analyze/route.ts` | `POST /analyze` | Not currently used by either page — the synchronous, blocks-until-done endpoint. Kept for direct API use |
| `jobs/route.ts` | `POST /analyze/jobs` | `useAnalysisJob` — starts a background job, returns `{ jobId }` immediately |
| `jobs/[jobId]/route.ts` | `GET /analyze/jobs/{jobId}` | `useAnalysisJob` — polled every second for progress. **Must keep `cache: "no-store"`** on its `fetch()` — see `CLAUDE.md`, this bit the project once already (stale cached responses made the UI look permanently stuck) |
| `correct/route.ts` | `POST /correct` | `/corrector` page |

All four use `127.0.0.1`, never `localhost`, for `BACKEND_URL`'s default — see the comment in
`analyze/route.ts` for why (Node can resolve `localhost` to the IPv6 loopback first, which fails
against uvicorn's IPv4-only default).

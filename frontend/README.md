# Frontend

Next.js 14 (App Router, TypeScript) internal tools for the backend. Not the
user-facing app — that is Phase 5 of [`docs/roadmap.md`](../docs/roadmap.md) and
does not exist yet.

**The working reference is [`CLAUDE.md`](CLAUDE.md) in this directory.** The
request/response contract that used to be written out here went out of date; the
source of truth is [`src/lib/types.ts`](src/lib/types.ts), which mirrors the
backend.

## Pages

| Page | What it does |
|---|---|
| `/` | Paste article URLs and follow each run phase by phase |
| `/live` | A second screen: every run in progress or recent, from any client — what was searched, which sources came back, how each was rated, the verdict |
| `/claim` | Verify one claim on its own |
| `/enrich` | Run only the NLP stage over pasted text |
| `/corrector` | Score a text on 7 editorial metrics |

Every page talks to the backend only through the server-side route handlers in
`src/app/api/`, which keeps `BACKEND_URL` out of the browser.

## Run

```bash
npm install
cp .env.local.example .env.local   # BACKEND_URL, and STORAGE_API_KEY if the backend sets one
npm run dev                        # http://localhost:3000
npx tsc --noEmit                   # the typecheck — the only automated gate
```

There is no linter configured and no test runner.

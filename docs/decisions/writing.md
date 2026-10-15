# Writing: from an analysed article to a published one

**Started 2026-10-15**, on `feature/newsroom-writing`. Out of the Oct 14
feature freeze by the author's decision: the roadmap had writing at P2
("Writing from verified sources", P1.3's design), behind every P0 and P1
item.

The newsroom's last steps. After an article has been analysed, a person
asks for a new article on the same story: the system finds news related
to it, writes a draft from those sources and the fact-checks, in
Catalan, Spanish or English, following the person's indications. The
corrector reviews it; if the metrics fall short, the person can have it
rewritten; once satisfied, they publish it. Today only to the web - this
app's own public reader. TikTok and Instagram are channels with nothing
behind them yet.

```
analysed article ──> write (related news + fact-checks + indications)
                          │
                          v
                     draft ──> review (corrector metrics, proposed corrections)
                       ^            │
                       │   below target? ──> rewrite (guided by the failing metrics)
                       │            │
                       └── edit ────┘
                                    │ satisfied
                                    v
                              approve ──> publish (web; TikTok, Instagram later)
```

## The contract

Built first, so the stages could be built at once. Each stage fills its
own fields and leaves the others alone.

- **One shape:** `ArticleDraft` (`backend/src/models/writer/draft.py`),
  mirrored in `frontend/src/lib/drafts.ts`. snake_case in Python,
  camelCase on disk and over the API (`by_alias=True`).
- **One store:** `DraftStore` (`backend/src/services/writer/draft_store.py`),
  one JSON file per draft under `settings.DRAFTS_PATH` (beside the lake,
  not in it). Every change is `update(id, change)`, a read-modify-write
  under one lock. `revise()` replaces the content and keeps history: the
  outgoing revision keeps its review, the draft's `review` is cleared.
- **Background work:** `run_in_background(id, busy, work)` marks the
  draft `busy`, runs `work` on a thread, keeps a failure in `error`,
  clears `busy`. A second step on a busy draft is a 409. A restart
  clears a stale `busy` with "Interrupted". Tests pass `wait=True`.
- **Citations:** the body cites `[n]`, 1-based into `sources`, which is
  never reordered once the draft exists.
- **Status** is editorial: `draft` → `approved` → `published`. What is
  running is `busy`. A person's edit sends an approved draft back to
  `draft`, and is refused on a published one.
- **Routes:** one module per stage, registered in `main.py` -
  `draft_routes.py` (list, get, edit; the writer adds create),
  `review_routes.py`, `publish_routes.py`; the rewrite stage adds its own.
  Everything under `/drafts` takes the API key.
- **Frontend:** one proxy, `app/api/drafts/[[...path]]/route.ts`, with
  every stage's action already allowlisted (`review`,
  `accept-correction`, `rewrite`, `approve`, `publish`, `unpublish`,
  `content`). `/drafts` lists and starts drafts; `/drafts/[id]` polls
  while `busy` and renders one component per stage, each taking
  `DraftStageProps` (`components/drafts/`).
- **Settings:** `DRAFTS_PATH`, `WRITER_LLM_MODEL` and
  `CORRECTOR_LLM_MODEL` (None = `LLM_MODEL`), `WRITER_LLM_TIMEOUT`
  (300 s). Infrastructure, in `NON_THRESHOLD_SETTINGS`. Targets a run
  can tune go in `PipelineThresholds`.
- **Tests:** `create_draft()` in `tests/factories.py`; the `draft_store`
  fixture puts a store over `tmp_path` in the container.

`/drafts` is behind the site password; only `/reader/*` is public
(Caddy's `@reader`). So nothing that starts a draft can live on the
reader's pages.

## Writing

*To be filled by the writer stage.*

## Review

*To be filled by the review stage.*

## Rewriting

*To be filled by the rewrite stage.*

## Publishing

*To be filled by the publishing stage.*

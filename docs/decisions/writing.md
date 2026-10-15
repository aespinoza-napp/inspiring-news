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
- **One body renderer:** `components/drafts/ArticleBody.tsx`, for the
  draft and the public page alike. React elements, never HTML (the text
  is a model's and the public sees it); `[n]` links to `#source-n`, the
  id every source list gives its n-th source.
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

**Built 2026-10-15.** Once a person is satisfied, they approve the text
and publish it. The web - this app's own public reader - is the one
channel that publishes; TikTok and Instagram are listed and say what
each would need.

### The lifecycle

| Action | From | To | Refused (409) when |
|---|---|---|---|
| `POST /drafts/{id}/approve` | `draft` (or `approved`: no change) | `approved` | busy, or published. 422 with no title or body |
| `POST /drafts/{id}/publish` `{channels}` | `approved` | `published` | busy, not approved, already published, or a channel unavailable |
| `POST /drafts/{id}/unpublish` | `published` | `approved` | busy, or not published |
| a person's edit (`draft_routes.py`) | `approved` | `draft` | published (unpublish first) |

- **Approval is not gated on a review.** The panel warns when
  `draft.review` is null - the current text has none - and the person
  decides. A review describes the text it read; an editor may know the
  text is fine.
- **Publishing checks every channel before using any.** An unknown name
  is a 422, an unavailable channel a 409 with its reason, and in both
  cases nothing is written. If a channel fails half way, the ones that
  went out are taken back down; if the draft cannot be saved after the
  page went out, the page is taken down too (tested). All or none.
- **`published` lists where the article can be read now.** Each channel
  adds a `PublishRecord(channel, at, url)`, replacing that channel's
  earlier one; unpublishing clears them. A record that outlived its page
  would say "published" about something that is not. The history of
  publications is not kept (see the gaps below).
- **Unpublishing leaves the draft approved,** not draft: the text did not
  change. It can be published again as it is, or edited - which sends it
  to `draft`, so the new text takes a new approval.
- **Re-publishing replaces the snapshot.** The address stays the same
  (`/reader/stories/<draft id>`), and `publishedAt` is the new
  publication's: what is public is a new text.
- **Synchronous, not `run_in_background`.** The only channel that works
  writes one small file; a thread would add a busy state, a poll and a
  race for milliseconds. It runs under the store's lock and refuses a
  busy draft, so it cannot interleave with a review or a rewrite. A
  channel that renders media and posts to someone else's API is minutes
  of work: that is when publishing moves onto
  `run_in_background(id, "publishing", ...)`, which `Busy` already
  names.

### What the public sees: a snapshot

`WebPublisher` (`backend/src/services/publishing/web.py`) writes one
`PublishedStory` per article to `DRAFTS_PATH / "published" /
<id>.json`, beside and renamed over as `DraftStore.save` does.
`DraftStore.list` reads only its own directory's `*.json`, so the
snapshots are never taken for drafts. The public endpoints read the
snapshot, never the draft: a draft goes on changing after it is
published (a background step finishing, a field a later stage adds), and
the page must show what a person published until they publish again or
take it down.

**Built from an allowlist** (`services/publishing/story.py`), not by
dumping the draft and excluding what is private. `ArticleDraft` grows
with every stage; an exclude list would publish whatever the next stage
adds. A new draft field is private until it is copied in by name.

- In: the id, the analysed article's reader id, the language, the title,
  subtitle and body, the sources (url, title, domain, origin, date - in
  the draft's order, which the citations depend on), the fact-checks,
  the metadata (slug, SEO description, keywords, topic, tags),
  `publishedAt`, and the disclosure.
- Out: the instructions, the revisions, the review, `error`, `busy`,
  `status`, the records - and each source's `excerpt`, which is the
  text of somebody else's page; the reader never republishes that
  either (`services/reader/views.py`).

### The AI disclosure: shown, with the model's name

Every snapshot carries `disclosure: {aiWritten, models, humanEdited}`:
every model whose text became the article (the writer, then any rewrite
or accepted correction), and whether a person edited it. The story page
says so **before** the text - "Written by an AI model (llama3.2:3b)
from the sources listed below, then approved for publication by a
person on our team" - and each card says "Written with AI · approved by
a person".

Recommended and implemented, for four reasons:

1. The EU AI Act's Article 50(4), applicable since 2 August 2026, asks
   whoever publishes AI-generated text "with the purpose of informing the
   public on matters of public interest" to disclose it. It exempts text that has
   undergone human review or editorial control **when a person holds
   editorial responsibility** for it. Every article here is approved by
   a person, but whether this site meets the exemption - a named
   publisher, editorial responsibility - is a judgement nobody has
   made. Disclosing does not depend on it.
2. The reader already names the model that **checked** an article
   (`checkedWith.model`). Naming the one that **wrote** one is the same
   rule.
3. The site's point is that a reader can see what a text rests on: its
   sources, the checks behind it - and what wrote it.
4. It costs one sentence. A model name is jargon to most readers, which
   is why it comes after "an AI model", not instead of it.

### Routes and pages

- `GET /publishing/channels` (key): each channel, available or not, and
  why. **Not `/drafts/channels`**: `draft_routes.py`'s
  `GET /drafts/{draft_id}` is registered first and matches any single
  segment; FastAPI answers 422 on its id pattern rather than falling
  through (`test_the_channels_are_not_under_drafts_...`). So it has its
  own proxy, `app/api/publishing/channels/route.ts`, behind the site
  password; the drafts proxy forwards only `/drafts/<16 hex>`.
- `POST /drafts/{id}/approve|publish|unpublish` (key, each declares
  `require_storage_key` itself: the router has none, so the public
  routes below can share the module).
- `GET /reader/stories` and `GET /reader/stories/{id}`: **open**, in
  `OPEN_ENDPOINTS`, like `/reader/articles`. Cards (no body) newest
  first, filterable by `topic` and `language`, paged and faceted like
  the reader feed; one story whole. Read from the files on every
  request, without the reader's index: a few stories a day, a few KB
  each.
- `/reader/stories/[id]` is **rendered on the server**, so its text and
  `generateMetadata`'s title, description and Open Graph tags are in the
  HTML, and a taken-down story answers a real 404. It is the one page
  that reads the backend itself (`loadStory.ts`, with the proxies'
  `headers()` and `no-store`) rather than through a proxy. It shows a
  plain message on failure, never the backend's address.
- `/reader` lists the published articles above the checked-news feed
  (`components/reader/StoryList.tsx`), outside its filters - a story's
  topic is its own, and it may be Catalan - and not at all while none
  is published.
- `components/drafts/PublishPanel.tsx`: Approve, the channel checkboxes
  (TikTok and Instagram disabled, "Not available yet", with the
  reason), Publish, Unpublish (confirmed), the records with a link to
  the public page. Disabled while the draft is busy.

**Caddy needs no change.** Every new public path is under `/reader/*`
or `/api/reader/*`, which `@reader` already serves without the password;
`/api/publishing/channels` and `/drafts/*` stay behind it.
`test_deployment_config.py` holds the list of public proxies, and gained
`api/reader/stories` on purpose. Two comments still say the reader has
"two proxies" (the Caddyfile's `@reader` block, and "The front door" in
`deployment.md`); it has three now, and the story page reads the backend
from the server. Text only, nothing to change in behaviour.

### TikTok and Instagram: what each would need

Both publish **media** with a caption; neither takes text alone. So the
article would first have to become media - a short video, or a carousel
of cards whose caption links back to the web page - a stage that does
not exist. `services/publishing/social.py` makes no network call and
holds no credential; there is no setting that turns either on.

- **TikTok**, Content Posting API (read 2026-10-15,
  developers.tiktok.com/doc/content-posting-api-get-started and
  .../content-posting-api-reference-direct-post): a developer app
  approved for the `video.publish` scope; the creator's OAuth token
  through Login Kit; the video uploaded, or pulled from a URL prefix or
  domain verified with TikTok (photos only from a verified domain); a
  `privacy_level` from the creator's own options; captions up to 2,200
  characters. Until TikTok audits the app, every post is private.
- **Instagram**, content publishing through the Graph API (read
  2026-10-15, developers.facebook.com/docs/instagram-platform/content-publishing/):
  a professional (business or creator) account; a Meta app with
  `instagram_business_content_publish` (Instagram Login) or
  `instagram_content_publish` (Facebook Login) at Advanced Access, and
  the account's token; each image a JPEG at a public URL when the
  container is created, then published in a second call; up to 100
  posts in 24 hours.

### Gaps

- **A model step that changes `content` must send an approved draft
  back to `draft`,** as a person's edit does. Publishing trusts
  `status`: a rewrite or an accepted correction that left an approved
  draft approved would let text nobody approved go public. For the
  review and rewrite stages to hold.
- **Adding a channel to a published article means unpublishing first,**
  since publishing requires `approved`. Moot while the web is the only
  channel.
- **No record of past publications,** and no correction note on a page
  published again with a changed text. The records say where the
  article is now.
- **The link to the analysed article can 404:** a re-check can withdraw
  it from the reader (its newest check decides), while the story stays.
- **`docs/decisions/deployment.md` and the Caddyfile's comments** still
  say two proxies (above).
- `lib/reader.ts`'s `languageName` knows `en` and `es`; the stories use
  `storyLanguageName` in `lib/stories.ts`, which knows Catalan.
- `ArticleBody`'s `.article-body` has no global style; the story page
  styles it under its own CSS module.

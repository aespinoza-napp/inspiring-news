# The news map: the readers' app

Asked for on 2026-10-29 by the author: an app for readers where the news
feels like one enormous graph. Each article is a point, joined to its
entities and topics, and the topics sit in sections, so the whole reads
as a cloud of points. The goals are in `docs/goals.md`, "News map"
(N1-N9). Built on `feature/news-map`.

## The map's data (N1, 2026-10-29)

`backend/src/services/news_map/`: `layout.py` decides where an article
goes, `days.py` which day it belongs to, `index.py` keeps the map in step
with the lake. `backend/src/api/map_routes.py` serves it, open like
`/reader`.

### Where an article goes

The map is a disc of radius 1. The five topic groups are sectors of it,
in `TOPIC_GROUPS`' order, clockwise from the top. The circle is cut into
one slot per topic plus 0.6 of a slot of empty space after each group,
so a group's sector is 4 or 5 slots wide and the sections read as
sections. Each topic's anchor is its slot's centre, on one of two rings
(0.60 and 0.88), alternating around the whole circle.

An article sits at its **main topic's** anchor. A second topic within
0.05 confidence of the main one pulls it towards that topic's anchor, by
up to 0.045 when tied. Then its embedding moves it by up to 0.075 (the
cluster's radius), so similar stories sit side by side within a topic.

Three things were measured, not assumed:

- **Not a confidence-weighted mean of the anchors**, which the goal first
  said. The classifier's confidences are compressed. The first article
  read on 29 Oct had Entertainment 0.373, Sustainability 0.360 and
  Cities & Society 0.350: three topics in three groups, whose mean is
  near the centre. Every article would have ended up there, with no
  sections. The main topic decides the place, and a second one counts
  only when it ties it.
- **The pull is a distance, not a share of the way.** As a share
  (0.30 of the distance), that first article moved 0.25 from its anchor,
  past a neighbouring one (Arts), because the other anchors were across
  the disc.
- **The rings alternate around the whole circle.** Alternating within
  each group put two neighbouring groups' edge anchors on the same ring,
  0.18 apart (Food and Arts). The radii and the gap were then searched
  for the widest closest pair with a gap still visible: 0.287 apart
  (0.239 before), over the 0.24 that two clusters at full pull need. A
  test holds it. 23 topics cannot alternate around a circle, so one pair
  shares a ring: two outer anchors across a group's gap.

**The squash is tanh, not r·z/√(1+|z|²).** Drawn at 3,000 articles,
the first squash made rings and crescents: dense at the cluster's edge,
empty in its middle. Embedded by bge-m3, the 139 hand-labelled claims
gave a projection centred near 0 (mean -0.05, -0.03), spreading 0.78 a
side, with |z| at a median of 0.98 and a p90 of 1.67. That squash put
half of every cluster in its outer 30%. `tanh(|z| / 2)` puts the median
point at 0.46 of the radius and still keeps every point inside it. A
topic's own lean (a mean |z| of 0.22-0.64 across the eight largest
topics, a spread of 0.47-0.83 within each) now shifts its cloud a little
instead of flattening it against the edge. Not yet released, so
`LAYOUT_VERSION` stays 1.

An article with no vector is placed by its topics, with a deterministic
offset from its id, and says `approx: "no_vector"`. One with no known
topic goes on a ring just outside the disc (1.08), saying `"no_topic"`.

### Why positions never move

**An article's place is a function of that article and `LAYOUT_VERSION`
alone.** No corpus statistic and no fit, so a new article moves no old
one (a test). The embedding offset is a projection on a fixed random
basis seeded by the version, not a PCA of the corpus. A PCA would move
every point each time it was refitted, and needs a corpus the lake does
not have yet (2 publishable articles on 29 Oct). A unit vector's
projection on a random unit direction spreads by about 1/sqrt(1024), so
it is scaled to roughly N(0, 1) and squashed into the cluster's radius.
Changing any layout constant changes the map, so it changes
`LAYOUT_VERSION` too.

A PCA basis fitted once, saved and versioned is the natural next step
when there are a few hundred articles. It would spread similar stories
better than a random projection.

### Which day

The day is Madrid's: a reader opening "today" at 00:30 there expects what
was published after midnight there. A time with a zone is converted. A
naive time is read in its **source's** zone, from the source YAML's
`country`, not as Madrid's: on 29 Oct 11 of the 32 enabled sources were
Spanish and 20 wrote in English, from the UK, the US and Australia.
`INT` and `EU` are read as UTC. With no publication time, the time it was
checked decides.

### The index

`MapIndex` sits on `ReaderIndex.published()`, a method added for it, so
which run of an article is current and whether it is published are
decided in one place. Each published record is read once (its
exploitation record and, for the vector, the claims, the evidence URLs
and the body, its processed one) and kept until the reader drops it. An
unchanged lake costs no read (a test). The vectors stay in memory as
float32: 4 KB an article, 40 MB at 10k.

**Entities.** GLiNER's spans include "D", "J" and "universidad" as people
and companies (the first record read). A name needs two characters and a
capital to be shown. An article's entities are ranked by being named in
the title, then by mentions in the title and body, then by type (who
before what). An entity spelled several ways is shown the way most
articles spell it, ties going to more capitals. Keys are the graph's own
(`entity_key`), so the map and Neo4j name the same entity the same way.

**Related articles** use `/graph/related`'s weights: a shared claim 3.0,
a shared evidence page 1.5, a shared entity 2 / (articles naming it), a
shared topic 0.3. A test reads them out of the Cypher query, so the two
cannot drift. They are computed from the lake, so the map's links work
whether or not Neo4j is up.

### What leaves the server

| Route | What |
|---|---|
| `GET /map/articles[?day=]` | The frame (groups, topic anchors, layout version) and every published article as columns (`id`, `title`, `lang`, `day`, `src`, `g`, `t`, `e`, `v`, `x`, `y`, `approx`). Sources and entities are indices into tables in the same document |
| `GET /map/entities[?limit=]` | Entities named by more than one published article, each at the mean of its articles' places |
| `GET /map/articles/{id}/links` | Its topics with confidence, its top 5 entities with their article counts, and up to 10 related articles, each with what joins them |

Only what `/reader` shows. A test checks that no body, scraped page,
lineage, record id or embedding is in any of the three. The articles
come as columns (one list per field) rather than one object per article:
smaller, and decoded straight into typed arrays (N8). They are gzipped
once per set of articles and filter, with an ETag that changes only when
the set or the layout does, so a revisit is a 304. **At 10k synthetic
articles the payload serialises in under 200 ms and is under 1 MB
gzipped** (a test: the best of three runs, in CPU time, since the wall
clock failed it inside the full suite while the model benchmark loaded
the machine and passed it alone).

## The renderer: regl, measured against sigma.js (N2, 2026-10-29)

`frontend/src/app/map/bench` draws the same synthetic points (the real
frame's 23 anchors, 0.075 clusters) through `lib/mapRenderer.ts`, the
regl renderer the map runs, or through sigma.js 3.0.3 on graphology, along
the same 180-frame pan and zoom. Each frame is drawn synchronously and
waited for by reading a pixel back. `gl.finish` was not enough under
ANGLE: the first run timed regl's 50k points on SwiftShader at 0.2 ms.
Every run also counts the pixels its first frame lit, as proof it drew.
`scripts/bench_map_renderers.py` runs it in headless Chrome 155 on two
backends:

- **The dev laptop's integrated GPU**, through
  `--use-angle=vulkan --enable-features=Vulkan --ignore-gpu-blocklist`
  ("Intel(R) Graphics (MTL)", Mesa). Without those flags, or with
  `--disable-gpu`, headless Chrome draws in software.
- **SwiftShader**, that software path: a reader with no usable GPU.

Milliseconds per frame, median / p95, 29 Oct 14:0x, with the model
benchmark loading the CPU (load average 13-18 on 14 threads).
`backend/data/evaluation/experiments/news-map/renderers-2026-10-29.json`:

| | regl | sigma.js | an empty regl frame |
|---|---:|---:|---:|
| Intel GPU, 10k | 8.8 / 14.1 | 14.2 / 23.0 | 10.3 / 17.0 |
| Intel GPU, 50k | 10.4 / 19.9 | 15.1 / 25.7 | 8.6 / 12.7 |
| Software, 10k | 19.9 / 36.6 | 324.6 / 543.6 | 4.0 / 9.0 |
| Software, 50k | 33.5 / 61.9 | did not finish in 180 s | 3.8 / 6.6 |

First frame (setup, upload, first draw): regl 149-249 ms, sigma 352-1,763 ms.

**On the GPU an empty frame costs what a full one does.** The time is
Chrome's read-back round trip to its GPU process, and regl's points add
nothing measurable on top of it at 10k or at 50k. sigma's sit about 5 ms
above it. In software regl draws in 16 ms at 10k and 30 ms at 50k;
sigma takes 320 ms, and could not finish 50k. So **regl**: as fast where
there is a GPU, about 16x faster where there is not, and one draw call
whatever the count. It also has the smaller bundle and the plainer
model: the map is points and a few lines, not a graph to lay out, which
is what sigma is for.

This method ranks the two renderers. It does not check N8's absolute
budget, because every frame carries the read-back. N8 measures frame
intervals with normal drawing and nothing read back, on an idle machine.

Hover picking: a uniform grid of 0.01 map units over the points, built in
6-15 ms, answers a nearest-within-8-px query in under 0.1 ms at the p95
at 10k and at 50k.

**Found on the way: `./scripts/check.sh e2e` could not run on this
machine.** Every DevTools `Browser` in `scripts/e2e.py` failed with a
broken pipe. Chrome said why: "Remote debugging pipe file descriptors are
not open". `os.pipe()` gives close-on-exec descriptors, and in a fresh
process the first one is fd 3 itself, so `dup2(3, 3)` was a no-op that
left the flag set. Both ends are now copied above 10 first.

## The cloud (N2, 2026-10-29)

`/map`, public like `/reader` (Caddy's `@reader` matcher, the nav's
public list and `test_deployment_config.py`), through one proxy,
`app/api/map/[...path]`. The proxy forwards only the backend's three
`/map` routes, and `If-None-Match` both ways, so a revisit with nothing
new published is a 304. It relays the map as text, without parsing it.

- **`lib/newsMap.ts`** decodes the columns into typed arrays (positions as
  one `Float32Array`). **`lib/mapRenderer.ts`** draws them: one regl call
  for the points (round, soft-edged, sized by zoom), one for the selected
  article's lines, on demand and never on a loop. **`lib/spatialGrid.ts`**
  picks the point under the pointer, among the ones not dimmed.
- **`components/map/NewsMap.tsx`**: pan by drag, zoom by wheel (around the
  pointer) and by pinch, arrows and +/- and 0 from the keyboard, Escape
  to clear the selection, and zoom buttons. Clicking a section's or a
  topic's label flies to it. Labels are HTML, moved by style rather than
  re-rendered on every frame. A topic's label shows once its neighbours
  are 110 px apart, and entities (named by more than one article) once
  zoomed in 3x, at most 30 of them. Each group takes `--series-1..5`,
  read from CSS, so dark mode recolours the canvas too.
- **`components/map/MapView.tsx`**, which `/today` and `/for-you` reuse:
  filters for language, section and verdict that **dim** what they leave
  out rather than removing it, so the map keeps its shape. The selected
  article's panel shows its topics, its names (each shows its articles),
  and related articles with why each is related ("both name X", "the same
  claim: ..."). A list view with the same filters, 50 to a page, links
  each story to `/reader/<id>`. The filters and the selection are kept in
  the URL.

**Checked by `./scripts/check.sh e2e`**, which passed on 29 Oct after
the pipe fix: the map draws and counts its stories, the list lists them,
an unchanged map is a 304 through the proxy, the proxy forwards nothing
outside its three routes, and `/map` lays out within a 375 px screen.
**Looked at**, at 3,000 articles placed by the real layout with vectors
resampled from the real claims, in light and dark, whole and zoomed to
Science (the screenshots that found the crescents above): five sections,
one cloud per topic, and topic labels once zoomed.

Not done here, on purpose:

- **English only.** The reader is in Catalan, Spanish and English
  (`lib/readerText.ts`). The map's own strings are few, and putting them
  in that dictionary is a follow-up.
- **No entity lines on a large map.** An entity's articles are known only
  through each article's top five names. That is enough to highlight
  them, but not to draw every link.

## Search (N3, 2026-10-29)

`GET /map/search?q=&semantic=` (`backend/src/services/news_map/search.py`),
open like the rest of `/map`. It answers articles and names in one list,
each with why it matched. Three ways in, in this order:

1. **Names**, from every entity a published article names. The query
   and the names are folded (case, accents, punctuation, spaces): a
   whole-name, word-prefix or substring match scores 0.9-1.0, else
   character-trigram Jaccard at 0.35 or more. So "barca" finds "Barça"
   and "Ada Lovelase" finds "Ada Lovelace" (tests).
2. **Words**: every word of the query a prefix of a word in the title
   ("in the title"), else a topic's own name, an English keyword, or a
   Spanish stem that starts the query ("escuelas" finds Education:
   "about Education & Learning"). Both lexicons, as invariant 8 asks.
3. **Meaning**: the query embedded by `inference/` and compared with
   every published article's vector. The map index holds them in memory
   as one matrix of unit rows, so it is one product. Qdrant is not used:
   its collection holds every analysed article, published or not, and
   only the published may come back (a test with an unpublished article
   that is the nearest by construction). An article counts from a cosine
   of 0.45. That is reasoned, not fitted: two random hand-labelled
   claims average 0.34.

**Bounded**, because the third costs CPU in a service the pipeline
shares:

- At most 200 characters (422).
- Per visitor, 30 searches with meaning and 300 without per minute.
  Then a 429 with `Retry-After`.
- Cached for an hour by folded query, and keyed by the set of published
  articles, so a new article is searched for at once.
- A failed embedding is not cached, and the search still answers by
  name and word, saying `semantic: "unavailable"`.

"Per visitor" is the first address in `X-Forwarded-For`. Every request
arrives from the frontend's server, so the connection's address would
make every visitor one. Caddy sets that header from the connection, and
the map's proxy passes it on. On localhost, with no Caddy, a client could
set its own and escape the limit, which there limits nothing that
matters.

**On `/map`** (`components/map/MapSearch.tsx`): suggestions after 150 ms
of typing come from names and words only (`semantic=false`), so no
keystroke costs an embedding. Enter searches by meaning too. Arrows and
Enter move through the results. A story flies to it and opens its panel;
a name highlights its stories. The query is kept as `?q=`, and a link
with one runs it on arrival (an e2e check).

## Today (N4, 2026-10-29)

`/today`, public: the whole map with the day's stories at full colour
and the rest dimmed (`MapView`'s `emphasis`), then the day's stories by
section, each section with its count. The day is Madrid's, as the
backend dates every article (N1, "Which day"; the summer and winter
boundary tests are `test_days.py`'s). The browser asks
`Intl.DateTimeFormat` for Madrid's date, so a reader in New York at
20:00 still gets Madrid's day.

- **A day with nothing published** shows the latest earlier day that has
  stories, and says so ("Nothing was published on ... Showing ..."). It
  never shows an empty page. With no earlier day, it shows the latest
  day of all.
- **Earlier and later** go to the previous and next days *with stories*,
  not calendar days, so neither button leads to an empty page. The day
  is kept as `?day=`.
- **The cards are built from the map's own fields** (title, outlet,
  verdict, a link to `/reader/<id>`), not the reader's `ReaderCard`,
  which the goal named. That card needs the excerpt and the per-claim
  tally, which the map does not carry. They would cost a second request
  per day to `/reader/articles`, which has no day filter.

Checked by e2e: a day lists its stories by section; an empty day (5 Oct)
falls back to the latest day before it and says so; the sections'
counts add up to the day's total. `lib/today.ts` holds the logic. There
is no frontend test runner, so the e2e checks are its tests.

## Accounts (N5, 2026-10-29)

`backend/src/services/accounts/` (`store.py`, `service.py`) and
`src/api/account_routes.py`. `/account` on the frontend, through
`app/api/account/[...path]`, which forwards seven routes with one method
each, and only the session cookie. Open on the backend like `/reader`: a
reader has no key, so the session is the capability.

**Where.** One SQLite file, `settings.USERS_DB_PATH` (`data/users.db`,
on the backend's volume and in its snapshots). Standard library, WAL,
foreign keys on, numbered migrations. Not the lake, and not Neo4j:
`POST /graph/sync` rebuilds the graph from the lake, so a reader's rows
there would be wiped or would make sync protect them. A test reads the
accounts code's imports and fails on anything that reaches the lake, the
graph, the journal or `/metrics`.

**What is kept**: the username (lower case, unique), an email only if
given, an argon2id hash of the password, and per session the sha256 of
its token, its CSRF token, when it began and when it was last used. N6
adds what a reader follows. Export (`GET /account/export`, a JSON file)
returns all of it but the secrets. Delete (`POST /account/delete`, with
the password) removes every row of every table that names the user.
Both read the tables from the schema, so a table a later migration adds
is covered without being listed.

### Threat model

| Threat | What stops it |
|---|---|
| The database is copied | Passwords as argon2id (64 MiB, 3 passes); session tokens as sha256, so a copy opens no session; no email unless given |
| A password guessed online | 5 failures in 15 minutes per username **and** per client, then a 429 with `Retry-After`. 10 characters minimum |
| Whether a username exists, read from the timing | An unknown name is checked against a dummy hash: the same argon2 work and the same message as a wrong password (a test counts the hashes) |
| Hashing as a denial of service (64 MiB each) | At most `ACCOUNT_HASH_CONCURRENCY` (2) at once; registrations limited to 5 an hour per client |
| A forged state change from another site | Signed in: the session's CSRF token in `X-CSRF-Token`, compared in constant time. Signing in or registering: `X-Requested-With` must be set, which a cross-site form cannot do, and the backend allows no CORS. The cookie is `SameSite=Lax` besides |
| The session cookie stolen by a script | `HttpOnly`: page scripts cannot read it (checked in Chrome) |
| The cookie sent in clear | `Secure`, unless `ACCOUNT_COOKIE_SECURE` is turned off for plain-HTTP development |
| A session left open | Ends after 30 idle days, at sign-out, and at a password change (every other session) |
| A shared cache keeping someone's answer | `Cache-Control: no-store` on every `/account` answer, errors included (a route class: an error raised in a dependency is a new response) |
| A password in a log | Never logged; a test runs the flow and searches the logs and the database file for it; the real flow's backend log had it 0 times |
| One visitor's limit spent by another | "Per client" is the first `X-Forwarded-For` address, which Caddy sets from the connection |

**Not covered, on purpose:**

- No email confirmation or password reset by mail: no free mail service
  is configured, and the page says so. A forgotten password is a new
  account.
- No account lockout beyond the rate limit: a lock would let a stranger
  shut anyone out.
- The limits are in memory and per process. A restart forgets them,
  which gives an attacker at most one more window.

**Checked in a real browser on 29 Oct**: the worktree's backend with a
scratch database, the built frontend in front of it, and Chrome. Register
answered 201. The cookie arrived as `in_session` with `HttpOnly`,
`Secure` and `SameSite=Lax`, and `document.cookie` did not show it. The
reader was still signed in after a reload. Sign-out without the token
was 403 and with it 204, then `/me` was 401. The proxy answered 404 to
`/api/account/users`. Chrome kept the `Secure` cookie over
`http://127.0.0.1`.

**On the dependency**: `argon2-cffi` 25.1.0 (June 2025). It brings cffi
and pycparser, whose newest release (3.12) was a week old. `[tool.uv]`
constrains pycparser to 3.0 (January 2026).

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

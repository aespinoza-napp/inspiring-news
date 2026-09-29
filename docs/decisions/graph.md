# The graph (Neo4j)

> Read this before touching `backend/src/services/graph/`,
> `backend/src/database/neo4j_client.py`, the `/graph/*` endpoints or the
> frontend's `/graph` page.

Neo4j was configured scaffold for the project's first two months: a
container, a required password and a `GraphClient` nothing called. Since
2026-09-29 every finished analysis is written into it, the labeller's
hand-labelled facts are synced into it, and `/graph` reads it.

## The schema

Declared once, in `backend/src/services/graph/schema.py`. The writer's
constraints, the reader's schema view and the frontend's diagram all come
from there, and `tests/services/graph/` fails if the writer or a preset
query uses a label or relationship type that is not declared.

```
(:Article)-[:PUBLISHED_BY]->(:Source)<-[:PUBLISHED_BY]-(:Evidence)
    |  \                                                   ^
    |   `-[:MENTIONS]->(:Entity:Person|Country|...)         |
    |   `-[:ABOUT]->(:Topic)             ^           [:CHECKED_AGAINST]
    |                                    |                  |
    `-[:CONTAINS_CLAIM]->(:Claim)-[:MENTIONS]      (:Claim)-'
                            `-[:HAS_VERDICT]->(:Verdict)
```

| Label | Keyed by | Why that key |
|---|---|---|
| `Article` | `url` | The pipeline and the labeller both know the URL; nothing else. A labelled fact and a later analysis of the same article meet on one node. |
| `Entity` | `key` = `type:name` (case/space-folded) | GLiNER's type is part of identity: "Spain" the country and "Spain" the team are different things. The type is also a second label (`:Person`, `:Country`...), from `ENTITY_TYPE_LABELS`. |
| `Topic` | `name` | The topic key from `src/config/topics.py` - the labeller writes the same keys. |
| `Claim` | `id` = sha256 of the case/space-folded text | The same sentence in two articles is one claim. Anything looser than case and whitespace would merge two claims that differ in exactly the figure being checked. |
| `Verdict` | `name` | The five `Verdict` values, created up front. |
| `Evidence` | `url` | A page a claim was checked against. Shared across claims and methods. |
| `Source` | `domain` (host minus `www.`) | The same judgement of "same outlet" the ranker and the independence count already make. A configured source YAML fills in name and reliability; any other domain is `configured: false, reliability_known: false` - never a made-up rating. |

**Every relationship written carries `method`:** `pipeline` for what an
analysis wrote, `manual` for a hand label (plus the `fact_id`). That is
what lets the annotator's verdict and the model's verdict on one claim sit
side by side (`HAS_VERDICT {method: 'manual'}` next to
`{method: 'pipeline'}`) - the comparison the evaluation needs - rather
than one overwriting the other.

## The write path

`AnalysisService._store_graph`, after the lake writes, before `done`.

- **The lake is the record; the graph is a view of it.** So the graph
  write comes last and is fail-soft: Neo4j down costs one `graph_failed`
  event and a log line, never the analysis, and never the lake write.
  `GraphSync` can rebuild the graph from the lake at any time.
- **One transaction per article.** A half-written article - claims without
  their verdicts - would read as "checked, no verdict", which is a
  different and wrong answer.
- **Short timeouts** (`GraphClient`: 3 s to connect, 2 s of retries). The
  driver defaults added about a minute to every run with Neo4j stopped.
- **A re-analysis replaces what the last pipeline run wrote** about that
  article (its `MENTIONS`, `ABOUT`, `CONTAINS_CLAIM`, and the claims'
  pipeline `HAS_VERDICT` / `CHECKED_AGAINST`), never what the labeller
  wrote. Claims, entities and evidence left with no relationship are
  deleted: a claim is only ever reachable from an article.
- Rejected articles are written too (`admitted: false`, no verdict): what
  they mention and what they are about is still true.
- Cache hits are not re-written - they were written when computed.
- `AnalysisService.graph` has **no default**, like `lake`: Neo4j Community
  has one database, so a default would have every test writing into the
  developer's own graph. `settings.GRAPH_ENABLED=false` switches it off.

## Backfill: `GraphSync`

`POST /graph/sync` (the Sync button on `/graph`) or
`uv run python -m src.services.graph.graph_sync`. In order: the configured
sources, the hand-labelled facts in `data/evaluation/manual/`, and the
newest verified run per URL from the lake's `processed/` layer.
Idempotent - every write is a MERGE on the schema's keys, and a fact
replaces everything carrying its `fact_id` (so re-labelling, or editing a
claim's text, does not leave the old version behind). A file that fails is
reported and skipped.

**Re-run it after labelling facts.** The labeller writes files only; it
imports nothing from `backend/` on purpose, so it does not write the graph.

## Reading it

- `GET /graph/related?url=` - **the read use-case.** Articles connected to
  one article, each with what connects them and how much it counts: a
  shared claim 3, a shared evidence page 1.5, a shared entity 2 / (articles
  mentioning it), a shared topic 0.3. Hand-set, not fitted - there is no
  labelled "related" set to fit against - and shown next to every result
  so a score is never an unexplained number.
- `GET /graph/schema` - the declared schema plus live counts per label and
  per `(from)-[type]->(to)` pattern, and anything present but undeclared.
- `POST /graph/query` - the query console. See below.
- `GET /graph/presets` - the console's starting queries, in
  `graph_reader.py` next to the tests that check them against the schema.

## The query console is read-only, and why that is safe

`GraphClient.read` runs in a **READ transaction**, which Neo4j enforces:
`CREATE`, `MERGE`, `SET` and `DELETE` fail with "Writing in read access
mode not allowed" from the server itself (verified live, and pinned by
`test_neo4j_live.py::test_the_console_cannot_write`). A keyword filter is
not the guarantee.

What a READ transaction does *not* stop are reads with effects outside the
graph, so `graph_reader.check_query` refuses them before sending: `LOAD
CSV` (fetches any URL the server can reach - the SSRF `url_guard.py`
exists to prevent), `dbms.*` / `apoc.*` / `gds.*` procedures, `USE`, the
admin `SHOW USERS|ROLES|SETTINGS|TRANSACTIONS|...` and `TERMINATE`. String
literals are stripped first, so searching for the text "LOAD CSV" works.
Every query is capped at 10 s and 500 rows, and the endpoints sit behind
`STORAGE_API_KEY` like `/storage/*`.

For anything the console does not do (writes, `EXPLAIN`, saved queries),
use Neo4j Browser at http://localhost:7474.

## Testing

- `tests/services/graph/` - the writer's statements, the reader, sync and
  the routes, against `RecordingGraphClient`. No database. Part of the
  default run.
- `tests/database/test_neo4j_live.py` - the `neo4j` marker, excluded by
  default like `slow`, run with `./scripts/check.sh graph`. It **fails**
  when Neo4j is down. The `test_connection.py` it replaced skipped, so the
  one test of the database passed whether a database existed or not.
  Everything it writes carries a per-run token and is deleted afterwards.

## Incident: the old container had another password

The `neo4j` service used the image's anonymous `/data` volume, and the
database in it was created on 2026-09-18 - before the password moved to
`backend/.env`. `NEO4J_AUTH` only applies when a database is first
created, so the container rejected `.env`'s password. It now has a named
volume (`neo4j-data`); the old anonymous volume was left on disk, not
deleted. `docker volume ls` shows it; `docker volume rm` it once you are
sure nothing in it is wanted.

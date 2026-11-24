# Inspiring News Universe

The readers' 3D news universe. Every story is a star, placed by what it is
about, with its topics, the names it shares with other stories, and its
photos. It is a static Astro + three.js site, and it reads its data from the
backend's `/map` and `/account` routes. Why it is built this way:
[`docs/decisions/news-map.md`](../docs/decisions/news-map.md), "The universe".

## Running it

You need Node.js + npm, Python 3, and (for real stories) the backend's
requirements from the [main README](../README.md#requirements). Install the
packages once:

```bash
cd universe && npm ci && cd ..
```

### The stories: every article of the knowledge graph

The universe shows what the backend's map holds, and since 23 Nov that is
**every article of the positive graph**: the 187 posts of the WordPress
import, with their photos and WordPress labels, and every article the
pipeline analysed, with its verdict. Start the Docker stack (Neo4j and the
backend), then the universe, from the repository's root:

```bash
./scripts/dev.sh docker              # once; the backend on port 8000
python3 scripts/preview_universe.py
```

Open http://127.0.0.1:4321/. It builds `universe/dist` the first time, and
`--build` rebuilds it after you change something. Ctrl-C stops it. If the
backend does not answer, it says so and stops: it never falls back to
made-up stories.

- **The settings** (`backend/.env`, `backend/.env-example`):
  - `MAP_SOURCE=graph`, the default, reads the graph. `lake` is the map of
    published articles only.
  - `MAP_GRAPH_SOURCE_ID`, empty by default, is every article.
    `wordpress:inspiringnews.ai` is the import only.
  - `MAP_GRAPH_LABELS` adds the research labels, and `MAP_IMAGES_DIR` serves
    the photos. Both are optional. The photos are not in git:
    `python3 scripts/wordpress_images.py <the export's .xml>` downloads them,
    and `cd backend && uv run python ../scripts/optimize_map_photos.py
    <the images folder>` makes the light WebP copies the universe prefers
    (`docs/decisions/storage.md`, "Imports"). Docker mounts both and sets
    its own paths (`docker/docker-compose.yml`).
- **A backend on the host** instead: `cd backend && uv run uvicorn src.main:app
  --port 8010` reads the same `backend/.env` (its relative paths work because
  it runs from `backend/`), then `python3 scripts/preview_universe.py
  --backend http://127.0.0.1:8010`.
- **Made-up stories**, for the map's performance only:
  `python3 scripts/preview_universe.py --synthetic` (5,000; `--count` changes it).

## Clicking

Everything you can click in a story's panel shows that concept in the
universe: its section, its source, its verdict, a topic, a name, a WordPress
category or tag. Its stories light up, the camera goes to them and the panel
lists them. The "+" beside a topic follows it in For you. Only "Read it on
... ↗" leaves the universe: it opens the article on the web, where it was
published, in a new tab.

## Photos

The universe comes first: the floating photos appear once it is drawn and
the browser is idle, and none is fetched while you drag, zoom or the camera
flies. The switch (or P) turns them off, and this browser remembers your
choice. On a slow connection or with data saving on, they start off.

## Keys

| Key | Does |
|---|---|
| `/` | Search |
| H | The whole view |
| P | Photos on or off |
| M | Motion on or off |
| L | The list (the way in for a screen reader) |
| Esc | Close |

## Checking it

```bash
./scripts/check.sh universe   # typecheck; also part of ./scripts/check.sh
```

## What is not done

- **Not served in production yet.** Caddy should serve `universe/dist` and
  pass `/api/map` and `/api/account` to the backend, but that site and its
  test are not written.
- **Not linked from the newsroom's menu.** The 2D map, Today, For you and
  Account pages are in the frontend (`frontend/src/app/map/` and next to it).
- **No end-to-end checks for the universe.** It has been looked at in
  screenshots only.
- **`astro dev` is not used.** With no terminal, Astro 7 starts it as a
  background daemon, so `preview_universe.py` serves a static build instead,
  the way production will.

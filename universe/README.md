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

### Without a backend: synthetic stories

```bash
python3 scripts/preview_universe.py
```

Open http://127.0.0.1:4321/. This shows 5,000 made-up stories placed by the
real layout (`--count` changes the number). Nothing else needs to be running.
It builds `universe/dist` the first time, and `--build` rebuilds it after you
change something. Ctrl-C stops it.

### With real stories: the WordPress import, from the graph

Neo4j must be running (`./scripts/stack.sh analyse`, or `docker compose up
neo4j` in `docker/`). In one terminal, start a backend that reads the graph:

```bash
cd backend
MAP_SOURCE=graph \
MAP_GRAPH_LABELS=../research/wordpress-import/data/wordpress-labels.json \
MAP_IMAGES_DIR=data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images \
uv run uvicorn src.main:app --host 127.0.0.1 --port 8010
```

In another, from the repository's root:

```bash
python3 scripts/preview_universe.py --backend http://127.0.0.1:8010
```

Open http://127.0.0.1:4321/: the 187 imported posts, with their photos.

- **The settings:**
  - `MAP_SOURCE=graph` reads the positive graph's WordPress import. Without
    it, the backend serves the lake's analysed articles.
  - `MAP_GRAPH_LABELS` adds the research labels. It is optional.
  - `MAP_IMAGES_DIR` serves the photos. It is optional, and the folder is not
    in git: `python3 scripts/wordpress_images.py <the export's .xml>`
    downloads it (`docs/decisions/storage.md`, "Imports").
- **The relative paths** work because the backend runs from `backend/`.
- **The same settings** can go in `backend/.env` instead of on the command
  line.

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

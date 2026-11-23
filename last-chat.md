# Last chat - 23 Nov 2026

**Question:** why does `../inspiring-news-map` look almost the same as this
folder? It should also have the interface. Isn't the best way just to put the
map inside this repo?

**Answer:** it looks the same because it *is* this repository, checked out a
second time. And yes, bringing it in here is the right move.

**Done the same day:** everything is merged into this folder, on
`iterate/20261104-speed`, and every check passes (see "Done: the merge" below).
The 3D app is in `universe/`. `../inspiring-news-map` is still there, with
nothing left in it that this folder lacks.

## Why it looks the same

`../inspiring-news-map` is not a separate project. It is a **git worktree**: a
second folder attached to the same `.git` as this one, with a different branch
checked out.

```
$ cat ../inspiring-news-map/.git
gitdir: /home/aespinoz/dev/napp/inspiring-news/.git/worktrees/inspiring-news-map

$ git worktree list
/home/aespinoz/dev/napp/inspiring-news      ac61293 [iterate/20261104-speed]
/home/aespinoz/dev/napp/inspiring-news-map  4881403 [feature/news-map]
```

A branch always holds the whole project, not only the files you changed. The
map branch (`feature/news-map`) started from commit `7436611` on **29 Oct**. So
that folder holds a **29 Oct copy of everything** (backend, frontend, inference,
docs), plus the map's work on top. That is why it looks like this folder.

The two folders have grown apart since 29 Oct, in opposite directions:

| | Only in `../inspiring-news-map` | Only in this folder |
|---|---|---|
| Commits | 9, all from 29 Oct | 38 since 29 Oct (633 files, +123,000 lines) |
| What they are | `universe/` (the 3D app); the backend's `/map` and `/account` routes (`news_map/`, `accounts/`); the frontend's `/map`, `/today`, `/for-you`, `/account` | `livecheck/`, the two editions, `/trace`, packages, MiniCheck, AVeriTeC, the WordPress import, the labeller removed (the map folder still has `labeller/`) |
| Not committed | The 20 Nov photos and name: 15 changed files, 2 new | The 20 Nov import work, and your own earlier edits |

So **neither folder has the whole interface**. The map folder's frontend is the
one from 29 Oct, without anything built here since then. This folder's frontend
has no map pages and no universe. There are also two backends: to see the
universe with photos you ran the map folder's 29 Oct backend on port 8010,
reading data that lives in this folder.

## Yes: merge it into this folder

They are the same repository, so "putting the map inside this repo" means
**merging the branch `feature/news-map` into this branch**. Don't copy folders
across: that loses the map's history and leaves two copies to keep in sync.

### I tried it, in a throwaway copy

I did this in a clone in the scratchpad. **Nothing in either of your folders
changed.**

1. **The merge:** 4 conflicts. Each one is a place where both branches added
   lines, so I kept both:
   - `backend/src/main.py`: the router imports (this branch's `package_routes`,
     the map's `account_routes` and `map_routes`).
   - `scripts/check.sh`: this branch's `livecheck` and `lake` targets, and the
     map's `universe` target. I dropped the map's `labeller` target, because
     the labeller was removed on 17 Nov.
   - `scripts/e2e.py`: this branch's stubs for trace and restatement, and the
     map's stubs.
   - `docs/goals.md`: two new goal sections, one from each branch.
2. **Both folders' uncommitted work on top:** it applied cleanly. That includes
   `CLAUDE.md` and `backend/.env-example`, the only two files both folders
   changed.
3. **Checks on the result:**
   - `./scripts/check.sh fast`: 21 passed.
   - `./scripts/check.sh backend`: 2831 passed, 21 skipped, 3 xfailed,
     **0 failed**. The two feed tests that fail in the map folder pass here,
     because this branch already fixed them.
   - `./scripts/check.sh frontend`: the typecheck passes.
   - `./scripts/check.sh universe`: the typecheck passes.
   - `./scripts/check.sh e2e`: every check passes, including the map, Today,
     For you, accounts and Trace.

### What you get

- **One folder, one backend, one interface.** The frontend gains a "Readers"
  group in the menu (Map, Today, For you, Account) next to everything that is
  already there. `universe/` sits next to `frontend/`. The Docker backend
  serves `/map/*` too, after a rebuild.
- **Running the universe** uses this folder's backend:

  ```bash
  cd /home/aespinoz/dev/napp/inspiring-news/backend
  MAP_SOURCE=graph \
  MAP_GRAPH_LABELS=/home/aespinoz/dev/napp/inspiring-news/research/wordpress-import/data/wordpress-labels.json \
  MAP_IMAGES_DIR=/home/aespinoz/dev/napp/inspiring-news/backend/data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images \
  uv run uvicorn src.main:app --host 127.0.0.1 --port 8010

  # in another terminal, from /home/aespinoz/dev/napp/inspiring-news
  python3 scripts/preview_universe.py --backend http://127.0.0.1:8010 --port 4321
  ```

  Run `npm ci` once in `frontend/` and in `universe/`: the frontend gains three
  packages (graphology, regl, sigma).
- **Not done by the merge:** the 3D universe stays its own app on port 4321.
  The frontend's menu doesn't link to it, and production doesn't serve it yet
  (`docs/decisions/news-map.md` lists the Caddy site as not done). If "the
  interface" means the universe should open from the main app, that is a short
  follow-up: a "Universe" link in `NavLinks.tsx`, and serving `universe/dist`.

## Done: the merge (23 Nov)

You asked to merge everything and put it inside this repo, in `universe/` if
possible. Here are the commits, oldest first.

**Pushed, and moved to `dev` (23 Nov).** This folder is on `dev` now. `dev` on
GitHub was fast-forwarded to the merge (`1a1d182`), then got one more commit:
`9d697b5`, "e2e: Chrome told the language, not left to the machine's locale".
CI's `e2e` job had failed on every run since it was added on 3 Nov. On Linux,
Chrome takes its language from the machine's locale, and the runner is English,
so the check for the Spanish feed failed there. On this laptop the locale is
Spanish, so it passed. CI on `9d697b5` passes all three jobs (backend, frontend,
e2e): the first green run since 2 Nov.

- `iterate/20261104-speed` is pushed at `1a1d182`, one commit behind `dev`.
- `main` is untouched, still at `ac61293`.
- `git push origin` asks for a password and can't prompt here, so the pushes
  went over SSH (`git@github.com:aespinoza-napp/inspiring-news.git`).

| Commit | Where | What |
|---|---|---|
| `7027d8a` | `feature/news-map` | Universe: Inspiring News Universe, read from the graph, with the stories' photos (the map folder's 17 and 20 Nov work) |
| `efbaac5` | here | Topics: the MN-DS classifier's run, not adopted (30 of 56 against 46) |
| `e10b588` | here | WordPress import: the list of sources cut from the text, the photos kept and downloaded |
| `add3400` | here | Compose: the IPTC classifier's weights mounted read-only |
| `1a1d182` | here | Merge feature/news-map: the readers' map and Inspiring News Universe |

- **`add3400` is a fix the checks found.** Once `backend/data/models/` was
  committed, `test_every_committed_data_folder_the_backend_reads_is_mounted`
  failed. The backend reads that folder when `TOPIC_GROUP_CLASSIFIER=iptc`, but
  Docker didn't mount it, so the switch would have found no model in the
  container. Compose now mounts it read-only. I undid the first merge attempt,
  committed the fix and merged again, so every commit passes on its own.
- **The checks on the merge:**
  - `./scripts/check.sh`: backend 2831 passed (21 skipped, 3 xfailed);
    inference 31 passed with the real models; the frontend and universe
    typechecks pass; livecheck 49 passed.
  - `graph`: 7 passed, against the running Neo4j.
  - `e2e`: every check passes.
- **On `feature/news-map` itself,** 2 feed tests fail, before and after its
  commit: their October dates are now too old. They pass after the merge,
  because this branch already fixed them. The commit message says so.

### What is in `universe/`, and what can't be

`universe/` holds the 3D app (Astro + three.js): its page, scripts, styles and
packages. The rest of the map work can't move there, because it is part of the
other two apps:

- **The backend's `/map` and `/account` routes** (`backend/src/api/map_routes.py`,
  `account_routes.py`, `services/news_map/`, `services/accounts/`). The universe
  reads its data from them, and they run inside the same FastAPI process as
  everything else.
- **The 2D map pages** (`frontend/src/app/map/`, `today/`, `for-you/`,
  `account/`, `components/map/`). They are Next.js pages, so they live in the
  frontend.
- **The scripts and docs** (`scripts/preview_universe.py`,
  `docs/decisions/news-map.md`), next to the others of their kind.

### Left for you

- **The second folder.** `../inspiring-news-map` is committed and clean. Its
  `.env` files have no setting this folder lacks. To remove it:
  `git worktree remove ../inspiring-news-map`. That deletes the folder (and its
  installed packages), not the branch.
- **The backend on port 8010** that was started from this folder at 09:18 runs
  the code from before the merge. Restart it with the command under "What you
  get" to see the universe.
- **The Docker stack's backend** needs a rebuild to serve `/map`, and a
  recreate to pick up the new mount.
- **Packages:** I already ran `npm ci` in `frontend/` and `universe/` here.

---

# The chat before - 20 Nov 2026

The four goals: the name "Inspiring News Universe", sources ("Fuentes") cut out of
the import's text, the dump's photos downloaded, and the photos shown in the
universe. All four are done. The graph and the universe now show the fixed data.
**Nothing is committed in either worktree.**

## 1. The name

The app is now **Inspiring News Universe** in the page title, the header, the
loading screen and the docs (`../inspiring-news-map`).

## 2. Names without "Fuentes"

The import now cuts a post's closing list of sources out of its text before
anything reads it, and keeps the list separately, item by item with its link
(`source_list`).

- 104 of the 187 posts had such a list: 433 sources, 382 with a link.
- "Fuentes" had become a *person* in 5 posts, because the extractor read the
  heading as a surname. I cut the section rather than blocking the word, because
  "Fuentes" really is a surname, and a sentence like "Fuentes de la catedral
  resaltan..." stays in.
- I re-imported all 187 posts (28 minutes, 0 failures). Now no post names
  "Fuentes", and outlets that only appeared in source lists (Euronews, PETA Asia)
  are no longer counted as the story's names.
- Re-import results: 157 pass the filters, 30 rejected, 1768 claims, 2924
  entities, no post left without names. They are in
  `backend/data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/import-2026-11-20/`;
  the 3 Nov files are untouched.
- In the graph: 187 posts, 2302 distinct names, 2907 mentions, 214 shared names.
  BBC in 6 posts (was 7), Infobae in 2 (was 4). "Inspiring News" remains in 9
  posts, where the text really mentions it.

## 3. The photos in the dump

The export holds only where each photo is on the site, not the photo itself, so I
added `scripts/wordpress_images.py` to download them.

- It saved all 897 files (319 MB): each post's featured photo and the 141 in its
  text, each in three sizes (`full`, `medium_large`, `thumbnail`).
- They're in
  `backend/data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images/`,
  with a `manifest.json`. That folder is already ignored by git.
- The script can be re-run: files already there are kept. It downloads only from
  the export's own site, and never SVG files.
- The graph now stores each article's photo link (`image_url`, `image_alt`), and
  all 187 posts have one.

## 4. Photos in the universe

- The selected story's photo floats over it, and its connected stories show
  theirs. Near a section the closest stories show round photo bubbles, and a few
  appear in the whole view.
- The story panel opens on the photo with its caption and the post's other
  photos, and any photo opens full size.
- Thumbnails appear in the hover card and in every list. A "Photos" switch (or
  the P key) turns them off.
- I looked at it in screenshots at desktop and phone size (no errors, no
  sideways scroll). The two to look at first:
  - `/tmp/claude-1002/-home-aespinoz-dev-napp-inspiring-news/5d7ecfd1-92f8-482b-b37e-0d95d76853a2/scratchpad/shots/2-story.png`
  - `/tmp/claude-1002/-home-aespinoz-dev-napp-inspiring-news/5d7ecfd1-92f8-482b-b37e-0d95d76853a2/scratchpad/shots/phone-2-story.png`

  (That scratchpad folder can be cleared by a reboot.)

## Decisions for you

- **Entity rule.** Your 17 Nov rule extracts names only after an article passes
  its check, and an unverified import never does. Re-importing under that rule
  would have left the universe with no names, so I made one narrow exception: an
  unverified import keeps its names (`analyze_news(unchecked_entities=True)`).
  Nothing is drafted from these posts. Tell me if you'd rather keep the rule
  strict.
- **Photos for other outlets' stories.** Only your own site's posts show photos.
  The default universe (`MAP_SOURCE=lake`) shows other outlets' articles, whose
  photos are theirs, so I left those without photos until you decide.

## Checks

- The main repo's backend suite passes (`./scripts/check.sh backend`). The first
  run had two failures under the import's load, and both passed on a rerun once
  the machine was quieter.
- In the map worktree, the universe typechecks (`./scripts/check.sh universe`).
  Its backend suite has 2 failures in feed-reading tests whose October dates are
  now "too old" (`test_listings.py::test_a_dead_feed_falls_through_to_the_json_listing`,
  `test_ingestion_service.py::test_a_feed_with_only_old_items...`). They also fail
  on the branch without my changes and already pass on the main branch.

## What changed, by worktree

**Main worktree** (`inspiring-news`, branch `iterate/20261104-speed`):

- `backend/src/services/imports/wordpress.py`: cuts the source list, reads the
  photos (featured and in the text, with their sizes).
- `backend/src/services/imports/wordpress_import.py`: passes photos and sources
  on; the outcome counts entities, sources listed and images.
- `backend/src/services/analysis_service.py`: the `unchecked_entities` exception.
- `backend/src/models/core/news.py`, `enriched_article.py`,
  `backend/src/workflows/enrichment.py`, `backend/src/services/graph/graph_writer.py`:
  `image_url` / `image_alt` reach the graph.
- `scripts/wordpress_images.py` (new) and `backend/tests/test_wordpress_images_script.py` (new).
- Tests: `backend/tests/services/imports/test_wordpress.py`, `test_wordpress_import.py`.
- Docs: `docs/decisions/storage.md` ("Imports"), `docs/decisions/graph.md`,
  `docs/decisions/writing.md` ("Checked twice"), `CLAUDE.md`, `backend/CLAUDE.md`.
- These sit beside your earlier uncommitted edits in that worktree.

**Map worktree** (`../inspiring-news-map`, branch `feature/news-map`):

- `backend/src/services/news_map/index.py`, `graph_source.py`: each story's
  photos and thumbnails; `MAP_IMAGES_DIR` serves only the files the manifest lists.
- `backend/src/api/map_routes.py`: `GET /map/images/{name}`.
- `backend/src/config/settings.py`, `backend/src/container.py`, `backend/.env-example`:
  the `MAP_IMAGES_DIR` setting.
- Tests: `test_graph_source.py`, `test_invariants.py`, `test_api_key.py`.
- `universe/src/pages/index.astro`, `universe/src/scripts/data.ts`, `scene.ts`,
  `ui.ts`, `universe/src/styles/universe.css`: the name and the photos.
- Docs: `docs/decisions/news-map.md` (new section "Photos, and names without the
  sources (2026-11-20)"), `CLAUDE.md`, `scripts/preview_universe.py`.
- These sit on top of your 17 Nov graph work in that worktree.

## Running it again

The universe with photos, reading the graph (Neo4j must be up):

```bash
cd ../inspiring-news-map/backend
MAP_SOURCE=graph \
MAP_GRAPH_LABELS=/home/aespinoz/dev/napp/inspiring-news/research/wordpress-import/data/wordpress-labels.json \
MAP_IMAGES_DIR=/home/aespinoz/dev/napp/inspiring-news/backend/data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images \
uv run uvicorn src.main:app --host 127.0.0.1 --port 8010

# in another terminal, from ../inspiring-news-map
python3 scripts/preview_universe.py --backend http://127.0.0.1:8010 --port 4321
```

Then open http://127.0.0.1:4321/.

Downloading the photos again (keeps what is already there):

```bash
python3 scripts/wordpress_images.py <path to the WordPress export .xml>
```

## Left running at the end of the chat

- Docker: Neo4j, `inference/`, the backend and SearXNG.
  `./scripts/stack.sh idle` stops them all.
- The map backend on 127.0.0.1:8010 and the universe on http://127.0.0.1:4321/.

# Web search engines, one at a time

`search-engines.ipynb` (executed, 23 Nov 2026): which engines answer this machine, how much of what they return
is on the subject (the app's own 35% rule), whether they find the pages AVeriTeC's annotators cited, and how much
their results overlap. Retrieval only: no model and no verdict.

| File | What |
|---|---|
| `data/probe-2026-11-23-allowlist.jsonl` | The repo's allowlist (`docker/searxng/settings.yml`) on SearXNG 2026.11.2, each engine on its own, then all together as the app asks |
| `data/probe-2026-11-23-candidates.jsonl` | Every other default engine for the web and news, on 2026.11.2 (`searxng-probe.yml`) |
| `data/probe-2026-11-23-searxng-2026.9.8.jsonl` | The first pass, on the image the stack running that day had been started with |

The queries are the `proposition` queries of two recorded train runs: 18 AVeriTeC train claims (English) and 8
of the custom set's train half (Spanish), never dev or the test half.

## Running it again

Two throwaway SearXNG instances. Their secrets are made up on the spot, and they are removed when stopped:

```bash
docker run --rm -d --name engine-probe -p 127.0.0.1:8090:8080 -e SEARXNG_SECRET="$(openssl rand -hex 32)" \
  -v "$PWD/research/search-engines/searxng-probe.yml:/etc/searxng/settings.yml:ro" searxng/searxng:2026.11.2-cccbc9e15
docker run --rm -d --name engine-allowlist -p 127.0.0.1:8091:8080 -e SEARXNG_SECRET="$(openssl rand -hex 32)" \
  -v "$PWD/docker/searxng/settings.yml:/etc/searxng/settings.yml:ro" searxng/searxng:2026.11.2-cccbc9e15

cd backend
PYTHONPATH=. uv run python ../scripts/probe_search_engines.py --searxng http://127.0.0.1:8091 \
  --engines "duckduckgo,yahoo,google,brave,yep,bing news,wikipedia" --mix --out ../research/search-engines/data/<day>-allowlist.jsonl
PYTHONPATH=. uv run python ../scripts/probe_search_engines.py --searxng http://127.0.0.1:8090 \
  --out ../research/search-engines/data/<day>-candidates.jsonl
docker stop engine-probe engine-allowlist
```

Then point `FILES` in the notebook's first code cell at the new files and run it with
`uv run jupyter nbconvert --to notebook --execute --inplace search-engines.ipynb` from this folder.

An engine is measured from this machine's address: it can refuse it one week and answer the next.

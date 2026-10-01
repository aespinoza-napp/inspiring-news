# Deployment: Google Cloud, the production stack, and how it is watched

> Read this before touching `docker/docker-compose*.yml`, `docker/caddy/`,
> `docker/searxng/settings.yml`, `deploy/gcp/`,
> `backend/src/services/{health,run_metrics,log_format}.py`, or choosing
> or resizing the server.

Until 2026-10-01 the backend container had come up healthy and served
requests, but no analysis had ever run inside it. Everything below starts
from that first run and the measurements taken around it, not from the
compose files' own comments.

## Where each piece stands

| | How it was checked | Result |
|---|---|---|
| Dev stack (`docker-compose.yml`) | A full analysis inside the backend container, 2026-10-01 | Works: 75 s, 4 claims, lake and graph written |
| Production stack (`+ docker-compose.prod.yml`) | Booted on the dev machine, same article, LLM on CPU in its container | Works after one fix (the LLM timeouts below): 184 s, 4 real verdicts |
| Google Cloud infrastructure (`deploy/gcp/`) | `./scripts/check.sh gcp`: applied to Floci, a local Google Cloud emulator | 28 resources apply, the VM's `.env` renders from the secrets they hold, a second plan is empty, destroy is clean |
| A real Google Cloud deploy | - | **Not done.** Needs a project with billing; see "What Floci does not prove" |

## The stack, measured (2026-10-01)

**Dev:** Yale e360's "At Least 124 Environmental Defenders Killed", forced
past the cache. Scraped, enriched, admitted, 4 claims checked against
20-22 web results each, lake and Neo4j written, 75 s. The LLM was the
host's Ollama, partly on the laptop's GPU (17-29 s per claim).

**Production, the same article:** the LLM in its own container, CPU only.
The first run took 165 s and **3 of 4 claims came back `UNVERIFIED` -
"LLM provider was unreachable"**: the dev defaults sent all four claims at
Ollama at once (`LLM_MAX_CONCURRENCY=2` plus a slot per claim on Ollama's
side), each took 90-103 s sharing the same cores, and `LLM_TIMEOUT=30`
cut them off twice. On any CPU server most verdicts would have been
errors dressed as verdicts. The production file now sets
`LLM_MAX_CONCURRENCY=1`, `LLM_TIMEOUT=180` and `OLLAMA_NUM_PARALLEL=1`;
re-run, every claim got a verdict, each LLM call taking 31-53 s in turn,
184 s in all. (The verdicts themselves differed from the GPU run's on the
same article - FALSE where the GPU run said TRUE, for a claim the
hand-labelled set has as TRUE, fact027. Temperature is 0, so that is the
3B model and slightly different evidence between runs: what the
evaluation harness measures, not a deployment fault.)

Memory, from each container's cgroup (`memory.peak`, `memory.stat`,
`memory.events`) over those runs and a Chromium extraction:

| Container | Working set (anon) | With file cache | Prod cap |
|---|---|---|---|
| `inference` | 1.4-2.1 GiB | 3.8-4.9 GiB | 6g |
| `ollama` (`llama3.2:3b` Q4_K_M, 4096 ctx, one slot) | 3.2 GiB | 3.5 GiB | 4g |
| `neo4j` | 0.8 GiB | 1.0-1.1 GiB (hit the dev cap 120 times) | 1.5g |
| `backend` | 0.23 GiB with Chromium, 0.08 without | 0.4-0.5 GiB (hit the dev cap 10,276 times) | 1g |
| `searxng` | 0.1 GiB | 0.2 GiB | 256m |
| `caddy` (Google Cloud only) | - | - | 128m |

No container was OOM-killed. "Hit the cap" is the kernel reclaiming file
cache (Neo4j's page cache, Qdrant's storage, the lake) to stay under it:
slower, not broken, and growing with the corpus - hence the higher prod
caps. **~9.6 GiB were resident across the production stack**, which is
the whole sizing argument: 16 GB, not 8.

**CPU:** the LLM dominates. Forced onto the CPU with a 2,807-token prompt
(a claim and five passages): 52 s at 4 threads, 42 s at 8. A four-claim
article spends ~3 minutes in the LLM. Fine for ingestion and a demo;
slow for anyone watching the Live screen.

**Disk:** images ~9 GB, the model cache 7.4 GB, the LLM 2 GB, the graph
0.5 GB, the lake a few MB so far. The VM's disk is 60 GB.

## Where it runs: one Compute Engine VM

**Google Cloud is the target** - the project's final deliverable. The
stack runs there exactly as it runs anywhere: the same three compose
files on one VM. Google Cloud supplies what is around it.

**Not Cloud Run, not GKE.** The stack is stateful in ways a
request-scoped container is not: Qdrant's local storage takes a file
lock, `JobStore` is in memory and single-process, analyses run in
background threads after the response, and inference plus the LLM want
~6 GiB resident and warm. On Cloud Run each of those becomes a redesign
(a managed vector DB, a job queue, always-on instances paying for idle
CPU), for no user who needs scale-to-zero. Neo4j has no place there at
all. A VM keeps every measurement above valid.

**Machine: `e2-standard-4`** (4 vCPU, 16 GB) in `europe-southwest1`
(Madrid). ~$115/month on demand, ~$73 with a one-year commitment
(September 2026 list prices); Google Cloud's $300 free trial covers about
two and a half months. 16 GB is the measured floor, and the E2 family's
4-vCPU shape is the cheapest 16 GB Google sells with enough cores for the
LLM. Spot VMs cost a fraction, but can be stopped at any time,
mid-analysis.

The same compose stack would run on a Hetzner CX43 (8 vCPU, 16 GB, ~€16
a month) - seven times cheaper, and what this document recommended
before Google Cloud was chosen. Nothing in `docker/` depends on Google;
only `deploy/gcp/` does.

### What `deploy/gcp/` creates

Terraform, `~> 7.36` of the Google provider:

- **APIs** enabled (Compute, Secret Manager, IAM, Logging, Monitoring),
  never disabled on destroy.
- **A service account for the VM**: reads its three secrets, writes logs
  and metrics, nothing else. Not the default compute account, which is
  Editor on the project.
- **Three secrets in Secret Manager** - the Neo4j password, SearXNG's
  secret, the storage API key - generated by Terraform, so nobody types or
  commits one. They are in the Terraform state too: `deploy/gcp/.gitignore`
  keeps it out of git; a GCS backend is the next step if more than one
  person deploys.
- **Network:** a custom-mode VPC of its own (the project's `default`
  network opens SSH and RDP to the internet), 80/443 open for Caddy, SSH
  only from Identity-Aware Proxy's range, a static IP.
- **The VM**, Debian 12, 60 GB `pd-balanced`, OS Login. Its startup
  script only clones the repository at `repo_ref`
  and runs `deploy/gcp/vm/bootstrap.sh`, so what the VM does is reviewed
  and versioned with the code. On every boot the bootstrap installs Docker
  and the Ops Agent if missing, renders `backend/.env` from
  `.env-example` plus the secrets (Secret Manager's REST API, the VM's own
  token), and runs `docker compose -p inspiring-news` with all three
  files. **A deploy is "push, then reset the VM".**
- **Backups:** a daily snapshot schedule on the disk, kept 7 days. It
  holds every volume: the lake and Qdrant's corpus (the record), the
  graph (rebuildable), the model caches.
- **Alerts**, only with `alert_email` set: an uptime check on `/healthz`
  every 5 minutes, and a PromQL alert when over half of the last hour's
  web searches came back empty or failed - the failure that otherwise
  looks like a verdict.

`docker-compose.gcp.yml` adds one service: **Caddy**, the only container
on 80/443, forwarding `/healthz` and answering 404 to everything else -
the analysis endpoints take no key, and each run costs minutes of CPU.
With `domain` set, it serves HTTPS with a certificate it renews itself.

**Logs and metrics on Google Cloud:** Docker keeps its rotated json-file
logs; the **Ops Agent** (`deploy/gcp/vm/ops-agent.yaml`) reads them,
unwraps Docker's envelope, parses the backend's JSON lines so `phase`,
`step_seconds`, `total_seconds`, `job` and `url` are fields in Cloud
Logging, and scrapes `/metrics` into Cloud Monitoring's managed
Prometheus, which the search alert queries. Not Docker's `gcplogs` driver:
it ships each line as a string, losing exactly the fields that make the
JSON worth having.

### Deploying

```bash
cd deploy/gcp
cp terraform.tfvars.example terraform.tfvars   # project_id, alert_email, domain
gcloud auth application-default login
terraform init && terraform apply
terraform output follow_first_boot             # 20-30 min: builds, ~10 GB of models
```

Then, before trusting it, the search check below.

### The open risk: search from a datacenter IP

SearXNG scrapes Google, Bing, Brave and the rest from the VM's own
address, and cloud ranges - Google's included - are what search engines
CAPTCHA first. The engine list in `docker/searxng/settings.yml` was
measured from a home connection. **On a new VM, ask SearXNG before
anything else**: the source probe on `/scraper`, or from the VM, `docker
compose -p inspiring-news exec backend curl -s
'http://searxng:8080/search?q=...&format=json'`, and read
`unresponsive_engines`. If the web engines all refuse, every claim comes
back `UNVERIFIED` (`searchUnavailable`) and the search alert fires. The
fix is then an engine with an API key (`docs/decisions/retrieval.md`,
"What would fix it", item 1), not a different VM.

## Floci: the deployment, checked without an account

[Floci](https://floci.io) is a set of local cloud emulators (MIT,
free). `floci-gcp` answers Google Cloud's REST APIs on one port, so
`./scripts/check.sh gcp` (`deploy/gcp/emulator-check.sh`) can, with only
Docker:

1. merge the three compose files;
2. apply `deploy/gcp/` to the emulator - every API call Terraform makes,
   with the provider real deploys use (28 resources);
3. run the VM's own bootstrap (`render-env`) against the secrets just
   created, through Secret Manager's REST API, and check the key it
   renders is the key Terraform generated;
4. plan again and require no changes;
5. destroy everything. ~1.5 minutes.

It caught a real fault on its first run: secrets created with
region-pinned replication came back from the emulator without their
locations, so every plan wanted to replace them. That one is Floci's gap
(it keeps the replication type only); the module now uses automatic
replication, which loses nothing for three random strings.

### What Floci does not prove

- **Nothing runs inside the VM.** Floci manages VMs but executes no guest,
  so the startup script, the Docker install, the Ops Agent config and the
  stack's first boot on Debian are only known on a real VM. The stack
  itself is verified locally (above); its boot on Google Cloud is not.
- **No public images, and a small machine catalog.** Under the emulator
  the VM boots from an image made from a blank disk, and uses
  `n2-standard-4` (same shape) because the catalog has no `e2-standard-4`.
- **No uptime checks, alert policies or snapshot schedules** - Floci's
  Monitoring is the metrics API only. Those resources are skipped under
  the emulator, so they are checked by `terraform validate` alone.
- **Compute Engine is only in floci-gcp's nightlies** (none in the 0.9.0
  release). The check pins `nightly-09302026`; move to a release once one
  carries Compute.

## The production compose file

`docker/docker-compose.prod.yml`, layered on `docker-compose.yml`
(`docker/README.md` has the command), each change commented in place:

- **Only the API is published**, on `127.0.0.1:8000`. Neo4j, SearXNG,
  inference and the LLM stay on the compose network.
- **Every secret is required:** `NEO4J_PASSWORD`, `SEARXNG_SECRET`,
  `STORAGE_API_KEY`; compose refuses to start without them.
  `URL_GUARD_ENABLED` is forced on.
- **`restart: unless-stopped` and log rotation** (json-file, 5 × 10MB)
  everywhere. One four-claim analysis wrote 140 lines, 20KB.
- **The LLM is a service:** `ollama`, pinned, model kept loaded, one
  request at a time; `ollama-pull` fetches `LLM_MODEL` before the backend
  starts.
- **The LLM limits for a CPU** (above) and **memory caps** from the table.

`backend/tests/test_deployment_config.py` holds all of it, and the
Google Cloud layer: only Caddy published, only `/healthz` forwarded, the
firewall's two rules, the state never committable.

## SearXNG's settings and secret

`docker/searxng/settings.yml` is committed and mounted read-only; the
secret comes from `SEARXNG_SECRET`, which SearXNG reads over the file. It
used to be a gitignored copy of a committed `.example`, so it could hold
the secret - and the copy drifted: it ran the full default engine roster
for weeks after the allowlist was measured, and on 2026-10-01 still had
the placeholder secret and lacked the science engines added on
2026-09-28. With no copy there is nothing to drift. Without
`SEARXNG_SECRET` compose refuses to start; empty, SearXNG would refuse
too (it exits on its own placeholder).

The healthcheck used to search: `retrieval.md`, "2026-10-01: the
healthcheck was a search".

## Monitoring

- **Logs:** `LOG_FORMAT=json` (production sets it): one object per line,
  the phase timings as fields, uvicorn's access log through the same
  handler. Locally, `docker compose logs backend`; on Google Cloud, Cloud
  Logging via the Ops Agent.
- **Metrics:** `GET /metrics`, Prometheus' text format, no new
  dependency: runs by outcome and purpose, time per stage, verdicts, and
  `inspiring_web_searches_total{result="results"|"empty"|"unavailable"}`.
  Stage times run from each stage's start to its own end, per claim; the
  log line's "+4.66s" is time since *any* claim's last event, which is not
  the same once claims run concurrently (`src/services/run_metrics.py`).
- **Health:** `GET /healthz` asks inference, SearXNG, the LLM (which must
  serve `LLM_MODEL`, not merely answer) and Neo4j at once, 3 s each: 200,
  or 503 naming what failed and how, never the error text. The container
  healthcheck still asks only whether uvicorn answers.

## What is left

- **A real `terraform apply`**, then the search check on the VM, then one
  analysis there. Everything after "the stack boots on Google Cloud" is
  unverified until then.
- **Where the frontend runs.** Its server routes already send
  `STORAGE_API_KEY`. On Google Cloud it is stateless and fits Cloud Run,
  reaching the VM over the VPC; or on the VM behind Caddy. Either way
  Caddy's 404-for-everything rule changes with it.
- **A domain** for HTTPS (`domain`).
- **Terraform state in a GCS bucket** once more than one person applies.
- **Restoring a snapshot**, once, on purpose, before it is needed.

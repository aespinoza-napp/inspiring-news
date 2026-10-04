# Deployment: Google Cloud, the production stack, and how it is watched

> Read this before touching `docker/docker-compose*.yml`, `docker/caddy/`,
> `docker/frontend.Dockerfile`, `docker/searxng/settings.yml`,
> `deploy/gcp/`, `backend/src/services/{health,run_metrics,log_format}.py`,
> the API key (`require_storage_key`), or choosing or resizing the server.

Until 2026-10-01 the backend container had come up healthy and served
requests, but no analysis had ever run inside it. Everything below starts
from that first run and the measurements taken around it, not from the
compose files' own comments.

## Where each piece stands

| | How it was checked | Result |
|---|---|---|
| Dev stack (`docker-compose.yml`) | A full analysis inside the backend container, 2026-10-01 | Works: 75 s, 4 claims, lake and graph written |
| Production stack (`+ docker-compose.prod.yml`) | Booted on the dev machine, same article, LLM on CPU in its container | Works after one fix (the LLM timeouts below): 184 s, 4 real verdicts |
| Google Cloud infrastructure (`deploy/gcp/`) | `./scripts/check.sh gcp`: applied to Floci, a local Google Cloud emulator | 32 resources apply, the VM's `.env` renders from the secrets they hold (the site password opens the rendered hash), a second plan is empty, destroy is clean |
| The frontend image (`docker/frontend.Dockerfile`) | Built, then run against a stub API, 2026-10-02 | Builds in 1m19s, 259 MB; every `/api/*` route is dynamic (nothing calls the API at build time); the key reached the API from every proxy tried; runs as `node` |
| The front door (`docker/caddy/Caddyfile`) | `caddy:2.10.2` in front of that frontend and the stub, both modes, 2026-10-02 | Without a domain: `/healthz` only, all else 404. With TLS (Caddy's internal CA on `localhost` standing in for a domain): HTTP redirected, `/healthz` open, the UI 401 without the password and served with it, no API path forwarded |
| A real Google Cloud deploy | - | **Not done.** Needs a project with billing: "The first real deploy, step by step" below |

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
| `frontend` (2026-10-02, against a stub API) | 35 MiB idle, 121 MiB peak RSS over ~480 requests | - | 256m |
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
- **A service account for the VM**: reads its four secrets, writes logs
  and metrics, nothing else. Not the default compute account, which is
  Editor on the project.
- **Four secrets in Secret Manager** - the Neo4j password, SearXNG's
  secret, the API key, and the bcrypt hash of the site's password -
  generated by Terraform, so nobody types or commits one. The site's
  password itself never leaves the state (`terraform output -raw
  site_password`). All of them are in the Terraform state:
  `deploy/gcp/.gitignore` keeps it out of git; a GCS backend is the next
  step if more than one person deploys.
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
on 80/443. It forwards `/healthz` to the API and, with `domain` set, the
site to the frontend - over HTTPS, with a certificate it renews itself,
behind a password. Without a domain only `/healthz` answers. "The front
door", below, has why.

**Logs and metrics on Google Cloud:** Docker keeps its rotated json-file
logs; the **Ops Agent** (`deploy/gcp/vm/ops-agent.yaml`) reads them,
unwraps Docker's envelope, parses the backend's JSON lines so `phase`,
`step_seconds`, `total_seconds`, `job` and `url` are fields in Cloud
Logging, and scrapes `/metrics` into Cloud Monitoring's managed
Prometheus, which the search alert queries. Not Docker's `gcplogs` driver:
it ships each line as a string, losing exactly the fields that make the
JSON worth having.

### Where the frontend runs: on the VM, beside the API (2026-10-02)

The frontend is a container in `docker-compose.prod.yml`, built by
`docker/frontend.Dockerfile` (Next's standalone server on Node 22, 259
MB). Like the API it is published on the VM's loopback only, and reached
from outside through Caddy. It calls the API at `http://backend:8000`
across the compose network, sending `STORAGE_API_KEY` from the same
variable the backend reads.

**Rejected: Cloud Run.** The frontend is stateless, which is what Cloud
Run is for, and this document leaned that way until the choice was made.
On the evidence it costs more than it gives:

- **It would have to reach an API that listens on loopback.** From Cloud
  Run that means Direct VPC egress or a Serverless VPC Access connector,
  the API published on the VM's subnet address instead of `127.0.0.1`,
  and a firewall rule for it - the one place in the design where port
  8000 would leave the machine. On the VM it is a hop across the compose
  network.
- **A custom domain in Madrid needs a load balancer.** Cloud Run's domain
  mappings are not offered in `europe-southwest1`, and are Preview
  everywhere, "not recommended for production services" (Google's Cloud
  Run documentation, read 2026-10-02). What it names instead is a global
  external Application Load Balancer - a forwarding rule billed by the
  hour whether anyone visits - or Firebase Hosting in front. The VM
  already has Caddy, a static IP and 80/443 open: HTTPS there is one
  variable.
- **A second deploy path**: an image registry, a push and a deploy per
  release, beside "push, then reset the VM", which builds the frontend
  with everything else.
- **Nothing to scale.** The users are the authors and a few reviewers,
  and every page waits on the same VM's API anyway: a frontend scaling
  on its own would queue behind the same CPU. Scale to zero, and a
  frontend that stays up while the VM restarts, are worth nothing while
  the API it shows is on that VM.
- **It is cheap where it is.** 35 MiB idle, 121 MiB at peak; the 256m
  cap is under 2% of the 16 GB the stack was sized for.

### The front door

Three rules, held by `backend/tests/test_deployment_config.py` and
`backend/tests/api/test_api_key.py`:

1. **The API takes a key on everything but `/healthz`, `/metrics` and
   polling a job by id** (`STORAGE_API_KEY`, sent as `X-API-Key`). Until
   2026-10-02 the analysis endpoints were open on purpose - "the key
   guards stored content, not the ability to run an analysis" - which held
   while only a browser on the same machine could reach them. Behind a
   public site, one `POST /analyze/jobs` is minutes of the server's CPU
   and a request to an arbitrary site, and `/enrich` and `/verify-claim`
   can start Chromium. A new route is closed unless `OPEN_ENDPOINTS` says,
   with a reason, that it may be open. `/metrics` is open on the API but
   not forwarded: the Ops Agent scrapes it on loopback.
2. **The site takes a password** (user `editor`, Caddy's `basic_auth`).
   The key alone protects nothing once the frontend is public: its server
   routes attach the key to every call they forward, so an open frontend
   is the API with the key already in it - the Cypher console, ingestion,
   an analysis per click. The key stops anyone calling the API directly;
   the password stops anyone calling it through the frontend. Terraform
   generates the password, and only its bcrypt hash reaches Secret
   Manager, the VM and Caddy. The hash is `random_password`'s
   `bcrypt_hash`, kept in the state: Terraform's `bcrypt()` function
   salts anew on every plan, and the secret would never stop changing.
3. **The site only over HTTPS.** Basic auth sends the password with every
   request, so Caddy hands the frontend only requests that arrived over
   TLS (`@https protocol https`).

With `domain` set, Caddy gets a Let's Encrypt certificate for it,
redirects HTTP to HTTPS and serves the site. **Without a domain the
fallback is closed, not cleartext:** Caddy listens on `:80` and answers
`/healthz` alone; every other path is a 404 that says where the site is.
The site is then reached through an IAP tunnel to the VM's loopback
(`terraform output ui_tunnel`: the UI on `127.0.0.1:3000`, the API on
`127.0.0.1:8000`), which takes a Google login with SSH rights on the
project and no password of ours. The tunnel works with a domain too - it
is the way to the API, which Caddy never forwards.

Two details found on the way, both checked now:

- **The hash in `backend/.env` is single-quoted.** It is `$2a$10$...`,
  and compose reads each unquoted `$word` as a variable: tried on
  2026-10-02, Caddy received `$2a$10`, which no password matches.
  `./scripts/check.sh gcp` checks that the merged config hands Caddy the
  hash intact, and that the hash the VM renders accepts the password
  Terraform outputs.
- **Shell scripts are LF** (`.gitattributes`). With Git for Windows'
  `core.autocrlf=true` they were checked out CRLF: the Floci check died
  on `$'\r': command not found`, and the VM's startup script, rendered
  by `terraform apply` from such a checkout, would have died on its first
  line. `vm.tf` strips CRs from it as well, for a checkout made before
  the rule.

### The first real deploy, step by step

Not done yet: it needs a project with billing. Everything up to the VM's
first boot has been applied to Floci; nothing after it has run anywhere
but the dev machine.

**Before you start**

- A Google Cloud project with billing, on which you are Owner: Terraform
  enables APIs, creates a service account and grants it roles.
- `gcloud`, and Terraform 1.6 or later (or the `hashicorp/terraform:1.16`
  image the Floci check uses).
- **The VM runs what is on GitHub, not what is on your disk:** it clones
  `repo_url` at `repo_ref` (`main` by default). Merge and push first.
- From a Windows checkout, `git ls-files --eol deploy/gcp scripts` should
  show `w/lf` on every line (see "The front door"). `vm.tf` copes with a
  CRLF template, but the habit is cheaper than the diagnosis.
- Optional: a domain whose DNS you control. Without one only `/healthz`
  is public, and the site is reached through the tunnel.

**1. Credentials and variables**

```bash
gcloud auth login
gcloud auth application-default login      # what Terraform uses
gcloud config set project <project-id>

cd deploy/gcp
cp terraform.tfvars.example terraform.tfvars   # project_id; alert_email; domain
terraform init
```

**2. With a domain: the address first, then DNS.** Caddy asks for the
certificate as soon as it starts, about a minute into the boot, and Let's
Encrypt refuses a name that does not resolve to the VM yet. Caddy retries
with backoff, but repeated failures count against the CA's limits.

```bash
terraform apply -target=google_project_service.apis -target=google_compute_address.vm
terraform output external_ip                 # an A record: <domain> -> this address
dig +short <domain>                          # repeat until it prints external_ip
```

**3. Apply**

```bash
terraform plan        # 32 to add (26 after step 2); 4 more with alert_email (a channel, the uptime check, two alerts)
terraform apply
```

The VM boots as soon as it exists. The secrets are created before it
(`depends_on`), but the grant that lets it read them can take a minute to
propagate.

**4. Follow the first boot** (20-30 minutes: the images build, ~10 GB of
models download):

```bash
eval "$(terraform output -raw follow_first_boot)"   # eval: the command carries its own quotes
```

The journal of `google-startup-scripts`, each line prefixed by the
startup-script runner. What the bootstrap prints, in order:

```
[bootstrap] installing Docker Engine and the compose plugin
[bootstrap] installing the Ops Agent
[bootstrap] rendering backend/.env from Secret Manager
[bootstrap] starting the stack (the first boot builds the images and downloads ~10GB of models)
  ... compose: image pulls, three builds, then a long quiet wait: the
      backend starts only once inference is healthy (up to 15 minutes)
SERVICE    STATUS
backend    Up ... (healthy)
caddy      Up ...
frontend   Up ... (healthy)
...
[bootstrap] site: https://<domain>/ (user editor, 'terraform output -raw site_password'); health: https://<domain>/healthz
[bootstrap] done
```

Without a domain the `site:` line reads `no domain: only
http://<external_ip>/healthz is public; the UI is behind 'terraform output
ui_tunnel'`. `install_*` print nothing on a later boot: they are skipped
once installed. **If it stops after `rendering backend/.env`** with a
curl 403, the VM could not read its secrets yet: reset it (`gcloud
compute instances reset inspiring-news --zone europe-southwest1-a`) and
the next boot renders again. The certificate, on the VM (`eval
"$(terraform output -raw ssh)"`): `sudo docker logs inspiring-news-caddy-1
2>&1 | grep -i certificate` should show it obtained. These commands use
the default `name` and `zone`; `terraform output ssh` prints yours.

**5. Search from the VM's address, before anything else** (the reason is
the next section):

```bash
gcloud compute ssh inspiring-news --zone europe-southwest1-a --tunnel-through-iap --command \
  "sudo docker exec inspiring-news-backend-1 curl -s 'http://searxng:8080/search?q=coral+reef+restoration&format=json'" \
  | python3 -c "import json, sys; d = json.load(sys.stdin); print(len(d['results']), 'results'); print('unresponsive:', d['unresponsive_engines'])"
```

Try two or three queries, one in Spanish. Tens of results with a few
engines unresponsive is a working search. **Zero results with Google,
Bing, Brave and the rest listed as unresponsive (CAPTCHA, too many
requests, access denied) means stop**: every claim would come back
`UNVERIFIED` with `searchUnavailable`, which looks like a verdict. The
fix is an engine with an API key (`docs/decisions/retrieval.md`, "What
would fix it", item 1), not another VM.

**6. Health**

```bash
curl -s https://<domain>/healthz                               # with a domain
curl -s http://$(terraform output -raw external_ip)/healthz    # without
```

200 with every dependency `ok`, or 503 naming the one that is not. The
LLM failing in the first minutes is its model still being pulled.

**7. The tunnel, the key, and the smoke test.** In a terminal of its own,
left open:

```bash
eval "$(terraform output -raw ui_tunnel)"
```

Then, from another:

```bash
KEY="$(terraform output -raw storage_api_key)"
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8000/analyze/jobs   # 401: the key is on
scripts/smoke.sh http://127.0.0.1:8000 "$KEY"            # add --claim for one real claim, ~1 min
```

With a domain, also: `https://<domain>/` asks for a password (user
`editor`, `terraform output -raw site_password`), and `http://<domain>/`
redirects to it.

**8. One analysis.** In the site (or `http://127.0.0.1:3000` through the
tunnel), the article the stack was measured with locally: Yale e360's
"At Least 124 Environmental Defenders Killed", forced past the cache. Or
through the tunnel:

```bash
curl -s -X POST -H "X-API-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"url": "<article-url>", "forceRefresh": true}' http://127.0.0.1:8000/analyze/jobs   # {"jobId": ...}
curl -s http://127.0.0.1:8000/analyze/jobs/<jobId>        # poll until status is done
```

Expect about three minutes for four claims (184 s on the dev machine's
CPU). It worked if every claim has a verdict, none says "LLM provider was
unreachable", none is `searchUnavailable`, and `/live` showed sources for
each.

**9. Write it down.** The boot's duration, the search counts, the
analysis's time and verdicts, `sudo docker stats --no-stream` on the VM:
into "Where each piece stands" above, and the roadmap's Phase 3 item.

`terraform destroy` removes everything but the APIs and the disk's
snapshots (`KEEP_AUTO_SNAPSHOTS`).

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

1. merge the three compose files, and check the site password's hash
   reaches Caddy intact;
2. apply `deploy/gcp/` to the emulator - every API call Terraform makes,
   with the provider real deploys use (32 resources);
3. run the VM's own bootstrap (`render-env`) against the secrets just
   created, through Secret Manager's REST API, and check the API key it
   renders is the key Terraform generated, and the password hash it
   renders accepts the password Terraform outputs;
4. plan again and require no changes;
5. destroy everything. ~1.5 minutes once the images are pulled.

It caught a real fault on its first run: secrets created with
region-pinned replication came back from the emulator without their
locations, so every plan wanted to replace them. That one is Floci's gap
(it keeps the replication type only); the module now uses automatic
replication, which loses nothing for a few random strings. On
2026-10-02 it caught the CRLF checkout ("The front door").

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
- **No certificate.** Nothing in the check reaches Let's Encrypt. The
  HTTPS half of the Caddyfile was run with Caddy's internal CA on
  `localhost` instead (2026-10-02, "Where each piece stands"); a real one
  needs a real domain pointing at a real VM.
- **Compute Engine is only in floci-gcp's nightlies** (none in the 0.9.0
  release). The check pins `nightly-09302026`; move to a release once one
  carries Compute.

## The production compose file

`docker/docker-compose.prod.yml`, layered on `docker-compose.yml`
(`docker/README.md` has the command), each change commented in place:

- **Only the API and the UI are published**, on `127.0.0.1:8000` and
  `127.0.0.1:3000`. Neo4j, SearXNG, inference and the LLM stay on the
  compose network.
- **The frontend is a service** ("Where the frontend runs"): it reaches
  the API as `backend:8000` with the key, starts without waiting for it,
  and its healthcheck asks the prerendered home page, never the API.
- **Every secret is required:** `NEO4J_PASSWORD`, `SEARXNG_SECRET`,
  `STORAGE_API_KEY` (the backend's and the frontend's, one variable);
  compose refuses to start without them. `URL_GUARD_ENABLED` is forced
  on.
- **`restart: unless-stopped` and log rotation** (json-file, 5 × 10MB)
  everywhere. One four-claim analysis wrote 140 lines, 20KB.
- **The LLM is a service:** `ollama`, pinned, model kept loaded, one
  request at a time; `ollama-pull` fetches `LLM_MODEL` before the backend
  starts.
- **The LLM limits for a CPU** (above) and **memory caps** from the table.

`backend/tests/test_deployment_config.py` holds all of it, and the
Google Cloud layer: only Caddy published; only `/healthz` forwarded to
the API; the UI only over HTTPS and behind the password; the domain's
way from `variables.tf` to the Caddyfile; every secret Terraform creates
read by the bootstrap; the password hash quoted; the scripts LF; the
firewall's two rules; the state never committable.

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
  analysis there: "The first real deploy, step by step". Everything after
  "the stack boots on Google Cloud" is unverified until then - the
  certificate included.
- **A domain**, chosen and pointed at `external_ip`. The variable, the
  certificate and the fallback without one are in place.
- **Public pages.** Everything the site serves is behind the password. A
  page meant for anyone - the reader view - needs its paths, and its
  `/api` proxies, exempted in the Caddyfile on purpose, and
  `test_the_ui_is_served_only_over_https_and_behind_a_password` changed
  to match; its backend routes need the same decision in
  `OPEN_ENDPOINTS`.
- **Terraform state in a GCS bucket** once more than one person applies.
- **Restoring a snapshot**, once, on purpose, before it is needed.

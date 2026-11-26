"""
The deployment's configuration, held by tests: the compose files and
SearXNG's settings are outside src/, so nothing else would notice them
drift.

Each of these has gone wrong once. SearXNG's live settings drifted from
the committed example for weeks; its healthcheck sent a real search to
every engine every 5 seconds; the Neo4j password was in the compose file
in plain text. docs/decisions/deployment.md.

The front door is held here too: what Caddy forwards, that the UI is
only served over HTTPS behind a password, and that the domain, the
secrets and the API key each reach the container that needs them. The
Caddyfile and the frontend image were exercised against the real images
on 2026-10-02; these keep them the way they were exercised.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

DOCKER = Path(__file__).resolve().parents[2] / "docker"

BASE = DOCKER / "docker-compose.yml"
PROD = DOCKER / "docker-compose.prod.yml"
SEARXNG_SETTINGS = DOCKER / "searxng" / "settings.yml"


class ComposeLoader(yaml.SafeLoader):
    """Compose's merge tags, kept as (tag, value) so a test can see them."""


def _tagged(tag):
    def construct(loader, node):
        if isinstance(node, yaml.SequenceNode):
            return (tag, loader.construct_sequence(node))
        if isinstance(node, yaml.MappingNode):
            return (tag, loader.construct_mapping(node))
        return (tag, loader.construct_scalar(node))
    return construct


for _tag in ("!reset", "!override"):
    ComposeLoader.add_constructor(_tag, _tagged(_tag))


def load(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=ComposeLoader)


@pytest.fixture(scope="module")
def base() -> dict:
    return load(BASE)["services"]


@pytest.fixture(scope="module")
def prod() -> dict:
    return load(PROD)


# ----------------------------------------------------------------------
# SearXNG
# ----------------------------------------------------------------------


def test_searxng_runs_the_committed_settings_file_read_only(base):
    """
    No local copy to drift: the file in git is the file that runs. It used
    to be a gitignored copy of a committed `.example`, and the copy ran
    the full default engine roster for weeks after the allowlist was
    measured.
    """

    assert "./searxng/settings.yml:/etc/searxng/settings.yml:ro" in base["searxng"]["volumes"]


def test_the_committed_searxng_settings_hold_no_secret():

    settings = yaml.safe_load(SEARXNG_SETTINGS.read_text(encoding="utf-8"))

    assert "secret_key" not in settings.get("server", {})


def test_searxng_refuses_to_start_without_its_secret(base):

    assert any(
        entry.startswith("SEARXNG_SECRET=${SEARXNG_SECRET:?")
        for entry in base["searxng"]["environment"]
    )


def test_searxng_answers_the_json_the_backend_asks_for():
    """SearxngClient calls ?format=json; without it every search is a 403."""

    settings = yaml.safe_load(SEARXNG_SETTINGS.read_text(encoding="utf-8"))

    assert "json" in settings["search"]["formats"]


def test_no_healthcheck_sends_a_search_to_the_engines(base):
    """
    A search is not local: SearXNG forwards it to every enabled engine.
    The healthcheck used to search every 5 seconds - ~17,000 searches a
    day per engine from an idle stack, and Brave suspended this instance
    for exactly that query.
    """

    for name, service in base.items():
        test = " ".join(service.get("healthcheck", {}).get("test", []))
        assert "/search" not in test, name


# ----------------------------------------------------------------------
# Production overrides
# ----------------------------------------------------------------------


# Services the production file adds that run for good (ollama-pull is
# one-shot). Each must meet the same rules as the base file's.
PROD_ONLY = {"ollama", "frontend"}


def test_production_publishes_nothing_but_the_api_and_the_ui_on_loopback(base, prod):

    for name, service in base.items():
        if not service.get("ports") or name == "backend":
            continue
        assert prod["services"][name].get("ports") == ("!reset", []), name

    tag, ports = prod["services"]["backend"]["ports"]
    assert tag == "!override"
    assert ports == ["127.0.0.1:8000:8000"]

    assert prod["services"]["frontend"]["ports"] == ["127.0.0.1:3000:3000"]

    for name in PROD_ONLY - {"frontend"}:
        assert not prod["services"][name].get("ports"), name


def test_every_long_running_service_restarts_and_rotates_its_logs(base, prod):

    services = prod["services"]
    long_running = set(base) | PROD_ONLY

    for name in long_running:
        assert services[name].get("restart") == "unless-stopped", name
        assert services[name]["logging"]["options"]["max-size"], name


def test_production_will_not_start_without_its_secrets(prod):

    environment = prod["services"]["backend"]["environment"]

    assert any(e.startswith("STORAGE_API_KEY=${STORAGE_API_KEY:?") for e in environment)
    assert "URL_GUARD_ENABLED=true" in environment


def test_every_production_service_has_a_memory_ceiling(base, prod):
    """
    One process without a ceiling can take the host's memory from every
    other one - and the LLM and the models share it.
    """

    for name in set(base) | PROD_ONLY:
        limit = prod["services"].get(name, {}).get("mem_limit") or base.get(name, {}).get("mem_limit")
        assert limit, name


def test_production_uses_the_cpu_limits_the_pilot_measured(prod):
    """
    The dev defaults assume a GPU. On a CPU the LLM timed out at 30 s
    (2026-10-01) and inference at 30 s under four claims at once (the
    X-Fact pilot, 2026-10-13), each time turning a claim into an outage
    rather than a verdict.
    """

    environment = dict(
        e.split("=", 1) for e in prod["services"]["backend"]["environment"]
    )

    assert int(environment["LLM_MAX_CONCURRENCY"]) == 1
    assert float(environment["LLM_TIMEOUT"]) >= 180
    assert float(environment["INFERENCE_TIMEOUT"]) >= 120
    assert int(environment["CLAIM_MAX_CONCURRENCY"]) <= 2


def test_the_backend_waits_for_the_llm_model_to_be_pulled(prod):

    depends = prod["services"]["backend"]["depends_on"]

    assert depends["ollama-pull"]["condition"] == "service_completed_successfully"
    assert "http://ollama:11434/v1" in " ".join(prod["services"]["backend"]["environment"])


# ----------------------------------------------------------------------
# Google Cloud (docker-compose.gcp.yml, deploy/gcp/)
# ----------------------------------------------------------------------

GCP = DOCKER / "docker-compose.gcp.yml"
CADDYFILE = DOCKER / "caddy" / "Caddyfile"
DEPLOY = DOCKER.parent / "deploy" / "gcp"


def test_on_google_cloud_only_the_proxy_faces_the_internet(base):
    """
    The VM's firewall opens 80 and 443 (deploy/gcp/network.tf); the one
    container listening there must be Caddy, and nothing the gcp layer adds
    may publish anything else - the frontend included, which the prod
    file keeps on loopback.
    """

    services = load(GCP)["services"]

    published = {name for name, service in services.items() if service.get("ports")}
    assert published == {"caddy"}
    assert services["caddy"]["ports"] == ["80:80", "443:443"]


UNIVERSE_SITE = "{$UNIVERSE_ADDRESS:http://universe.invalid} {"


def caddy_all() -> str:
    """The Caddyfile without its comments, which name every route too."""

    text = CADDYFILE.read_text(encoding="utf-8")

    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def caddy_code() -> str:
    """The newsroom's site: everything before the universe's block."""

    code = caddy_all()

    return code[:code.index(UNIVERSE_SITE)]


def universe_code() -> str:
    """The readers' universe: its block, the file's last."""

    code = caddy_all()

    return code[code.index(UNIVERSE_SITE):]


def caddy_handles(code: str | None = None) -> list[tuple[str, str]]:
    """
    Every `handle` block of `code` (the newsroom's site by default) as
    (matcher, body), in file order; "" for the catch-all. Braces are
    counted rather than matched by a regex: the bodies hold
    {$PLACEHOLDERS} and nested blocks.
    """

    code = caddy_code() if code is None else code
    handles = []

    for match in re.finditer(r"^\s*handle(?:[ \t]+([^\s{]+))?[ \t]*\{", code, flags=re.MULTILINE):
        depth, end = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(code[end], 0)
            end += 1
        handles.append((match.group(1) or "", code[match.end():end - 1]))

    return handles


def test_the_proxy_forwards_healthz_to_the_api_and_nothing_else_of_it():
    """
    The API's other endpoints take the key, and whatever needs them goes
    through the frontend's server routes (or an SSH tunnel). /healthz is
    the uptime check's, and the one endpoint open by design.
    """

    to_backend = [matcher for matcher, body in caddy_handles() if "backend:" in body]

    assert to_backend == ["/healthz"]
    assert caddy_code().count("backend:") == 1
    assert "reverse_proxy backend:8000" in dict(caddy_handles())["/healthz"]


def test_the_ui_is_served_only_over_https_and_behind_a_password():
    """
    The frontend's server routes attach the API key to every call they
    forward: open, the site would be the backend with the key in it -
    the Cypher console, ingestion, minutes of CPU per analysis. And the
    password crosses the network in every request, so never over plain
    HTTP: without a domain the site is not served at all.
    """

    code = caddy_code()
    handles = caddy_handles()

    to_frontend = [matcher for matcher, body in handles if "frontend:" in body]
    assert to_frontend == ["@reader", "@https"]
    assert code.count("frontend:") == 2
    assert re.search(r"^\s*@https\s+protocol\s+https\s*$", code, flags=re.MULTILINE)

    ui = dict(handles)["@https"]
    assert "reverse_proxy frontend:3000" in ui
    assert re.search(r"basic_auth\s*\{\s*\{\$SITE_USER:editor\}\s+\{\$SITE_PASSWORD_HASH\}\s*\}", ui)


def test_only_the_reader_view_is_served_without_the_password():
    """
    /reader is public. What a public visitor may reach is exactly its
    pages, their proxies (onto backend routes that are open anyway)
    and the static bundles; anything added here skips the password, so
    the list is held. The frontend link list never prefetches past it.
    """

    code = caddy_code()

    matcher = re.search(r"^\s*@reader\s+path\s+(.+)$", code, flags=re.MULTILINE)
    assert matcher, "the @reader matcher is gone"
    assert matcher.group(1).split() == [
        "/reader", "/reader/*", "/api/reader/*", "/map", "/map/*", "/today", "/for-you", "/api/map/*",
        "/account", "/api/account/*", "/_next/static/*", "/favicon.ico",
    ]

    reader = dict(caddy_handles())["@reader"]
    assert reader.strip() == "reverse_proxy frontend:3000"
    assert "basic_auth" not in reader

    # The open handle comes before the password one, which would
    # otherwise answer first with 401.
    matchers = [m for m, _ in caddy_handles()]
    assert matchers.index("@reader") < matchers.index("@https")

    # Every proxy the reader pages use is one Caddy lets through.
    proxies = sorted(
        path.parent.relative_to(FRONTEND / "src" / "app").as_posix()
        for path in (FRONTEND / "src" / "app" / "api" / "reader").rglob("route.ts")
    )
    # stories: the newsroom's published articles (src/api/publish_routes.py),
    # open on the backend like articles. Their page, /reader/stories/<id>,
    # reads the backend from the server and has no proxy of its own.
    assert proxies == ["api/reader/articles", "api/reader/articles/[id]", "api/reader/stories"]

    # The news map's one proxy, which forwards only /map's four routes
    # (open on the backend: test_api_key.py::OPEN_ENDPOINTS).
    map_proxies = sorted(
        path.parent.relative_to(FRONTEND / "src" / "app").as_posix()
        for path in (FRONTEND / "src" / "app" / "api" / "map").rglob("route.ts")
    )
    assert map_proxies == ["api/map/[...path]"]
    allowlist = (FRONTEND / "src" / "app" / "api" / "map" / "[...path]" / "route.ts").read_text(encoding="utf-8")

    # The account proxy forwards nineteen routes, each with its one
    # method, and only the session cookie.
    account = (FRONTEND / "src" / "app" / "api" / "account" / "[...path]" / "route.ts").read_text(encoding="utf-8")
    assert re.search(r"const ROUTES: Record<string, \"GET\" \| \"POST\"> = \{(.*?)\};", account, re.S).group(1).count(":") == 19
    assert 'const SESSION_COOKIE = "in_session";' in account
    assert 'path === "articles" || path === "entities" || path === "search" || ARTICLE_LINKS.test(path)' in allowlist

    nav = (FRONTEND / "src" / "components" / "NavLinks.tsx").read_text(encoding="utf-8")
    assert "prefetch={onPublicPage" in nav
    assert 'const PUBLIC = ["/reader", "/map", "/today", "/for-you", "/account"];' in nav


def test_everything_else_at_the_door_is_a_404():

    matcher, body = caddy_handles()[-1]

    assert matcher == ""
    assert re.search(r"^\s*respond\s+.*\b404\s*$", body, flags=re.MULTILINE)
    assert "reverse_proxy" not in body


def test_the_vm_firewall_opens_only_the_proxy_and_iap_ssh():

    network = (DEPLOY / "network.tf").read_text(encoding="utf-8")
    ports = re.findall(r'ports\s*=\s*\[([^\]]*)\]', network)

    assert sorted(ports) == ['"22"', '"80", "443"']
    # SSH from Identity-Aware Proxy's range only, never the internet.
    assert '"35.235.240.0/20"' in network


def test_no_terraform_state_or_real_tfvars_is_committable():
    """The state holds the generated secrets in plain text."""

    ignored = (DEPLOY / ".gitignore").read_text(encoding="utf-8").split()

    for pattern in ("*.tfstate", "*.tfstate.*", "terraform.tfvars", ".terraform/"):
        assert pattern in ignored


def test_scripts_for_linux_reach_it_with_lf_line_endings():
    """
    Git for Windows checks text out as CRLF, and Linux bash reads the CR
    as part of each command: `./scripts/check.sh gcp` died on it on
    2026-10-02, and the VM's startup script would have too.
    .gitattributes fixes new checkouts; vm.tf strips CRs from the rendered
    startup script for a checkout made before it.
    """

    attributes = (DOCKER.parent / ".gitattributes").read_text(encoding="utf-8")
    vm = (DEPLOY / "vm.tf").read_text(encoding="utf-8")

    assert re.search(r"^\*\.sh\s+text eol=lf$", attributes, flags=re.MULTILINE)
    assert re.search(r"^\*\.tftpl\s+text eol=lf$", attributes, flags=re.MULTILINE)
    assert re.search(r'startup-script = replace\(templatefile\(.*?\), "\\r", ""\)', vm, flags=re.DOTALL)


# ----------------------------------------------------------------------
# The frontend (docker-compose.prod.yml, docker/frontend.Dockerfile)
# ----------------------------------------------------------------------

FRONTEND = DOCKER.parent / "frontend"
FRONTEND_DOCKERFILE = DOCKER / "frontend.Dockerfile"


def test_the_frontend_is_built_from_its_standalone_output(prod):
    """
    The image ships .next/standalone, which `next build` only writes with
    `output: "standalone"`: without it the COPY fails.
    """

    build = prod["services"]["frontend"]["build"]
    assert build == {"context": "../frontend", "dockerfile": "../docker/frontend.Dockerfile"}

    assert re.search(r'output:\s*"standalone"', (FRONTEND / "next.config.js").read_text(encoding="utf-8"))

    dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    assert "/app/.next/standalone ./" in dockerfile
    assert "/app/.next/static ./.next/static" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile


def test_the_frontend_image_runs_unprivileged_and_listens_beyond_its_container_id():
    """
    Docker sets HOSTNAME to the container id, and the standalone server
    binds to whatever HOSTNAME names: without the override neither the
    healthcheck on 127.0.0.1 nor Caddy across the compose network would
    reach it.
    """

    dockerfile = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
    final_stage = dockerfile.rsplit("\nFROM ", 1)[1]

    assert re.search(r"^USER node$", final_stage, flags=re.MULTILINE)
    assert "HOSTNAME=0.0.0.0" in final_stage
    assert "PORT=3000" in final_stage


def test_no_secret_or_host_build_reaches_the_frontend_image():

    ignored = (FRONTEND / ".dockerignore").read_text(encoding="utf-8").split()

    for pattern in (".env*", "node_modules/", ".next/"):
        assert pattern in ignored

    # Nor passed at build time, where it would land in a layer.
    assert not re.search(r"^ARG\b", FRONTEND_DOCKERFILE.read_text(encoding="utf-8"), flags=re.MULTILINE)


def test_the_frontend_reaches_the_api_over_the_compose_network_with_the_key(prod):
    """
    From the backend's own variable, so the key the frontend sends is the
    key the backend expects, and neither starts without it.
    """

    frontend = prod["services"]["frontend"]["environment"]
    backend = prod["services"]["backend"]["environment"]

    assert "BACKEND_URL=http://backend:8000" in frontend

    def key_of(environment):
        return next(e for e in environment if e.startswith("STORAGE_API_KEY="))

    assert key_of(frontend).startswith("STORAGE_API_KEY=${STORAGE_API_KEY:?")
    assert key_of(backend).startswith("STORAGE_API_KEY=${STORAGE_API_KEY:?")


def test_the_frontend_healthcheck_asks_only_the_frontend(prod):
    """
    A backend still loading its models (10-15 minutes on a first boot)
    must not mark the UI unhealthy, or hold it back: the check asks the
    prerendered home page, nothing behind /api, and there is no
    depends_on.
    """

    frontend = prod["services"]["frontend"]
    test = " ".join(frontend["healthcheck"]["test"])

    assert "http://127.0.0.1:3000/'" in test
    assert "/api" not in test and "backend" not in test
    assert "depends_on" not in frontend


# ----------------------------------------------------------------------
# The domain and the secrets, from Terraform to the container
# ----------------------------------------------------------------------

BOOTSTRAP = DEPLOY / "vm" / "bootstrap.sh"


def test_the_domain_reaches_caddy():
    """
    variables.tf -> vm.tf -> the startup script -> bootstrap.sh's .env ->
    the gcp compose layer -> the Caddyfile's site address. A break
    anywhere and Caddy serves ":80" with no certificate, silently.
    """

    vm = (DEPLOY / "vm.tf").read_text(encoding="utf-8")
    startup = (DEPLOY / "startup.sh.tftpl").read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    caddy = load(GCP)["services"]["caddy"]

    assert re.search(
        r'site_address\s+= var\.domain != "" \? var\.domain : \(var\.free_hostnames \? "admin\.\$\{local\.free_name\}" : ":80"\)',
        vm,
    )
    assert re.search(r"site_address\s+= local\.site_address", vm)
    assert 'export SITE_ADDRESS="${site_address}"' in startup
    assert 'echo "SITE_ADDRESS=${SITE_ADDRESS:-:80}"' in bootstrap
    assert "SITE_ADDRESS=${SITE_ADDRESS:-:80}" in caddy["environment"]
    assert caddy_code().lstrip().startswith("{$SITE_ADDRESS::80} {")


def test_the_universe_address_reaches_caddy_and_is_never_empty():
    """
    The same way for the universe: variables.tf -> vm.tf -> the startup
    script -> the .env -> compose -> its block of the Caddyfile. Never
    empty on the way: Caddy takes an empty address for a global options
    block and refuses the whole file (`server block without any key is
    global configuration`, tried 2026-11-26), and /healthz goes down with
    the universe. Compose's `:-` covers unset and empty both.
    """

    vm = (DEPLOY / "vm.tf").read_text(encoding="utf-8")
    startup = (DEPLOY / "startup.sh.tftpl").read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    caddy = load(GCP)["services"]["caddy"]

    assert re.search(
        r'universe_address = var\.universe_domain != "" \? var\.universe_domain : \(var\.free_hostnames \? local\.free_name : "http://\$\{google_compute_address\.vm\.address\}"\)',
        vm,
    )
    assert re.search(r"universe_address\s+= local\.universe_address", vm)
    assert 'export UNIVERSE_ADDRESS="${universe_address}"' in startup
    assert 'echo "UNIVERSE_ADDRESS=${UNIVERSE_ADDRESS:-http://universe.invalid}"' in bootstrap
    assert "UNIVERSE_ADDRESS=${UNIVERSE_ADDRESS:-http://universe.invalid}" in caddy["environment"]
    assert UNIVERSE_SITE in caddy_all()


def test_the_domain_variable_takes_a_bare_hostname_only():
    """
    The pattern is read from variables.tf and run here: Terraform's
    regex() is RE2, and this one means the same in Python's re.
    """

    variables = (DEPLOY / "variables.tf").read_text(encoding="utf-8")
    pattern = re.search(r'can\(regex\("([^"]+)", var\.domain\)\)', variables).group(1)

    for good in ("factcheck.example.org", "news.inspiring-news.es", "a.io"):
        assert re.search(pattern, good), good

    for bad in ("https://factcheck.example.org", "factcheck.example.org/", "factcheck.example.org:443",
                "Factcheck.example.org", "localhost", "34.175.1.2", "-x.example.org"):
        assert not re.search(pattern, bad), bad


def test_every_secret_terraform_creates_is_read_on_the_vm():
    """
    main.tf's map and bootstrap.sh's reads, side by side: a secret created
    and never read, or read and never created, would fail a real boot only.
    """

    main = (DEPLOY / "main.tf").read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    secrets_block = re.search(r"  secrets = \{(.*?)\n  \}", main, flags=re.DOTALL).group(1)
    created = set(re.findall(r'"([a-z0-9-]+)"\s*=', secrets_block))
    read = set(re.findall(r"\$\(secret ([a-z0-9-]+)\)", bootstrap))

    assert created == read == {"neo4j-password", "searxng-secret", "storage-api-key", "site-password-hash"}

    # Given, not generated, and only when given: read as optional, so a VM
    # without it still boots.
    optional = set(re.findall(r'optional_secrets = .*?\{ "([a-z0-9-]+)" = var\.', main))
    assert optional == set(re.findall(r"\$\(optional_secret ([a-z0-9-]+)\)", bootstrap)) == {"groq-api-key"}
    assert "all_secrets = merge(local.secrets, local.optional_secrets)" in main
    assert main.count("for_each = local.all_secrets") == 3


def test_only_the_site_password_hash_reaches_the_vm():
    """
    The password stays in the Terraform state and its sensitive output;
    the VM and Caddy get the bcrypt hash - kept in the state, not
    Terraform's bcrypt(), which salts anew on every plan.
    """

    main = (DEPLOY / "main.tf").read_text(encoding="utf-8")
    outputs = (DEPLOY / "outputs.tf").read_text(encoding="utf-8")
    code = "\n".join(line for line in main.splitlines() if not line.strip().startswith("#"))

    assert '"site-password-hash" = random_password.site.bcrypt_hash' in code
    assert "bcrypt(" not in code
    assert re.search(
        r'output "site_password" \{[^}]*value\s*=\s*random_password\.site\.result[^}]*sensitive\s*=\s*true',
        outputs,
    )


def test_the_password_hash_is_rendered_where_compose_cannot_expand_it():
    """
    A bcrypt hash is `$2a$10$...`. Unquoted in backend/.env, compose reads
    each `$word` as a variable and Caddy gets "$2a$10" - tried on
    2026-10-02. ./scripts/check.sh gcp checks the merged config as well.
    """

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    caddy = load(GCP)["services"]["caddy"]

    assert "echo \"SITE_PASSWORD_HASH='$site_hash'\"" in bootstrap
    assert any(e.startswith("SITE_PASSWORD_HASH=${SITE_PASSWORD_HASH:?") for e in caddy["environment"])


def test_ollama_holds_one_model_and_every_configured_model_is_pulled(prod):
    """
    With a writer beside the verifier, both stayed in memory for good
    (KEEP_ALIVE=-1), and only LLM_MODEL was pulled: a 16 GB machine
    held two models, and the first draft met a missing one. One resident
    model, swapped on demand; every model backend/.env names, pulled
    before the backend starts (2026-10-19).
    """

    ollama = prod["services"]["ollama"]
    pull = prod["services"]["ollama-pull"]

    assert "OLLAMA_MAX_LOADED_MODELS=1" in ollama["environment"]
    assert ollama["mem_limit"].startswith("${OLLAMA_MEM_LIMIT:-")

    assert pull["entrypoint"] == ["/bin/sh", "/pull-models.sh"]
    assert "./ollama/pull-models.sh:/pull-models.sh:ro" in pull["volumes"]
    passed = " ".join(pull["environment"])
    for name in ("LLM_MODEL", "WRITER_LLM_MODEL", "WRITER_LLM_BASE", "CORRECTOR_LLM_MODEL", "CORRECTOR_LLM_BASE"):
        assert f"{name}=${{{name}" in passed, name

    script = (DOCKER / "ollama" / "pull-models.sh").read_text(encoding="utf-8")
    assert 'pull "${LLM_MODEL:?' in script
    # Only the verifier is required: a writer that cannot be had must
    # not keep the backend from starting.
    assert 'optional "${WRITER_LLM_MODEL:-}"' in script
    assert "PARAMETER num_ctx" in script
    # The reviewer reads a draft and its sources: a long context too.
    assert 'serve_long "${CORRECTOR_LLM_MODEL:?' in script


def test_the_writing_variants_take_a_thread_count_and_a_batch_only_when_set(prod):
    """
    Ollama's default thread count halved the answer speed on the dev
    laptop's hybrid CPU, and its default batch crashes an integrated GPU
    serving Qwen 3.5 (2026-10-21, docs/decisions/performance.md). Both
    are machine facts: passed through, unset by default, and only then
    written into the variants' Modelfile.
    """

    passed = " ".join(prod["services"]["ollama-pull"]["environment"])
    script = (DOCKER / "ollama" / "pull-models.sh").read_text(encoding="utf-8")

    for name, parameter in (("OLLAMA_NUM_THREAD", "num_thread"), ("OLLAMA_NUM_BATCH", "num_batch")):
        assert f"{name}=${{{name}:-}}" in passed, name
        assert f'[ -z "${{{name}:-}}" ] || printf \'PARAMETER {parameter} %s' in script, name


def test_the_backend_starts_without_waiting_for_neo4j(base, prod):
    """
    The graph write is fail-soft (graph_failed, never a failed analysis),
    so the backend must not wait on Neo4j's health, nor drag a ~1 GB
    database into an activity that has no use for it (Sep 21 audit;
    removed 2026-10-20).
    """

    for backend in (base["backend"], prod["services"]["backend"]):
        assert "neo4j" not in (backend.get("depends_on") or {})


# ----------------------------------------------------------------------
# The committed data the backend reads
# ----------------------------------------------------------------------

# Committed folders under backend/data the running backend never reads:
# sample articles for the tests (CLAUDE.md, invariant 9).
NOT_READ_BY_THE_SERVER = {"raw", "processed"}


def _committed_data_folders() -> set[str]:

    import subprocess

    try:
        listed = subprocess.run(
            ["git", "ls-files", "backend/data"],
            cwd=DOCKER.parent, capture_output=True, text=True, check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("needs a git checkout to know what backend/data commits")

    return {path.split("/")[2] for path in listed if path.count("/") >= 3}


def test_every_committed_data_folder_the_backend_reads_is_mounted(base):
    """
    .dockerignore keeps backend/data/ out of the image and the backend-data
    volume shadows /app/data, so a committed folder the server reads exists
    in the container only if compose mounts it. data/evaluation was not
    mounted: in the Docker stack /evaluation showed 0 of 139 facts. Nor was
    data/trends (26 Oct): the Trending lens had no signals and a trending
    round came back empty without saying why (both found 2026-10-27).
    Read-only: the server only
    reads them, and docker-compose.eval.yml mounts data/evaluation again,
    writable, for the harness's runs - compose keys a mount by its path in
    the container, so the later file's wins.
    """

    mounts = set(base["backend"]["volumes"])

    for folder in sorted(_committed_data_folders() - NOT_READ_BY_THE_SERVER):
        assert f"../backend/data/{folder}:/app/data/{folder}:ro" in mounts, folder


# ----------------------------------------------------------------------
# The readers' universe (its Caddyfile block, docker/caddy.Dockerfile)
# ----------------------------------------------------------------------

CADDY_DOCKERFILE = DOCKER / "caddy.Dockerfile"
UNIVERSE = DOCKER.parent / "universe"


def test_the_universe_reaches_the_backend_only_for_its_open_routes():
    """
    Open to anyone, and so it reaches the backend for exactly three things:
    /healthz, and the two route groups the universe reads, each with /api
    taken off as the universe's own dev proxy does (astro.config.mjs). Any
    other /api path is a 404, never the frontend and never the password.
    Exercised 2026-11-26 against the dev stack's backend: the map, names,
    search and a photo 200, /api/account/me 401, /api/storage and
    /api/ingest 404.
    """

    handles = caddy_handles(universe_code())
    by_matcher = dict(handles)

    to_backend = [matcher for matcher, body in handles if "backend:" in body]
    assert to_backend == ["/healthz", "/api/map/*", "/api/account/*"]
    assert universe_code().count("backend:") == 3

    for matcher in ("/api/map/*", "/api/account/*"):
        body = by_matcher[matcher]
        assert re.search(r"uri strip_prefix /api\s+reverse_proxy backend:8000", body), matcher

    assert re.search(r'respond\s+".*"\s+404', by_matcher["/api/*"])
    assert [m for m, _ in handles].index("/api/*") > [m for m, _ in handles].index("/api/account/*")

    site = by_matcher[""]
    assert "root * /srv/universe" in site and "file_server" in site

    assert "frontend:" not in universe_code()
    assert "basic_auth" not in universe_code()


def test_every_backend_route_the_universe_can_reach_is_open_by_design():
    """
    Caddy forwards all of /map/* and /account/* - a new route there is
    public the moment it exists - so each must be one test_api_key.py
    already lists as open, with its reason.
    """

    # From the OpenAPI schema, as test_api_key.py reads it: app.routes no
    # longer lists an included router's routes, and a walk over it finds
    # nothing and passes (this test's first version did).
    from tests.api.test_api_key import OPEN_ENDPOINTS, endpoints

    reached = {(method, path) for method, path in endpoints() if path.startswith(("/map/", "/account/"))}

    assert len(reached) >= 20
    assert reached <= set(OPEN_ENDPOINTS), sorted(reached - set(OPEN_ENDPOINTS))


def test_the_universe_is_built_into_the_proxys_image():
    """
    One image for the door and the site it serves: built on the VM with
    the rest of the stack, from universe/ alone, with no key and no API at
    build time (the site reads them in the browser).
    """

    caddy = load(GCP)["services"]["caddy"]
    assert caddy["build"] == {"context": "../universe", "dockerfile": "../docker/caddy.Dockerfile"}

    dockerfile = CADDY_DOCKERFILE.read_text(encoding="utf-8")
    assert "RUN npm ci" in dockerfile and "RUN npm run build" in dockerfile
    assert "FROM caddy:2.10.2" in dockerfile
    assert "COPY --from=universe /universe/dist /srv/universe" in dockerfile
    assert "STORAGE_API_KEY" not in dockerfile

    ignored = (UNIVERSE / ".dockerignore").read_text(encoding="utf-8").split()
    assert {"node_modules/", "dist/"} <= set(ignored)


# ----------------------------------------------------------------------
# The lite stack: the universe and /discover, Groq as the LLM
# ----------------------------------------------------------------------

LITE = DOCKER / "docker-compose.lite.yml"


def test_the_lite_stack_runs_no_local_model_and_no_second_graph():
    """
    What made the full stack need 16 GB, left out by profiles nothing asks
    for: `up` then starts backend, caddy, frontend, inference, neo4j and
    searxng (`docker compose config --services`, 2026-11-26).
    """

    services = load(LITE)["services"]

    for name in ("ollama", "ollama-pull", "neo4j-devastating"):
        assert services[name]["profiles"], name

    # The production file's wait for the model pull is replaced, not added
    # to: the base file's two waits are all that is left.
    tag, depends = services["backend"]["depends_on"]
    assert tag == "!override"
    assert depends == {
        "searxng": {"condition": "service_healthy"},
        "inference": {"condition": "service_healthy"},
    }

    # /healthz asks Groq instead of a local server.
    assert "LLM_LOCAL=false" in services["backend"]["environment"]


def test_the_lite_stack_fits_its_machine():
    """
    Every cap of what it runs, the production file's with the lite file's
    over them, adds up to under e2-standard-2's 8 GB: 7.1 GiB on
    2026-11-26. The caps are ceilings, not reservations; the working sets
    are ~4 GiB.
    """

    base_services = load(BASE)["services"]
    prod_services = load(PROD)["services"]
    gcp_services = load(GCP)["services"]
    lite_services = load(LITE)["services"]

    def gib(limit: str) -> float:
        number, unit = re.fullmatch(r"(\d+)([mg])", limit).groups()
        return int(number) / (1024 if unit == "m" else 1)

    total = 0.0
    for name in ("backend", "caddy", "frontend", "inference", "neo4j", "searxng"):
        limit = next(
            layer[name]["mem_limit"]
            for layer in (lite_services, gcp_services, prod_services, base_services)
            if name in layer and layer[name].get("mem_limit")
        )
        total += gib(limit)

    assert total < 7.5, total

    vm = (DEPLOY / "vm.tf").read_text(encoding="utf-8")
    assert 'var.stack == "lite" ? "e2-standard-2" : "e2-standard-4"' in vm


def test_the_vm_layers_the_lite_file_only_for_the_lite_stack():

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    variables = (DEPLOY / "variables.tf").read_text(encoding="utf-8")
    startup = (DEPLOY / "startup.sh.tftpl").read_text(encoding="utf-8")

    assert re.search(r'if \[ "\$STACK" = "lite" \]; then\s+files\+=\(-f docker-compose\.lite\.yml\)', bootstrap)
    assert 'STACK="${STACK:-full}"' in bootstrap
    assert 'export STACK="${stack}"' in startup
    assert 'contains(["full", "lite"], var.stack)' in variables
    # The key is optional in the module, sensitive, and reaches the backend
    # only when there is one.
    assert re.search(r'variable "groq_api_key" \{[^}]*sensitive\s*=\s*true', variables)
    assert 'echo "GROQ_API_KEY=$groq"' in bootstrap


# ----------------------------------------------------------------------
# The seed (scripts/gcp_seed.sh -> the bucket -> bootstrap.sh, seed)
# ----------------------------------------------------------------------

SEED_SCRIPT = DOCKER.parent / "scripts" / "gcp_seed.sh"


def test_the_seed_restores_the_photos_where_compose_mounts_them(base):
    """
    The photos are a bind mount of a gitignored folder of the checkout: a
    fresh clone has an empty one, and the universe would show no photos.
    The seed script names the folder, the manifest carries it, and the VM
    restores it there.
    """

    script = SEED_SCRIPT.read_text(encoding="utf-8")
    photos = re.search(r'^PHOTOS_PATH="([^"]+)"$', script, flags=re.MULTILINE).group(1)

    assert f"../{photos}:/app/data/map-images:ro" in base["backend"]["volumes"]
    assert photos.startswith("backend/data/imports/")


def test_the_seed_never_overwrites_what_the_vm_wrote():
    """
    A seed uploaded after the stack ran must not replace its graph or its
    lake: each part is restored only into a volume compose has not made
    yet, or an empty photo folder, and a failed load takes its volume with
    it so the next boot tries again.
    """

    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    seed = bootstrap[bootstrap.index("\nseed() {"):]

    assert "if ! has_volume neo4j-data; then" in seed
    assert "if ! has_volume backend-data; then" in seed
    assert '[ -z "$(ls -A "$photos" 2>/dev/null)" ]' in seed
    assert seed.count('|| { docker volume rm "${PROJECT}_') == 2
    # Before the stack starts, so compose finds the volumes made.
    assert re.search(r"\n    seed\n.*\n    up\n", bootstrap)
    # The volumes compose makes for project inspiring-news.
    assert "PROJECT=inspiring-news" in bootstrap and "docker compose -p inspiring-news" in bootstrap


def test_the_seed_carries_no_readers_accounts_and_no_cache():
    """Readers' accounts on the dev machine are test accounts; the cache is rebuilt."""

    script = SEED_SCRIPT.read_text(encoding="utf-8")
    keep = re.search(r'^BACKEND_KEEP="([^"]+)"$', script, flags=re.MULTILINE).group(1).split()

    assert keep == ["lake", "vector_db", "drafts", "imports"]
    # The manifest goes up last: until it is there, a VM sees no seed.
    assert script.index('cp "$OUT/manifest.json"') > script.index('cp "$OUT/neo4j.dump"')


def test_the_seed_bucket_is_private_and_only_the_vm_reads_it():

    main = (DEPLOY / "main.tf").read_text(encoding="utf-8")
    vm = (DEPLOY / "vm.tf").read_text(encoding="utf-8")
    bucket = re.search(r'resource "google_storage_bucket" "seed" \{(.*?)\n\}', main, flags=re.DOTALL).group(1)

    assert 'public_access_prevention    = "enforced"' in bucket
    assert "uniform_bucket_level_access = true" in bucket
    assert re.findall(r'role\s*=\s*"(roles/storage\.[a-zA-Z]+)"', main) == ["roles/storage.objectViewer"]
    assert "seed_bucket      = google_storage_bucket.seed.name" in vm

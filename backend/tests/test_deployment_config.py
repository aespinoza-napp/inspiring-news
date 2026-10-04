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


def caddy_code() -> str:
    """The Caddyfile without its comments, which name every route too."""

    text = CADDYFILE.read_text(encoding="utf-8")

    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))


def caddy_handles() -> list[tuple[str, str]]:
    """
    Every `handle` block as (matcher, body), in file order; "" for the
    catch-all. Braces are counted rather than matched by a regex: the
    bodies hold {$PLACEHOLDERS} and nested blocks.
    """

    code = caddy_code()
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
    assert to_frontend == ["@https"]
    assert code.count("frontend:") == 1
    assert re.search(r"^\s*@https\s+protocol\s+https\s*$", code, flags=re.MULTILINE)

    ui = dict(handles)["@https"]
    assert "reverse_proxy frontend:3000" in ui
    assert re.search(r"basic_auth\s*\{\s*\{\$SITE_USER:editor\}\s+\{\$SITE_PASSWORD_HASH\}\s*\}", ui)


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

    assert 'site_address = var.domain != "" ? var.domain : ":80"' in vm
    assert "site_address  = local.site_address" in vm
    assert 'export SITE_ADDRESS="${site_address}"' in startup
    assert 'echo "SITE_ADDRESS=${SITE_ADDRESS:-:80}"' in bootstrap
    assert "SITE_ADDRESS=${SITE_ADDRESS:-:80}" in caddy["environment"]
    assert caddy_code().lstrip().startswith("{$SITE_ADDRESS::80} {")


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
    secrets_block = re.search(r"secrets = \{(.*?)\n  \}", main, flags=re.DOTALL).group(1)
    created = set(re.findall(r'"([a-z0-9-]+)"\s*=', secrets_block))

    read = set(re.findall(r"\$\(secret ([a-z0-9-]+)\)", BOOTSTRAP.read_text(encoding="utf-8")))

    assert created == read == {"neo4j-password", "searxng-secret", "storage-api-key", "site-password-hash"}


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

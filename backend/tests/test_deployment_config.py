"""
The deployment's configuration, held by tests: the compose files and
SearXNG's settings are outside src/, so nothing else would notice them
drift.

Each of these has gone wrong once. SearXNG's live settings drifted from
the committed example for weeks; its healthcheck sent a real search to
every engine every 5 seconds; the Neo4j password was in the compose file
in plain text. docs/decisions/deployment.md.
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


def test_production_publishes_nothing_but_the_api_on_loopback(base, prod):

    for name, service in base.items():
        if not service.get("ports") or name == "backend":
            continue
        assert prod["services"][name].get("ports") == ("!reset", []), name

    tag, ports = prod["services"]["backend"]["ports"]
    assert tag == "!override"
    assert ports == ["127.0.0.1:8000:8000"]


def test_every_long_running_service_restarts_and_rotates_its_logs(base, prod):

    services = prod["services"]
    long_running = set(base) | {"ollama"}

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

    for name in set(base) | {"ollama"}:
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
    may publish anything else.
    """

    services = load(GCP)["services"]

    published = {name for name, service in services.items() if service.get("ports")}
    assert published == {"caddy"}
    assert services["caddy"]["ports"] == ["80:80", "443:443"]


def test_the_proxy_forwards_healthz_and_nothing_else():
    """
    The analysis endpoints take no key and each run costs minutes of CPU:
    until the frontend has a home, only the uptime check gets through.
    """

    caddyfile = CADDYFILE.read_text(encoding="utf-8")
    forwarded = re.findall(r"handle\s+(\S+)\s*\{\s*reverse_proxy", caddyfile)

    assert forwarded == ["/healthz"]
    assert caddyfile.count("reverse_proxy") == 1


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

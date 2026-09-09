"""
The SSRF guard.

Every fetch in this app is server-side with a URL supplied from outside:
POST /analyze takes it straight from the caller, and the evidence
scraper takes it from whatever SearXNG returned. Without the guard the
service is an HTTP proxy into its own network - which, since compose puts
it beside Neo4j and SearXNG, means POST /analyze can read the graph
database, and on a cloud host the metadata endpoint is one request away.
"""

import pytest

from src.config.settings import settings
from src.services.scraper.url_guard import (
    BlockedURL,
    check_url,
    is_allowed,
)


@pytest.fixture(autouse=True)
def guard_on(monkeypatch):
    monkeypatch.setattr(settings, "URL_GUARD_ENABLED", True)
    monkeypatch.setattr(settings, "URL_GUARD_ALLOWED_HOSTS", [])


def resolves_to(monkeypatch, address: str):
    """Pin DNS so these tests never depend on a live resolver."""

    monkeypatch.setattr(
        "src.services.scraper.url_guard.socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", (address, 0))],
    )


# ----------------------------------------------------------------------
# Schemes
# ----------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "gopher://example.com/",
    "ftp://example.com/x",
    "data:text/html,<script>",
])
def test_only_http_and_https_are_fetchable(url):
    with pytest.raises(BlockedURL, match="http and https"):
        check_url(url)


def test_a_url_with_no_host_is_blocked():
    with pytest.raises(BlockedURL, match="no host"):
        check_url("http:///just-a-path")


# ----------------------------------------------------------------------
# Addresses - the actual attack surface
# ----------------------------------------------------------------------


@pytest.mark.parametrize("address", [
    "127.0.0.1",        # loopback - the app itself
    "10.0.0.5",         # private
    "172.16.4.1",       # private
    "192.168.1.1",      # private
    "169.254.169.254",  # link-local - cloud instance metadata
    "0.0.0.0",          # unspecified
    "::1",              # IPv6 loopback
    "fc00::1",          # IPv6 unique-local
])
def test_private_and_reserved_addresses_are_blocked(monkeypatch, address):
    resolves_to(monkeypatch, address)

    with pytest.raises(BlockedURL, match="private or reserved"):
        check_url("http://anything.example/article")


def test_a_public_address_is_allowed(monkeypatch):
    resolves_to(monkeypatch, "93.184.216.34")

    assert check_url("https://example.com/a") == "https://example.com/a"


def test_dns_is_resolved_rather_than_trusted(monkeypatch):
    """
    A perfectly ordinary-looking hostname can have an A record pointing
    at 127.0.0.1. The name alone cannot tell you that.
    """

    resolves_to(monkeypatch, "127.0.0.1")

    with pytest.raises(BlockedURL):
        check_url("https://totally-normal-news.example/story")


def test_every_resolved_address_must_pass(monkeypatch):
    """
    A name answering with both a public and a private address is
    rejected: which one `requests` picks is not ours to decide.
    """

    monkeypatch.setattr(
        "src.services.scraper.url_guard.socket.getaddrinfo",
        lambda host, port: [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ],
    )

    with pytest.raises(BlockedURL):
        check_url("https://split-horizon.example/a")


def test_an_unresolvable_host_is_blocked(monkeypatch):
    import socket as socket_module

    def boom(host, port):
        raise socket_module.gaierror("nope")

    monkeypatch.setattr(
        "src.services.scraper.url_guard.socket.getaddrinfo", boom
    )

    with pytest.raises(BlockedURL, match="Could not resolve"):
        check_url("https://does-not-exist.example/a")


def test_a_host_resolving_to_nothing_is_blocked(monkeypatch):
    monkeypatch.setattr(
        "src.services.scraper.url_guard.socket.getaddrinfo",
        lambda host, port: [],
    )

    with pytest.raises(BlockedURL, match="no addresses"):
        check_url("https://empty.example/a")


# ----------------------------------------------------------------------
# Ports
# ----------------------------------------------------------------------


@pytest.mark.parametrize("port", [7474, 7687, 5432, 6379, 27017, 22])
def test_infrastructure_ports_are_blocked(port):
    """
    Defence in depth. 7474/7687 are the compose Neo4j, which sits on the
    same network as the backend.
    """

    with pytest.raises(BlockedURL, match="not fetchable"):
        check_url(f"http://neo4j:{port}/")


def test_ordinary_web_ports_are_fine(monkeypatch):
    resolves_to(monkeypatch, "93.184.216.34")

    assert check_url("https://example.com:8443/a")


# ----------------------------------------------------------------------
# Escape hatches
# ----------------------------------------------------------------------


def test_an_allowlisted_host_skips_the_address_check(monkeypatch):
    """
    So that "I need to reach my staging box on a private network" is not
    solved by turning the whole guard off.
    """

    monkeypatch.setattr(settings, "URL_GUARD_ALLOWED_HOSTS", ["staging.internal"])
    resolves_to(monkeypatch, "10.0.0.9")

    assert check_url("http://staging.internal/article")


def test_the_allowlist_does_not_exempt_other_hosts(monkeypatch):
    monkeypatch.setattr(settings, "URL_GUARD_ALLOWED_HOSTS", ["staging.internal"])
    resolves_to(monkeypatch, "10.0.0.9")

    with pytest.raises(BlockedURL):
        check_url("http://other.internal/article")


def test_the_guard_can_be_disabled_wholesale(monkeypatch):
    monkeypatch.setattr(settings, "URL_GUARD_ENABLED", False)

    assert check_url("file:///etc/passwd") == "file:///etc/passwd"


# ----------------------------------------------------------------------
# Non-raising form
# ----------------------------------------------------------------------


def test_is_allowed_mirrors_check_url(monkeypatch):
    resolves_to(monkeypatch, "93.184.216.34")

    assert is_allowed("https://example.com/a") is True
    assert is_allowed("file:///etc/passwd") is False

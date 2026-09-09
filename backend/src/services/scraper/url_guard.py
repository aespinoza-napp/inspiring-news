"""
Decides whether the server is allowed to fetch a URL.

Every fetch in this app is server-side and the URL comes from outside:
`POST /analyze` takes it straight from the caller, and the evidence
scraper takes it from whatever SearXNG returned. Without this the
service is a general-purpose HTTP proxy into whatever network it is on -
which, since `docker/docker-compose.yml` puts it on a network with Neo4j
and SearXNG, means `POST /analyze {"urls": ["http://neo4j:7474"]}` reads
the graph database, and on any cloud host the instance metadata endpoint
is one request away.

The check is deliberately deny-by-default on address, not allow-by-list
on domain: an allowlist of news domains would be wrong for `/analyze`,
whose whole job is to accept a URL the user found somewhere. What must
never be reachable is the *infrastructure*, and that is an address-space
question.

DNS is resolved here rather than trusted, because `evil.example` can
have an A record of `127.0.0.1`, and the hostname alone cannot tell you
that. Every resolved address must pass - a name that returns both a
public and a private address is rejected.

Known limitation, stated rather than hidden: this is checked before the
request, so it does not close the DNS-rebinding window between this
resolution and the one `requests` performs, and redirects are followed
by `requests` itself. `TrafilaturaStrategy` therefore disables automatic
redirects and re-checks each hop through this same guard.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from src.config.settings import settings

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Ports that are never a public web page but are common internal
# services. Blocking them is defence in depth - the address check below
# already covers anything on a private network.
BLOCKED_PORTS = frozenset({
    22, 23, 25, 445, 3306, 5432, 6379, 7474, 7687, 9200, 11211, 27017,
})


class BlockedURL(ValueError):
    """Raised when a URL must not be fetched. The message is user-facing."""


def _is_forbidden_address(address: str) -> bool:

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True

    return (
        ip.is_private            # 10/8, 172.16/12, 192.168/16, fc00::/7
        or ip.is_loopback        # 127/8, ::1
        or ip.is_link_local      # 169.254/16 - cloud metadata lives here
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _resolve(host: str) -> list[str]:

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise BlockedURL(f"Could not resolve host {host!r}: {exc}") from exc

    return [info[4][0] for info in infos]


def check_url(url: str) -> str:
    """
    Returns the URL when it is safe to fetch, raises BlockedURL when it
    is not. Returning the URL lets callers write `requests.get(check_url(u))`.
    """

    if not settings.URL_GUARD_ENABLED:
        return url

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise BlockedURL(
            f"Only http and https URLs can be fetched, not {parsed.scheme!r}."
        )

    host = parsed.hostname

    if not host:
        raise BlockedURL("The URL has no host.")

    if parsed.port in BLOCKED_PORTS:
        raise BlockedURL(f"Port {parsed.port} is not fetchable.")

    for host_pattern in settings.URL_GUARD_ALLOWED_HOSTS:
        # An explicit escape hatch, empty by default: someone running
        # this against a staging host on a private network needs a way
        # to say so that is not "turn the guard off".
        if host == host_pattern:
            return url

    addresses = _resolve(host)

    if not addresses:
        raise BlockedURL(f"Host {host!r} resolved to no addresses.")

    forbidden = [a for a in addresses if _is_forbidden_address(a)]

    if forbidden:
        # Every resolved address must pass: a name answering with both a
        # public and a private address would otherwise be fetchable, and
        # which one `requests` picks is not ours to decide.
        raise BlockedURL(
            f"Host {host!r} resolves to a private or reserved address "
            f"({forbidden[0]}), which this service will not fetch."
        )

    return url


def is_allowed(url: str) -> bool:
    """Non-raising form, for filtering a list of candidates."""

    try:
        check_url(url)
    except BlockedURL:
        return False

    return True

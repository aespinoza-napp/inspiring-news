"""
GET /healthz: could this process run an analysis right now?

The container's own healthcheck only asks whether uvicorn answers. That
stays green while every analysis fails: SearXNG down, inference/ still
loading, the LLM missing its model. Each of those has been the reason a
run "worked" and was wrong - a search that answers nothing is an
UNVERIFIED verdict, not an error. This asks each dependency directly,
so an uptime monitor polling it alerts on the thing that is broken.

Every check has a short timeout and they run at once, so a dead
dependency costs this endpoint ~3s, not the sum of every timeout.
Answers carry the dependency's name and the kind of failure, never the
exception text: the endpoint is unauthenticated, and that text names
internal hosts.
"""

from __future__ import annotations

import time
from typing import Callable

import httpx

from src.config.settings import settings
from src.services.concurrency import bounded_map

TIMEOUT_SECONDS = 3.0


class CheckFailed(Exception):
    """A dependency answered, but not with what an analysis needs."""


def _get(url: str, headers: dict | None = None) -> httpx.Response:
    response = httpx.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response


def _check_llm() -> None:
    """
    The endpoint answering is not enough: Ollama answers with no model
    pulled, and every verification then fails. So the configured model
    must be one it serves.
    """

    response = _get(
        f"{settings.LLM_BASE_URL.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {settings.LLM_API_KEY.get_secret_value()}"},
    )
    served = {model.get("id") for model in response.json().get("data", [])}

    if settings.LLM_MODEL not in served:
        raise CheckFailed(f"model {settings.LLM_MODEL} is not served")


def _check_neo4j() -> None:
    # Local import: the container imports half the application.
    from src.container import get_graph_client

    get_graph_client().verify_connection()


def default_checks() -> dict[str, Callable[[], None]]:

    checks = {
        "inference": lambda: _get(f"{settings.INFERENCE_URL.rstrip('/')}/healthz"),
        "searxng": lambda: _get(f"{settings.SEARXNG_URL.rstrip('/')}/healthz"),
        "llm": _check_llm,
    }

    # Off, the pipeline never touches the graph, so its absence is not a
    # failure.
    if settings.GRAPH_ENABLED:
        checks["neo4j"] = _check_neo4j

    return checks


def run_checks(checks: dict[str, Callable[[], None]]) -> dict:

    def run(item: tuple[str, Callable[[], None]]) -> tuple[str, dict]:

        name, check = item
        started = time.monotonic()

        try:
            check()
            result = {"ok": True}
        except CheckFailed as exc:
            result = {"ok": False, "error": str(exc)}
        except httpx.HTTPStatusError as exc:
            result = {"ok": False, "error": f"HTTP {exc.response.status_code}"}
        except Exception as exc:
            result = {"ok": False, "error": type(exc).__name__}

        result["ms"] = round((time.monotonic() - started) * 1000)
        return name, result

    results = dict(bounded_map(run, checks.items(), max_workers=max(len(checks), 1), thread_name_prefix="health"))

    return {
        "ok": all(result["ok"] for result in results.values()),
        "checks": results,
    }

"""
Whether a statement is true: the project's fact-checker, over HTTP.

Nothing of `backend/` is imported, as with the labeller. POST /verify-claim
runs the same chain an article's claims go through.
"""

import httpx

TRUE, FALSE, MIXED, UNVERIFIED, NOT_CHECKED = (
    "true", "false", "mixed", "unverified", "not_checked",
)

NEEDED = ("inference", "searxng", "llm")

_OUTCOMES = {
    "TRUE": TRUE,
    "FALSE": FALSE,
    "PARTIALLY_TRUE": MIXED,
    "MISLEADING": MIXED,
    "UNVERIFIED": UNVERIFIED,
}


def to_outcome(body: dict) -> dict:
    """
    A failed search or an unreachable model says nothing about the claim,
    and comes back from the pipeline as an UNVERIFIED that looks like a
    finding (CLAUDE.md, "Web search mostly returns nothing"). Kept apart.
    """

    verdict = body.get("verdict")

    if body.get("searchUnavailable"):
        outcome, note = NOT_CHECKED, "The web search failed."
    elif body.get("llmUnreachable"):
        outcome, note = NOT_CHECKED, "The verifying model could not be reached."
    else:
        outcome, note = _OUTCOMES.get(verdict, NOT_CHECKED), ""

    sources = [
        {
            "url": item.get("url"),
            "title": item.get("title"),
            "stance": item.get("stance"),
            "quote": item.get("quote"),
        }
        for item in body.get("evidence") or []
        if item.get("cited")
    ]

    return {
        "outcome": outcome,
        "verdict": verdict,
        "confidence": body.get("confidence"),
        "explanation": body.get("explanation") or note,
        "note": note,
        "sources": sources,
    }


class BackendVerifier:

    def __init__(
        self,
        url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 900,
    ):
        self.url = url.rstrip("/")
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.timeout = timeout

    def reachable(self) -> str | None:
        """
        None when it can check a claim, otherwise why not.

        /healthz answers 503 whenever any service is down, Neo4j included,
        and a claim needs no graph: read what it needs from the checks, not
        the status code.
        """

        try:
            body = httpx.get(f"{self.url}/healthz", timeout=5).json()
        except Exception as exc:
            return str(exc)

        down = [
            name
            for name in NEEDED
            if not (body.get("checks", {}).get(name) or {}).get("ok")
        ]

        return f"down: {', '.join(down)}" if down else None

    def __call__(self, claim: str) -> dict:

        try:
            response = httpx.post(
                f"{self.url}/verify-claim",
                json={"claim": claim[:2000]},
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            return {
                "outcome": NOT_CHECKED,
                "verdict": None,
                "confidence": None,
                "explanation": f"The fact-checker could not be asked: {exc}",
                "note": str(exc),
                "sources": [],
            }

        return to_outcome(response.json())

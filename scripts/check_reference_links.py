#!/usr/bin/env python3
"""
Link rot in an x-fact set's reference links: which of the sources the
fact-checker cited when the dataset was built (2021) still answer today.

    cd backend
    uv run python ../scripts/check_reference_links.py \
        data/evaluation/xfact_en_es_pilot.jsonl \
        data/evaluation/reports/xfact_en_es_pilot/reference_links.json

Why it exists: the harness's retrieval recall (RQ2) counts a reference
link "found" when the pipeline's live search returns it. A reference that
no longer exists cannot be found, so recall measured in 2026 is bounded
by what survived. This puts a number on that bound
(docs/decisions/xfact-comparison.md, "Time elapsed").

Polite on purpose, since every request lands on someone else's server:
one request at a time per host with a pause between them, at most three
hosts at once, HEAD first and a GET (first 64 KB only) only when HEAD is
refused. Social-media links (Twitter, Facebook, Reddit, YouTube) are not
requested: those platforms answer 200 or a login wall whether the post
exists or not, so a status code says nothing. `<LINK NOT AVAILABLE>`
placeholders (every English PolitiFact row) are counted, not requested.

A link that is dead, unreachable or sent to the site's home page is then
looked up in the Wayback Machine's availability API, once, to say
whether the evidence is recoverable at all.

Outcomes, in the order they are decided:

    placeholder      `<LINK NOT AVAILABLE>`
    social           not requested (above)
    unreachable      DNS, connection, TLS or timeout: the host is gone or down
    dead             404 or 410
    blocked          401, 403, 429, 451, 999: refused us, existence unknown
    server_error     5xx
    redirected_home  answered, but at the site's root while the link had a
                     path: the usual shape of a removed page (a soft 404)
    moved            answered, at a different path
    alive            answered at the same path

Run from the host, not a container: it measures the web, not the stack.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import httpx  # noqa: E402

from src.evaluation.dataset import load_dataset  # noqa: E402
from src.services.concurrency import bounded_map  # noqa: E402

USER_AGENT = (
    "Mozilla/5.0 (compatible; inspiring-news reference-link check; "
    "academic research, one request per page)"
)

PLACEHOLDER = "<LINK NOT AVAILABLE>"

SOCIAL = ("twitter.com", "x.com", "facebook.com", "instagram.com", "reddit.com", "youtube.com", "t.co")

TIMEOUT = 15.0
PER_HOST_PAUSE = 1.0
HOSTS_AT_ONCE = 3
GET_BYTES = 64 * 1024

BLOCKED = {401, 403, 429, 451, 999}
GONE = {404, 410}

# Outcomes worth asking the Wayback Machine about.
LOST = {"unreachable", "dead", "redirected_home", "server_error"}

OUTCOMES = (
    "placeholder", "social", "unreachable", "dead", "blocked",
    "server_error", "redirected_home", "moved", "alive",
)


def host_of(url: str) -> str:

    return (urlsplit(url).hostname or "").lower()


def is_social(host: str) -> bool:

    return any(host == domain or host.endswith("." + domain) for domain in SOCIAL)


def on_site(host: str, site: str) -> bool:

    site = (site or "").lower()

    return bool(site) and (host == site or host.endswith("." + site))


def _path(url: str) -> str:

    return urlsplit(url).path.rstrip("/").lower()


def classify(url: str, status: int | None, final_url: str | None, error: str | None) -> str:
    """The outcome of one request, from what came back. Pure: tested by reading."""

    if error is not None:
        return "unreachable"

    if status in GONE:
        return "dead"

    if status in BLOCKED:
        return "blocked"

    if status is not None and status >= 500:
        return "server_error"

    if status is not None and status >= 400:
        # Any other 4xx: the page is not served to anyone.
        return "dead"

    original, final = _path(url), _path(final_url or url)

    if original and not final:
        return "redirected_home"

    if original != final:
        return "moved"

    return "alive"


def request(client: httpx.Client, url: str) -> dict:
    """HEAD, then a capped GET if HEAD was refused or failed."""

    result = {"status": None, "finalUrl": None, "method": None, "error": None}

    for method in ("HEAD", "GET"):

        try:
            with client.stream(method, url) as response:
                if method == "GET":
                    # Enough to have the page answer; never the whole body.
                    for _ in response.iter_bytes(GET_BYTES):
                        break
                result.update(status=response.status_code, finalUrl=str(response.url), method=method, error=None)
        except httpx.HTTPError as exc:
            result.update(status=None, finalUrl=None, method=method, error=f"{type(exc).__name__}: {exc}"[:200])

        # A HEAD that answered with anything but "not allowed here" stands.
        if method == "HEAD" and result["error"] is None and result["status"] not in (400, 403, 405, 406, 501):
            break

    return result


def wayback(client: httpx.Client, url: str, year: str | None) -> dict:

    timestamp = f"{year}0101" if year else "20210101"

    try:
        response = client.get(
            f"https://archive.org/wayback/available?url={quote(url, safe='')}&timestamp={timestamp}",
            timeout=TIMEOUT,
        )
        closest = (response.json().get("archived_snapshots") or {}).get("closest") or {}
    except (httpx.HTTPError, ValueError) as exc:
        return {"archived": None, "archiveError": f"{type(exc).__name__}"[:80]}

    return {
        "archived": bool(closest.get("available")),
        "archiveTimestamp": closest.get("timestamp"),
    }


def main() -> int:

    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    dataset = load_dataset(sys.argv[1])
    target = Path(sys.argv[2])

    # One entry per distinct URL, with every claim that cites it.
    entries: dict[str, dict] = {}
    placeholders: Counter = Counter()

    for row in dataset.rows:
        for url in row.reference_links:
            if url.strip() == PLACEHOLDER:
                placeholders[row.language] += 1
                continue
            entry = entries.setdefault(url, {
                "url": url,
                "host": host_of(url),
                "claimIds": [],
                "languages": set(),
                "ownSite": on_site(host_of(url), row.site),
                "claimYear": (row.claim_date or "")[:4] or None,
            })
            entry["claimIds"].append(row.id)
            entry["languages"].add(row.language)

    by_host: dict[str, list[dict]] = defaultdict(list)

    for entry in entries.values():
        if is_social(entry["host"]):
            entry.update(outcome="social", status=None, finalUrl=None, method=None, error=None)
        else:
            by_host[entry["host"]].append(entry)

    printing = threading.Lock()

    def check_host(item: tuple[str, list[dict]]) -> None:

        host, items = item

        with httpx.Client(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for index, entry in enumerate(items):
                if index:
                    time.sleep(PER_HOST_PAUSE)
                entry.update(request(client, entry["url"]))
                entry["outcome"] = classify(entry["url"], entry["status"], entry["finalUrl"], entry["error"])
                with printing:
                    print(f"{entry['outcome']:>15}  {entry['status']}  {entry['url'][:100]}", flush=True)

    bounded_map(check_host, sorted(by_host.items()), max_workers=HOSTS_AT_ONCE, thread_name_prefix="linkcheck")

    with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        for entry in entries.values():
            if entry["outcome"] in LOST:
                entry.update(wayback(client, entry["url"], entry["claimYear"]))
                time.sleep(PER_HOST_PAUSE)

    rows = sorted(entries.values(), key=lambda entry: entry["url"])

    for entry in rows:
        entry["languages"] = sorted(entry["languages"])

    def summary(selected: list[dict]) -> dict:
        counts = Counter(entry["outcome"] for entry in selected)
        return {outcome: counts.get(outcome, 0) for outcome in OUTCOMES if outcome != "placeholder"} | {
            "distinct": len(selected),
        }

    requested = [entry for entry in rows if entry["outcome"] != "social"]
    lost = [entry for entry in requested if entry["outcome"] in LOST]

    claims_with_live_other = {
        claim
        for entry in rows
        if entry["outcome"] in ("alive", "moved") and not entry["ownSite"]
        for claim in entry["claimIds"]
    }

    report = {
        "dataset": {"path": str(dataset.path), "sha256": dataset.sha256, "rows": len(dataset.rows)},
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "userAgent": USER_AGENT,
        "politeness": {
            "hostsAtOnce": HOSTS_AT_ONCE,
            "perHostPauseSeconds": PER_HOST_PAUSE,
            "timeoutSeconds": TIMEOUT,
            "getBytes": GET_BYTES,
        },
        "placeholders": dict(placeholders),
        "summary": {
            "all": summary(rows),
            "ownSite": summary([entry for entry in rows if entry["ownSite"]]),
            "otherSites": summary([entry for entry in rows if not entry["ownSite"]]),
        },
        "requested": len(requested),
        "lost": len(lost),
        "lostArchived": sum(1 for entry in lost if entry.get("archived")),
        "claimsWithALiveNonOwnSiteReference": len(claims_with_live_other),
        "links": rows,
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({key: report[key] for key in report if key != "links"}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Fact labeller - the tool for hand-labelling the custom validation set.

Standard library only: no install, no virtualenv, nothing from backend/.
Each fact is saved as its own file, backend/data/evaluation/manual/
factNNN.json, so every fact verified by hand is visible (and reviewable)
in the repository. When the set is finished, `join` merges them into
backend/data/evaluation/custom_en_es.jsonl, beside x-fact's file and in
x-fact's format.

    python labeller/app.py              # http://127.0.0.1:8765
    python labeller/app.py --port 9000
    python labeller/app.py join         # manual/*.json -> custom_en_es.jsonl

The Today tab asks the backend for the day's batch - ~10 articles, each
with the 1-3 claims the pipeline would check - so labelling starts from
the claims instead of from a search. That one button needs the backend
running (LABELLER_BACKEND_URL, default http://127.0.0.1:8000); labelling
itself still needs nothing. Batches are saved beside the facts, in
backend/data/evaluation/queue/.

The labelling guide (the tie-break rules this file enforces) is
docs/final_document/sections/custom_dataset.tex.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections import Counter
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "backend" / "data" / "evaluation" / "manual"
JOINED = ROOT / "backend" / "data" / "evaluation" / "custom_en_es.jsonl"
TOPICS_FILE = ROOT / "backend" / "src" / "config" / "topics.py"
PAGE = Path(__file__).resolve().parent / "index.html"


# ----------------------------------------------------------------------
# The format
# ----------------------------------------------------------------------

# The keys of one x-fact row, in the order scripts/prepare_xfact_eval.py
# writes them. Every fact starts with these, in this order, so whatever
# reads xfact_en_es.jsonl reads the joined custom set unchanged.
XFACT_FIELDS = (
    "language", "site", "claimant", "claim", "claimDate", "reviewDate",
    "labelRaw", "label", "referenceEvidenceLinks", "split",
)

# label is the pipeline's Verdict; labelRaw the guide's name for it,
# after AVeriTeC - as x-fact keeps the fact-checker's own label beside
# the mapped one.
LABELS = {
    "TRUE": "supported",
    "PARTIALLY_TRUE": "partially supported",
    "MISLEADING": "conflicting evidence/cherrypicking",
    "FALSE": "refuted",
    "UNVERIFIED": "not enough evidence",
}

LABEL_HELP = {
    "TRUE": "The evidence supports the claim as stated.",
    "PARTIALLY_TRUE": "The central claim holds; a detail does not.",
    "MISLEADING": "Sources of equal standing conflict, or true but cherry-picked.",
    "FALSE": "The evidence refutes the claim.",
    "UNVERIFIED": "Not enough independent evidence, either way.",
}

CLAIM_TYPES = ("factual", "numerical", "interpretive")

# Strongest source used, in the guide's hierarchy (rule 4).
SOURCE_TIERS = ("primary", "reference_media", "press_release", "social_media")

# The five groups topics.py is laid out in. 23 topics over 150 facts is
# too thin to balance on; 5 groups x 5 verdicts is 25 cells of 6. A test
# holds every topic to exactly one group.
TOPIC_GROUPS = {
    "society": ["education", "community", "employment", "cities"],
    "science": ["space", "technology", "research", "biology"],
    "environment": ["climate", "nature", "energy", "sustainability", "food"],
    "culture": ["arts", "entertainment", "heritage", "literature", "inspiration"],
    "health": ["medicine", "mental_health", "nutrition", "fitness", "public_health"],
}
GROUP_OF = {t: g for g, topics in TOPIC_GROUPS.items() for t in topics}

TARGET_TOTAL = 150
MINIMUM_TOTAL = 100
REVIEW_SHARE = 0.2

# Every custom fact is held out; x-fact's held-out split has this name.
SPLIT = "test"

FACT_ID = re.compile(r"^fact(\d{3,})$")

# The day's batch (see the Today tab). The labeller asks the backend for
# it and keeps it here, beside the facts: the backend may run in a
# container whose data directory this machine cannot see.
QUEUE = ROOT / "backend" / "data" / "evaluation" / "queue"
BATCH_FILE = re.compile(r"^\d{4}-\d{2}-\d{2}(-\d+)?\.json$")
BACKEND_URL = os.environ.get("LABELLER_BACKEND_URL", "http://127.0.0.1:8000")

# Why a proposed claim was not labelled. Kept, because the share of the
# pipeline's proposals worth checking at all is itself a result: the
# precision of its claim selection, measured by the annotator.
SKIP_REASONS = {
    "opinion": "Opinion or interpretation, not a checkable fact",
    "prediction": "A prediction or a plan: nothing to check yet",
    "trivial": "Checkable, but not worth checking",
    "fragment": "Not a whole claim (a cut sentence, a caption)",
    "duplicate": "Same claim as another one",
    "other": "Other",
}


def load_topics(path: Path = TOPICS_FILE) -> dict[str, str]:
    """
    {key: display name}, read from topics.py without importing it -
    importing would need pydantic, and this tool needs nothing. One list
    of topics, the classifier's own.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "TOPICS" for t in node.targets
        ):
            topics = {}
            for key, value in zip(node.value.keys, node.value.values):
                name = next(
                    (kw.value.value for kw in value.keywords if kw.arg == "name"),
                    key.value,
                )
                topics[key.value] = name
            return topics

    raise RuntimeError(f"No TOPICS dict in {path}")


# ----------------------------------------------------------------------
# Validation - the guide's rules that can be checked mechanically
# ----------------------------------------------------------------------


def validate(data: dict, topics: dict[str, str]) -> tuple[dict, list[str]]:
    """The cleaned input and every problem with it, all at once."""

    errors = []

    def text(key, limit, required=False):
        value = data.get(key)
        value = value.strip() if isinstance(value, str) else ""
        if required and not value:
            errors.append(f"{key} is required.")
        if len(value) > limit:
            errors.append(f"{key} is longer than {limit} characters.")
        return value or None

    def day(key, required=False):
        value = text(key, 10, required)
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            errors.append(f"{key} is not a date (YYYY-MM-DD).")
            return None

    def http(url):
        return urlparse(url).scheme in ("http", "https") and bool(urlparse(url).netloc)

    clean = {
        "claim": text("claim", 1000, required=True),
        "language": data.get("language"),
        "site": text("site", 200),
        "claimant": text("claimant", 200),
        "claimDate": day("claimDate", required=True),
        "label": data.get("label"),
        "topic": data.get("topic"),
        "claimType": data.get("claimType"),
        "sourceTier": data.get("sourceTier"),
        "onlyOwnSource": data.get("onlyOwnSource") is True,
        "evidenceDate": day("evidenceDate"),
        "articleUrl": text("articleUrl", 2000),
        "annotatorNote": text("annotatorNote", 2000),
    }

    for key, allowed in (
        ("language", ("en", "es")),
        ("label", tuple(LABELS)),
        ("claimType", CLAIM_TYPES),
        ("sourceTier", SOURCE_TIERS),
    ):
        if clean[key] not in allowed:
            errors.append(f"{key} must be one of {', '.join(allowed)}.")

    if clean["topic"] not in topics:
        errors.append("topic must be one of the classifier's topics.")

    links = data.get("referenceEvidenceLinks") or []
    if isinstance(links, str):
        links = links.split()
    links = list(dict.fromkeys(l.strip() for l in links if isinstance(l, str) and l.strip()))
    for link in links:
        if not http(link):
            errors.append(f"Not an http(s) URL: {link}")
    clean["referenceEvidenceLinks"] = links

    if clean["articleUrl"] and not http(clean["articleUrl"]):
        errors.append(f"Not an http(s) URL: {clean['articleUrl']}")

    if not clean["site"] and clean["articleUrl"] and http(clean["articleUrl"]):
        host = urlparse(clean["articleUrl"]).hostname or ""
        clean["site"] = host[4:] if host.startswith("www.") else host

    if not clean["site"]:
        errors.append("Give the outlet (site) or the article URL.")

    if clean["label"] != "UNVERIFIED" and not links:
        errors.append("A verdict other than UNVERIFIED needs at least one evidence link.")

    # Rule 1: the organisation's own source alone is not enough evidence.
    if clean["onlyOwnSource"]:
        if clean["label"] != "UNVERIFIED":
            errors.append("Only the organisation's own source backs it: the guide labels that UNVERIFIED.")
        if not clean["annotatorNote"]:
            errors.append("Only the organisation's own source backs it: name that source in the note.")

    # Rule 3: only evidence available when the article was published.
    if clean["evidenceDate"] and clean["claimDate"] and clean["evidenceDate"] > clean["claimDate"]:
        errors.append("The evidence is newer than the article. Use only evidence available on the publication date.")

    return clean, errors


def build_record(fact_id: str, clean: dict, now: str, previous: dict | None = None) -> dict:
    """x-fact's keys first and in x-fact's order, then the custom set's own."""

    return {
        "language": clean["language"],
        "site": clean["site"],
        "claimant": clean["claimant"],
        "claim": clean["claim"],
        "claimDate": clean["claimDate"].isoformat(),
        # x-fact: when the fact-checker published the verdict. Here: when
        # the annotator last set it.
        "reviewDate": now,
        "labelRaw": LABELS[clean["label"]],
        "label": clean["label"],
        "referenceEvidenceLinks": clean["referenceEvidenceLinks"],
        "split": SPLIT,
        "id": fact_id,
        "topic": clean["topic"],
        "claimType": clean["claimType"],
        "sourceTier": clean["sourceTier"],
        "onlyOwnSource": clean["onlyOwnSource"],
        "evidenceDate": clean["evidenceDate"].isoformat() if clean["evidenceDate"] else None,
        "articleUrl": clean["articleUrl"],
        "annotatorNote": clean["annotatorNote"],
        "createdAt": (previous or {}).get("createdAt", now),
        # A correction made after a review keeps the review: its
        # firstLabel is what self-agreement is measured on.
        "review": (previous or {}).get("review"),
    }


# ----------------------------------------------------------------------
# One file per fact
# ----------------------------------------------------------------------


class Store:

    def __init__(self, folder: Path = MANUAL, topics: dict[str, str] | None = None):
        self.folder = Path(folder)
        self.topics = topics if topics is not None else load_topics()

    def path(self, fact_id: str) -> Path:
        return self.folder / f"{fact_id}.json"

    def load(self) -> tuple[list[dict], list[dict]]:
        """(facts in number order, files that could not be read)."""

        facts, broken = [], []

        if not self.folder.exists():
            return facts, broken

        for path in sorted(self.folder.glob("fact*.json"), key=_number):
            try:
                facts.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError) as error:
                # A file edited by hand can break; show it, do not crash.
                broken.append({"file": path.name, "error": str(error)})

        return facts, broken

    def get(self, fact_id: str) -> dict | None:
        path = self.path(fact_id)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def create(self, data: dict) -> tuple[dict | None, list[str]]:

        clean, errors = validate(data, self.topics)
        if errors:
            return None, errors

        self.folder.mkdir(parents=True, exist_ok=True)
        numbers = [_number(p) for p in self.folder.glob("fact*.json")]
        fact_id = f"fact{(max(numbers) + 1 if numbers else 1):03d}"
        record = build_record(fact_id, clean, _now())

        # "x": never overwrite a fact that appeared under this name meanwhile.
        with self.path(fact_id).open("x", encoding="utf-8") as f:
            f.write(_dump(record))

        return record, []

    def update(self, fact_id: str, data: dict) -> tuple[dict | None, list[str]]:

        previous = self.get(fact_id)
        if previous is None:
            return None, ["Fact not found."]

        clean, errors = validate(data, self.topics)
        if errors:
            return None, errors

        record = build_record(fact_id, clean, _now(), previous)
        self._write(record)

        return record, []

    def review(self, fact_id: str, label: str, note: str | None) -> tuple[dict | None, list[str]]:

        record = self.get(fact_id)
        if record is None:
            return None, ["Fact not found."]
        if label not in LABELS:
            return None, [f"label must be one of {', '.join(LABELS)}."]

        first = (record.get("review") or {}).get("firstLabel", record["label"])
        record["review"] = {
            "label": label,
            "firstLabel": first,
            "agrees": label == first,
            "note": (note or "").strip() or None,
            "reviewedAt": _now(),
        }
        self._write(record)

        return record, []

    def _write(self, record: dict) -> None:
        path = self.path(record["id"])
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(_dump(record), encoding="utf-8")
        os.replace(tmp, path)

    def join(self, out: Path = JOINED) -> dict:
        """Every fact file, re-validated, into one JSONL in number order."""

        facts, broken = self.load()
        problems = [f"{b['file']}: {b['error']}" for b in broken]

        for fact in facts:
            _, errors = validate(fact, self.topics)
            problems += [f"{fact.get('id')}: {e}" for e in errors]
            missing = [k for k in XFACT_FIELDS if k not in fact]
            if missing:
                problems.append(f"{fact.get('id')}: missing {', '.join(missing)}")

        if problems:
            raise ValueError("Not joined - fix these first:\n  " + "\n  ".join(problems))

        with out.open("w", encoding="utf-8") as f:
            for fact in facts:
                f.write(json.dumps(fact, ensure_ascii=False) + "\n")

        return summarise(facts)


# ----------------------------------------------------------------------
# Balance, review sample, agreement
# ----------------------------------------------------------------------


def summarise(facts: list[dict]) -> dict:

    matrix = {label: {g: 0 for g in TOPIC_GROUPS} for label in LABELS}
    for fact in facts:
        group = GROUP_OF.get(fact.get("topic"))
        if fact.get("label") in matrix and group:
            matrix[fact["label"]][group] += 1

    def count(key, order):
        c = Counter(key(f) for f in facts)
        return {k: c.get(k, 0) for k in order}

    return {
        "total": len(facts),
        "byLabel": count(lambda f: f.get("label"), LABELS),
        "byGroup": count(lambda f: GROUP_OF.get(f.get("topic")), TOPIC_GROUPS),
        "byTopic": count(lambda f: f.get("topic"), GROUP_OF),
        "byLanguage": count(lambda f: f.get("language"), ("en", "es")),
        "byClaimType": count(lambda f: f.get("claimType"), CLAIM_TYPES),
        "matrix": matrix,
    }


def review_sample(facts: list[dict]) -> list[dict]:
    """
    ceil(20%) of the set: every fact already reviewed, then the rest in
    the order of a SHA-256 of their id. Not chosen by the annotator, and
    stable - adding facts only adds to it.
    """

    if not facts:
        return []

    size = math.ceil(len(facts) * REVIEW_SHARE)
    reviewed = [f for f in facts if f.get("review")]
    rest = sorted(
        (f for f in facts if not f.get("review")),
        key=lambda f: hashlib.sha256(f["id"].encode()).hexdigest(),
    )

    return reviewed + rest[: max(0, size - len(reviewed))]


def agreement(facts: list[dict]) -> dict:
    """
    First label against the blind second one: observed agreement and
    Cohen's kappa, which discounts what two labellings would agree on by
    chance given how often each used every label.
    """

    pairs = [(f["review"]["firstLabel"], f["review"]["label"], f) for f in facts if f.get("review")]
    n = len(pairs)

    if not n:
        return {"reviewed": 0, "observed": None, "kappa": None, "disagreements": []}

    observed = sum(a == b for a, b, _ in pairs) / n
    first = Counter(a for a, _, _ in pairs)
    second = Counter(b for _, b, _ in pairs)
    expected = sum(first[k] * second[k] for k in first) / (n * n)

    # All pairs on one and the same label: kappa is undefined, not perfect.
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)

    return {
        "reviewed": n,
        "observed": round(observed, 4),
        "kappa": None if kappa is None else round(kappa, 4),
        "disagreements": [
            {"id": f["id"], "claim": f["claim"], "firstLabel": a, "secondLabel": b}
            for a, b, f in pairs if a != b
        ],
    }


def blinded(fact: dict) -> dict:
    """A review-sample item without whatever gives the first label away."""

    hidden = {"label", "labelRaw", "annotatorNote", "onlyOwnSource"}
    row = {k: v for k, v in fact.items() if k not in hidden}
    if row.get("review"):
        row["review"] = {"label": row["review"]["label"]}
    return row


def state(store: Store) -> dict:

    facts, broken = store.load()
    sample = review_sample(facts)

    return {
        "facts": list(reversed(facts)),
        "broken": broken,
        "folder": str(store.folder.relative_to(ROOT)) if store.folder.is_relative_to(ROOT) else str(store.folder),
        "summary": summarise(facts),
        "review": {"sample": [blinded(f) for f in sample], "sampleSize": len(sample), "agreement": agreement(facts)},
        "schema": {
            "labels": [{"label": k, "labelRaw": v, "help": LABEL_HELP[k]} for k, v in LABELS.items()],
            "topics": [{"id": k, "name": v, "group": GROUP_OF.get(k)} for k, v in store.topics.items()],
            "groups": list(TOPIC_GROUPS),
            "claimTypes": list(CLAIM_TYPES),
            "sourceTiers": list(SOURCE_TIERS),
            "targets": {
                "total": TARGET_TOTAL,
                "minimum": MINIMUM_TOTAL,
                "perLabel": TARGET_TOTAL // len(LABELS),
                "perGroup": TARGET_TOTAL // len(TOPIC_GROUPS),
                "perCell": TARGET_TOTAL // (len(LABELS) * len(TOPIC_GROUPS)),
                "reviewShare": REVIEW_SHARE,
            },
        },
    }


# ----------------------------------------------------------------------
# The day's batch
# ----------------------------------------------------------------------


class BackendUnreachable(Exception):
    pass


class Backend:
    """The backend's /labelling/batch, over urllib: nothing to install."""

    def __init__(self, base_url: str = BACKEND_URL, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("STORAGE_API_KEY")

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.loads(error.read() or b"{}")
            except ValueError:
                return error.code, {"detail": f"HTTP {error.code}"}
        except (urllib.error.URLError, OSError) as error:
            raise BackendUnreachable(
                f"Could not reach the backend at {self.base_url} ({error}). Start it: "
                "cd backend && uv run uvicorn src.main:app"
            ) from error


class Queue:
    """One file per batch: YYYY-MM-DD.json, then -2, -3 on the same day."""

    def __init__(self, folder: Path = QUEUE):
        self.folder = Path(folder)

    def names(self) -> list[str]:
        if not self.folder.exists():
            return []
        return sorted(p.name for p in self.folder.glob("*.json") if BATCH_FILE.match(p.name))

    def load(self, name: str) -> dict | None:
        if not BATCH_FILE.match(name or ""):
            return None
        path = self.folder / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def all(self) -> list[dict]:
        batches = []
        for name in self.names():
            try:
                batches.append(self.load(name))
            except (OSError, ValueError):
                continue
        return [b for b in batches if b]

    def save(self, batch: dict, today: str) -> str:
        """Stores a batch from the backend. The same request twice is one file."""

        for existing in self.all():
            if batch.get("requestId") and existing.get("requestId") == batch["requestId"]:
                return existing["file"]

        self.folder.mkdir(parents=True, exist_ok=True)
        name, n = f"{today}.json", 1
        while (self.folder / name).exists():
            n += 1
            name = f"{today}-{n}.json"

        record = {**batch, "file": name, "date": today}
        for article in record.get("articles", []):
            for claim in article.get("claims", []):
                claim.setdefault("status", "pending")
                claim.setdefault("factIds", [])
                claim.setdefault("skipReason", None)

        self._write(name, record)
        return name

    def mark(self, name: str, article: int, claim: int, status: str,
             reason: str | None = None, fact_id: str | None = None) -> tuple[dict | None, list[str]]:

        batch = self.load(name)
        if batch is None:
            return None, ["Batch not found."]
        try:
            if article < 0 or claim < 0:
                raise IndexError
            item = batch["articles"][article]["claims"][claim]
        except (IndexError, KeyError, TypeError):
            return None, ["No such claim in that batch."]

        if status == "labelled":
            item["status"] = "labelled"
            item["skipReason"] = None
            if fact_id and fact_id not in item["factIds"]:
                item["factIds"].append(fact_id)
        elif status == "skipped":
            if reason not in SKIP_REASONS:
                return None, [f"reason must be one of {', '.join(SKIP_REASONS)}."]
            item["status"] = "skipped"
            item["skipReason"] = reason
        elif status == "pending":
            item["status"] = "labelled" if item["factIds"] else "pending"
            item["skipReason"] = None
        else:
            return None, ["status must be labelled, skipped or pending."]

        self._write(name, batch)
        return batch, []

    def known_urls(self) -> set[str]:
        urls = set()
        for batch in self.all():
            urls.update(a.get("url") for a in batch.get("articles", []))
            urls.update(s.get("url") for s in batch.get("skipped", []))
        return {u for u in urls if u}

    def stats(self) -> dict:
        """
        Over every batch: what was proposed and what became of it. The
        selection precision is labelled / (labelled + skipped); pending
        claims have not been judged yet.
        """

        counts = Counter()
        reasons = Counter()
        for batch in self.all():
            for article in batch.get("articles", []):
                for claim in article.get("claims", []):
                    counts[claim.get("status", "pending")] += 1
                    if claim.get("status") == "skipped":
                        reasons[claim.get("skipReason")] += 1

        judged = counts["labelled"] + counts["skipped"]
        return {
            "proposed": sum(counts.values()),
            "labelled": counts["labelled"],
            "skipped": counts["skipped"],
            "pending": counts["pending"],
            "byReason": {k: reasons.get(k, 0) for k in SKIP_REASONS},
            "precision": round(counts["labelled"] / judged, 4) if judged else None,
        }

    def _write(self, name: str, batch: dict) -> None:
        path = self.folder / name
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(_dump(batch), encoding="utf-8")
        os.replace(tmp, path)


def prefer_topics(summary: dict) -> list[str]:
    """
    The topics of every group below the average group count: what the
    balance table is short of. Nothing when the groups are level.
    """

    counts = summary["byGroup"]
    average = sum(counts.values()) / len(counts)
    short = [g for g, n in counts.items() if n < average]
    return [t for g in short for t in TOPIC_GROUPS[g]]


def batch_request(store: "Store", queue: Queue, options: dict, request_id: str, today: str) -> dict:
    """What to ask the backend for: never an article already labelled or proposed."""

    facts, _ = store.load()
    exclude = {f.get("articleUrl") for f in facts if f.get("articleUrl")} | queue.known_urls()

    languages = options.get("languages")
    if languages not in (None, ["en"], ["es"], ["en", "es"]):
        languages = None

    return {
        "articles": max(1, min(30, _int(options.get("articles")) if _int(options.get("articles")) > 0 else 10)),
        "claimsPerArticle": max(1, min(3, _int(options.get("claimsPerArticle")) if _int(options.get("claimsPerArticle")) > 0 else 3)),
        "exclude": sorted(exclude),
        "preferTopics": prefer_topics(summarise(facts)),
        "languages": languages,
        "seed": today,
        "requestId": request_id,
    }


# ----------------------------------------------------------------------
# HTTP
# ----------------------------------------------------------------------


def make_handler(store: Store, queue: Queue | None = None, backend: Backend | None = None):

    # Beside the facts folder, so a test's temporary store gets a
    # temporary queue too.
    queue = queue if queue is not None else Queue(store.folder.parent / "queue")
    backend = backend if backend is not None else Backend()

    # The batch this labeller asked for and has not saved yet.
    pending: dict = {}

    def queue_state(name: str | None) -> dict:
        names = queue.names()
        current = queue.load(name) if name in names else (queue.load(names[-1]) if names else None)
        files = []
        for batch in queue.all():
            claims = [c for a in batch.get("articles", []) for c in a.get("claims", [])]
            files.append({
                "name": batch["file"],
                "claims": len(claims),
                "done": sum(c.get("status") != "pending" for c in claims),
            })
        return {
            "files": files,
            "current": current,
            "stats": queue.stats(),
            "skipReasons": SKIP_REASONS,
            "pending": dict(pending) or None,
            "backend": backend.base_url,
        }

    def batch_status() -> tuple[int, dict]:
        if not pending:
            return 200, {"running": False}
        try:
            code, data = backend.call("GET", "/labelling/batch")
        except BackendUnreachable as error:
            return 502, {"errors": [str(error)]}
        if code != 200:
            return 502, {"errors": [data.get("detail") or f"The backend answered {code}."]}
        if data.get("running"):
            return 200, {"running": True, "startedAt": data.get("startedAt")}
        batch = data.get("batch") or {}
        request_id = pending.get("requestId")
        pending.clear()
        if data.get("error"):
            return 502, {"errors": [f"The batch failed in the backend: {data['error']}"]}
        if batch.get("requestId") != request_id:
            return 502, {"errors": ["The backend finished a different batch; ask again."]}
        name = queue.save(batch, date.today().isoformat())
        return 200, {"running": False, "saved": name}

    class Handler(BaseHTTPRequestHandler):

        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/state":
                self._json(200, state(store))
            elif url.path == "/api/queue":
                name = (parse_qs(url.query).get("name") or [None])[0]
                self._json(200, queue_state(name))
            elif url.path == "/api/queue/status":
                self._json(*batch_status())
            else:
                self._json(404, {"errors": ["Not found."]})

        def do_POST(self):
            body = self._body()
            if body is None:
                return
            if self.path == "/api/facts":
                record, errors = store.create(body)
                ref = body.get("queueRef")
                if record is not None and isinstance(ref, dict):
                    # A fact labelled from the day's batch: mark its claim.
                    queue.mark(str(ref.get("name")), _int(ref.get("article")), _int(ref.get("claim")),
                               "labelled", fact_id=record["id"])
                self._answer(record, errors, created=True)
                return
            if self.path == "/api/queue/fetch":
                if pending:
                    self._json(409, {"errors": ["A batch is already being built; wait for it."]})
                    return
                request_id = uuid.uuid4().hex
                request = batch_request(store, queue, body, request_id, date.today().isoformat())
                try:
                    code, data = backend.call("POST", "/labelling/batch", request)
                except BackendUnreachable as error:
                    self._json(502, {"errors": [str(error)]})
                    return
                if code != 202:
                    self._json(502, {"errors": [data.get("detail") or f"The backend answered {code}."]})
                    return
                pending.update({"requestId": request_id, "startedAt": _now()})
                self._json(202, {"started": True, "excluded": len(request["exclude"]),
                                 "preferTopics": request["preferTopics"]})
                return
            if self.path == "/api/queue/claim":
                batch, errors = queue.mark(str(body.get("name")), _int(body.get("article")),
                                           _int(body.get("claim")), str(body.get("status")),
                                           reason=body.get("reason"))
                if batch is None:
                    self._json(422, {"errors": errors})
                else:
                    self._json(200, {"ok": True})
                return
            match = re.fullmatch(r"/api/facts/(fact\d{3,})/review", self.path)
            if match:
                record, errors = store.review(match.group(1), body.get("label"), body.get("note"))
                self._answer(record, errors)
                return
            self._json(404, {"errors": ["Not found."]})

        def do_PUT(self):
            body = self._body()
            if body is None:
                return
            match = re.fullmatch(r"/api/facts/(fact\d{3,})", self.path)
            if not match:
                self._json(404, {"errors": ["Not found."]})
                return
            record, errors = store.update(match.group(1), body)
            self._answer(record, errors)

        def _body(self):
            # Only JSON, and only from this page: a browser will not send
            # a cross-site application/json request without a preflight
            # this server never answers, so another site cannot write
            # facts through it.
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                self._json(415, {"errors": ["Send application/json."]})
                return None
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                self._json(400, {"errors": ["The body is not JSON."]})
                return None
            if not isinstance(body, dict):
                self._json(400, {"errors": ["The body must be a JSON object."]})
                return None
            return body

        def _answer(self, record, errors, created=False):
            if record is not None:
                self._json(201 if created else 200, record)
            elif errors == ["Fact not found."]:
                self._json(404, {"errors": errors})
            else:
                self._json(422, {"errors": errors})

        def _json(self, status, payload):
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")

    return Handler


# ----------------------------------------------------------------------
# Helpers and entry point
# ----------------------------------------------------------------------


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _number(path: Path) -> int:
    match = FACT_ID.match(path.stem)
    return int(match.group(1)) if match else 0


def _dump(record: dict) -> str:
    # Indented and unescaped: one fact per file is meant to be read in
    # the repository, and half of them are Spanish.
    return json.dumps(record, ensure_ascii=False, indent=2) + "\n"


def _now() -> str:
    # x-fact's reviewDate format: seconds, no zone.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description="Hand-label the custom validation set.")
    parser.add_argument("command", nargs="?", default="serve", choices=("serve", "join"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)

    store = Store()

    if args.command == "join":
        try:
            summary = store.join()
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        print(f"Joined {summary['total']} facts into {JOINED.relative_to(ROOT)}")
        print(f"By label: {summary['byLabel']}")
        print(f"By group: {summary['byGroup']}")
        return 0

    # 127.0.0.1 only: this writes into the repository.
    server = HTTPServer(("127.0.0.1", args.port), make_handler(store))
    url = f"http://127.0.0.1:{args.port}"
    print(f"Fact labeller on {url} - facts go to {store.folder.relative_to(ROOT)}/  (Ctrl+C to stop)")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

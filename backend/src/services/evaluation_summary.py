"""
What the evaluation has produced so far, in one read-only answer for the
frontend's /evaluation page:

1. The hand-labelled facts (data/evaluation/manual/factNNN.json, written
   by labeller/): every fact, and the counts the paper reports - per
   verdict, per topic group, the verdict x group balance against the
   150-fact target, per language, claim type and source tier.
2. The daily labelling batches (data/evaluation/queue/*.json): what the
   pipeline's claim selector proposed and what became of each proposal.
   labelled / (labelled + skipped) is the selector's precision as judged
   by the annotator - a result for the paper, not just progress.
3. The evaluation harness's reports (data/evaluation/reports/<dataset>/
   <model>/<key>/metrics.json), passed through as written, so this file
   does not have to change every time the metrics gain a key.

Nothing here imports labeller/: the labeller imports nothing from the
backend, on purpose, and the dependency stays one-way in the other
direction too. The topic groups are therefore declared twice, and
tests/services/test_evaluation_summary.py holds this copy to the
labeller's.

Every file is read on every call. The set is a few hundred small files
at most (150 facts is the target), so a cache would cost more in
staleness - a fact saved in the labeller should show on the next
refresh - than it saves in reads.
"""

import json
from collections import Counter
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

EVALUATION_PATH = Path("data/evaluation")

# Same order as the labeller's LABELS: from supported to not enough
# evidence. The page draws its rows in this order.
LABELS = ("TRUE", "PARTIALLY_TRUE", "MISLEADING", "FALSE", "UNVERIFIED")

# labeller/app.py's TOPIC_GROUPS - balance is steered over these five
# groups, not the 23 topics (too thin at 150 facts). Held to the
# labeller's copy by a test.
TOPIC_GROUPS = {
    "society": ["education", "community", "employment", "cities"],
    "science": ["space", "technology", "research", "biology"],
    "environment": ["climate", "nature", "energy", "sustainability", "food"],
    "culture": ["arts", "entertainment", "heritage", "literature", "inspiration"],
    "health": ["medicine", "mental_health", "nutrition", "fitness", "public_health"],
}
GROUP_OF = {t: g for g, topics in TOPIC_GROUPS.items() for t in topics}

CLAIM_TYPES = ("factual", "numerical", "interpretive")
SOURCE_TIERS = ("primary", "reference_media", "press_release", "social_media")
SKIP_REASONS = ("opinion", "prediction", "trivial", "fragment", "duplicate", "other")

TARGET_TOTAL = 150
MINIMUM_TOTAL = 100

# A fact labelled by an AI assistant rather than the human annotator
# starts its note with this. The paper's method is a single human
# annotator, so these are shown apart until a person has checked them.
AI_NOTE_PREFIX = "[AI label:"

# A report's metrics.json is passed through whole; one that grew past
# this is a bug in the harness, not something to ship to a browser.
MAX_REPORT_BYTES = 512 * 1024


def _read_json(path: Path) -> tuple[object | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as error:
        return None, str(error)


def _fact_number(path: Path) -> int:
    digits = path.stem.removeprefix("fact")
    return int(digits) if digits.isdigit() else 0


def _annotator(fact: dict) -> str:
    note = fact.get("annotatorNote") or ""
    return "ai" if note.startswith(AI_NOTE_PREFIX) else "human"


def _counts(values, keys) -> dict[str, int]:
    """Every declared key, zero included, then anything undeclared seen."""

    counter = Counter(values)
    counts = {key: counter.pop(key, 0) for key in keys}
    counts.update({str(key): n for key, n in counter.items() if key is not None})
    return counts


def _facts(folder: Path) -> tuple[list[dict], list[dict]]:

    facts, broken = [], []

    if not folder.exists():
        return facts, broken

    for path in sorted(folder.glob("fact*.json"), key=_fact_number):
        data, error = _read_json(path)
        if error is not None or not isinstance(data, dict):
            # A file edited by hand can break; show it, do not fail the page.
            broken.append({"file": path.name, "error": error or "not a JSON object"})
            continue

        topic = data.get("topic")
        facts.append({
            "id": data.get("id") or path.stem,
            "claim": data.get("claim"),
            "label": data.get("label"),
            "labelRaw": data.get("labelRaw"),
            "language": data.get("language"),
            "site": data.get("site"),
            "claimant": data.get("claimant"),
            "claimDate": data.get("claimDate"),
            "topic": topic,
            "group": GROUP_OF.get(topic),
            "claimType": data.get("claimType"),
            "sourceTier": data.get("sourceTier"),
            "onlyOwnSource": data.get("onlyOwnSource") is True,
            "evidenceDate": data.get("evidenceDate"),
            "articleUrl": data.get("articleUrl"),
            "evidenceLinks": list(data.get("referenceEvidenceLinks") or []),
            "note": data.get("annotatorNote"),
            "createdAt": data.get("createdAt"),
            "annotator": _annotator(data),
            "reviewed": bool(data.get("review")),
        })

    return facts, broken


def _fact_totals(facts: list[dict]) -> dict:

    matrix = {label: {group: 0 for group in TOPIC_GROUPS} for label in LABELS}
    for fact in facts:
        if fact["label"] in matrix and fact["group"]:
            matrix[fact["label"]][fact["group"]] += 1

    # createdAt is x-fact's reviewDate format, "YYYY-MM-DDTHH:MM:SS".
    per_day = Counter((fact["createdAt"] or "")[:10] for fact in facts if fact["createdAt"])

    return {
        "total": len(facts),
        "target": TARGET_TOTAL,
        "minimum": MINIMUM_TOTAL,
        "perCell": TARGET_TOTAL // (len(LABELS) * len(TOPIC_GROUPS)),
        "byLabel": _counts((f["label"] for f in facts), LABELS),
        "byGroup": _counts((f["group"] for f in facts), TOPIC_GROUPS),
        "byLanguage": _counts((f["language"] for f in facts), ("en", "es")),
        "byClaimType": _counts((f["claimType"] for f in facts), CLAIM_TYPES),
        "bySourceTier": _counts((f["sourceTier"] for f in facts), SOURCE_TIERS),
        "byAnnotator": _counts((f["annotator"] for f in facts), ("human", "ai")),
        "reviewed": sum(1 for f in facts if f["reviewed"]),
        "matrix": matrix,
        "perDay": [{"date": day, "value": n} for day, n in sorted(per_day.items())],
    }


def _selection(folder: Path) -> dict:
    """The claim selector's proposals, batch by batch, and their fate."""

    batches, broken = [], []
    reasons = Counter()
    by_language = {}

    paths = sorted(folder.glob("*.json")) if folder.exists() else []

    for path in paths:
        data, error = _read_json(path)
        if error is not None or not isinstance(data, dict):
            broken.append({"file": path.name, "error": error or "not a JSON object"})
            continue

        counts = Counter()
        batch_reasons = Counter()

        for article in data.get("articles") or []:
            language = article.get("language") or "unknown"
            for claim in article.get("claims") or []:
                status = claim.get("status") or "pending"
                counts[status] += 1
                by_language.setdefault(language, Counter())[status] += 1
                if status == "skipped":
                    batch_reasons[claim.get("skipReason") or "other"] += 1

        reasons.update(batch_reasons)
        batches.append({
            "file": path.name,
            "date": data.get("date") or path.stem[:10],
            "articles": len(data.get("articles") or []),
            "proposed": sum(counts.values()),
            "labelled": counts["labelled"],
            "skipped": counts["skipped"],
            "pending": counts["pending"],
            "byReason": _counts(batch_reasons.elements(), SKIP_REASONS),
        })

    labelled = sum(b["labelled"] for b in batches)
    skipped = sum(b["skipped"] for b in batches)

    def precision(l: int, s: int) -> float | None:
        return round(l / (l + s), 4) if l + s else None

    return {
        "batches": batches,
        "broken": broken,
        "proposed": sum(b["proposed"] for b in batches),
        "labelled": labelled,
        "skipped": skipped,
        "pending": sum(b["pending"] for b in batches),
        "precision": precision(labelled, skipped),
        "byReason": _counts(reasons.elements(), SKIP_REASONS),
        "byLanguage": {
            language: {
                "labelled": c["labelled"],
                "skipped": c["skipped"],
                "pending": c["pending"],
                "precision": precision(c["labelled"], c["skipped"]),
            }
            for language, c in sorted(by_language.items())
        },
    }


def _runs(folder: Path) -> list[dict]:
    """
    Every harness report found, newest first. The directory names say
    which dataset and model the run was; metrics.json says how it went,
    passed through as written.
    """

    runs = []

    if not folder.exists():
        return runs

    for path in folder.glob("*/*/*/metrics.json"):
        key_dir = path.parent
        try:
            size = path.stat().st_size
        except OSError:
            continue

        if size > MAX_REPORT_BYTES:
            metrics, error = None, f"metrics.json is {size} bytes, over {MAX_REPORT_BYTES}"
        else:
            metrics, error = _read_json(path)

        run, _ = _read_json(key_dir / "run.json") if (key_dir / "run.json").exists() else (None, None)

        runs.append({
            "dataset": key_dir.parent.parent.name,
            "model": key_dir.parent.name,
            "key": key_dir.name,
            "modifiedAt": path.stat().st_mtime,
            "metrics": metrics if isinstance(metrics, dict) else None,
            "run": run if isinstance(run, dict) else None,
            "error": error,
        })

    runs.sort(key=lambda r: r["modifiedAt"], reverse=True)
    return runs


def evaluation_summary(base: Path | None = None) -> dict:
    """The whole /evaluation page's data. Read-only; never raises on a bad file."""

    # Resolved per call, not as a default argument, so a test can point
    # the module at tmp_path.
    base = base if base is not None else EVALUATION_PATH

    facts, broken = _facts(base / "manual")

    return {
        "facts": facts,
        "brokenFacts": broken,
        "totals": _fact_totals(facts),
        "selection": _selection(base / "queue"),
        "runs": _runs(base / "reports"),
        "labels": list(LABELS),
        "groups": {group: list(topics) for group, topics in TOPIC_GROUPS.items()},
        "skipReasons": list(SKIP_REASONS),
        "found": (base / "manual").exists() or (base / "queue").exists(),
    }

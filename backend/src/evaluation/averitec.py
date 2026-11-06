"""
AVeriTeC: the benchmark every evaluation is measured on since 2026-11-05.

Schlichtkrull et al., NeurIPS 2023: 4,568 real claims from 50 fact-checking
organisations, four verdicts, and a date for each claim. Measured here as
ClaimCheck measures it (Putta et al., 2025, arXiv:2510.01226): on the 500
claims of the development split, whose labels are public (the test split has
none), by verdict accuracy, with nothing published from the claim's date on
readable as evidence (`services/fact_checker/retrieval/temporal.py`).

Three things this module holds that a generic metric would get wrong:

- **Four classes.** The pipeline has five verdicts; AVeriTeC has four. Both
  PARTIALLY_TRUE and MISLEADING are "Conflicting Evidence/Cherrypicking", the
  labeller's own reading of the two (labeller/app.py, LABELS).
- **Every claim counts.** A published accuracy is over the whole split, so a
  claim whose search failed or whose model never answered counts as wrong here,
  though the harness's own report sets it apart.
- **The trivial answer is good.** 61% of the dev split is Refuted, so "always
  Refuted" scores 61.0% without reading anything. An accuracy means little
  without that line and macro-F1 beside it.

Licence: the data is CC BY-NC 4.0 and is not in git (`backend/data/evaluation/
averitec/`, gitignored). `cli averitec import` rebuilds the rows from the pinned
files, and the provenance beside them says what they were made from.
"""

from __future__ import annotations

import hashlib
import json
import random
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from src.models.fact_checker.questions import NO_ANSWER
from src.services.fact_checker.retrieval import temporal

# The Hugging Face revision the official files were downloaded from.
SOURCE = "https://huggingface.co/chenxwh/AVeriTeC"
SOURCE_REVISION = "2ca9dee23a2a6fa64c5bd918e0cd28ed0aa09031"

SUPPORTED = "Supported"
REFUTED = "Refuted"
NOT_ENOUGH = "Not Enough Evidence"
CONFLICTING = "Conflicting Evidence/Cherrypicking"

CLASSES = (SUPPORTED, REFUTED, NOT_ENOUGH, CONFLICTING)

# AVeriTeC's label -> the pipeline's, for the row's `label`.
TO_VERDICT = {
    SUPPORTED: "TRUE",
    REFUTED: "FALSE",
    NOT_ENOUGH: "UNVERIFIED",
    CONFLICTING: "MISLEADING",
}

# The pipeline's verdict -> AVeriTeC's, for scoring. Not TO_VERDICT reversed:
# PARTIALLY_TRUE ("holds, but a source contradicts a detail") has no class of
# its own there.
TO_CLASS = {
    "TRUE": SUPPORTED,
    "FALSE": REFUTED,
    "UNVERIFIED": NOT_ENOUGH,
    "MISLEADING": CONFLICTING,
    "PARTIALLY_TRUE": CONFLICTING,
}

# ClaimCheck's Table 1, accuracy on the dev split. `n` says how many claims.
# Live-web systems, the knowledge store's, and no evidence at all: compare a
# run only with its own kind. GPT-4o's two web rows are left out of "before the
# claim": the paper says they could not be held to the date and did read the
# fact-checks.
PUBLISHED = (
    {"system": "ClaimCheck (Qwen3-4B)", "accuracy": 0.764, "n": 500, "evidence": "web, before the claim"},
    {"system": "PASS-FC (GPT-4o)", "accuracy": 0.720, "n": 500, "evidence": "web"},
    {"system": "DEFAME (GPT-4o)", "accuracy": 0.705, "n": 500, "evidence": "web"},
    {"system": "GPT-4o + web search", "accuracy": 0.746, "n": 500, "evidence": "web, leaks"},
    {"system": "GPT-4o mini + web search", "accuracy": 0.704, "n": 500, "evidence": "web, leaks"},
    {"system": "Papelo (GPT-4o mini)", "accuracy": 0.415, "n": 500, "evidence": "web"},
    {"system": "HerO (Llama 3.1 70B)", "accuracy": 0.752, "n": 500, "evidence": "knowledge store"},
    {"system": "InFact (GPT-4o)", "accuracy": 0.724, "n": 500, "evidence": "knowledge store"},
    {"system": "GPT-4o", "accuracy": 0.532, "n": 500, "evidence": "none"},
    {"system": "Qwen3-4B", "accuracy": 0.520, "n": 500, "evidence": "none"},
    {"system": "GPT-4o mini", "accuracy": 0.468, "n": 500, "evidence": "none"},
)

LANGUAGE = "en"


# ----------------------------------------------------------------------
# The rows
# ----------------------------------------------------------------------


def iso_date(value: str | None) -> str | None:
    """The official files write "31-10-2020". None for no date or an impossible one."""

    try:
        day, month, year = (int(part) for part in str(value or "").strip().split("-"))
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def row_id(split: str, index: int) -> str:
    """Stable: the claim's position in the pinned official file."""

    return f"averitec-{split}-{index:04d}"


def order_key(identifier: str) -> str:
    """
    The order rows are written in: by hash, so that `--limit N` is a fixed
    random sample that a later `--limit M` extends, in the same run directory.
    ClaimCheck's ablations used a random 100 of the dev split too. Set once,
    by a rule that reads nothing of the claim or its label.
    """

    return hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def reference_links(raw: dict) -> list[str]:
    """The annotators' sources, each once: the gold evidence's addresses."""

    links = []

    for question in raw.get("questions") or []:

        answers = question.get("answers") if isinstance(question, dict) else None

        for answer in answers or []:

            url = answer.get("source_url") if isinstance(answer, dict) else None

            if url and url not in links:
                links.append(url)

    return links


def to_row(raw: dict, split: str, index: int) -> dict | None:
    """
    One official claim as a harness row, or None when it has no usable date
    or label: with no date there is no cutoff, and it cannot be run soundly.
    A claim before 2000 is a typo in the date, not a claim from 1919: its
    cutoff would refuse the whole web.
    """

    claim_date = iso_date(raw.get("claim_date"))
    label = TO_VERDICT.get(raw.get("label"))

    if not claim_date or not label or not raw.get("claim") or claim_date < "2000-01-01":
        return None

    fact_check = temporal.unarchived(raw.get("fact_checking_article") or "")

    return {
        "dataset": "averitec",
        "id": row_id(split, index),
        "split": split,
        "language": LANGUAGE,
        "site": urlsplit(fact_check).netloc.lower().removeprefix("www.") or None,
        "claim": raw["claim"],
        "claimDate": claim_date,
        "label": label,
        "labelRaw": raw["label"],
        "referenceEvidenceLinks": reference_links(raw),
        "factCheckUrl": fact_check or None,
        # Carried for breakdowns and for a later experiment. Never given to
        # the pipeline: the first run measures the claim alone.
        "claimTypes": raw.get("claim_types") or [],
        "speaker": raw.get("speaker"),
        "location": raw.get("location_ISO_code"),
        "reportingSource": raw.get("reporting_source"),
        "requiredReannotation": bool(raw.get("required_reannotation")),
    }


def import_split(raw_path: Path, split: str, target: Path) -> dict:
    """
    The official JSON as the harness's JSONL, hash-ordered, with a provenance
    file beside it. Returns the provenance.
    """

    data = raw_path.read_bytes()

    raw = json.loads(data.decode("utf-8"))

    rows, excluded = [], []

    for index, item in enumerate(raw):

        row = to_row(item, split, index)

        if row is None:
            excluded.append({"id": row_id(split, index), "claimDate": item.get("claim_date"), "label": item.get("label")})
        else:
            rows.append(row)

    rows.sort(key=lambda row: order_key(row["id"]))

    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    provenance = {
        "source": SOURCE,
        "revision": SOURCE_REVISION,
        "file": raw_path.name,
        "fileSha256": hashlib.sha256(data).hexdigest(),
        "split": split,
        "official": len(raw),
        "rows": len(rows),
        "excluded": excluded,
        "order": "sha256 of the row id, so --limit N is a fixed random sample",
        "labels": {name: sum(1 for row in rows if row["labelRaw"] == name) for name in CLASSES},
    }

    target.with_suffix(".provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return provenance


# ----------------------------------------------------------------------
# The scores
# ----------------------------------------------------------------------


def predicted_class(record: dict) -> str | None:
    """AVeriTeC's class for a record, or None when it gave no answer at all."""

    return TO_CLASS.get(record.get("verdict") or "")


def _gold(record: dict) -> str:

    return record.get("labelRaw") or next(
        (name for name, verdict in TO_VERDICT.items() if verdict == record.get("label")),
        "",
    )


def f1_per_class(pairs: list[tuple[str, str | None]]) -> dict[str, float]:
    """F1 of each of the four classes, 0.0 when undefined, as the official scorer has it."""

    scores = {}

    for name in CLASSES:

        tp = sum(1 for gold, guess in pairs if gold == name and guess == name)
        fp = sum(1 for gold, guess in pairs if gold != name and guess == name)
        fn = sum(1 for gold, guess in pairs if gold == name and guess != name)

        scores[name] = 2 * tp / (2 * tp + fp + fn) if tp else 0.0

    return scores


def accuracy(pairs: list[tuple[str, str | None]]) -> float | None:

    return sum(1 for gold, guess in pairs if gold == guess) / len(pairs) if pairs else None


def macro_f1(pairs: list[tuple[str, str | None]]) -> float | None:

    return sum(f1_per_class(pairs).values()) / len(CLASSES) if pairs else None


def _interval(pairs, statistic, seed: int, resamples: int) -> dict | None:

    if not pairs:
        return None

    rng = random.Random(seed)

    values = sorted(
        statistic([pairs[rng.randrange(len(pairs))] for _ in pairs])
        for _ in range(resamples)
    )

    return {
        "low": round(values[int(0.025 * resamples)], 4),
        "high": round(values[min(resamples - 1, int(0.975 * resamples))], 4),
    }


def scores(pairs: list[tuple[str, str | None]], seed: int = 20261105, resamples: int = 2000) -> dict:

    return {
        "n": len(pairs),
        "accuracy": accuracy(pairs),
        "accuracyCi": _interval(pairs, accuracy, seed, resamples),
        "macroF1": macro_f1(pairs),
        "macroF1Ci": _interval(pairs, macro_f1, seed, resamples),
        "f1": f1_per_class(pairs),
    }


def confusion(pairs: list[tuple[str, str | None]]) -> dict[str, dict[str, int]]:

    columns = (*CLASSES, None)

    return {
        gold: {str(guess): sum(1 for g, p in pairs if g == gold and p == guess) for guess in columns}
        for gold in CLASSES
    }


def temporal_audit(records: list[dict]) -> dict:
    """
    Whether the rule held in what the model was actually given, read from the
    records and not from the gate's own word: every source of every claim
    against that claim's date. `late` and `factCheck` must both be zero;
    anything else is a bug and the report says so at the top.
    """

    sources = dated = undated = 0
    late: list[dict] = []
    fact_checks: list[dict] = []
    living: list[dict] = []
    without_evidence = 0
    late_in_text: list[dict] = []
    undated_anywhere = 0
    refused_late = refused_undated = refused_living = refused_fact_checks = refused_in_text = 0

    for record in records:

        cutoff = temporal_cutoff(record)

        evidence = record.get("evidence") or []

        if record.get("status") == "ok" and not evidence:
            without_evidence += 1

        own = _comparable(record.get("factCheckUrl"))

        for item in evidence:

            sources += 1

            days = _source_days(item)

            stated = _text_day(item)

            if not days and stated is None:
                undated_anywhere += 1

            if (
                cutoff
                and stated
                and stated >= cutoff
                and not temporal.proved_older(item.get("url") or "", cutoff)
            ):
                late_in_text.append({
                    "id": record.get("id"),
                    "url": item.get("url"),
                    "claimDate": record.get("claimDate"),
                    "statedInText": stated.isoformat(),
                })

            if days:
                dated += 1
            else:
                undated += 1

                # With no date, nothing says this is not the verdict.
                if temporal.looks_like_fact_check(item.get("url") or "", item.get("title")) or (
                    record.get("factCheckUrl")
                    and temporal.site_of(item.get("url") or "") == temporal.site_of(record["factCheckUrl"])
                ):
                    fact_checks.append({"id": record.get("id"), "url": item.get("url")})

            if cutoff and any(day >= cutoff for day in days):
                late.append({"id": record.get("id"), "url": item.get("url"), "claimDate": record.get("claimDate")})

            if own and _comparable(item.get("url")) == own:
                fact_checks.append({"id": record.get("id"), "url": item.get("url")})

            if temporal.is_living(item.get("url") or ""):
                living.append({"id": record.get("id"), "url": item.get("url")})

        for item in record.get("candidates") or []:

            reason = item.get("reason") or ""

            refused_late += reason == temporal.REASON_LATE
            refused_undated += reason == temporal.REASON_UNDATED
            refused_living += reason == temporal.REASON_LIVING
            refused_fact_checks += reason == temporal.REASON_FACT_CHECK
            refused_in_text += reason == temporal.REASON_LATE_IN_TEXT

    return {
        "claims": len(records),
        "sources": sources,
        "datedBeforeTheClaim": dated - len(late),
        "undated": undated,
        "undatedAnywhere": undated_anywhere,
        "late": late,
        "lateInText": late_in_text,
        "factCheckInEvidence": fact_checks,
        "livingInEvidence": living,
        "claimsWithoutEvidence": without_evidence,
        "refusedAsLate": refused_late,
        "refusedAsUndated": refused_undated,
        "refusedAsLiving": refused_living,
        "refusedAsFactCheck": refused_fact_checks,
        "refusedForTheirText": refused_in_text,
        "held": not late and not late_in_text and not fact_checks and not living,
    }


def temporal_cutoff(record: dict) -> date | None:

    try:
        return date.fromisoformat(str(record.get("claimDate"))[:10])
    except ValueError:
        return None


def _source_days(item: dict) -> list[date]:

    days = []

    try:
        if item.get("publishedAt"):
            days.append(date.fromisoformat(str(item["publishedAt"])[:10]))
    except ValueError:
        pass

    in_url = temporal.date_in_url(item.get("url") or "")

    if in_url:
        days.append(in_url)

    return days


def _text_day(item: dict) -> date | None:

    try:
        return date.fromisoformat(str(item.get("latestDateInText"))[:10])
    except ValueError:
        return None


def _comparable(url: str | None) -> str:

    parts = urlsplit(temporal.unarchived(url or "").strip().lower())

    return f"{parts.netloc.removeprefix('www.')}{parts.path.rstrip('/')}"


def evaluate(records: list[dict], rows: int | None = None, seed: int = 20261105, resamples: int = 2000) -> dict:
    """
    The benchmark's numbers for a run, over every record: a claim with no
    usable verdict counts as wrong, as it would in any published accuracy.
    `scored` is the same over the claims the harness scored, the difference
    being what an outage cost.
    """

    every = [(_gold(record), predicted_class(record)) for record in records]

    answered = [
        (gold, guess)
        for (gold, guess), record in zip(every, records)
        if record.get("status") == "ok" and not record.get("searchUnavailable") and not record.get("llmUnreachable")
    ]

    trivial = [(gold, REFUTED) for gold, _ in every]

    predicted = {
        str(name): sum(1 for _, guess in every if guess == name)
        for name in (*CLASSES, None)
    }

    return {
        "rows": rows,
        "records": len(records),
        "complete": rows is not None and len(records) >= rows,
        "all": scores(every, seed, resamples),
        "scored": scores(answered, seed, resamples),
        "alwaysRefuted": {
            "accuracy": accuracy(trivial),
            "macroF1": macro_f1(trivial),
        },
        "predicted": predicted,
        "confusion": confusion(every),
        "temporal": temporal_audit(records),
        "published": list(PUBLISHED),
    }


def _pct(value) -> str:

    return "-" if value is None else f"{value * 100:.1f}%"


def _num(value) -> str:

    return "-" if value is None else f"{value:.3f}"


def _ci(block: dict | None, formatter) -> str:

    return f" [{formatter(block['low'])}, {formatter(block['high'])}]" if block else ""


def render(result: dict) -> list[str]:
    """The report's opening section, before the harness's own."""

    every = result["all"]
    audit = result["temporal"]

    partial = (
        ""
        if result["complete"]
        else f"**Partial: {result['records']} of {result['rows']} claims.** A fixed random sample "
        "(the rows are in hash order), so not comparable with a figure over the whole split.\n\n"
    )

    lines = [
        "## AVeriTeC (the benchmark's own measure)",
        "",
        partial
        + "Four classes; every claim counts, a claim with no verdict as wrong. Labels are the "
        "fact-checkers', reviewed by the dataset's annotators.",
        "",
        "| | Accuracy | Macro-F1 | n |",
        "|---|---:|---:|---:|",
        f"| **This run** | **{_pct(every['accuracy'])}**{_ci(every['accuracyCi'], _pct)} "
        f"| **{_num(every['macroF1'])}**{_ci(every['macroF1Ci'], _num)} | {every['n']} |",
        f"| Over the claims with a working search and model | {_pct(result['scored']['accuracy'])} "
        f"| {_num(result['scored']['macroF1'])} | {result['scored']['n']} |",
        f"| Always answering Refuted | {_pct(result['alwaysRefuted']['accuracy'])} "
        f"| {_num(result['alwaysRefuted']['macroF1'])} | {every['n']} |",
        "",
        "F1 by class: "
        + ", ".join(f"{name} {_num(value)}" for name, value in every["f1"].items())
        + ".",
        "",
        "Confusion (gold rows, predicted columns; `None` is no verdict):",
        "",
        "| gold \\ predicted | " + " | ".join((*CLASSES, "None")) + " |",
        "|---|" + "---:|" * (len(CLASSES) + 1),
        *(
            f"| {gold} | " + " | ".join(str(result["confusion"][gold][str(name)]) for name in (*CLASSES, None)) + " |"
            for gold in CLASSES
        ),
        "",
        "### Nothing from after the claim",
        "",
        (
            "**Held**: no source given to the model is dated on or after its claim, by its address or "
            "its text, none is the claim's own fact-check, none is an undated fact-check, and none is a "
            "reference page as served today."
            if audit["held"]
            else f"**BROKEN**: {len(audit['late'])} sources dated on or after their claim, "
            f"{len(audit['lateInText'])} stating such a date in their text, "
            f"{len(audit['factCheckInEvidence'])} a fact-check with no date, or the claim's own, "
            f"{len(audit['livingInEvidence'])} reference pages as served today. Do not read this run's figures."
        ),
        "",
        "| | |",
        "|---|---:|",
        f"| Sources given to the model | {audit['sources']} |",
        f"| ... with a date before the claim | {audit['datedBeforeTheClaim']} |",
        f"| ... with no date (kept only under `evidence_undated: keep`) | {audit['undated']} |",
        f"| ... with no date anywhere, address or text: nothing shows when these were written | {audit['undatedAnywhere']} |",
        f"| Refused as published on or after the claim | {audit['refusedAsLate']} |",
        f"| Refused for a date in their text on or after the claim | {audit['refusedForTheirText']} |",
        f"| Refused for having no date | {audit['refusedAsUndated']} |",
        f"| Refused as a reference work rewritten since | {audit['refusedAsLiving']} |",
        f"| Refused as an undated fact-check | {audit['refusedAsFactCheck']} |",
        f"| Claims left with no evidence at all | {audit['claimsWithoutEvidence']} |",
        "",
        "Not covered by this audit: a page with no date anywhere, one edited later without a trace, and what the model "
        "itself remembers from training (see a `--closed-book` run).",
        "",
        "### Published on the same split",
        "",
        "ClaimCheck (Putta et al., 2025), Table 1. Compare with systems using the same kind of evidence.",
        "",
        "| System | Accuracy | Evidence |",
        "|---|---:|---|",
        *(
            f"| {row['system']} | {_pct(row['accuracy'])} | {row['evidence']} |"
            for row in result["published"]
        ),
        "",
    ]

    return lines


def submission(records: list[dict]) -> list[dict]:
    """
    A run in the shared task's submission shape, in the official file's order.
    Under `query_plan: questions` the claim's kept questions and their answers
    go in `questions`, as the official scorer reads them; every source's
    passage goes in `string_evidence`, its other input.
    """

    ordered = sorted(records, key=lambda record: record.get("id") or "")

    return [
        {
            "claim_id": record.get("id"),
            "claim": record.get("claim"),
            "pred_label": predicted_class(record) or NOT_ENOUGH,
            "questions": [
                {
                    "question": item["text"],
                    "answers": [{"answer": item.get("answer") or NO_ANSWER, "answer_type": "Extractive"}],
                }
                for item in ((record.get("questionPlan") or {}).get("questions") or [])
                if (record.get("questionPlan") or {}).get("used") and item.get("kept")
            ],
            "string_evidence": [
                text
                for text in (
                    item.get("quote") or item.get("title") or ""
                    for item in record.get("evidence") or []
                )
                if text
            ],
        }
        for record in ordered
    ]

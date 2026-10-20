#!/usr/bin/env python3
"""
What the years between an x-fact claim and today's web search do to a
run: the numbers behind docs/decisions/xfact-comparison.md, "Time
elapsed", read from a harness run's records and nothing else.

    cd backend
    uv run python ../scripts/xfact_time_elapsed.py \
        data/evaluation/runs/xfact_en_es_pilot/llama3.2-3b/<key> \
        data/evaluation/reports/xfact_en_es_pilot/llama3.2-3b/<key>/time_elapsed.json \
        [--links data/evaluation/reports/xfact_en_es_pilot/reference_links.json] \
        [--closed-book data/evaluation/reports/xfact_en_es_pilot/closed_book_llama3.2-3b.json]

Each effect is a split of the scored claims into two groups, with each
group's accuracy and macro-F1 (the harness's own metrics, with its
bootstrap intervals), so "how much does it matter" is read off one table:

- verdict leak: a ranked source is on the row's own fact-checker
  (the harness's `verdictLeak`), and, wider, any fact-checker at all
  (FACT_CHECKERS below, or "fact-check" in the URL path);
- temporal leak: a cited source is newer than the claim (`temporalLeak`;
  only dated claims can be judged);
- drift-prone claims: the claim pins itself to its own present ("now",
  "this year", "hoy", "récord"...), so a correct label then can be wrong
  now (DRIFT_MARKERS);
- link rot (with --links): every reference outside the fact-checker's
  own site is gone;
- the model's memory (with --closed-book): the model gave the gold label
  from the claim alone.

Plus the evidence's age: publication years of what was ranked and cited,
and how much of it postdates the dataset (mid-2021) and the model's
training cutoff (December 2023). And both columns of evaluation.md's
stage attribution for every wrong verdict, from src/evaluation/
attribution.py (here before it existed, kept so the JSON keeps its keys).

Read-only. Standard library plus the harness's metrics.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.evaluation import metrics  # noqa: E402
from src.evaluation.attribution import by_reference, by_trace  # noqa: E402
from src.evaluation.report import load_run  # noqa: E402
from src.evaluation.retrieval import claim_retrieval  # noqa: E402

# X-Fact was released in June 2021 (ACL 2021); its evidence snippets were
# collected before that.
DATASET_BUILT = date(2021, 6, 1)

# llama3.2's pretraining data cutoff, from Meta's model card
# (github.com/meta-llama/llama-models, models/llama3_2/MODEL_CARD.md).
MODEL_CUTOFF = date(2023, 12, 31)

# Fact-checking outlets that publish verdicts in English or Spanish. A
# page from any of them is somebody's answer, not evidence for one.
FACT_CHECKERS = {
    "politifact.com", "chequeado.com", "snopes.com", "factcheck.org",
    "fullfact.org", "maldita.es", "newtral.es", "colombiacheck.com",
    "verificado.com.mx", "leadstories.com", "checkyourfact.com",
    "truthorfiction.com", "boomlive.in", "efeverifica.com", "factual.afp.com",
    "factuel.afp.com", "factcheck.afp.com", "ecuadorchequea.com",
    "bolivianverifica.com", "factchequeado.com", "cotejo.info", "aosfatos.org",
    # A general outlet's fact-check desk, by path; the rest of such outlets
    # are caught by "fact-check" (and its Spanish forms) in the path below.
    "washingtonpost.com/politics/fact-checker",
}

# A claim that dates itself to the moment it was made. Two kinds, both
# whole words or phrases, case-insensitive, matched on the claim text:
#
# - relative time: "now", "this year", "hoy", "los últimos dos años". It
#   can only be resolved against the claim's date, and no Spanish x-fact
#   row has one;
# - records and rankings: "the highest", "de la historia", "por primera
#   vez". True until surpassed, so a label right then can be wrong now.
#
# A heuristic, reported as one: it finds the claims that announce their
# dependence on time, not every claim whose figure has since been revised.
DRIFT_MARKERS = {
    "relativeTime": {
        "en": [
            r"now", r"nowadays", r"currently", r"today", r"this year", r"last year",
            r"next year", r"right now", r"at the moment", r"so far", r"is set to",
            r"in recent years", r"still", r"no longer",
        ],
        "es": [
            r"hoy", r"ahora", r"actualmente", r"en la actualidad", r"actual", r"este año",
            r"el año pasado", r"últimos?", r"últimas?", r"hasta acá", r"hasta ahora",
            r"hasta hoy", r"mes a mes", r"lleva", r"llevamos", r"pasaron", r"tendrá",
            r"desde hace", r"sigue", r"siguen", r"todavía", r"ya no",
        ],
    },
    "recordOrRanking": {
        "en": [
            r"record(?! of)", r"in history", r"ever", r"first time", r"highest", r"lowest",
            r"largest", r"biggest", r"worst", r"best", r"top \w+", r"second only",
            r"more than any", r"second-lowest",
        ],
        "es": [
            r"récord", r"de la historia", r"histórico", r"histórica", r"nunca",
            r"por primera vez", r"más altos?", r"más altas?", r"más bajos?", r"más bajas?",
            r"de los más", r"de las más", r"donde más", r"el más", r"la más",
            r"máximo", r"mínimo", r"piso", r"techo",
        ],
    },
}


def _day(value) -> date | None:

    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def is_fact_checker(url: str, domain: str | None) -> bool:

    domain = (domain or urlsplit(url).hostname or "").lower().removeprefix("www.")
    path = urlsplit(url).path.lower()

    if any(domain == d or domain.endswith("." + d) for d in FACT_CHECKERS if "/" not in d):
        return True

    if any(f"{domain}{path}".startswith(d) for d in FACT_CHECKERS if "/" in d):
        return True

    return any(marker in path for marker in ("fact-check", "factcheck", "fact_check", "verificacion", "chequeo"))


def drift_markers(record: dict) -> dict[str, list[str]]:

    text = record["claim"].lower()

    found = {}

    for kind, by_language in DRIFT_MARKERS.items():
        hits = [
            marker
            for marker in by_language.get(record["language"], [])
            if re.search(rf"(?<!\w){marker}(?!\w)", text)
        ]
        if hits:
            found[kind] = hits

    return found


# The stage attribution's two columns, from the harness's own module
# since it exists (G5, 2026-10-20) - copied here before, they could drift.
attribute = by_trace
attribute_by_reference = by_reference


def block(records: list[dict]) -> dict:
    """n, accuracy and macro-F1 with the harness's intervals."""

    if not records:
        return {"n": 0}

    pairs = [(record["label"], record["verdict"]) for record in records]
    result = metrics.classification(pairs)
    intervals = metrics.bootstrap(pairs)

    return {
        "n": len(records),
        "correct": sum(1 for gold, said in pairs if gold == said),
        "accuracy": result["accuracy"],
        "accuracyCI": intervals.get("accuracy"),
        "macroF1": result["macroF1"],
        "coverage": result["coverage"],
        "ids": [record["id"] for record in records],
    }


def split(records: list[dict], test) -> dict:

    groups = {"yes": [], "no": [], "unknown": []}

    for record in records:
        value = test(record)
        groups["unknown" if value is None else ("yes" if value else "no")].append(record)

    return {name: block(group) for name, group in groups.items()}


def evidence_age(records: list[dict]) -> dict:

    def years(items):
        return Counter(day.year for day in (_day(item.get("publishedAt")) for item in items) if day)

    ranked = [item for record in records for item in record.get("evidence") or []]
    cited = [item for item in ranked if item.get("cited")]

    def shares(items):
        days = [_day(item.get("publishedAt")) for item in items]
        dated = [day for day in days if day]
        return {
            "items": len(items),
            "dated": len(dated),
            "afterDatasetBuilt": sum(1 for day in dated if day > DATASET_BUILT),
            "afterModelCutoff": sum(1 for day in dated if day > MODEL_CUTOFF),
            "medianYear": statistics.median(day.year for day in dated) if dated else None,
            "byYear": dict(sorted(years(items).items())),
        }

    # Dated claims only: how far after the claim its evidence was published.
    gaps, eras = [], Counter()

    for record in records:
        claimed = _day(record.get("claimDate"))
        if claimed is None:
            continue
        for item in record.get("evidence") or []:
            published = _day(item.get("publishedAt"))
            if published is None:
                eras["undated"] += 1
                continue
            gap = (published - claimed).days / 365.25
            gaps.append(gap)
            eras["before claim" if gap < 0 else "within a year after" if gap <= 1 else "more than a year after"] += 1

    return {
        "ranked": shares(ranked),
        "cited": shares(cited),
        "datedClaims": {
            "rankedSources": sum(eras.values()),
            "byEra": dict(eras),
            "medianYearsAfterClaim": round(statistics.median(gaps), 1) if gaps else None,
        },
    }


def main() -> int:

    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("out")
    parser.add_argument("--links")
    parser.add_argument("--closed-book")
    args = parser.parse_args()

    run = load_run(args.run)

    scored = [record for record in run.records if metrics.outcome(record) == metrics.SCORED]

    def any_fact_checker(record, depth="evidence"):
        return any(is_fact_checker(item["url"], item.get("domain")) for item in record.get(depth) or [])

    result = {
        "run": {"key": run.key, "model": run.model, "dataset": run.dataset_stem},
        "outcomes": dict(Counter(metrics.outcome(record) for record in run.records)),
        "scored": block(scored),
        "byLanguage": {
            language: block([record for record in scored if record["language"] == language])
            for language in sorted({record["language"] for record in scored})
        },
        "verdictLeak": split(scored, metrics.verdict_leak),
        "verdictLeakCited": split(scored, lambda r: any(
            item.get("cited") and metrics.on_site(item.get("domain"), r.get("site"))
            for item in r.get("evidence") or []
        )),
        "anyFactCheckerRanked": split(scored, any_fact_checker),
        "anyFactCheckerCandidate": split(scored, lambda r: any_fact_checker(r, "candidates")),
        "factCheckerDomainsRanked": dict(Counter(
            (item.get("domain") or "")
            for record in scored for item in record.get("evidence") or []
            if is_fact_checker(item["url"], item.get("domain"))
        )),
        "temporalLeak": split(scored, metrics.temporal_leak),
        "newerUncitedRanked": sum(metrics.newer_uncited(record) for record in scored),
        "driftProne": split(scored, lambda r: bool(drift_markers(r))),
        "driftRelativeTime": split(scored, lambda r: "relativeTime" in drift_markers(r)),
        "driftRecordOrRanking": split(scored, lambda r: "recordOrRanking" in drift_markers(r)),
        "driftMarkers": {
            record["id"]: drift_markers(record) for record in scored if drift_markers(record)
        },
        "evidenceAge": evidence_age(scored),
        # evaluation.md §Stage attribution, both columns (attribution.py):
        # aggregation first, then the first of retrieval, ranking,
        # reasoning, aggregation that explains a wrong verdict.
        "attributionTraceOnly": dict(Counter(
            attribute(record) for record in scored if record["verdict"] != record["label"]
        )),
        "attributionTraceOnlyIds": {
            stage: [r["id"] for r in scored if r["verdict"] != r["label"] and attribute(r) == stage]
            for stage in ("retrieval", "ranking", "reasoning", "aggregation")
        },
        "attributionByReference": dict(Counter(
            str(attribute_by_reference(record)) for record in scored if record["verdict"] != record["label"]
        )),
        "explanationNamesFactChecker": [
            record["id"] for record in scored
            if re.search(r"politifact|chequeado|pants on fire|fact[- ]?check", (record.get("explanation") or "").lower())
        ],
    }

    if args.links:
        links = json.loads(Path(args.links).read_text(encoding="utf-8"))["links"]
        lost = {"unreachable", "dead", "redirected_home", "server_error"}
        per_claim: dict[str, list[str]] = {}
        for link in links:
            if link["ownSite"]:
                continue
            for claim in link["claimIds"]:
                per_claim.setdefault(claim, []).append(link["outcome"])

        def all_lost(record):
            outcomes = [o for o in per_claim.get(record["id"], []) if o != "social"]
            if not outcomes:
                return None
            return all(o in lost for o in outcomes)

        result["referencesAllLost"] = split(scored, all_lost)

    if args.closed_book:
        book = {row["id"]: row for row in json.loads(Path(args.closed_book).read_text(encoding="utf-8"))["claims"]}

        def remembered(record):
            row = book.get(record["id"])
            return None if row is None or row.get("status") == "unreachable" else row.get("verdict") == record["label"]

        result["closedBookRight"] = split(scored, remembered)
        result["closedBookRecallsFactCheck"] = split(
            scored, lambda r: None if r["id"] not in book else bool(book[r["id"]].get("recallsFactCheck"))
        )
        result["closedBookAgreesWithPipeline"] = sum(
            1 for record in scored if record["id"] in book and book[record["id"]].get("verdict") == record["verdict"]
        )

        # The pipeline (B) against the same model without evidence (A),
        # paired over the claims both answered: what the evidence bought.
        both = [
            record for record in scored
            if record["id"] in book and book[record["id"]].get("status") != "unreachable"
        ]
        closed = [(record["label"], book[record["id"]]["verdict"]) for record in both]
        piped = [(record["label"], record["verdict"]) for record in both]
        paired = metrics.paired_bootstrap(closed, piped)
        result["pipelineMinusClosedBook"] = {
            "n": len(both),
            "accuracy": paired.get("accuracy"),
            "macroF1": paired.get("macroF1"),
            **metrics.discordant(closed, piped),
        }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    def line(name, groups):
        cells = []
        for group in ("yes", "no", "unknown"):
            b = groups[group]
            if b["n"]:
                cells.append(f"{group}: n={b['n']} acc={b['accuracy']:.3f} F1={b['macroF1']:.3f}")
        print(f"{name:<28} " + " | ".join(cells))

    print(f"scored n={result['scored']['n']} acc={result['scored']['accuracy']:.3f} F1={result['scored']['macroF1']:.3f}")
    for name in ("verdictLeak", "verdictLeakCited", "anyFactCheckerRanked", "anyFactCheckerCandidate",
                 "temporalLeak", "driftProne", "driftRelativeTime", "driftRecordOrRanking", "referencesAllLost", "closedBookRight", "closedBookRecallsFactCheck"):
        if name in result:
            line(name, result[name])
    print("attribution (trace only):", result["attributionTraceOnly"])
    print("attribution (by reference; None = no reference):", result["attributionByReference"])
    print(json.dumps(result["evidenceAge"], indent=1))

    return 0


if __name__ == "__main__":
    sys.exit(main())

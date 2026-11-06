"""
Troubleshooting the fact-checker part by part, against Claude's own checks.

The 4 Nov comparison (docs/troubleshooting/fact-checking/README.md) checked
20 train claims by hand, blind, and then compared each part of the pipeline
with what Claude did at the same point: what it looked for, the queries it
typed, the source that settled it, where that source was cut, and which
stance decided the verdict. This module makes that protocol repeatable on
any 20 train claims, one part at a time, with an agent (`claude -p`) doing
Claude's side and the analysis, and this script doing everything that can
be counted.

The split between the two is the point. The agent writes its plan and its
searches **before** it can see a label or a pipeline record: the script
gives it only `claims.jsonl`, and `.claude/hooks/troubleshoot_blind.py`
refuses the run records, the labels and the comparison files while
TROUBLESHOOT_PHASE is `plan` or `search`. Every number in an experiment's
write-up - coverage, candidates, cuts, verdicts - is computed here, from the
files on disk, and written by this script into the experiment file's
"Measured" section. The agent writes only the interpretation and the
proposal, and it cannot edit the measured files (the same hook). So a
claim the agent makes about a number can be checked against a file it did
not write.

    uv run python -m src.evaluation.troubleshoot prepare --batch 20261105-next20
    uv run python -m src.evaluation.troubleshoot agent --batch 20261105-next20 --stage 01
    uv run python -m src.evaluation.troubleshoot status --batch 20261105-next20

`../scripts/troubleshoot.sh` wraps the same commands from the repo root.

Train half only: the claims come from a train run's records
(DEFAULT_EVIDENCE_RUN covers all 69), never from the label files, so the
sealed test half is never read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ----------------------------------------------------------------------
# Where things are
# ----------------------------------------------------------------------

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent

RUNS = BACKEND / "data/evaluation/runs/manual-train/llama3.2-3b-bench"

# The searched train run of 29 Oct whose evidence every replay uses: its
# queries, candidates and cuts (stages 02-04). All 69 train claims.
DEFAULT_EVIDENCE_RUN = RUNS / "cc053417c0cb"

# Today's defaults replayed on that evidence (4 Nov): the stances and
# verdicts as the pipeline now gives them (stage 05). Its seconds were
# measured under CPU contention; nothing here reads them.
DEFAULT_REPLAY_RUN = RUNS / "1d07e163a659"

EXPERIMENTS = BACKEND / "data/evaluation/experiments/troubleshooting/fact-checking"
DOCS = REPO / "docs/troubleshooting/fact-checking"

# The first 20 train claims were the 4 Nov comparison
# (experiments/claude-search/); a new batch starts after them by default.
DEFAULT_OFFSET = 20
DEFAULT_LIMIT = 20

# One part of the pipeline each, upstream first; `needs` is which of
# Claude's blind files the comparison reads.
STAGES = {
    "01": {"slug": "what-to-look-for", "title": "Knowing what to look for", "needs": ("plan",)},
    "02": {"slug": "queries", "title": "Query planning", "needs": ("plan",)},
    "03": {"slug": "search-results", "title": "Search results", "needs": ("plan", "search")},
    "04": {"slug": "ranking", "title": "Ranking", "needs": ("plan", "search")},
    "05": {"slug": "verification", "title": "Verification", "needs": ("plan", "search")},
}

CLAIMS = "claims.jsonl"
PLAN = "plan.jsonl"
SEARCH = "claude.jsonl"

PLAN_FIELDS = ("id", "lookingFor", "decisive", "wouldSettleIt", "sourceType", "queries")
SEARCH_FIELDS = ("id", "searches", "found", "verdict", "sources", "settlingSource")

VERDICTS = {"TRUE", "FALSE", "PARTIALLY_TRUE", "UNVERIFIED"}

VOTING = {"supports", "contradicts"}

# The tools each agent phase may use, comma-separated (a rule like
# `Bash(git diff:*)` holds a space). No shell or Grep while blind: either
# reads anything. The hook narrows Read/Write further (troubleshoot_blind.py).
PHASE_TOOLS = {
    "plan": "Read,Write,Glob,Skill",
    "search": "Read,Write,Glob,Skill,WebSearch,WebFetch",
    "analyse": "Read,Write,Edit,Glob,Grep,Skill,Bash(git diff:*),Bash(git status:*)",
    "implement": (
        "Read,Write,Edit,Glob,Grep,Skill,Bash(git diff:*),Bash(git status:*),"
        "Bash(uv run pytest:*),Bash(./scripts/check.sh fast),Bash(../scripts/check.sh fast)"
    ),
}


class TroubleshootError(RuntimeError):
    """A step asked for out of order, or a file that does not hold what it must."""


# ----------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:

    if not path.exists():
        return []

    rows = []

    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError as error:
                raise TroubleshootError(f"{path}:{number}: not JSON ({error})") from error

    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_json(path: Path, value) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def latest(path: Path) -> dict[str, dict]:
    """The last record per claim id, as runner.latest_records reads a run."""

    records: dict[str, dict] = {}

    for record in read_jsonl(path):
        records[record["id"]] = record

    return records


def stage_key(stage: str) -> str:

    key = stage.zfill(2)[:2]

    if key not in STAGES:
        raise TroubleshootError(f"no stage {stage!r} ({', '.join(f'{k} {v['slug']}' for k, v in STAGES.items())})")

    return key


def stage_dir(batch_dir: Path, stage: str) -> Path:

    key = stage_key(stage)

    return batch_dir / f"{key}-{STAGES[key]['slug']}"


def experiment_doc(batch: str, stage: str) -> Path:

    key = stage_key(stage)

    return DOCS / "experiments" / f"{key}-{STAGES[key]['slug']}" / f"{batch}.md"


def domain(url: str) -> str:

    host = (urlparse(url or "").hostname or "").lower()

    return host[4:] if host.startswith("www.") else host


def now() -> str:

    return datetime.now().astimezone().isoformat(timespec="seconds")


# ----------------------------------------------------------------------
# Does a text carry a detail?
# ----------------------------------------------------------------------

DIGITS = re.compile(r"\d+(?:[.,]\d+)*")


def _fold(text: str) -> str:

    from src.services.fact_checker.terms import fold

    return fold(text or "")


def _numbers(text: str) -> set[str]:
    """Every figure in the text, separators dropped: 138,000 and 138.000 are 138000."""

    return {re.sub(r"[.,]", "", match) for match in DIGITS.findall(text or "")}


def carries(text: str, detail: str) -> bool:
    """
    Whether `text` carries `detail`, one of the decisive details Claude named.

    Approximate on purpose, and the same rule for every plan, so the
    comparison is fair even where it is wrong:
    - a detail with a figure is carried when every figure in it is in the
      text ("0.001%" by "0.001 per cent", "138,000" by "138000");
    - otherwise every word of it longer than two letters must start a word
      of the text, folded ("sea ice" by "Sea-ice", "dengue" by "Dengue").
    """

    if not detail or not detail.strip():
        return False

    figures = _numbers(detail)

    if figures:
        return figures <= _numbers(text)

    words = [word for word in re.findall(r"[^\W_]+", _fold(detail)) if len(word) > 2]

    if not words:
        return _fold(detail).strip() in _fold(text)

    haystack = re.findall(r"[^\W_]+", _fold(text))

    return all(any(token.startswith(word) for token in haystack) for word in words)


def coverage(text: str, details: list[str]) -> dict:

    carried = [detail for detail in details if carries(text, detail)]

    return {
        "carried": carried,
        "missing": [detail for detail in details if detail not in carried],
        "share": round(len(carried) / len(details), 3) if details else None,
    }


# ----------------------------------------------------------------------
# prepare: the blind claims
# ----------------------------------------------------------------------

def blind_row(record: dict, headline: str) -> dict:
    """
    What Claude may see of a claim: the 4 Nov protocol's fields, plus the
    article's headline (the app has it; the harness has it since 4 Nov).
    No label, no reference links, no queries, no evidence.
    """

    return {
        "id": record["id"],
        "language": record.get("language"),
        "claimDate": record.get("claimDate"),
        "articleUrl": record.get("articleUrl"),
        "excludeSite": domain(record.get("articleUrl") or ""),
        "headline": headline,
        "claim": record["claim"],
    }


def cmd_prepare(args) -> int:

    batch_dir = EXPERIMENTS / args.batch

    if (batch_dir / CLAIMS).exists() and not args.force:
        raise TroubleshootError(f"{batch_dir / CLAIMS} exists; a batch's claims are fixed once prepared (--force replaces them)")

    run = Path(args.evidence_run)
    records = list(latest(run / "results.jsonl").values())

    if not records:
        raise TroubleshootError(f"no records in {run}")

    if any(record.get("dataset") and "test" in str(record.get("dataset")) for record in records):
        raise TroubleshootError(f"{run} is not a train run")

    if args.ids:
        wanted = [claim_id.strip() for claim_id in args.ids.split(",") if claim_id.strip()]
        by_id = {record["id"]: record for record in records}
        missing = [claim_id for claim_id in wanted if claim_id not in by_id]
        if missing:
            raise TroubleshootError(f"not in {run.name}: {', '.join(missing)}")
        chosen = [by_id[claim_id] for claim_id in wanted]
    else:
        chosen = records[args.offset: args.offset + args.limit]

    if not chosen:
        raise TroubleshootError(f"no claims at offset {args.offset} of {len(records)}")

    from src.evaluation.dataset import _article_key, article_titles
    from src.services.fact_checker.retrieval.checkable import headline_of

    titles = article_titles()

    rows = []

    for record in chosen:
        article = titles.get(_article_key(record.get("articleUrl") or "")) if record.get("articleUrl") else None
        rows.append(blind_row(record, headline_of(article["title"]) if article else ""))

    write_jsonl(batch_dir / CLAIMS, rows)

    write_json(batch_dir / "batch.json", {
        "batch": args.batch,
        "createdAt": now(),
        "evidenceRun": str(run.relative_to(BACKEND)) if run.is_relative_to(BACKEND) else str(run),
        "replayRun": str(Path(args.replay_run).relative_to(BACKEND)) if Path(args.replay_run).is_relative_to(BACKEND) else args.replay_run,
        "selection": {"ids": [row["id"] for row in rows]} if args.ids else {"offset": args.offset, "limit": args.limit},
        "ids": [row["id"] for row in rows],
    })

    print(f"{len(rows)} claims -> {batch_dir / CLAIMS}")
    print(", ".join(row["id"] for row in rows))

    return 0


def batch_info(batch_dir: Path) -> dict:

    path = batch_dir / "batch.json"

    if not path.exists():
        raise TroubleshootError(f"no batch at {batch_dir} (prepare it first)")

    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# Checking Claude's blind files
# ----------------------------------------------------------------------

def validate(batch_dir: Path, which: str) -> list[str]:
    """What is wrong with plan.jsonl or claude.jsonl; empty when it is whole."""

    ids = [row["id"] for row in read_jsonl(batch_dir / CLAIMS)]
    name, fields = (PLAN, PLAN_FIELDS) if which == "plan" else (SEARCH, SEARCH_FIELDS)
    path = batch_dir / name

    if not path.exists():
        return [f"{name} is missing"]

    problems = []

    try:
        rows = read_jsonl(path)
    except TroubleshootError as error:
        return [str(error)]

    by_id = {row.get("id"): row for row in rows}

    for claim_id in ids:
        row = by_id.get(claim_id)
        if row is None:
            problems.append(f"{claim_id}: no row in {name}")
            continue
        for field in fields:
            if field not in row:
                problems.append(f"{claim_id}: no `{field}`")
        if which == "plan" and not isinstance(row.get("decisive"), list):
            problems.append(f"{claim_id}: `decisive` must be a list of the details")
        if which == "search" and row.get("verdict") not in VERDICTS:
            problems.append(f"{claim_id}: verdict {row.get('verdict')!r} is not one of {sorted(VERDICTS)}")

    extra = set(by_id) - set(ids)

    if extra:
        problems.append(f"rows for claims not in the batch: {', '.join(sorted(map(str, extra)))}")

    return problems


# ----------------------------------------------------------------------
# pipeline: what the pipeline did at this stage, for the batch's claims
# ----------------------------------------------------------------------

def _thresholds(path: str | None):

    from src.evaluation.cli import load_thresholds

    return load_thresholds(path)


def _entities(texts: list[str]) -> tuple[dict[str, dict], str]:
    """
    The claims' entities, from inference/ when it answers. The runs do not
    record them, and without them checkable_point still finds multi-word
    names and acronyms itself; the file says which it was.
    """

    try:
        from src.processors.nlp.entities import EntityExtractor

        extractor = EntityExtractor()
        return {text: extractor.process(text) for text in texts}, "inference"
    except Exception as error:  # inference/ down: say so, plan without
        return {text: {} for text in texts}, f"none ({type(error).__name__}: inference/ not reachable)"


def plan_for(claim, context, language: str | None, thresholds) -> list:
    """
    The queries the retriever would plan, offline: the same call as
    EvidenceRetriever's `search_provider.plan(...)`. A new planning
    threshold must be passed here too, or the offline measure will not see it.
    """

    from src.services.fact_checker.retrieval.query_builder import plan_for_thresholds

    return plan_for_thresholds(claim, context, language, thresholds)


def offline_plans(claims: list[dict], thresholds_path: str | None) -> list[dict]:
    """
    Stages 01 and 02 without a search: the checkable point and both query
    plans, from the code as it is now, for each claim. `claim_restatement`
    (a model call) is not applied here, and the row says so.
    """

    from src.models.core.claim import Claim
    from src.services.fact_checker.claim_selector import ArticleContext
    from src.services.fact_checker.retrieval.checkable import point_for_thresholds
    from src.evaluation.dataset import _article_key, article_titles

    thresholds = _thresholds(thresholds_path)
    titles = article_titles()
    entities, source = _entities([row["claim"] for row in claims])

    rows = []

    for row in claims:
        claim = Claim(text=row["claim"], entities=entities.get(row["claim"]) or {}, confidence=1.0)
        article = titles.get(_article_key(row.get("articleUrl") or "")) if row.get("articleUrl") else None
        sentences = [s for s in (article or {}).get("sentences", []) if s.strip() != row["claim"].strip()]
        context = ArticleContext(
            url=row.get("articleUrl") or "", title="", lead="", keywords=[], entities={},
            search_title=(article or {}).get("title", ""), search_sentences=sentences,
        )
        language = row.get("language")

        plans = {}
        for style in ("sentence", "checkable"):
            plan_thresholds = thresholds.model_copy(update={"query_plan": style})
            plans[style] = [{"kind": q.kind.value, "text": q.text} for q in plan_for(claim, context, language, plan_thresholds)]

        rows.append({
            "id": row["id"],
            "checkablePoint": point_for_thresholds(claim, context, language, thresholds).as_dict(),
            "plans": plans,
            "planInUse": thresholds.query_plan,
            "entities": claim.entities,
            "entitiesFrom": source,
            "restatement": thresholds.claim_restatement,
            "note": "offline: no search, no restatement model call" if thresholds.claim_restatement != "off" else "offline: no search",
        })

    return rows


def recorded(claims: list[dict], run: Path, replay: Path) -> list[dict]:
    """Stages 02-05 as the recorded runs did them: queries, candidates, kept evidence, stances, verdict."""

    searched = latest(run / "results.jsonl")
    replayed = latest(replay / "results.jsonl") if replay and (replay / "results.jsonl").exists() else {}

    rows = []

    for row in claims:
        record = searched.get(row["id"]) or {}
        now_record = replayed.get(row["id"]) or {}
        rows.append({
            "id": row["id"],
            "queries": record.get("queries") or [],
            "candidates": [
                {key: candidate.get(key) for key in ("url", "domain", "title", "origin", "stoppedAt", "reason", "score")}
                for candidate in record.get("candidates") or []
            ],
            "evidenceSearched": [_evidence(item) for item in record.get("evidence") or []],
            "evidenceNow": [_evidence(item) for item in now_record.get("evidence") or []],
            "verdictSearched": record.get("verdict"),
            "verdictNow": now_record.get("verdict"),
            "rawVerdictNow": now_record.get("rawVerdict"),
            "searchUnavailable": record.get("searchUnavailable"),
        })

    return rows


def _evidence(item: dict) -> dict:

    return {key: item.get(key) for key in (
        "url", "domain", "title", "stance", "cited", "quote", "relevance", "pertinence", "foundBy",
    )}


def gold(claims: list[dict], run: Path) -> dict[str, dict]:
    """The label and the reference links, from the train run's own records (never the label files)."""

    records = latest(run / "results.jsonl")

    return {
        row["id"]: {
            "label": (records.get(row["id"]) or {}).get("label"),
            "origin": (records.get(row["id"]) or {}).get("origin"),
            "referenceDomains": sorted({domain(url) for url in (records.get(row["id"]) or {}).get("referenceEvidenceLinks") or [] if url.startswith("http")}),
        }
        for row in claims
    }


def cmd_pipeline(args) -> int:

    batch_dir = EXPERIMENTS / args.batch
    info = batch_info(batch_dir)
    out = Path(args.out) if getattr(args, "out", None) else stage_dir(batch_dir, args.stage)
    label = args.label or "before"

    claims = read_jsonl(batch_dir / CLAIMS)

    # A loop round's own runs (03-05) in place of the recorded ones.
    run = Path(args.run) if getattr(args, "run", None) else BACKEND / info["evidenceRun"]
    replay = Path(args.replay) if getattr(args, "replay", None) else BACKEND / info["replayRun"]

    rows = recorded(claims, run, replay)
    offline = {row["id"]: row for row in offline_plans(claims, args.thresholds)}

    for row in rows:
        row["offline"] = offline[row["id"]]

    write_jsonl(out / f"pipeline-{label}.jsonl", rows)

    write_json(out / f"pipeline-{label}.json", {
        "label": label, "at": now(), "thresholds": args.thresholds,
        "thresholdsOverrides": json.loads(Path(args.thresholds).read_text(encoding="utf-8")) if args.thresholds else {},
        "gitCommit": _git("rev-parse", "--short", "HEAD"), "dirty": bool(_git("status", "--porcelain", "--", "backend/src")),
        "run": str(run), "replay": str(replay),
    })

    print(f"pipeline ({label}) -> {out / f'pipeline-{label}.jsonl'}")

    return 0


def _git(*arguments: str) -> str:

    try:
        return subprocess.run(["git", *arguments], cwd=REPO, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ----------------------------------------------------------------------
# join: the comparison and its numbers, per stage
# ----------------------------------------------------------------------

def _query_text(queries: list) -> str:

    return " ".join(q.get("text", "") if isinstance(q, dict) else str(q) for q in queries)


def _point_text(point: dict) -> str:

    parts = []

    for value in point.values():
        parts += value if isinstance(value, list) else [str(value or "")]

    return " ".join(parts)


def compare(stage: str, claims: list[dict], plan: dict, search: dict, pipeline: dict, labels: dict) -> list[dict]:
    """One row per claim: Claude's side, the pipeline's side, and what was counted."""

    key = stage_key(stage)
    rows = []

    for claim in claims:
        claim_id = claim["id"]
        mine = plan.get(claim_id, {})
        found = search.get(claim_id, {})
        pipe = pipeline.get(claim_id, {})
        offline = pipe.get("offline", {})
        details = [str(detail) for detail in mine.get("decisive") or []]

        row = {
            "id": claim_id, "language": claim.get("language"), "claim": claim["claim"],
            "gold": labels.get(claim_id, {}).get("label"), "origin": labels.get(claim_id, {}).get("origin"),
            "claude": {"lookingFor": mine.get("lookingFor"), "decisive": details, "sourceType": mine.get("sourceType"), "queries": mine.get("queries")},
        }

        if key == "01":
            point = offline.get("checkablePoint") or {}
            row["pipeline"] = {"checkablePoint": point, "sentencePlanQueries": [q["text"] for q in offline.get("plans", {}).get("sentence", [])]}
            row["counted"] = {
                "checkablePoint": coverage(_point_text(point), details),
                "sentencePlan": coverage(_query_text(offline.get("plans", {}).get("sentence", [])), details),
                "pipelineNamesSourceType": False,
            }

        elif key == "02":
            plans = {"recorded": pipe.get("queries") or [], **offline.get("plans", {})}
            row["pipeline"] = {name: [q.get("text") if isinstance(q, dict) else q for q in queries] for name, queries in plans.items()}
            row["counted"] = {name: coverage(_query_text(queries), details) for name, queries in plans.items()}
            row["counted"]["claude"] = coverage(" ".join(mine.get("queries") or []), details)

        else:
            settling = [domain(url) for url in ([found.get("settlingSource")] if found.get("settlingSource") else []) + (found.get("sources") or []) if url]
            settling = list(dict.fromkeys(settling))
            candidates = pipe.get("candidates") or []
            candidate_domains = [c.get("domain") or domain(c.get("url") or "") for c in candidates]
            row["claude"].update({"verdict": found.get("verdict"), "found": found.get("found"), "settlingDomains": settling})

            if key == "03":
                reference = labels.get(claim_id, {}).get("referenceDomains") or []
                row["pipeline"] = {"queries": [q.get("text") for q in pipe.get("queries") or []], "candidateDomains": candidate_domains}
                row["counted"] = {
                    "candidates": len(candidates),
                    "settlingInCandidates": [d for d in settling if d in candidate_domains],
                    "referenceInCandidates": [d for d in reference if d in candidate_domains],
                    "referenceDomains": reference,
                    "searchUnavailable": pipe.get("searchUnavailable"),
                }

            elif key == "04":
                fates = []
                for candidate in candidates:
                    d = candidate.get("domain") or domain(candidate.get("url") or "")
                    if d in settling:
                        fates.append({"domain": d, "url": candidate.get("url"), "stoppedAt": candidate.get("stoppedAt"), "reason": candidate.get("reason"), "score": candidate.get("score")})
                kept = pipe.get("evidenceNow") or pipe.get("evidenceSearched") or []
                row["pipeline"] = {"kept": [[e.get("domain"), e.get("stance"), e.get("relevance"), e.get("pertinence")] for e in kept], "settlingFates": fates}
                row["counted"] = {
                    "candidates": len(candidates),
                    "kept": len(kept),
                    "keptSilent": sum(1 for e in kept if e.get("stance") not in VOTING),
                    "settlingKept": any(f.get("stoppedAt") == "ranked" for f in fates),
                    "settlingCut": [f.get("reason") for f in fates if f.get("stoppedAt") != "ranked"],
                }

            else:  # 05
                kept = pipe.get("evidenceNow") or []
                votes = [e for e in kept if e.get("stance") in VOTING]
                off_point = [
                    {"domain": e.get("domain"), "stance": e.get("stance"), "quote": e.get("quote")}
                    for e in votes if details and not any(carries(e.get("quote") or "", d) for d in details)
                ]
                row["pipeline"] = {
                    "verdict": pipe.get("verdictNow"), "rawVerdict": pipe.get("rawVerdictNow"),
                    "stances": [[e.get("domain"), e.get("stance"), e.get("quote")] for e in kept],
                }
                row["counted"] = {
                    "pipelineRight": pipe.get("verdictNow") == row["gold"],
                    "claudeRight": found.get("verdict") == row["gold"],
                    "votes": len(votes),
                    "silent": len(kept) - len(votes),
                    "votesWithoutDecisiveDetail": off_point,
                    "decidedOffPoint": bool(votes) and len(off_point) == len(votes),
                }

        rows.append(row)

    return rows


def summarise(stage: str, rows: list[dict]) -> dict:
    """The stage's headline numbers, from the comparison rows alone."""

    key = stage_key(stage)
    n = len(rows)

    def share(values: list) -> float | None:
        values = [v for v in values if v is not None]
        return round(sum(values) / len(values), 3) if values else None

    if key == "01":
        return {
            "claims": n,
            "decisiveDetails": sum(len(r["claude"]["decisive"]) for r in rows),
            "checkablePointCoverage": share([r["counted"]["checkablePoint"]["share"] for r in rows]),
            "checkablePointAllCarried": sum(1 for r in rows if r["counted"]["checkablePoint"]["missing"] == [] and r["claude"]["decisive"]),
            "sentencePlanCoverage": share([r["counted"]["sentencePlan"]["share"] for r in rows]),
            "claudeNamedSourceType": sum(1 for r in rows if r["claude"].get("sourceType")),
        }

    if key == "02":
        names = sorted({name for r in rows for name in r["counted"]})
        return {"claims": n, **{f"{name}Coverage": share([r["counted"][name]["share"] for r in rows]) for name in names},
                **{f"{name}AllCarried": sum(1 for r in rows if r["counted"][name]["missing"] == [] and r["claude"]["decisive"]) for name in names}}

    if key == "03":
        return {
            "claims": n,
            "settlingDomainInCandidates": sum(1 for r in rows if r["counted"]["settlingInCandidates"]),
            "referenceDomainInCandidates": sum(1 for r in rows if r["counted"]["referenceInCandidates"]),
            "searchUnavailable": sum(1 for r in rows if r["counted"]["searchUnavailable"]),
            "medianCandidates": sorted(r["counted"]["candidates"] for r in rows)[n // 2] if n else None,
        }

    if key == "04":
        with_settling = [r for r in rows if r["pipeline"]["settlingFates"]]
        return {
            "claims": n,
            "settlingAmongCandidates": len(with_settling),
            "settlingKept": sum(1 for r in with_settling if r["counted"]["settlingKept"]),
            "settlingCut": sum(1 for r in with_settling if not r["counted"]["settlingKept"]),
            "keptSources": sum(r["counted"]["kept"] for r in rows),
            "keptSilent": sum(r["counted"]["keptSilent"] for r in rows),
        }

    return {
        "claims": n,
        "pipelineRight": sum(1 for r in rows if r["counted"]["pipelineRight"]),
        "claudeRight": sum(1 for r in rows if r["counted"]["claudeRight"]),
        "pipelineWrong": sum(1 for r in rows if not r["counted"]["pipelineRight"]),
        "wrongAndDecidedOffPoint": sum(1 for r in rows if not r["counted"]["pipelineRight"] and r["counted"]["decidedOffPoint"]),
        "claudeAgreesWithGoldPipelineNot": sum(1 for r in rows if r["counted"]["claudeRight"] and not r["counted"]["pipelineRight"]),
    }


def cmd_join(args) -> int:

    batch_dir = EXPERIMENTS / args.batch
    info = batch_info(batch_dir)
    key = stage_key(args.stage)
    out = Path(args.out) if getattr(args, "out", None) else stage_dir(batch_dir, key)
    label = args.label or "before"

    for need in STAGES[key]["needs"]:
        problems = validate(batch_dir, need)
        if problems:
            raise TroubleshootError(f"Claude's {need} file is not complete:\n  " + "\n  ".join(problems))

    pipeline_path = out / f"pipeline-{label}.jsonl"

    if not pipeline_path.exists():
        raise TroubleshootError(f"{pipeline_path} is missing (run `pipeline --stage {key}` first)")

    claims = read_jsonl(batch_dir / CLAIMS)
    plan = {row["id"]: row for row in read_jsonl(batch_dir / PLAN)}
    search = {row["id"]: row for row in read_jsonl(batch_dir / SEARCH)}
    pipeline = {row["id"]: row for row in read_jsonl(pipeline_path)}
    labels = gold(claims, BACKEND / info["evidenceRun"])

    rows = compare(key, claims, plan, search, pipeline, labels)
    metrics = summarise(key, rows)

    write_json(out / f"comparison-{label}.json", rows)
    write_json(out / f"metrics-{label}.json", {"stage": key, "label": label, "at": now(), **metrics})

    print(json.dumps(metrics, ensure_ascii=False, indent=1))

    return 0


# ----------------------------------------------------------------------
# The experiment file: measured by this script, read by the agent
# ----------------------------------------------------------------------

MEASURED_START = "<!-- measured:start (written by src/evaluation/troubleshoot.py; do not edit) -->"
MEASURED_END = "<!-- measured:end -->"


def measured_section(out: Path, key: str, notes: list[str] | None = None) -> str:

    lines = ["## Measured", ""] + (notes or [])

    labels = sorted((path.stem.removeprefix("metrics-") for path in out.glob("metrics-*.json")), key=lambda label: (label != "before", label))
    metrics = {label: json.loads((out / f"metrics-{label}.json").read_text(encoding="utf-8")) for label in labels}

    if not metrics:
        return "\n".join(lines + ["Nothing measured yet.", ""])

    names = [name for name in next(iter(metrics.values())) if name not in ("stage", "label", "at")]

    lines += ["| | " + " | ".join(labels) + " |", "|---|" + "---:|" * len(labels)]

    for name in names:
        lines.append(f"| {name} | " + " | ".join(str(metrics[label].get(name, "")) for label in labels) + " |")

    lines += ["", f"Files: `{out.relative_to(REPO)}/` (`comparison-<label>.json` per claim, `pipeline-<label>.json` the code and thresholds measured).", ""]

    comparison = out / "comparison-before.json"

    if comparison.exists():
        lines += ["### Per claim (before)", ""]
        lines += per_claim_table(key, json.loads(comparison.read_text(encoding="utf-8")))

    return "\n".join(lines)


def per_claim_table(key: str, rows: list[dict]) -> list[str]:

    def cell(value) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")[:160]

    if key in ("01", "02"):
        head = "| Claim | Gold | Claude's decisive details | Missing from the checkable point | Missing from the sentence plan |" if key == "01" else \
               "| Claim | Gold | Claude's decisive details | Missing: recorded queries | Missing: checkable plan |"
        lines = [head, "|---|---|---|---|---|"]
        for r in rows:
            c = r["counted"]
            first, second = (c["checkablePoint"], c["sentencePlan"]) if key == "01" else (c["recorded"], c.get("checkable", {}))
            lines.append(f"| {r['id']} | {r['gold']} | {cell(', '.join(r['claude']['decisive']))} | {cell(', '.join(first.get('missing', [])))} | {cell(', '.join(second.get('missing', [])))} |")
        return lines + [""]

    if key == "03":
        lines = ["| Claim | Gold | Claude | Claude's settling domains | Among the candidates | Reference among them |", "|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['gold']} | {r['claude'].get('verdict')} | {cell(', '.join(r['claude']['settlingDomains']))} | {cell(', '.join(r['counted']['settlingInCandidates']) or '-')} | {cell(', '.join(r['counted']['referenceInCandidates']) or '-')} |")
        return lines + [""]

    if key == "04":
        lines = ["| Claim | Settling source among candidates | Kept | Cut because | Kept and silent |", "|---|---|---|---|---|"]
        for r in rows:
            fates = r["pipeline"]["settlingFates"]
            lines.append(f"| {r['id']} | {'yes' if fates else 'no'} | {'yes' if r['counted']['settlingKept'] else '-'} | {cell('; '.join(str(x) for x in r['counted']['settlingCut']) or '-')} | {r['counted']['keptSilent']} of {r['counted']['kept']} |")
        return lines + [""]

    lines = ["| Claim | Gold | Claude | Pipeline | Votes | Votes without a decisive detail |", "|---|---|---|---|---:|---|"]
    for r in rows:
        off = r["counted"]["votesWithoutDecisiveDetail"]
        lines.append(f"| {r['id']} | {r['gold']} | {r['claude'].get('verdict')} | {r['pipeline']['verdict']} | {r['counted']['votes']} | {cell(', '.join(f'{o['domain']} ({o['stance']})' for o in off) or '-')} |")
    return lines + [""]


def write_experiment(batch: str, key: str, out: Path | None = None, path: Path | None = None,
                     notes: list[str] | None = None, title: str | None = None) -> Path:
    """Create the experiment file, or refresh only its measured section."""

    path = path or experiment_doc(batch, key)
    batch_dir = EXPERIMENTS / batch
    out = out or stage_dir(batch_dir, key)
    section = f"{MEASURED_START}\n{measured_section(out, key, notes)}\n{MEASURED_END}"

    if path.exists():
        text = path.read_text(encoding="utf-8")
        if MEASURED_START in text and MEASURED_END in text:
            before, rest = text.split(MEASURED_START, 1)
            _, after = rest.split(MEASURED_END, 1)
            path.write_text(before + section + after, encoding="utf-8")
            return path

    info = batch_info(batch_dir)
    stage = STAGES[key]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"""# {key}. {stage['title']}: {title or f'batch {batch}'}

**Claims:** {len(info['ids'])} train claims ({', '.join(info['ids'])}).
**Pipeline records:** searched `{info['evidenceRun']}`, replayed `{info['replayRun']}`.
**Claude's blind files:** `{batch_dir.relative_to(REPO)}/` (`plan.jsonl`, `claude.jsonl`), written before any label or pipeline record was readable.
**The part's file:** [../../{key}-{stage['slug']}.md](../../{key}-{stage['slug']}.md)

{section}

## Findings

*(the agent's, each citing a claim id and the field of `comparison-before.json` it read)*

## Proposed change

*(the agent's: one change, its lever, replay or searched, and the prediction)*

## Result of the change

*(measured by the script after `--implement`; empty until then)*
""", encoding="utf-8")

    return path


# ----------------------------------------------------------------------
# Standard settings, and no cost beyond the subscription
# ----------------------------------------------------------------------
#
# Two things can cost money here. The agent: `claude -p` bills the claude.ai
# subscription when it is logged in that way and no API credential is in
# its environment; with ANTHROPIC_API_KEY (or Bedrock / Vertex / a gateway)
# set, the same command bills an API account per token. And the harness's
# model, for 04-05: local Ollama costs nothing, LLM_BASE_URL pointed at a
# hosted provider (Groq has a key in backend/.env) costs per call. The
# `total_cost_usd` the agent reports is the API price of the tokens; under a
# subscription it is a measure of usage, not a charge.

CONFIG = EXPERIMENTS / "config.json"

# Credentials that would switch `claude -p` from the subscription to per-token billing.
API_BILLING_ENV = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
    "AWS_BEARER_TOKEN_BEDROCK",
)

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def credit_risk(info: dict) -> str | None:
    """
    Why this rate-limit report means extra credits could be spent; None when
    it does not. Reproduced on 5 Nov: an account past its five-hour limit with
    usage credits switched on kept running on them (`isUsingOverage`) with
    `apiKeySource: none`, so the login and the key said nothing about it. An
    account where they are merely available counts too: one long call can
    cross the limit before anything could stop it. `overageStatus` "rejected"
    is the only safe answer.
    """

    if info.get("isUsingOverage") or info.get("overageInUse"):
        return "this account is spending extra credits right now"

    if info.get("overageEnabled") or info.get("overageStatus") not in (None, "rejected"):
        return "this account has extra credits switched on, and a step could spend them"

    return None


def _rate_limit(line: str) -> dict:

    try:
        event = json.loads(line)
    except ValueError:
        return {}

    return (event.get("rate_limit_info") or {}) if event.get("type") == "rate_limit_event" else {}


def credit_probe() -> str | None:
    """
    One very short call, to read the account's rate-limit report before a
    run starts: nothing else says whether credits are on. It fails closed: no
    report means it could not be confirmed, and the run does not start.
    """

    env = {key: value for key, value in os.environ.items() if key not in API_BILLING_ENV}

    try:
        output = subprocess.run(
            ["claude", "-p", "Reply with OK.", "--model", "haiku", "--output-format", "stream-json", "--verbose", "--no-session-persistence"],
            capture_output=True, text=True, timeout=120, env=env,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        return f"could not confirm that extra credits are off ({type(error).__name__})"

    reports = [info for info in map(_rate_limit, output.splitlines()) if info]

    if not reports:
        return "could not confirm that extra credits are off (no rate-limit report)"

    return next((risk for risk in map(credit_risk, reports) if risk), None)


def load_config() -> dict:

    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def configured(args, name: str, key: str, fallback=None):
    """A flag when given, else config.json, else the fallback; written back onto args."""

    value = getattr(args, name, None)

    if value is None:
        value = load_config().get(key, fallback)
        setattr(args, name, value)

    return value


def preflight(stages: list[str], llm_model: str | None = None, probe: bool = True) -> list[str]:
    """What would cost money or break comparability; empty when nothing does."""

    config = load_config()
    problems = []

    if config.get("billing", "subscription") == "subscription":

        set_vars = [name for name in API_BILLING_ENV if os.environ.get(name)]

        if set_vars:
            problems.append(f"{', '.join(set_vars)} set: `claude -p` would bill an API account per token (the script strips them from the agent's environment, but unset them to be sure)")

        try:
            status = json.loads(subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=30).stdout or "{}")
        except (OSError, subprocess.SubprocessError, ValueError):
            status = {}

        if not status.get("loggedIn"):
            problems.append("`claude` is not logged in (claude auth login)")
        elif status.get("authMethod") != "claude.ai":
            problems.append(f"`claude` is logged in by {status.get('authMethod')!r}, not the claude.ai subscription")
        elif probe and config.get("extraCredits", "never") == "never":
            risk = credit_probe()
            if risk:
                problems.append(f"{risk} ({status.get('email') or 'this login'}): use an account with extra credits off, or switch them off on claude.ai")

    if config.get("localOnly", True) and any(key in ("04", "05") for key in stages):

        from src.config.settings import settings

        host = (urlparse(settings.LLM_BASE_URL).hostname or "").lower()

        if host not in LOCAL_HOSTS:
            problems.append(f"LLM_BASE_URL is {settings.LLM_BASE_URL}: the harness's model would be a hosted, paid provider")

    from src.config.settings import settings

    if settings.FACT_CHECK_PROFILE != "thorough":
        problems.append(f"FACT_CHECK_PROFILE={settings.FACT_CHECK_PROFILE} in backend/.env: runs would not be the thorough pipeline every earlier round measured")

    return problems


def cmd_preflight(args) -> int:

    config = load_config()
    stages = list(STAGES) if args.stage == "all" else [stage_key(args.stage)]

    print(f"config ({CONFIG.relative_to(REPO)}): " + json.dumps({k: v for k, v in config.items() if not k.startswith("_")}))

    problems = preflight(stages)

    missing = [m for key in stages for m in services_missing(key, config.get("llmModel", "llama3.2:3b-bench"))]
    missing = list(dict.fromkeys(missing))

    print("cost:     " + ("OK: the claude.ai subscription, extra credits off; every other call is local" if not problems else "PROBLEMS"))
    for problem in problems:
        print(f"  - {problem}")

    print("services: " + ("OK" if not missing else "missing (the stages need them)"))
    for item in missing:
        print(f"  - {item}")

    return 1 if problems else 0


# ----------------------------------------------------------------------
# agent: Claude's blind side, then the analysis
# ----------------------------------------------------------------------

def _claude(prompt: str, phase: str, batch_dir: Path, log_name: str, args, extra_env: dict | None = None) -> int:
    """One `claude -p` session, its whole stream kept in the batch's logs."""

    if not shutil.which("claude"):
        raise TroubleshootError("the `claude` CLI is not on PATH")

    command = [
        "claude", "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
        "--allowedTools", PHASE_TOOLS[phase],
        "--no-session-persistence",
    ]

    if phase in ("plan", "search"):
        command += ["--disallowedTools", "Bash,Agent,Edit,Grep"]

    model = configured(args, "model", "agentModel")
    effort = load_config().get("agentEffort")

    if model:
        command += ["--model", model]

    if effort:
        command += ["--effort", effort]

    budget = configured(args, "max_budget_usd", "maxStepUsd")

    if budget:
        command += ["--max-budget-usd", str(budget)]

    env = {**os.environ, "TROUBLESHOOT_PHASE": phase, "TROUBLESHOOT_BATCH": str(batch_dir), **(extra_env or {})}

    # Under a subscription, no API credential reaches the agent: with one,
    # the same command bills per token.
    if load_config().get("billing", "subscription") == "subscription":
        for name in API_BILLING_ENV:
            env.pop(name, None)

    log = batch_dir / "logs" / f"{log_name}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)

    shown = " ".join(part if " " not in part else repr(part[:60] + "...") for part in command)
    print(f"\n[{phase}] {shown}\n        log: {log.relative_to(REPO)}")

    if args.dry_run:
        print(f"        prompt:\n{prompt}\n")
        return 0

    started = now()
    result: dict = {}
    init: dict = {}
    credits = None

    with log.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, text=True)
        for line in process.stdout:
            handle.write(line)
            init = init or _init(line)
            result = _echo(line) or result
            credits = credit_risk(_rate_limit(line)) if load_config().get("extraCredits", "never") == "never" else None
            if credits:
                process.kill()
                break
        status = process.wait()

    # When each step ran and what it cost, stamped here: the agent has no
    # clock (its own `writtenAt` was invented on the first try, 5 Nov).
    record_step(batch_dir, log_name, {
        "startedAt": started, "finishedAt": now(), "exit": status,
        "turns": result.get("num_turns"), "costUsd": result.get("total_cost_usd"),
        "outcome": f"stopped: {credits}" if credits else result.get("subtype"), "log": str(log.relative_to(REPO)),
        "model": init.get("model") or model or "default", "effort": effort,
        "apiKeySource": init.get("apiKeySource"),
        "config": {k: v for k, v in load_config().items() if not k.startswith("_")},
    })

    if credits:
        raise TroubleshootError(f"stopped at once, to spend no extra credits: {credits}")

    # "none" is the subscription login. Anything else is a key, billed per
    # token: stop before another step runs.
    if load_config().get("billing", "subscription") == "subscription" and init.get("apiKeySource") not in (None, "none"):
        raise TroubleshootError(f"the agent ran on an API key ({init.get('apiKeySource')}), not the subscription: stopped")

    return status


def _init(line: str) -> dict:

    try:
        event = json.loads(line)
    except ValueError:
        return {}

    return event if event.get("type") == "system" and event.get("subtype") == "init" else {}


def record_step(batch_dir: Path, name: str, step: dict) -> None:

    path = batch_dir / "batch.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    info.setdefault("steps", {}).setdefault(name, []).append(step)
    write_json(path, info)


def _echo(line: str) -> dict | None:
    """A one-line trace of each tool call and the final answer, so a run can be followed live; the result event back."""

    try:
        event = json.loads(line)
    except ValueError:
        return None

    if event.get("type") == "assistant":
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "tool_use":
                arguments = json.dumps(part.get("input", {}), ensure_ascii=False)
                print(f"   - {part.get('name')} {arguments[:140]}")
    elif event.get("type") == "result":
        print(f"   = {event.get('subtype')} ({event.get('num_turns')} turns, ${event.get('total_cost_usd') or 0:.2f})")
        return event

    return None


PLAN_PROMPT = """You are doing the blind first step of the fact-checker troubleshooting protocol.
Use the what-to-search skill (.claude/skills/what-to-search/SKILL.md) and follow it exactly.
Batch directory: {batch_dir}
Read {batch_dir}/claims.jsonl (and nothing else under data/evaluation). For every claim, write one
line to {batch_dir}/plan.jsonl, as the skill says. Do not search: this is the plan before any search.
When done, say how many rows you wrote. Nothing is committed in this step."""

SEARCH_PROMPT = """You are doing the blind second step of the fact-checker troubleshooting protocol.
Use the what-to-search skill (.claude/skills/what-to-search/SKILL.md), section "Searching".
Batch directory: {batch_dir}
Read {batch_dir}/claims.jsonl and your own {batch_dir}/plan.jsonl. For every claim, run the plan's
queries with WebSearch (never the article's own site: `excludeSite`), at most one follow-up where
the first left the decisive detail open, and write one line to {batch_dir}/claude.jsonl as the skill says.
You have not seen, and must not look for, the labels or the pipeline's records.
When done, say how many rows you wrote. Nothing is committed in this step."""

ANALYSE_PROMPT = """You are the analyst for stage {key} ({title}) of the fact-checker troubleshooting.
Use the troubleshoot-fact-check skill (.claude/skills/troubleshoot-fact-check/SKILL.md), its section
for stage {key}, and follow it exactly.
Batch: {batch}. Comparison: {stage_dir}/comparison-before.json and metrics-before.json.
The part's file: docs/troubleshooting/fact-checking/{key}-{slug}.md.
Write the "Findings" and "Proposed change" sections of {doc}, and {stage_dir}/proposal.json.
{implement}
Never edit the measured section, the comparison, metrics, pipeline, plan or claude files.
End by listing the files you changed, and say that nothing was committed."""

IMPLEMENT = """--implement is on: implement the proposed change as the skill's "Implementing" section says
(behind a new threshold value, the default unchanged, with a test; run `./scripts/check.sh fast` from the
repo root and the touched tests). Put the overrides that switch it on in proposal.json's `thresholds`."""


def cmd_agent(args) -> int:

    batch_dir = EXPERIMENTS / args.batch
    batch_info(batch_dir)
    key = stage_key(args.stage)

    problems = preflight([key], probe=not args.dry_run)

    if problems and not args.dry_run:
        raise TroubleshootError("preflight:\n  " + "\n  ".join(problems))
    stage = STAGES[key]
    out = stage_dir(batch_dir, key)

    # 1-2. Claude's blind side, once per batch, shared by every stage.
    for need, prompt, name in (("plan", PLAN_PROMPT, "plan"), ("search", SEARCH_PROMPT, "search")):

        if need not in stage["needs"] or not validate(batch_dir, need):
            continue

        if (batch_dir / (PLAN if need == "plan" else SEARCH)).exists() and not args.redo_blind:
            problems = validate(batch_dir, need)
            raise TroubleshootError(f"{need} file exists but is incomplete (fix it, or --redo-blind):\n  " + "\n  ".join(problems))

        status = _claude(prompt.format(batch_dir=batch_dir.relative_to(REPO)), need, batch_dir, name, args)

        if args.dry_run:
            continue

        problems = validate(batch_dir, need)

        if status or problems:
            raise TroubleshootError(f"the {need} step did not finish (exit {status}):\n  " + "\n  ".join(problems))

    if args.dry_run:
        print("\n[dry run] then: pipeline, join, write the experiment file, analyse")
        return 0

    # 3. The pipeline's side and the numbers: this script, not the agent.
    cmd_pipeline(argparse.Namespace(batch=args.batch, stage=key, label="before", thresholds=args.thresholds))
    cmd_join(argparse.Namespace(batch=args.batch, stage=key, label="before"))
    doc = write_experiment(args.batch, key)

    # 4. The analysis (and the change, with --implement).
    phase = "implement" if args.implement else "analyse"
    prompt = ANALYSE_PROMPT.format(
        key=key, title=stage["title"], batch=args.batch, slug=stage["slug"],
        stage_dir=out.relative_to(REPO), doc=doc.relative_to(REPO),
        implement=IMPLEMENT if args.implement else "Do not change any code: propose only.",
    )

    status = _claude(prompt, phase, batch_dir, f"{key}-{phase}", args)

    if status:
        raise TroubleshootError(f"the analysis did not finish (exit {status})")

    # 5. Measured again after a change, where the stage can be measured offline.
    if args.implement:
        measure_after(args.batch, key)

    write_experiment(args.batch, key)

    print(f"\nexperiment: {doc.relative_to(REPO)}")
    print(f"review:     git diff; {out.relative_to(REPO)}/proposal.json; {batch_dir.relative_to(REPO)}/logs/")

    return 0


def measure_after(batch: str, key: str) -> None:
    """
    Stages 01 and 02 are measured offline, so a change to them is measured
    here, by the same count as before. Stages 03-05 need a run: the
    proposal goes to the iteration loop instead (`cli iterate propose`).
    """

    out = stage_dir(EXPERIMENTS / batch, key)
    proposal_path = out / "proposal.json"

    if not proposal_path.exists():
        print("no proposal.json: nothing to measure after")
        return

    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    overrides = proposal.get("thresholds") or {}

    if key not in ("01", "02"):
        print(f"stage {key} is measured by a run, not offline: hand proposal.json to `cli iterate propose` (/iterate-fact-check).")
        return

    try_path = out / "try.json"
    write_json(try_path, overrides)

    cmd_pipeline(argparse.Namespace(batch=batch, stage=key, label="after", thresholds=str(try_path)))
    cmd_join(argparse.Namespace(batch=batch, stage=key, label="after"))


def cmd_measure(args) -> int:
    """Re-measure one stage (before, and after if there is a proposal), and refresh the experiment file."""

    key = stage_key(args.stage)

    cmd_pipeline(argparse.Namespace(batch=args.batch, stage=key, label="before", thresholds=args.thresholds))
    cmd_join(argparse.Namespace(batch=args.batch, stage=key, label="before"))

    if (stage_dir(EXPERIMENTS / args.batch, key) / "proposal.json").exists():
        measure_after(args.batch, key)

    print(write_experiment(args.batch, key).relative_to(REPO))

    return 0


def cmd_status(args) -> int:

    batch_dir = EXPERIMENTS / args.batch
    info = batch_info(batch_dir)

    print(f"batch {args.batch}: {len(info['ids'])} claims, from {info['evidenceRun']}")

    for name, runs in (info.get("steps") or {}).items():
        last = runs[-1]
        print(f"  step {name:13} {last.get('outcome')}, {last.get('finishedAt')}, {last.get('turns')} turns, ${last.get('costUsd') or 0:.2f}, log {last.get('log')}")

    for need, name in (("plan", PLAN), ("search", SEARCH)):
        problems = validate(batch_dir, need)
        print(f"  {name:13} {'complete' if not problems else problems[0] + (f' (+{len(problems) - 1} more)' if len(problems) > 1 else '')}")

    for key, stage in STAGES.items():
        out = stage_dir(batch_dir, key)
        measured = sorted(path.stem.removeprefix("metrics-") for path in out.glob("metrics-*.json"))
        doc = experiment_doc(args.batch, key)
        proposal = "proposal" if (out / "proposal.json").exists() else ""
        print(f"  {key} {stage['slug']:18} measured: {', '.join(measured) or '-':14} {proposal:9} {doc.relative_to(REPO) if doc.exists() else ''}")

    return 0


# ----------------------------------------------------------------------
# loop: round after round, each change kept only if it holds on a batch
# the agent never saw
# ----------------------------------------------------------------------
#
# A round: the agent reads where the stage stands (the tune batch's
# comparison under the changes kept so far), proposes one change and builds
# it; this script checks the code, measures the stage again on the tune
# batch and on the held-out batch, in a fresh process each time, and keeps
# the change only by the rule in `decide`. A rejected change's code is put
# back as it was. The kept overrides accumulate in the tune batch's
# `loop.json` and carry over to the next stage.
#
# Why a held-out batch: the agent writes lexicons and rules while looking at
# the tune batch's 20 claims, and a string-match measure is easy to fit. A
# change that only helps the claims it was written for does not hold on 20
# claims it never saw. The held-out batch's comparison is refused to the
# agent by the hook (TROUBLESHOOT_HOLDOUT), and loop.json carries only its
# verdict, not its numbers.

LOOP = "loop.json"

# Each stage's primary number (higher is better) and the per-claim value a
# round must not lower. 04 weighs a settling source kept above a silent one
# saved: the second is model time, the first is the verdict.
PRIMARY = {
    "01": lambda m: m["checkablePointCoverage"] or 0,
    "02": lambda m: m.get("checkableCoverage") or 0,
    "03": lambda m: m["settlingDomainInCandidates"],
    "04": lambda m: m["settlingKept"] * 100 - m["keptSilent"],
    "05": lambda m: m["pipelineRight"],
}

PER_CLAIM = {
    "01": lambda r: r["counted"]["checkablePoint"]["share"] or 0,
    "02": lambda r: (r["counted"].get("checkable") or {}).get("share") or 0,
    "03": lambda r: 1 if r["counted"]["settlingInCandidates"] else 0,
    "04": lambda r: 1 if r["counted"]["settlingKept"] else 0,
    "05": lambda r: 1 if r["counted"]["pipelineRight"] else 0,
}

# 03 is a live search: the same queries differ run to run (6-9 points of
# accuracy on the train half, CLAUDE.md). One claim's candidates moving is
# within that, so a searched gain must be two claims net.
MIN_NET_GAIN = {"01": 0, "02": 0, "03": 2, "04": 1, "05": 1}

# What a round's change is tested with, besides the stage's measure. Fast,
# and covering every module a round may touch.
GATE = (
    ["./scripts/check.sh", "fast"],
    ["uv", "run", "pytest", "-q", "-x", "tests/services/fact_checker", "tests/evaluation", "tests/test_fake_contracts.py", "tests/test_invariants.py"],
)


def decide(key: str, tune: tuple[list, list], holdout: tuple[dict, dict]) -> tuple[str, str, dict]:
    """
    keep / reject, why, and the per-claim changes on the tune batch.

    - the tune batch's primary number goes up;
    - for 01-02 (offline, exact) no tune claim's value falls; for 03-05
      (a run) the claims gained outnumber the claims lost by MIN_NET_GAIN;
    - the held-out batch's primary number does not fall.
    """

    before_rows, after_rows = tune
    before_hold, after_hold = holdout

    per_claim = PER_CLAIM[key]
    before = {r["id"]: per_claim(r) for r in before_rows}
    after = {r["id"]: per_claim(r) for r in after_rows}
    gained = sorted(i for i in before if after.get(i, 0) > before[i])
    lost = sorted(i for i in before if after.get(i, 0) < before[i])

    tune_before = PRIMARY[key](summarise(key, before_rows))
    tune_after = PRIMARY[key](summarise(key, after_rows))
    hold_before, hold_after = PRIMARY[key](before_hold), PRIMARY[key](after_hold)

    changed = {"gained": gained, "lost": lost, "tuneBefore": tune_before, "tuneAfter": tune_after}

    if tune_after <= tune_before:
        return "reject", f"the tune batch did not improve ({tune_before} -> {tune_after})", changed

    if key in ("01", "02") and lost:
        return "reject", f"claims got worse on the tune batch: {', '.join(lost)}", changed

    if len(gained) - len(lost) < MIN_NET_GAIN[key]:
        return "reject", f"net gain {len(gained) - len(lost)} claim(s), under {MIN_NET_GAIN[key]} (run-to-run noise)", changed

    if hold_after < hold_before:
        return "reject", "the held-out batch got worse", changed

    return "keep", f"tune {tune_before} -> {tune_after}, held-out batch not worse", changed


def _hash(overrides: dict) -> str:

    import hashlib

    return hashlib.sha256(json.dumps(overrides, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def _python(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    """This module in a fresh process: the code a round just changed is the code measured."""

    result = subprocess.run(
        [sys.executable, "-m", "src.evaluation.troubleshoot", *arguments],
        cwd=BACKEND, capture_output=True, text=True,
    )

    if check and result.returncode:
        raise TroubleshootError(f"`troubleshoot {' '.join(arguments)}` failed:\n{result.stderr[-2000:]}")

    return result


def _dataset_of(run: Path) -> str:

    manifest = json.loads((run / "run.json").read_text(encoding="utf-8"))

    path = (manifest.get("dataset") or {}).get("path")

    if not path:
        raise TroubleshootError(f"{run} does not say which dataset it ran over")

    return path.replace("\\", "/")


def harness_run(batch_dir: Path, key: str, thresholds_path: Path, tag: str, llm_model: str) -> tuple[str | None, str | None]:
    """
    The runs a stage's measure reads, for 03-05: (searched run, replayed run).
    03 searches again (`--retrieval-only`: candidates, no model); 04 and 05
    replay the evidence run's candidates through ranking and the model.
    01-02 need none.
    """

    if key in ("01", "02"):
        return None, None

    info = batch_info(batch_dir)
    ids = ",".join(info["ids"])

    command = [
        "uv", "run", "python", "-m", "src.evaluation.cli", "run",
        # The evidence run's own set: a batch is over the claims it was drawn from,
        # and the benchmark has been AVeriTeC since 5 Nov, the custom set before it.
        "--dataset", _dataset_of(BACKEND / info["evidenceRun"]), "--split", "train", "--ids", ids,
        "--thresholds", str(thresholds_path), "--label", f"troubleshoot-{tag}",
    ]

    command += ["--retrieval-only"] if key == "03" else ["--replay", str(BACKEND / info["evidenceRun"]), "--model", llm_model]

    print(f"      run: {' '.join(command[:9])} ... {' '.join(command[-4:])}")

    result = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True)

    match = re.search(r'"run":\s*"([^"]+)"', result.stdout)

    if not match:
        raise TroubleshootError(f"the harness run did not finish:\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}")

    directory = match.group(1)

    return (directory, None) if key == "03" else (directory, directory)


def measure_batch(batch: str, key: str, overrides: dict, out: Path, label: str, llm_model: str) -> tuple[dict, list]:
    """One measure of one batch under these overrides: (metrics, comparison rows). Cached by the overrides and the code."""

    batch_dir = EXPERIMENTS / batch
    out.mkdir(parents=True, exist_ok=True)

    thresholds_path = out / f"thresholds-{label}.json"
    write_json(thresholds_path, overrides)

    run, replay = harness_run(batch_dir, key, thresholds_path, f"{batch}-{key}-{_hash(overrides)}", llm_model)

    arguments = ["--batch", batch, "--stage", key, "--label", label, "--out", str(out)]
    pipeline = ["pipeline", *arguments, "--thresholds", str(thresholds_path)]

    if run:
        pipeline += ["--run", run]
    if replay:
        pipeline += ["--replay", replay]

    _python(*pipeline)
    _python("join", *arguments)

    return (
        json.loads((out / f"metrics-{label}.json").read_text(encoding="utf-8")),
        json.loads((out / f"comparison-{label}.json").read_text(encoding="utf-8")),
    )


def snapshot() -> dict[str, bytes]:
    """Every file a round may change (the hook confines its writes to these trees), to put back on a rejection."""

    files = {}

    for tree in ("backend/src", "backend/tests"):
        for path in (REPO / tree).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files[str(path.relative_to(REPO))] = path.read_bytes()

    return files


def restore(files: dict[str, bytes]) -> list[str]:
    """The trees as they were; returns what was put back."""

    now_files = snapshot()
    changed = []

    for name, content in files.items():
        if now_files.get(name) != content:
            (REPO / name).parent.mkdir(parents=True, exist_ok=True)
            (REPO / name).write_bytes(content)
            changed.append(name)

    for name in set(now_files) - set(files):
        (REPO / name).unlink()
        changed.append(name)

    return sorted(changed)


def touched(files: dict[str, bytes]) -> list[str]:

    now_files = snapshot()

    return sorted({name for name in files if now_files.get(name) != files[name]} | (set(now_files) - set(files)))


def gate() -> tuple[bool, str]:
    """The round's code passes the invariants and the fact-checker's tests, run here, not taken from the agent."""

    for command in GATE:
        cwd = REPO if command[0].startswith("./") else BACKEND
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode:
            return False, f"`{' '.join(command)}` failed: {(result.stdout + result.stderr)[-600:]}"

    return True, "check.sh fast and the fact-checker / evaluation tests pass"


def services_missing(key: str, llm_model: str) -> list[str]:
    """What a stage's runs need and is not answering. 01-02 need nothing but a better entity read."""

    import urllib.request

    def up(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.status < 500
        except Exception:
            return False

    from src.config.settings import settings

    missing = []

    if key in ("03", "04", "05") and not up(settings.INFERENCE_URL.rstrip("/") + "/health"):
        missing.append(f"inference/ at {settings.INFERENCE_URL} (cd inference && uv run uvicorn src.main:app --port 8001)")

    if key == "03" and not up(settings.SEARXNG_URL.rstrip("/") + "/healthz"):
        missing.append(f"SearXNG at {settings.SEARXNG_URL} (cd docker && docker compose up -d searxng)")

    if key in ("04", "05"):
        base = settings.LLM_BASE_URL.rstrip("/").removesuffix("/v1")
        try:
            with urllib.request.urlopen(base + "/api/tags", timeout=3) as response:
                names = [model.get("name") for model in json.loads(response.read()).get("models", [])]
            if not any(name and name.split(":latest")[0] == llm_model.split(":latest")[0] for name in names):
                missing.append(f"the model {llm_model} in Ollama (ollama list)")
        except Exception:
            missing.append(f"Ollama at {base}")

    return missing


LOOP_PROMPT = """You are round {round} of the improvement loop for stage {key} ({title}) of the fact-checker.
Use the troubleshoot-fact-check skill (.claude/skills/troubleshoot-fact-check/SKILL.md): its section for
stage {key}, its "The loop" section and its "Implementing" section. Follow them exactly.
Tune batch: {batch}. This round's directory: {round_dir}.
Where the stage stands now, under the changes kept so far ({base}):
  {round_dir}/comparison-before.json and metrics-before.json.
Every earlier round, its change and why it was kept or rejected: {loop}. Do not repeat a rejected change
unless you name what is different.
Propose ONE new change and build it behind a new threshold value (or set an existing threshold). A change
already in the code behind a threshold but never through this loop (e.g. one built by `agent --implement`)
may be a round of its own, with no new code.
Write {round_dir}/proposal.json, whose `thresholds` holds ONLY the new overrides this round adds, and the
"Findings" and "Proposed change" sections of {doc}.
The script then runs the tests itself, measures this batch and a held-out batch you cannot read, and keeps
or undoes your change. Never edit the measured files. End with the files you changed; nothing is committed."""


def load_loop(batch_dir: Path) -> dict:

    path = batch_dir / LOOP

    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"base": {}, "rounds": []}


def spent(batch_dir: Path) -> float:

    return round(sum(step.get("costUsd") or 0 for steps in (batch_info(batch_dir).get("steps") or {}).values() for step in steps), 2)


def ensure_blind(batch: str, key: str, args) -> None:
    """Claude's blind plan (and search, for 03-05) of a batch, once."""

    batch_dir = EXPERIMENTS / batch

    for need, prompt in (("plan", PLAN_PROMPT), ("search", SEARCH_PROMPT)):
        if need in STAGES[key]["needs"] and validate(batch_dir, need):
            if (batch_dir / (PLAN if need == "plan" else SEARCH)).exists():
                raise TroubleshootError(f"{batch}: the {need} file is incomplete: " + "; ".join(validate(batch_dir, need)[:3]))
            status = _claude(prompt.format(batch_dir=batch_dir.relative_to(REPO)), need, batch_dir, need, args)
            if status or validate(batch_dir, need):
                raise TroubleshootError(f"{batch}: the {need} step did not finish")


def loop_stage(args, key: str) -> None:

    tune, hold = args.batch, args.holdout
    tune_dir, hold_dir = EXPERIMENTS / tune, EXPERIMENTS / hold
    stage = STAGES[key]

    missing = services_missing(key, args.llm_model)

    if missing:
        raise TroubleshootError(f"stage {key} measures with runs, and these are not answering:\n  " + "\n  ".join(missing))

    ensure_blind(tune, key, args)
    ensure_blind(hold, key, args)

    state = load_loop(tune_dir)
    state["holdout"] = hold

    if args.base and not state["rounds"]:
        state["base"] = json.loads(args.base)
    rejected_in_a_row = 0
    done = [r for r in state["rounds"] if r["stage"] == key]

    print(f"\n=== stage {key} {stage['slug']}: {len(done)} round(s) before, base {state['base']}")

    for number in range(len(done) + 1, len(done) + args.rounds + 1):

        if args.max_total_usd and spent(tune_dir) + spent(hold_dir) >= args.max_total_usd:
            print(f"--- stop: ${spent(tune_dir) + spent(hold_dir):.2f} spent, the limit is ${args.max_total_usd:.2f}")
            return

        round_dir = stage_dir(tune_dir, key) / f"round-{number:02d}"
        hold_round = stage_dir(hold_dir, key) / f"round-{number:02d}"
        base = dict(state["base"])

        print(f"\n--- round {number}: measuring the base on both batches")
        before_tune, before_rows = measure_batch(tune, key, base, round_dir, "before", args.llm_model)
        before_hold, _ = measure_batch(hold, key, base, hold_round, "before", args.llm_model)

        doc = experiment_doc(tune, key).with_name(f"{tune}-round-{number:02d}.md")
        write_experiment(tune, key, out=round_dir, path=doc, title=f"loop round {number}, batch {tune}",
                         notes=[f"Base (kept so far): `{json.dumps(base)}`. Held-out batch: `{hold}` (not readable by the agent).", ""])

        files = snapshot()
        prompt = LOOP_PROMPT.format(
            round=number, key=key, title=stage["title"], batch=tune, round_dir=round_dir.relative_to(REPO),
            base=json.dumps(base), loop=(tune_dir / LOOP).relative_to(REPO), doc=doc.relative_to(REPO),
        )

        try:
            status = _claude(prompt, "implement", tune_dir, f"{key}-round-{number:02d}", args, {"TROUBLESHOOT_HOLDOUT": str(hold_dir)})
        except TroubleshootError:
            # Stopped mid-round (credits, a key): no half-built change stays.
            restore(files)
            raise

        record = {"stage": key, "round": number, "at": now(), "base": base, "doc": str(doc.relative_to(REPO))}
        proposal_path = round_dir / "proposal.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8")) if proposal_path.exists() else {}
        new = proposal.get("thresholds") or {}
        record.update({"change": proposal.get("change"), "thresholds": new, "files": touched(files)})

        decision, reason, changed = None, None, {}

        if status or not proposal:
            decision, reason = "invalid", f"the agent's step did not finish with a proposal (exit {status})"
        elif not new and not record["files"]:
            decision, reason = "invalid", "the proposal switches nothing on and changes no file"
        else:
            ok, why = gate()
            if not ok:
                decision, reason = "reject", why
            else:
                print(f"--- round {number}: measuring {json.dumps(new)} on both batches")
                after_tune, after_rows = measure_batch(tune, key, {**base, **new}, round_dir, "after", args.llm_model)
                after_hold, _ = measure_batch(hold, key, {**base, **new}, hold_round, "after", args.llm_model)
                decision, reason, changed = decide(key, (before_rows, after_rows), (before_hold, after_hold))
                # The held-out numbers stay with the held-out batch, out of the agent's reach.
                write_json(hold_round / "result.json", {"before": before_hold, "after": after_hold, "decision": decision})

        record.update({"decision": decision, "reason": reason, **changed})

        if decision == "keep":
            state["base"] = {**base, **new}
            rejected_in_a_row = 0
        else:
            record["restored"] = restore(files)
            rejected_in_a_row += 1

        state["rounds"].append(record)
        write_json(tune_dir / LOOP, state)

        write_experiment(tune, key, out=round_dir, path=doc, notes=[
            f"Base (kept so far): `{json.dumps(base)}`. This round adds `{json.dumps(new)}`.",
            f"**Decision: {decision}**: {reason}." + (f" Gained: {', '.join(changed.get('gained', [])) or '-'}; lost: {', '.join(changed.get('lost', [])) or '-'}." if changed else ""),
            f"Files changed: {', '.join(record['files']) or '-'}" + ("; put back as they were." if decision != "keep" else "; kept, uncommitted."),
            "",
        ])

        print(f"--- round {number}: {decision.upper()}: {reason}")

        if rejected_in_a_row >= args.patience:
            print(f"--- stop stage {key}: {rejected_in_a_row} rounds in a row without a kept change")
            return


def cmd_loop(args) -> int:

    stages = list(STAGES) if args.stage == "all" else [stage_key(args.stage)]

    for name, key, fallback in (("rounds", "rounds", 5), ("patience", "patience", 2), ("max_total_usd", "maxTotalUsd", 30.0), ("llm_model", "llmModel", "llama3.2:3b-bench")):
        configured(args, name, key, fallback)

    problems = preflight(stages, args.llm_model)

    if problems:
        raise TroubleshootError("preflight:\n  " + "\n  ".join(problems))

    if args.holdout == args.batch:
        raise TroubleshootError("the held-out batch must not be the tune batch")

    tune_ids = set(batch_info(EXPERIMENTS / args.batch)["ids"])
    hold_ids = set(batch_info(EXPERIMENTS / args.holdout)["ids"])

    if tune_ids & hold_ids:
        raise TroubleshootError(f"the batches share claims: {', '.join(sorted(tune_ids & hold_ids))}")

    for key in stages:
        loop_stage(args, key)

    state = load_loop(EXPERIMENTS / args.batch)
    kept = [r for r in state["rounds"] if r["decision"] == "keep"]

    print(f"\nkept {len(kept)} of {len(state['rounds'])} rounds; base now {json.dumps(state['base'])}")
    print(f"review: git diff; {(EXPERIMENTS / args.batch / LOOP).relative_to(REPO)}; docs/troubleshooting/fact-checking/experiments/*/{args.batch}-round-*.md")

    return 0


# ----------------------------------------------------------------------
# The command line
# ----------------------------------------------------------------------

def parser() -> argparse.ArgumentParser:

    root = argparse.ArgumentParser(prog="python -m src.evaluation.troubleshoot", description=__doc__.split("\n\n")[0])
    commands = root.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="choose the batch's train claims and write them blind")
    prepare.add_argument("--batch", required=True, help="a name, e.g. 20261105-next20")
    prepare.add_argument("--offset", type=int, default=DEFAULT_OFFSET, help=f"skip this many of the run's claims (default {DEFAULT_OFFSET}: the 4 Nov batch)")
    prepare.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    prepare.add_argument("--ids", help="comma-separated claim ids instead of offset/limit")
    prepare.add_argument("--evidence-run", default=str(DEFAULT_EVIDENCE_RUN))
    prepare.add_argument("--replay-run", default=str(DEFAULT_REPLAY_RUN))
    prepare.add_argument("--force", action="store_true")
    prepare.set_defaults(handler=cmd_prepare)

    agent = commands.add_parser("agent", help="Claude's blind plan/search (once per batch), the numbers, then the stage's analysis")
    agent.add_argument("--batch", required=True)
    agent.add_argument("--stage", required=True, help="01-05")
    agent.add_argument("--implement", action="store_true", help="let the agent implement its proposal (opt-in, default unchanged), then measure it")
    agent.add_argument("--thresholds", help="overrides for the 'before' measure (default: the environment's)")
    agent.add_argument("--model", help="the Claude model for the agent (default: yours)")
    agent.add_argument("--max-budget-usd", type=float, help="stop a phase past this spend")
    agent.add_argument("--redo-blind", action="store_true", help="rewrite an incomplete plan/claude file")
    agent.add_argument("--dry-run", action="store_true", help="print the claude commands and prompts, run nothing")
    agent.set_defaults(handler=cmd_agent)

    for name, handler, text in (
        ("pipeline", cmd_pipeline, "write the pipeline's side of one stage"),
        ("join", cmd_join, "compare it with Claude's files and count"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--batch", required=True)
        command.add_argument("--stage", required=True)
        command.add_argument("--label", default="before")
        command.add_argument("--out", help="write here instead of the batch's stage directory (a loop round)")
        if name == "pipeline":
            command.add_argument("--thresholds")
            command.add_argument("--run", help="read candidates from this run instead of the batch's evidence run")
            command.add_argument("--replay", help="read stances and verdicts from this run instead of the batch's replay")
        command.set_defaults(handler=handler)

    loop = commands.add_parser("loop", help="rounds of propose -> build -> test -> measure on the tune and held-out batches -> keep or undo")
    loop.add_argument("--batch", required=True, help="the tune batch: the agent reads its comparison")
    loop.add_argument("--holdout", required=True, help="the held-out batch: measured every round, never shown to the agent")
    loop.add_argument("--stage", required=True, help="01-05, or all (in order, each building on what the last kept)")
    loop.add_argument("--rounds", type=int, help="at most this many rounds per stage (config.json: rounds)")
    loop.add_argument("--patience", type=int, help="stop a stage after this many rounds in a row with nothing kept (config.json: patience)")
    loop.add_argument("--max-total-usd", type=float, help="stop when both batches' agent steps have used this much, at API prices (config.json: maxTotalUsd)")
    loop.add_argument("--max-budget-usd", type=float, help="the most one agent step may use, at API prices (config.json: maxStepUsd)")
    loop.add_argument("--base", help="the overrides to start from, as JSON, when the loop has no rounds yet")
    loop.add_argument("--llm-model", help="the verifier for 04-05's replays (config.json: llmModel, the evidence run's)")
    loop.add_argument("--model", help="the Claude model for the agent (default: yours)")
    loop.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    loop.set_defaults(handler=cmd_loop)

    measure = commands.add_parser("measure", help="pipeline + join (+ after) + refresh the experiment file, no agent")
    measure.add_argument("--batch", required=True)
    measure.add_argument("--stage", required=True)
    measure.add_argument("--thresholds")
    measure.set_defaults(handler=cmd_measure)

    check = commands.add_parser("preflight", help="the standard config, whether anything would cost beyond the subscription, and the services")
    check.add_argument("--stage", default="all")
    check.set_defaults(handler=cmd_preflight)

    status = commands.add_parser("status", help="what the batch has so far")
    status.add_argument("--batch", required=True)
    status.set_defaults(handler=cmd_status)

    return root


def main(argv: list[str] | None = None) -> int:

    args = parser().parse_args(argv)

    try:
        return args.handler(args)
    except TroubleshootError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

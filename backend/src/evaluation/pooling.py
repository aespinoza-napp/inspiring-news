"""
Pooled relevance judgements: retrieval variants scored on the same
judgements (roadmap, Thesis priorities P1.1; TREC's pooling method).

    uv run python -m src.evaluation.cli pool --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli judge --judgements data/evaluation/judgements/<set>.jsonl
    uv run python -m src.evaluation.cli pooled --run A --run B ... --judgements data/evaluation/judgements/<set>.jsonl

The annotator's reference links are one witness of relevance, and a
strict one: another page can be as good, and a miss is not proof of
failure (§Retrieval evaluation). So each variant's top `depth` ranked
sources per claim are pooled, a person judges each pooled page once -
does it bear on the claim, for or against? - and every variant is scored
on the same judgements. A later variant reuses them: `pool` adds only the
pages it brings, and those are all that need judging.

**The pool** is one JSONL line per (claim, page), the page keyed with the
retriever's own URL normaliser (`_comparable`), so the same page found by
two variants is judged once. `relevant` is null until judged, then true
or false; `pooledFrom` names the runs that ranked it.

**The scores**, per run, over the claims it searched (outcome scored or
llmUnreachable, as in retrieval.py), each a mean over claims with a
bootstrap interval, then paired against the first run:

    precision@depth  relevant / judged among its top `depth`
    recall           relevant it ranked / relevant in the pool, for claims with any
    mrr              1 / rank of its first relevant page, same claims
    judged           the share of its top `depth` that is judged (coverage)

An unjudged page counts in none of the first three, and coverage says how
many there were: a variant pooled after the judging is scored on what was
judged, and reports how much was not.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.metrics import LLM_UNREACHABLE, SCORED, outcome
from src.evaluation.stats import bootstrap_mean, mean, paired_bootstrap_mean, rounded
from src.services.fact_checker.retrieval.evidence_retriever import _comparable

DEPTH = 5

METRICS = ("precision", "recall", "mrr", "judged")


def _searched(record: dict) -> bool:

    return outcome(record) in (SCORED, LLM_UNREACHABLE)


def _top(record: dict, depth: int) -> list[dict]:

    return (record.get("evidence") or [])[:depth]


def run_name(run) -> str:
    """How a run is named in the pool and the table: its label, else its key."""

    return run.manifest.get("label") or run.key


# ----------------------------------------------------------------------
# The judgement file
# ----------------------------------------------------------------------


def load_judgements(path: Path) -> list[dict]:

    if not path.exists():
        return []

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_judgements(path: Path, entries: list[dict]) -> None:
    """Written whole, through a temporary file: a judging session interrupted mid-write loses nothing."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries), encoding="utf-8")
    tmp.replace(path)


def pool(runs: list, judgements: list[dict], depth: int = DEPTH) -> tuple[list[dict], int]:
    """
    The judgements with every run's top `depth` pages added: new pages
    unjudged, pages already there kept with their judgement and the new
    run named among those that ranked them. Returns them and how many
    pages were new.
    """

    by_key = {(entry["claimId"], entry["key"]): entry for entry in judgements}
    added = 0

    for run in runs:

        name = run_name(run)

        for record in run.records:

            if not _searched(record):
                continue

            for item in _top(record, depth):

                key = _comparable(item.get("url") or "")

                if not key:
                    continue

                entry = by_key.get((record["id"], key))

                if entry is None:
                    entry = {
                        "claimId": record["id"],
                        "claim": record.get("claim"),
                        "language": record.get("language"),
                        "key": key,
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "domain": item.get("domain"),
                        "pooledFrom": [],
                        "relevant": None,
                        "note": "",
                    }
                    by_key[(record["id"], key)] = entry
                    added += 1

                if name not in entry["pooledFrom"]:
                    entry["pooledFrom"].append(name)

    # Claim by claim, in the order pages were first pooled, so a person
    # judges one claim's pages together.
    ordered = sorted(by_key.values(), key=lambda entry: entry["claimId"])

    return ordered, added


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------


def claim_scores(record: dict, judged: dict[tuple[str, str], bool], relevant_in_pool: int, depth: int) -> dict:
    """The four values for one claim of one run; None where undefined."""

    top = _top(record, depth)
    marks = [judged.get((record["id"], _comparable(item.get("url") or ""))) for item in top]

    known = [mark for mark in marks if mark is not None]
    hits = sum(1 for mark in known if mark)
    first = next((rank for rank, mark in enumerate(marks, start=1) if mark), None)

    return {
        "precision": (hits / len(known)) if known else None,
        "recall": (hits / relevant_in_pool) if relevant_in_pool else None,
        "mrr": ((1 / first) if first else 0.0) if relevant_in_pool else None,
        "judged": (len(known) / len(top)) if top else None,
    }


def pooled_table(runs: list, judgements: list[dict], *, depth: int = DEPTH, seed: int, resamples: int) -> dict:

    judged = {(entry["claimId"], entry["key"]): entry["relevant"] for entry in judgements if entry["relevant"] is not None}

    relevant_in_pool: dict[str, int] = {}
    for (claim_id, _), mark in judged.items():
        relevant_in_pool[claim_id] = relevant_in_pool.get(claim_id, 0) + (1 if mark else 0)

    per_run = []

    for run in runs:

        claims = {
            record["id"]: claim_scores(record, judged, relevant_in_pool.get(record["id"], 0), depth)
            for record in run.records if _searched(record)
        }

        block = {}

        for name in METRICS:
            values = [scores[name] for scores in claims.values() if scores[name] is not None]
            interval = bootstrap_mean(values, seed=seed, resamples=resamples)
            block[name] = {
                "n": len(values),
                "value": rounded(mean(values)),
                "low": rounded(interval["low"]),
                "high": rounded(interval["high"]),
            }

        per_run.append({"name": run_name(run), "key": run.key, "claims": claims, "metrics": block})

    baseline = per_run[0] if per_run else None

    for row in per_run[1:]:

        row["vsBaseline"] = {}

        for name in METRICS:
            shared = [
                claim for claim in row["claims"]
                if claim in baseline["claims"]
                and row["claims"][claim][name] is not None
                and baseline["claims"][claim][name] is not None
            ]
            a = [baseline["claims"][claim][name] for claim in shared]
            b = [row["claims"][claim][name] for claim in shared]
            interval = paired_bootstrap_mean(a, b, seed=seed, resamples=resamples)
            row["vsBaseline"][name] = {"pairs": len(shared), **{k: rounded(v) for k, v in interval.items()}}

    for row in per_run:
        del row["claims"]

    return {
        "depth": depth,
        "pool": {
            "pages": len(judgements),
            "judged": len(judged),
            "relevant": sum(1 for mark in judged.values() if mark),
            "claims": len({entry["claimId"] for entry in judgements}),
            "claimsWithRelevant": sum(1 for count in relevant_in_pool.values() if count),
        },
        "runs": per_run,
        "bootstrap": {"seed": seed, "resamples": resamples},
    }


# ----------------------------------------------------------------------
# Judging, in a terminal
# ----------------------------------------------------------------------


def judge(path: Path, ask=input, say=print) -> dict:
    """
    Every unjudged page, one at a time: the claim, the page's title,
    domain and address, and y (bears on the claim, for or against), n
    (does not), s (skip for now), q (stop). Saved after every answer, so
    stopping loses nothing; a later session resumes at the first
    unjudged page.
    """

    entries = load_judgements(path)
    pending = [entry for entry in entries if entry["relevant"] is None]
    done = 0

    say(f"{len(pending)} of {len(entries)} pooled pages to judge. y = bears on the claim (for or against), "
        "n = does not, s = skip, q = stop.")

    claim = None

    for entry in pending:

        if entry["claimId"] != claim:
            claim = entry["claimId"]
            say(f"\n[{claim}] {entry['claim']}")

        say(f"  {entry.get('title') or '(no title)'} - {entry.get('domain')}\n  {entry.get('url')}")

        while True:
            answer = (ask("  relevant? [y/n/s/q] ") or "").strip().lower()
            if answer in ("y", "n", "s", "q"):
                break

        if answer == "q":
            break

        if answer == "s":
            continue

        entry["relevant"] = answer == "y"
        done += 1
        save_judgements(path, entries)

    left = sum(1 for entry in entries if entry["relevant"] is None)
    say(f"\n{done} judged this session, {left} left.")

    return {"judged": done, "left": left}


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def _pct(value) -> str:

    return "n/a" if value is None else f"{value * 100:.1f}%"


def render(table: dict) -> str:

    p = table["pool"]
    depth = table["depth"]

    lines = [
        "# Pooled relevance judgements",
        "",
        f"Every run's top {depth} ranked sources per claim, pooled and judged once by a person "
        "(src/evaluation/pooling.py; TREC's method): "
        f"{p['pages']} pages over {p['claims']} claims, {p['judged']} judged, {p['relevant']} relevant; "
        f"{p['claimsWithRelevant']} claims have at least one relevant page. Means over claims with 95% bootstrap "
        "intervals; differences paired against the first run.",
        "",
        f"| Run | Precision@{depth} | Recall of the pool's relevant | MRR | Judged |",
        "|---|---|---|---|---|",
    ]

    for row in table["runs"]:
        m = row["metrics"]
        cells = [
            f"{_pct(m[name]['value'])} [{_pct(m[name]['low'])}, {_pct(m[name]['high'])}] (n={m[name]['n']})"
            if name != "mrr" else
            (f"{m[name]['value']:.3f} (n={m[name]['n']})" if m[name]["value"] is not None else "n/a")
            for name in METRICS
        ]
        lines.append(f"| {row['name']} | " + " | ".join(cells) + " |")

    if len(table["runs"]) > 1:
        lines += [
            "",
            f"| Run - {table['runs'][0]['name']} | Precision@{depth} | Recall | MRR | Judged |",
            "|---|---|---|---|---|",
        ]
        for row in table["runs"][1:]:
            cells = []
            for name in METRICS:
                d = row["vsBaseline"][name]
                if d.get("difference") is None:
                    cells.append("n/a")
                elif name == "mrr":
                    cells.append(f"{d['difference']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}] ({d['pairs']})")
                else:
                    cells.append(
                        f"{d['difference'] * 100:+.1f} pts [{d['low'] * 100:+.1f}, {d['high'] * 100:+.1f}] ({d['pairs']})"
                    )
            lines.append(f"| {row['name']} | " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"

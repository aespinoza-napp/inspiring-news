"""
Does the pipeline give the same verdict twice? (`cli consistency --run A
--run B`)

The annotator labels a fifth of the test half a second time, blind, to
measure whether the guide is applied consistently (labeller/app.py,
`review_sample`). The same fifth is run through the pipeline a second
time (`run --split test --sample recheck`), to measure the same thing of
the system: an open-web pipeline is not a function of its input. The
web it searches changes between two runs, search engines answer
differently, and a local model at temperature 0 still varies.

Reported over the claims both runs scored:

- **Verdict agreement and Cohen's kappa** between the two runs, with
  intervals, and the confusion of run A's verdicts by run B's. The kappa
  is on the scale of the annotator's self-agreement, so the two
  ceilings can be put side by side.
- **Where a change came from**: the overlap of the two runs' ranked
  evidence per claim (Jaccard over normalised URLs). A verdict that
  changed on the same evidence is the model's; one that changed with
  the evidence is the web's.
- **Whether it matters**: each run's accuracy against gold on the same
  claims, and the paired difference. Two runs can disagree on a claim
  and both be wrong.

docs/decisions/evaluation.md, "Consistency".
"""

from __future__ import annotations

import random
from pathlib import Path

from src.evaluation import metrics
from src.evaluation.metrics import DEFAULT_RESAMPLES, DEFAULT_SEED, LEVEL, SCORED, outcome
from src.evaluation.report import _table, default_reports_root, load_run, num, pct, with_ci
from src.evaluation.stats import bootstrap_mean, mean, percentile
from src.evaluation.store import write_json
from src.services.fact_checker.retrieval.evidence_retriever import _comparable


def _first(record: dict) -> str:
    """The first pass's verdict: before a second look, if one was taken."""

    return (record.get("secondLook") or {}).get("first_verdict") or record["verdict"]


def jaccard(a: set, b: set) -> float:

    if not a and not b:
        return 1.0

    return len(a & b) / len(a | b)


def _ranked(record: dict) -> set[str]:

    return {_comparable(item["url"]) for item in record.get("evidence") or []}


def consistency(run_a, run_b, *, seed: int = DEFAULT_SEED, resamples: int = DEFAULT_RESAMPLES) -> dict:

    a = {record["id"]: record for record in run_a.records}
    b = {record["id"]: record for record in run_b.records}

    shared = sorted(set(a) & set(b))

    scored = [i for i in shared if outcome(a[i]) == SCORED and outcome(b[i]) == SCORED]

    set_apart = {
        i: {"a": outcome(a[i]), "b": outcome(b[i])}
        for i in shared if i not in scored
    }

    # Run A in the gold seat: kappa and the confusion matrix are symmetric
    # in what they measure, and the code that computes them is the one
    # the gold comparison uses.
    pairs = [(a[i]["verdict"], b[i]["verdict"]) for i in scored]
    raw = [(a[i]["rawVerdict"] or "UNVERIFIED", b[i]["rawVerdict"] or "UNVERIFIED") for i in scored]
    # Runs with the second look on: the first pass's verdicts too, so a
    # change the second look added is told from one already there.
    first = [(_first(a[i]), _first(b[i])) for i in scored]

    overlap = {i: jaccard(_ranked(a[i]), _ranked(b[i])) for i in scored}

    changed = [i for i in scored if a[i]["verdict"] != b[i]["verdict"]]

    gold_a = [(a[i]["label"], a[i]["verdict"]) for i in scored]
    gold_b = [(b[i]["label"], b[i]["verdict"]) for i in scored]

    return {
        "runA": {"run": str(run_a.directory), "key": run_a.key, "dataset": run_a.dataset_stem,
                 "startedAt": run_a.manifest.get("startedAt")},
        "runB": {"run": str(run_b.directory), "key": run_b.key, "dataset": run_b.dataset_stem,
                 "startedAt": run_b.manifest.get("startedAt")},
        "model": run_a.model if run_a.model == run_b.model else f"{run_a.model} / {run_b.model}",
        "seed": seed,
        "resamples": resamples,
        "shared": len(shared),
        "onlyA": sorted(set(a) - set(b)),
        "onlyB": sorted(set(b) - set(a)),
        "scored": len(scored),
        "setApart": set_apart,
        "verdict": _agreement(pairs, seed=seed, resamples=resamples),
        "rawVerdict": _agreement(raw, seed=seed, resamples=resamples),
        "firstPass": (
            _agreement(first, seed=seed, resamples=resamples)
            if any(a[i].get("secondLook") or b[i].get("secondLook") for i in scored) else None
        ),
        "confusion": metrics.confusion(pairs),
        "evidenceOverlap": {
            "mean": mean(list(overlap.values())),
            "ci": bootstrap_mean(list(overlap.values()), seed=seed, resamples=resamples),
            "identical": sum(1 for value in overlap.values() if value == 1.0),
            "disjoint": sum(1 for value in overlap.values() if value == 0.0),
        },
        # A change on the very same ranked evidence is the model's alone.
        "changedOnSameEvidence": sorted(i for i in changed if overlap[i] == 1.0),
        "changedWithEvidence": sorted(i for i in changed if overlap[i] < 1.0),
        "changes": [
            {
                "id": i,
                "claim": a[i]["claim"],
                "gold": a[i]["label"],
                "a": a[i]["verdict"],
                "b": b[i]["verdict"],
                "evidenceOverlap": round(overlap[i], 3),
            }
            for i in changed
        ],
        "gold": {
            "accuracyA": metrics.accuracy(metrics.counts(gold_a)),
            "accuracyB": metrics.accuracy(metrics.counts(gold_b)),
            "comparison": metrics.paired_bootstrap(gold_a, gold_b, seed=seed, resamples=resamples).get("accuracy"),
            **metrics.discordant(gold_a, gold_b),
        },
    }


def _agreement(pairs: list[tuple[str, str]], *, seed: int, resamples: int) -> dict:
    """Observed agreement and kappa between two labellings, with intervals."""

    point = metrics.counts(pairs)

    draws = {"agreement": [], "kappa": []}

    if pairs:

        rng = random.Random(seed)
        n = len(pairs)

        for _ in range(resamples):
            c = metrics.counts(pairs[rng.randrange(n)] for _ in range(n))
            draws["agreement"].append(metrics.accuracy(c))
            kappa = metrics.cohen_kappa(c)
            if kappa is not None:
                draws["kappa"].append(kappa)

    tail = (1 - LEVEL) / 2 * 100

    def interval(values):
        return {
            "low": percentile(values, tail),
            "high": percentile(values, 100 - tail),
            "undefinedResamples": resamples - len(values) if pairs else None,
        }

    return {
        "n": point.n,
        "agreement": metrics.accuracy(point),
        "kappa": metrics.cohen_kappa(point),
        "ci": {"agreement": interval(draws["agreement"]), "kappa": interval(draws["kappa"])},
    }


def render_consistency(result: dict) -> str:

    verdict, raw, overlap, gold = (
        result["verdict"], result["rawVerdict"], result["evidenceOverlap"], result["gold"]
    )

    def started(side):
        return result[side]["startedAt"] or "?"

    lines = [
        "# Consistency: the same claims, run twice",
        "",
        f"Run A `{result['runA']['key']}` ({result['runA']['dataset']}, started {started('runA')}) "
        f"against run B `{result['runB']['key']}` ({result['runB']['dataset']}, started "
        f"{started('runB')}); model `{result['model']}`. {result['shared']} claims in both, "
        f"{result['scored']} scored in both. Bootstrap: {result['resamples']} resamples, seed "
        f"{result['seed']}.",
        "",
        _table(
            ["", "n", "Agreement [95% CI]", "Cohen's kappa [95% CI]"],
            [
                ["Verdict", str(verdict["n"]),
                 with_ci(verdict["agreement"], verdict["ci"]["agreement"]),
                 with_ci(verdict["kappa"], verdict["ci"]["kappa"], num)],
                ["The model's own verdict, before recalibration", str(raw["n"]),
                 with_ci(raw["agreement"], raw["ci"]["agreement"]),
                 with_ci(raw["kappa"], raw["ci"]["kappa"], num)],
                *([["The first pass's verdict, before any second look", str(result["firstPass"]["n"]),
                    with_ci(result["firstPass"]["agreement"], result["firstPass"]["ci"]["agreement"]),
                    with_ci(result["firstPass"]["kappa"], result["firstPass"]["ci"]["kappa"], num)]]
                  if result.get("firstPass") else []),
            ],
        ),
        "",
        f"Ranked evidence shared between the two runs (Jaccard, per claim): mean "
        f"{with_ci(overlap['mean'], overlap['ci'], num)}; identical for {overlap['identical']}, "
        f"disjoint for {overlap['disjoint']}.",
        "",
        f"Verdicts that changed on the very same evidence (the model's): "
        f"{', '.join(result['changedOnSameEvidence']) or 'none'}. "
        f"With different evidence (the web's): {', '.join(result['changedWithEvidence']) or 'none'}.",
        "",
        f"Against gold on the same claims: run A {pct(gold['accuracyA'])}, run B "
        f"{pct(gold['accuracyB'])}; only A right {gold['onlyA']}, only B right {gold['onlyB']}.",
        "",
    ]

    if result["changes"]:
        lines += [
            "## Claims whose verdict changed",
            "",
            _table(
                ["Id", "Claim", "Gold", "Run A", "Run B", "Evidence overlap"],
                [[c["id"], c["claim"][:120], c["gold"], c["a"], c["b"], num(c["evidenceOverlap"], 2)]
                 for c in result["changes"]],
            ),
            "",
        ]

    def ids(values):
        # A re-check run is a sample of the other by design: its missing
        # claims are a count, not a list to read.
        return ", ".join(values) if len(values) <= 10 else f"{len(values)} claims"

    if result["setApart"] or result["onlyA"] or result["onlyB"]:
        lines += [
            "## Left out",
            "",
            f"Set apart on either side: "
            + (", ".join(f"{i} ({v['a']} / {v['b']})" for i, v in result["setApart"].items()) or "none")
            + f". Only in A: {ids(result['onlyA']) or 'none'}. "
            + f"Only in B: {ids(result['onlyB']) or 'none'}.",
            "",
        ]

    return "\n".join(lines)


def write_consistency(
    run_a: str | Path,
    run_b: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:

    a, b = load_run(run_a), load_run(run_b)

    result = consistency(a, b, seed=seed, resamples=resamples)

    target = Path(root or default_reports_root()) / b.dataset_stem / "consistency"
    target.mkdir(parents=True, exist_ok=True)

    write_json(target / f"{a.key}-{b.key}.json", result)
    (target / f"{a.key}-{b.key}.md").write_text(render_consistency(result), encoding="utf-8", newline="\n")

    return target / f"{a.key}-{b.key}.md"

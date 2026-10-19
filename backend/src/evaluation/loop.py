"""
What the tuning loop found (`cli loop --run <dir>`), for a run made with
`run --loop` on the custom set's train half.

Two questions, kept apart:

1. **The loop**, which uses the gold label: of the claims whose first
   verdict disagrees with gold, how many a second look fixes, and of
   those it does not, whether the annotator's own pages give the gold
   label (the search never found them: `retrieval`), the pipeline's
   verdict (a person decides between model and label: `adjudicate`) or
   a third one (`reasoning`). That is a diagnosis of the train half, not
   a score: it chose which claims to look at by their label.
2. **The trigger**, which does not: what the pipeline's own rule
   (`second_look.doubt`: UNVERIFIED, or below the run's confidence) would
   do to accuracy if the second verdict replaced the first wherever it
   fires, paired over the same claims, with the flips each way. This is
   what decides whether `SECOND_LOOK_ENABLED` is worth turning on before
   the test half is run.

docs/decisions/evaluation.md, "The second look".
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.evaluation import metrics
from src.evaluation.metrics import DEFAULT_RESAMPLES, DEFAULT_SEED, SCORED, outcome
from src.evaluation.report import _table, load_run, num, pct, report_directory, with_ci
from src.evaluation.runner import LOOP_OUTCOMES, MANIFEST
from src.evaluation.store import write_json

OUTCOME_MEANING = {
    "agreed": "the first verdict is the gold label",
    "fixed": "the second look reached the gold label",
    "retrieval": "the annotator's pages give the gold label: the search never found them",
    "adjudicate": "the annotator's pages give the pipeline's verdict: a person decides, model or label",
    "reasoning": "the annotator's pages give a third verdict",
    "unreadable": "no annotator page could be read",
    "no_reference": "the row has no annotator links (an UNVERIFIED gold label needs none)",
    "unavailable": "the first pass's search or model was never reached",
}


def _second(record: dict) -> str | None:

    second = (record.get("loop") or {}).get("secondLook")

    return second["verdict"] if second else None


def policy(records: list[dict], rule) -> list[tuple[str, str]]:
    """(gold, verdict) with the second look's verdict wherever `rule` fires."""

    pairs = []

    for record in records:

        second = _second(record)

        verdict = second if second and rule(record) else record["verdict"]

        pairs.append((record["label"], verdict))

    return pairs


def _flips(first: list[tuple[str, str]], after: list[tuple[str, str]], records: list[dict]) -> dict:

    fixed = [r["id"] for (g, a), (_, b), r in zip(first, after, records) if a != g and b == g]
    broken = [r["id"] for (g, a), (_, b), r in zip(first, after, records) if a == g and b != g]
    changed = sum(1 for (_, a), (_, b) in zip(first, after) if a != b)

    return {"changed": changed, "wrongToRight": fixed, "rightToWrong": broken}


def _first(record: dict) -> str:
    """The first pass's verdict: before the pipeline's own second look, if it took one."""

    return (record.get("secondLook") or {}).get("first_verdict") or record["verdict"]


def second_look_report(run, *, seed: int = DEFAULT_SEED, resamples: int = DEFAULT_RESAMPLES) -> dict:
    """
    A run with `second_look_enabled` (the test half): the pipeline took
    its second looks itself, with no gold, and each record keeps the
    first verdict beside the final one. Accuracy with the first verdicts
    against the final ones, paired, for the trigger the run used and for
    UNVERIFIED alone (the final verdict only where that one fired).
    """

    scored = [record for record in run.records if outcome(record) == SCORED]

    if not any(record.get("secondLook") for record in run.records):
        raise ValueError(f"{run.directory}: no second look and no loop in any record")

    first = [(record["label"], _first(record)) for record in scored]

    rules = {
        "unverifiedOrUnsure": lambda record: bool(record.get("secondLook")),
        "unverifiedOnly": lambda record: (record.get("secondLook") or {}).get("trigger") == "unverified",
    }

    triggers = {}

    for name, rule in rules.items():

        after = [
            (record["label"], record["verdict"] if rule(record) else _first(record))
            for record in scored
        ]

        triggers[name] = {
            "fired": sum(1 for record in scored if rule(record)),
            "comparison": metrics.paired_bootstrap(first, after, seed=seed, resamples=resamples),
            "final": {**metrics.classification(after), "ci": metrics.bootstrap(after, seed=seed, resamples=resamples)},
            **_flips(first, after, scored),
        }

    looks = [record["secondLook"] for record in scored if record.get("secondLook")]

    return {
        "kind": "secondLook",
        "run": str(run.directory),
        "key": run.key,
        "model": run.model,
        "dataset": run.dataset_stem,
        "seed": seed,
        "resamples": resamples,
        "claims": len(run.records),
        "scored": len(scored),
        "firstPass": {**metrics.classification(first), "ci": metrics.bootstrap(first, seed=seed, resamples=resamples)},
        "triggers": triggers,
        "secondLooks": len(looks),
        "byTrigger": dict(Counter(look["trigger"] for look in looks)),
        "withNewEvidence": sum(1 for look in looks if look.get("new_evidence")),
        "searchUnavailable": sum(1 for look in looks if look.get("search_unavailable")),
        "secondLookSeconds": round(sum(
            (record.get("latency") or {}).get("secondLook") or 0 for record in scored
        ), 1),
    }


def render_second_look(result: dict) -> str:

    first = result["firstPass"]

    lines = [
        f"# The second look, as the pipeline takes it: {result['dataset']}",
        "",
        f"Run `{result['key']}`, model `{result['model']}`, `second_look_enabled`. "
        f"{result['scored']} of {result['claims']} claims scored. Bootstrap: "
        f"{result['resamples']} resamples, seed {result['seed']}.",
        "",
        f"First pass: accuracy {with_ci(first['accuracy'], first['ci'].get('accuracy'))}, "
        f"macro-F1 {with_ci(first['macroF1'], first['ci'].get('macroF1'), num)}. "
        f"{result['secondLooks']} second looks "
        f"({', '.join(f'{k} {v}' for k, v in result['byTrigger'].items()) or 'none'}), "
        f"{result['withNewEvidence']} with a new source in the final evidence, "
        f"{result['searchUnavailable']} whose follow-up search failed; "
        f"{result['secondLookSeconds']} s spent in them.",
        "",
        _table(
            ["Rule", "Fired", "Accuracy first", "final", "Difference [95% CI]", "Macro-F1 final",
             "Wrong to right", "Right to wrong"],
            [
                [
                    name,
                    str(block["fired"]),
                    pct(block["comparison"].get("accuracy", {}).get("a")),
                    pct(block["comparison"].get("accuracy", {}).get("b")),
                    _difference(block["comparison"].get("accuracy") or {}),
                    with_ci(block["final"]["macroF1"], block["final"]["ci"].get("macroF1"), num),
                    str(len(block["wrongToRight"])),
                    str(len(block["rightToWrong"])),
                ]
                for name, block in result["triggers"].items()
            ],
        ),
        "",
    ]

    return "\n".join(lines)


def loop_report(run, *, seed: int = DEFAULT_SEED, resamples: int = DEFAULT_RESAMPLES) -> dict:

    looped = [record for record in run.records if record.get("loop")]

    if not looped:
        raise ValueError(f"{run.directory}: no record has a loop - was it run with --loop?")

    scored = [record for record in looped if outcome(record) == SCORED]

    first = [(record["label"], record["verdict"]) for record in scored]

    outcomes = Counter(record["loop"]["outcome"] for record in looped)

    by_outcome = {
        name: sorted(record["id"] for record in looped if record["loop"]["outcome"] == name)
        for name in LOOP_OUTCOMES
    }

    disagreements = [record for record in scored if record["loop"]["disagrees"]]

    # The rule the pipeline would apply, with no gold: the trigger the run
    # recorded (UNVERIFIED or below its confidence), and UNVERIFIED alone.
    policies = {
        "unverifiedOrUnsure": lambda record: bool(record["loop"]["trigger"]),
        "unverifiedOnly": lambda record: record["loop"]["trigger"] == "unverified",
    }

    triggers = {}

    for name, rule in policies.items():

        after = policy(scored, rule)

        triggers[name] = {
            "fired": sum(1 for record in scored if rule(record)),
            "comparison": metrics.paired_bootstrap(first, after, seed=seed, resamples=resamples),
            **_flips(first, after, scored),
        }

    by_origin = {}

    for origin in sorted({record.get("origin") or "unknown" for record in disagreements}):
        part = [record for record in disagreements if (record.get("origin") or "unknown") == origin]
        by_origin[origin] = dict(Counter(record["loop"]["outcome"] for record in part))

    usage = [record["loop"].get("usage") or {} for record in looped]

    return {
        "run": str(run.directory),
        "key": run.key,
        "model": run.model,
        "dataset": run.dataset_stem,
        "seed": seed,
        "resamples": resamples,
        "claims": len(looped),
        "scored": len(scored),
        "firstPass": {**metrics.classification(first), "ci": metrics.bootstrap(first, seed=seed, resamples=resamples)},
        "disagreements": len(disagreements),
        "outcomes": {name: outcomes.get(name, 0) for name in LOOP_OUTCOMES},
        "outcomeIds": by_outcome,
        "byOrigin": by_origin,
        # With the gold label choosing which claims get a second look: an
        # upper bound on what a perfect trigger could recover.
        "goldTriggered": {
            "accuracy": metrics.accuracy(metrics.counts(policy(scored, lambda r: r["loop"]["disagrees"]))),
        },
        "triggers": triggers,
        "adjudicate": [_case(record) for record in looped if record["loop"]["outcome"] == "adjudicate"],
        # What the model kept answering on the annotator's own pages. A
        # lean shows here: on X-Fact the 3B model answered FALSE to 43 of
        # 64 claims, and a list of FALSE against TRUE labels says more
        # about the model than about the labels.
        "adjudicateVerdicts": dict(Counter(
            f'{record["label"]} -> {record["loop"]["reference"]["verdict"]}'
            for record in looped if record["loop"]["outcome"] == "adjudicate"
        ).most_common()),
        "retrieval": [_case(record) for record in looped if record["loop"]["outcome"] == "retrieval"],
        "cost": {
            "secondLooks": sum(1 for record in looped if record["loop"].get("secondLook")),
            "referenceChecks": sum(1 for record in looped if record["loop"].get("reference")),
            "llmCalls": sum(u.get("calls") or 0 for u in usage),
            "seconds": round(sum(record["loop"].get("seconds") or 0 for record in looped), 1),
        },
    }


def _case(record: dict) -> dict:

    loop = record["loop"]
    reference = loop.get("reference") or {}

    return {
        "id": record["id"],
        "claim": record["claim"],
        "origin": record.get("origin"),
        "gold": record["label"],
        "first": loop["firstVerdict"],
        "secondLook": _second(record),
        "reference": reference.get("verdict"),
        "referenceExplanation": reference.get("explanation"),
        "pagesRead": reference.get("pagesRead"),
    }


def render_loop(result: dict) -> str:

    first = result["firstPass"]

    lines = [
        f"# The tuning loop: {result['dataset']}",
        "",
        f"Run `{result['key']}`, model `{result['model']}`. {result['scored']} of "
        f"{result['claims']} claims scored. Bootstrap: {result['resamples']} resamples, "
        f"seed {result['seed']}.",
        "",
        f"First pass: accuracy {with_ci(first['accuracy'], first['ci'].get('accuracy'))}, "
        f"{result['disagreements']} claims disagree with gold.",
        "",
        "## What the loop made of each claim",
        "",
        _table(
            ["Outcome", "Claims", "Meaning", "Ids"],
            [
                [name, str(result["outcomes"][name]), OUTCOME_MEANING[name],
                 ", ".join(result["outcomeIds"][name]) if name != "agreed" else ""]
                for name in LOOP_OUTCOMES
                if result["outcomes"][name]
            ],
        ),
        "",
        "Disagreements by origin: "
        + "; ".join(f"{origin} {dict(counts)}" for origin, counts in result["byOrigin"].items()),
        "",
        f"With the gold label choosing which claims get a second look (an upper bound, "
        f"not a score): accuracy {pct(result['goldTriggered']['accuracy'])}.",
        "",
        "## The trigger, without gold",
        "",
        "The second verdict in place of the first wherever the rule fires, paired over the same claims.",
        "",
        _table(
            ["Rule", "Fired", "Accuracy before", "after", "Difference [95% CI]", "Wrong to right", "Right to wrong"],
            [
                [
                    name,
                    str(block["fired"]),
                    pct(block["comparison"].get("accuracy", {}).get("a")),
                    pct(block["comparison"].get("accuracy", {}).get("b")),
                    _difference(block["comparison"].get("accuracy") or {}),
                    str(len(block["wrongToRight"])),
                    str(len(block["rightToWrong"])),
                ]
                for name, block in result["triggers"].items()
            ],
        ),
        "",
    ]

    for title, key in (("For a person to decide: model or label", "adjudicate"),
                       ("The search missed what the annotator found", "retrieval")):

        if not result[key]:
            continue

        lead = []

        if key == "adjudicate":
            lead = [
                "Gold label -> the model's verdict on the annotator's pages: "
                + "; ".join(f"{pair} ({n})" for pair, n in result["adjudicateVerdicts"].items()),
                "",
            ]

        lines += [
            f"## {title}",
            "",
            *lead,
            _table(
                ["Id", "Claim", "Gold", "First", "Second look", "On the annotator's pages", "Why"],
                [
                    [case["id"], case["claim"][:120], case["gold"], case["first"],
                     case["secondLook"] or "", case["reference"] or "",
                     (case["referenceExplanation"] or "")[:200].replace("|", "/")]
                    for case in result[key]
                ],
            ),
            "",
        ]

    cost = result["cost"]

    lines += [
        "## Cost",
        "",
        f"{cost['secondLooks']} second looks and {cost['referenceChecks']} checks against the "
        f"annotator's pages: {cost['llmCalls']} LLM calls, {cost['seconds']} s in all.",
        "",
    ]

    return "\n".join(lines)


def _difference(block: dict) -> str:

    if block.get("difference") is None:
        return "n/a"

    return f"{block['difference'] * 100:+.1f} [{_signed(block.get('low'))}, {_signed(block.get('high'))}]"


def _signed(value) -> str:

    return "n/a" if value is None else f"{value * 100:+.1f}"


def write_loop_report(
    run_directory: str | Path,
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:

    run = load_run(run_directory)

    # A tuning run (--loop) gets the loop's report; a run whose pipeline
    # took its own second looks (second_look_enabled) gets its first
    # verdicts against its final ones.
    if any(record.get("loop") for record in run.records):
        result = loop_report(run, seed=seed, resamples=resamples)
        text = render_loop(result)
    else:
        result = second_look_report(run, seed=seed, resamples=resamples)
        text = render_second_look(result)

    target = report_directory(run, root)
    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "loop.json", result)
    (target / "loop.md").write_text(text, encoding="utf-8", newline="\n")

    if not (target / MANIFEST).exists():
        (target / MANIFEST).write_bytes((run.directory / MANIFEST).read_bytes())

    return target

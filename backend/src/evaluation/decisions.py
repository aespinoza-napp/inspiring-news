"""Training and test sets for the Laya decisions, from labels already here.

    uv run python -m src.evaluation.decisions build

writes `data/evaluation/experiments/laya/data/<decision>_{train,test}.jsonl`
in the JSONL `laya-train` and `laya-evals` read: one case per line, its
`state`, its `questions` (from `src/config/decisions.py`, so training and
the pipeline ask the same thing), and the answer as `expected` (a label)
or `gold` (a distribution). A test line also carries `meta`: the id and
what the pipeline's current component answered for the same item, so the
comparison is paired.

Which items train and which test is fixed by the rule written before any
run (`experiments/laya/rule.md`): a different day's rounds, a different
week's batches, never the custom set's test half. Every label is the AI
pass's unless the rule says otherwise.
"""

import argparse
import json
import math
import random
from pathlib import Path
from urllib.parse import urlsplit

from src.config.decisions import CHECKABLE_CLAIM, TOPIC_GROUP_QUESTION, WORTH_OFFERING, candidate_state
from src.config.topics import TOPIC_GROUPS
from src.evaluation.experiments import RESAMPLES, SEED, _rank_auc, auc_interval, percentile, rounded

EVALUATION = Path(__file__).resolve().parents[2] / "data" / "evaluation"
EXPERIMENTS = EVALUATION / "experiments"
OUT = EXPERIMENTS / "laya" / "data"

# D3's split: the labelling batches before 2026-10-09 train, the rest test.
CHECKABLE_TEST_FROM = "2026-10-09"


def article_key(url: str) -> str:
    """Host and path, as the job store, cache and lake match an article."""
    parts = urlsplit(url)
    return parts.netloc.lower().removeprefix("www.") + parts.path.rstrip("/")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def labelled_candidates() -> tuple[list[dict], list[dict]]:
    """(train, test) candidates: 2026-10-09 and 10-13 train, 10-06 tests."""
    train = _load(EXPERIMENTS / "alignment" / "20261009T120000Z" / "labelled.json")["candidates"]
    train += _load(EXPERIMENTS / "emphasis" / "reserve-labels.json")["candidates"]
    test = _load(EXPERIMENTS / "ranking" / "20261006T133348Z" / "result.json")["candidates"]

    held_out = {article_key(c["url"]) for c in test}
    seen: set[str] = set()
    kept = []
    for candidate in train:
        key = article_key(candidate["url"])
        if key in held_out or key in seen:
            continue
        seen.add(key)
        kept.append(candidate)
    return kept, test


def worth_offering_cases() -> tuple[list[dict], list[dict]]:
    train, test = labelled_candidates()
    question = {"worth_offering": WORTH_OFFERING}

    def case(c: dict, with_meta: bool) -> dict:
        line = {
            "state": candidate_state(c.get("title"), c.get("summary")),
            "questions": question,
            "expected": {"worth_offering": int(c["hand"])},
        }
        if with_meta:
            line["meta"] = {
                "id": c["url"],
                "round": c.get("round"),
                "language": c.get("lang"),
                # The comparators, read from the ranking experiment's record:
                # the 3B AI selection's score (0-10) and the story's own reading.
                "ai": c.get("ai"),
                "impact": c.get("impact"),
            }
        return line

    return [case(c, False) for c in train], [case(c, True) for c in test]


def topic_group_cases() -> tuple[list[dict], list[dict]]:
    train_candidates, _ = labelled_candidates()
    question = {"topic_group": TOPIC_GROUP_QUESTION}

    train = []
    for c in train_candidates:
        groups = [g for g in c.get("belongsTo") or [] if g in TOPIC_GROUPS]
        if not groups:
            continue
        share = 1.0 / len(groups)
        train.append({
            "state": candidate_state(c.get("title"), c.get("summary")),
            "questions": question,
            "gold": {"topic_group": {"probabilities": {
                g: (share if g in groups else 0.0) for g in TOPIC_GROUPS
            }}},
        })

    # The topic experiment's articles, read through the labelling queue:
    # their title and the claims proposed from them.
    articles = {}
    for path in sorted((EVALUATION / "queue").glob("*.json")):
        for article in _load(path)["articles"]:
            articles[article["url"]] = article
    rows = _load(EXPERIMENTS / "topics" / "20261020T093630Z" / "result.json")["rows"]

    test = []
    for row in rows:
        article = articles.get(row["url"])
        if article is None:
            continue
        sentences = " ".join(claim["text"] for claim in article["claims"])
        test.append({
            "state": f"{article['title'].strip()}\n{sentences}".strip(),
            "questions": question,
            "expected": {"topic_group": row["goldGroup"]},
            "meta": {"id": row["url"], "language": article.get("language"),
                     "classifier": row["topGroup"]},
        })
    return train, test


def checkable_claim_cases() -> tuple[list[dict], list[dict]]:
    question = {"checkable_claim": CHECKABLE_CLAIM}
    train, test = [], []
    for path in sorted((EVALUATION / "queue").glob("*.json")):
        batch = _load(path)
        day = batch.get("date") or path.stem
        for article in batch["articles"]:
            for claim in article["claims"]:
                if claim.get("status") not in ("labelled", "skipped"):
                    continue
                line = {
                    "state": f"Headline: {article['title'].strip()}\nSentence: {claim['text'].strip()}",
                    "questions": question,
                    "expected": {"checkable_claim": claim["status"] == "labelled"},
                }
                if day >= CHECKABLE_TEST_FROM:
                    line["meta"] = {"id": f"{day}:{article['url']}:{claim['text'][:60]}",
                                    "language": article.get("language"),
                                    "selectorScore": claim.get("score"),
                                    "skipReason": claim.get("skipReason")}
                    test.append(line)
                else:
                    train.append(line)
    return train, test


BUILDERS = {
    "worth_offering": worth_offering_cases,
    "topic_group": topic_group_cases,
    "checkable_claim": checkable_claim_cases,
}


def write_jsonl(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")


def build(out: Path = OUT) -> dict[str, dict[str, int]]:
    counts = {}
    for name, builder in BUILDERS.items():
        train, test = builder()
        write_jsonl(out / f"{name}_train.jsonl", train)
        write_jsonl(out / f"{name}_test.jsonl", test)
        counts[name] = {"train": len(train), "test": len(test)}
    return counts


# ---------- scoring ----------
#
# The predictions are written by inference/ (`python -m src.decisions
# predict`), which holds the model; they are scored here, beside the
# harness's other statistics, against the comparator recorded in each
# test line's `meta`. Paired: both sides resampled over the same items.


def _laya_value(decision: str, answer: dict):
    if decision == "worth_offering":
        return answer["score"]              # the expected level, 0-2
    if decision == "checkable_claim":
        return answer["noul"]               # P(true)
    return answer["choice"]                 # topic_group


def _paired(items: list, stat, seed: int = SEED, resamples: int = RESAMPLES) -> dict:
    """stat(items) for side 0 and 1, and the bootstrap interval of 1 - 0."""

    a, b = stat(items, 0), stat(items, 1)
    rng = random.Random(seed)
    n = len(items)
    differences = []
    for _ in range(resamples):
        draw = [items[rng.randrange(n)] for _ in range(n)]
        da, db = stat(draw, 0), stat(draw, 1)
        if da is not None and db is not None:
            differences.append(db - da)
    return {
        "comparator": rounded(a, 3), "laya": rounded(b, 3),
        "difference": rounded(b - a, 3) if a is not None and b is not None else None,
        "low": rounded(percentile(differences, 2.5), 3),
        "high": rounded(percentile(differences, 97.5), 3),
        "n": n,
    }


def score(decision: str, predictions: Path) -> dict:
    """The rule's primary metric for one decision: comparator, Laya, B - A [95% CI]."""

    lines = [json.loads(line) for line in predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    for line in lines:
        expected = line["expected"][decision]
        laya = _laya_value(decision, line["answers"][decision])
        meta = line["meta"] or {}
        if decision == "worth_offering":
            rows.append((meta.get("ai"), laya, expected, meta.get("impact")))
        elif decision == "checkable_claim":
            rows.append((meta.get("selectorScore"), laya, expected))
        else:
            rows.append((meta.get("classifier"), laya, expected))

    seconds = sorted(line.get("seconds", 0.0) for line in lines)
    result = {"decision": decision, "predictions": str(predictions), "n": len(rows),
              "secondsMedian": rounded(seconds[len(seconds) // 2], 3) if seconds else None}

    if decision == "worth_offering":
        clearly = lambda items, side: _rank_auc([(r[side], r[2] == 2) for r in items if r[side] is not None])
        worth = lambda items, side: _rank_auc([(r[side], r[2] >= 1) for r in items if r[side] is not None])
        result["primary"] = {"metric": "AUC, clearly positive against the rest", **_paired(rows, clearly)}
        result["worthOffering"] = {"metric": "AUC, worth offering (1 or 2) against not", **_paired(rows, worth)}
        result["storyReading"] = auc_interval([(r[3], r[2] == 2) for r in rows if r[3] is not None])
    elif decision == "checkable_claim":
        checkable = lambda items, side: _rank_auc([(r[side], bool(r[2])) for r in items if r[side] is not None])
        result["primary"] = {"metric": "AUC, kept as a claim against skipped", **_paired(rows, checkable)}
    else:
        right = lambda items, side: (sum(1 for r in items if r[side] == r[2]) / len(items)) if items else None
        result["primary"] = {"metric": "group accuracy", **_paired(rows, right)}

    primary = result["primary"]
    result["adopted"] = primary["low"] is not None and primary["low"] > 0
    return result


TOPIC_SYSTEMS = ("bge-m3", "laya zero-shot", "laya fine-tuned")


def _mcnemar(only_a: int, only_b: int) -> float:
    """Exact two-sided McNemar p on the discordant pairs."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare_topic_groups(zero_shot: Path, finetuned: Path) -> dict:
    """
    The topic classifier (bge-m3, `meta.classifier`) against Laya untrained
    and fine-tuned on the same articles: accuracy with paired intervals,
    each group's recall, the confusion tables, who is right alone, and -
    exploratory, chosen on this test set, so never adoptable from here -
    what a combination of the two would have scored.
    """

    def read(path):
        return {line["meta"]["id"]: line for line in map(json.loads, path.read_text(encoding="utf-8").splitlines())}

    zs, ft = read(zero_shot), read(finetuned)
    items = []
    for key, line in ft.items():
        answer = line["answers"]["topic_group"]
        items.append({
            "id": key,
            "language": line["meta"].get("language"),
            "gold": line["expected"]["topic_group"],
            "bge-m3": line["meta"]["classifier"],
            "laya zero-shot": zs[key]["answers"]["topic_group"]["choice"],
            "laya fine-tuned": answer["choice"],
            "layaProbability": answer["probabilities"][answer["choice"]],
        })

    def accuracy(system):
        return lambda rows, side=None: (sum(r[system] == r["gold"] for r in rows) / len(rows)) if rows else None

    def versus(system):
        return _paired(items, lambda rows, side: accuracy("bge-m3" if side == 0 else system)(rows))

    groups = list(TOPIC_GROUPS)
    result = {"n": len(items), "accuracy": {}, "perGroup": {}, "confusion": {}, "byLanguage": {}}
    for system in TOPIC_SYSTEMS:
        right = sum(r[system] == r["gold"] for r in items)
        result["accuracy"][system] = {"right": right, "share": rounded(right / len(items), 3),
                                      **({"vsBgeM3": versus(system)} if system != "bge-m3" else {})}
        result["perGroup"][system] = {
            g: [sum(r[system] == g for r in items if r["gold"] == g), sum(r["gold"] == g for r in items)]
            for g in groups
        }
        result["confusion"][system] = {
            g: {h: sum(1 for r in items if r["gold"] == g and r[system] == h) for h in groups} for g in groups
        }
        result["byLanguage"][system] = {
            lang: [sum(r[system] == r["gold"] for r in items if r["language"] == lang),
                   sum(r["language"] == lang for r in items)]
            for lang in sorted({r["language"] for r in items})
        }

    a, b = "bge-m3", "laya fine-tuned"
    both = sum(r[a] == r["gold"] and r[b] == r["gold"] for r in items)
    only_a = sum(r[a] == r["gold"] and r[b] != r["gold"] for r in items)
    only_b = sum(r[a] != r["gold"] and r[b] == r["gold"] for r in items)
    result["agreement"] = {
        "agree": sum(r[a] == r[b] for r in items),
        "agreeAndRight": sum(r[a] == r[b] == r["gold"] for r in items),
        "bothRight": both, "onlyBgeM3": only_a, "onlyLaya": only_b,
        "neither": len(items) - both - only_a - only_b,
        "mcnemarP": rounded(_mcnemar(only_a, only_b), 3),
        "eitherRight": both + only_a + only_b,
        "disagreements": [
            {k: r[k] for k in ("id", "gold", "bge-m3", "laya fine-tuned", "layaProbability")}
            for r in items if r[a] != r[b]
        ],
    }
    # Exploratory: where they disagree, Laya's group when its own
    # probability reaches t, else the classifier's.
    result["combination"] = {
        str(t): sum((r[b] if r[a] != r[b] and r["layaProbability"] >= t else r[a]) == r["gold"] for r in items)
        for t in (0.5, 0.7, 0.8, 0.9, 0.95)
    }
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.evaluation.decisions")
    sub = parser.add_subparsers(dest="command", required=True)
    build_cmd = sub.add_parser("build", help="write the train and test JSONL of every decision")
    build_cmd.add_argument("--out", type=Path, default=OUT)
    score_cmd = sub.add_parser("score", help="score a predictions file against its comparator")
    score_cmd.add_argument("--decision", required=True, choices=sorted(BUILDERS))
    score_cmd.add_argument("--predictions", type=Path, required=True)
    topics_cmd = sub.add_parser("compare-topics", help="bge-m3 against Laya untrained and fine-tuned, topic group")
    topics_cmd.add_argument("--zero-shot", type=Path, default=EXPERIMENTS / "laya" / "predictions" / "topic_group_multilingual.jsonl")
    topics_cmd.add_argument("--finetuned", type=Path, default=EXPERIMENTS / "laya" / "predictions" / "topic_group_finetuned.jsonl")
    args = parser.parse_args(argv)

    if args.command == "compare-topics":
        print(json.dumps(compare_topic_groups(args.zero_shot, args.finetuned), indent=2, ensure_ascii=False))
        return

    if args.command == "build":
        for name, count in build(args.out).items():
            print(f"{name}: {count['train']} train, {count['test']} test")
    else:
        print(json.dumps(score(args.decision, args.predictions), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""
Each phase of the pipeline against the other ways of doing it - the plan of
2026-11-10 (session d6b45b1c): the local pipeline, local LLMs, Claude through
the subscription's headless CLI (`src/evaluation/headless_claude.py`, never
the API) and a person, in quality, time and cost, on fixed inputs.

    uv run python -m src.evaluation.frameworks topics-fetch            # the 58 labelled articles' text, once
    uv run python -m src.evaluation.frameworks topics --model embedding
    uv run python -m src.evaluation.frameworks topics --model qwen3.5:4b-bench
    uv run python -m src.evaluation.frameworks topics --model claude-headless:haiku
    uv run python -m src.evaluation.frameworks report

The other phases reuse the harness: review is `cli writing run --model
claude-headless:<m>` (the corrector's own prompt over the 36 planted-defect
texts), fact-checking is `cli run --replay <run> --model claude-headless:<m>`
(the same evidence as the run it replays). `report` gathers what exists.

Topics
------

The gold is the annotator's topic per article as the 20 Oct experiment
recorded it (`experiments/topics/20261020T093630Z/result.json`, 58 rows), so
nothing here reads the labeller's fact files. The text is fetched once with
the extraction cascade and frozen in `experiments/frameworks/topics/articles.jsonl`:
every contender reads the same title and the same first `CHARS` characters.
The embedding classifier reads the whole body, as the pipeline does: its
cost per article is part of what is compared.

Caveat, said in the report: many topic labels came from an AI pass. A
Claude contender agreeing with labels a Claude wrote measures agreement, not
accuracy, until a person has reviewed them.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.config.topics import GROUP_OF, TOPICS
from src.evaluation.experiments import interval
from src.evaluation.stats import rounded

BACKEND = Path(__file__).resolve().parents[2]
OUT = BACKEND / "data/evaluation/experiments/frameworks"
TOPICS_OUT = OUT / "topics"
ARTICLES = TOPICS_OUT / "articles.jsonl"
GOLD = BACKEND / "data/evaluation/experiments/topics/20261020T093630Z/result.json"

CHARS = 3000

TOPIC_KEY = {topic.name: key for key, topic in TOPICS.items()}

SYSTEM = (
    "You classify news articles into a fixed list of topics. "
    "Answer with one JSON object only: {\"topics\": [\"<key>\", \"<key>\", \"<key>\"]} - "
    "the three topic keys that fit the article best, best first, using only keys from the list."
)


def now() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict]:

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def topic_list() -> str:

    return "\n".join(f"- {key}: {topic.name} - {topic.description}" for key, topic in TOPICS.items())


def user_prompt(article: dict) -> str:

    return (
        f"Topics:\n{topic_list()}\n\n"
        f"Article ({article['language']}):\nTitle: {article['title']}\n\n{article['text'][:CHARS]}"
    )


def gold_rows() -> list[dict]:

    return json.loads(GOLD.read_text(encoding="utf-8"))["rows"]


# ----------------------------------------------------------------------
# topics-fetch
# ----------------------------------------------------------------------

def cmd_topics_fetch(args) -> int:

    from src.services.fact_checker.retrieval.scraper import EvidenceScraper
    from src.services.scraper.extractor import ExtractorService

    have = {row["url"] for row in read_jsonl(ARTICLES)}
    extractor = ExtractorService()
    TOPICS_OUT.mkdir(parents=True, exist_ok=True)

    with ARTICLES.open("a", encoding="utf-8") as handle:
        for row in gold_rows():
            if row["url"] in have:
                continue
            started = time.perf_counter()
            try:
                news = extractor.extract(EvidenceScraper.GENERIC_SOURCE, row["url"], purpose="enrichment")
            except Exception as error:  # one page must not stop the rest
                news, failure = None, f"{type(error).__name__}: {error}"
            else:
                failure = None if news else "nothing extracted"
            entry = {
                "url": row["url"],
                "fetchedAt": now(),
                "seconds": round(time.perf_counter() - started, 2),
                "title": getattr(news, "title", None),
                "language": getattr(news, "language", None) or "en",
                "text": getattr(news, "content", None) or "",
                "error": failure,
            }
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{'OK ' if news else 'ERR'} {len(entry['text']):6d} {row['url']}", flush=True)

    return 0


# ----------------------------------------------------------------------
# topics
# ----------------------------------------------------------------------

def _embedding_contender():

    from src.processors.nlp.classifier import TopicClassifier

    classifier = TopicClassifier()

    def predict(article: dict) -> tuple[list[str], dict]:
        ranked = classifier.process(article["text"], threshold=0.0)
        ranked = sorted(ranked, key=lambda t: t.confidence or 0, reverse=True)
        return [TOPIC_KEY.get(t.topic, t.topic) for t in ranked[:3]], {}

    return predict


def _llm_contender(model: str):

    from src.evaluation.headless_claude import llm_client

    client = llm_client(model, timeout=300)

    def predict(article: dict) -> tuple[list[str], dict]:
        answer = client.complete_json(SYSTEM, user_prompt(article)) or {}
        topics = [t for t in (answer.get("topics") or []) if isinstance(t, str)]
        call = client.last_call() or {}
        return topics[:3], {"promptTokens": call.get("promptTokens"), "completionTokens": call.get("completionTokens"), "unusable": not topics or any(t not in TOPICS for t in topics[:3])}

    return predict


def cmd_topics(args) -> int:

    articles = {a["url"]: a for a in read_jsonl(ARTICLES) if a.get("text")}
    gold = {row["url"]: row["gold"] for row in gold_rows()}

    if not articles:
        raise SystemExit("no article text yet: run topics-fetch first")

    slug = args.model.replace(":", "-").replace("/", "-")
    out = TOPICS_OUT / f"{slug}.jsonl"
    done = {row["url"] for row in read_jsonl(out)}
    predict = _embedding_contender() if args.model == "embedding" else _llm_contender(args.model)

    todo = [url for url in gold if url in articles and url not in done][: args.limit or None]
    print(f"{args.model}: {len(todo)} to classify, {len(done)} done", flush=True)

    with out.open("a", encoding="utf-8") as handle:
        for url in todo:
            started = time.perf_counter()
            topics, extra = predict(articles[url])
            row = {"url": url, "gold": gold[url], "predicted": topics, "seconds": round(time.perf_counter() - started, 3), **extra}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            mark = "ok " if topics[:1] == [gold[url]] else "   "
            print(f"{mark}{row['seconds']:6.1f}s {gold[url]:>14} <- {topics}", flush=True)

    return 0


def score_topics(rows: list[dict]) -> dict:

    def share(test) -> dict:
        return interval([1.0 if test(r) else 0.0 for r in rows])

    return {
        "articles": len(rows),
        "top1": share(lambda r: r["predicted"][:1] == [r["gold"]]),
        "top3": share(lambda r: r["gold"] in r["predicted"][:3]),
        "group": share(lambda r: bool(r["predicted"]) and GROUP_OF.get(r["predicted"][0]) == GROUP_OF[r["gold"]]),
        "unusable": sum(1 for r in rows if r.get("unusable")),
        "medianSeconds": rounded(statistics.median(r["seconds"] for r in rows)) if rows else None,
        "totalSeconds": rounded(sum(r["seconds"] for r in rows)),
        "promptTokens": sum(r.get("promptTokens") or 0 for r in rows) or None,
        "completionTokens": sum(r.get("completionTokens") or 0 for r in rows) or None,
    }


# ----------------------------------------------------------------------
# standard sets: SIB-200 (topics) and CoNLL (entities), en and es
# ----------------------------------------------------------------------

BENCH = BACKEND / "data/evaluation/benchmarks"
BENCH_OUT = OUT / "standard"

ROWS_API = "https://datasets-server.huggingface.co/rows?dataset={dataset}&config={config}&split={split}&offset={offset}&length=100"

# SIB-200 (Adelani et al., 2024): Flores-200 sentences with one of seven
# topics, the same sentences in every language, so en and es are compared on
# identical content. CC BY-SA 4.0.
SIB = {"en": "eng_Latn", "es": "spa_Latn"}
SIB_LABELS = ["science/technology", "travel", "politics", "sports", "health", "entertainment", "geography"]

# CoNLL-2003 (English, Reuters) and CoNLL-2002 (Spanish, EFE): the standard
# human-labelled NER sets. Their text is licensed, so these files are
# gitignored; the sample is reproducible from the seed.
# Read from the files themselves: the rows API rate-limits and 503s a whole
# split. English: tner's JSON lines (tag ids, its label.json below); Spanish:
# the shared task's own test file (testb), latin-1, "token tag" per line.
CONLL = {
    "en": "https://huggingface.co/datasets/tner/conll2003/resolve/main/dataset/test.json",
    "es": "https://www.cs.upc.edu/~nlp/tools/nerc/esp.testb.gz",
}
TNER_LABELS = {"O": 0, "B-ORG": 1, "B-MISC": 2, "B-PER": 3, "I-PER": 4, "B-LOC": 5, "I-ORG": 6, "I-MISC": 7, "I-LOC": 8}
CONLL_SAMPLE = 300
SEED = 2026
ENTITY_TYPES = ("PER", "ORG", "LOC")


def _rows(dataset: str, config: str, split: str) -> tuple[list[dict], list]:

    import urllib.error
    import urllib.parse
    import urllib.request

    rows, features, offset = [], [], 0

    while True:
        url = ROWS_API.format(dataset=urllib.parse.quote(dataset, safe=""), config=config, split=split, offset=offset)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    page = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as error:
                # The rows API rate-limits a whole test split read at once.
                if error.code != 429 or attempt == 5:
                    raise
                time.sleep(10 * (attempt + 1))
        features = page.get("features") or features
        batch = [r["row"] for r in page.get("rows") or []]
        rows += batch
        offset += len(batch)
        if not batch or offset >= (page.get("num_rows_total") or 0):
            return rows, features
        time.sleep(2)


def _conll_sentences(language: str, url: str) -> list[tuple[list[str], list[str]]]:

    import gzip
    import urllib.request

    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()

    if language == "en":
        names = {i: name for name, i in TNER_LABELS.items()}
        rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        return [(r["tokens"], [names[t] for t in r["tags"]]) for r in rows]

    sentences, tokens, tags = [], [], []
    for line in gzip.decompress(raw).decode("latin-1").splitlines():
        parts = line.split()
        if not parts:
            if tokens:
                sentences.append((tokens, tags))
            tokens, tags = [], []
            continue
        tokens.append(parts[0])
        tags.append(parts[-1])
    if tokens:
        sentences.append((tokens, tags))
    return sentences


def conll_entities(tokens: list[str], tags: list[str]) -> list[list[str]]:
    """[type, text] for every PER/ORG/LOC span of a BIO-tagged sentence."""

    found, current = [], None

    for token, tag in zip(tokens, tags):
        if tag.startswith("B-") or (tag.startswith("I-") and (current is None or current[0] != tag[2:])):
            if current:
                found.append(current)
            current = [tag[2:], token]
        elif tag.startswith("I-"):
            current[1] += " " + token
        else:
            if current:
                found.append(current)
            current = None

    if current:
        found.append(current)

    return [e for e in found if e[0] in ENTITY_TYPES]


def cmd_bench_fetch(args) -> int:

    import random

    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / ".gitignore").write_text("# CoNLL text is licensed (Reuters, EFE): never committed.\nconll_*\n", encoding="utf-8")

    for language, config in SIB.items():
        for split in ("train", "test"):
            path = BENCH / f"sib200_{language}_{split}.jsonl"
            if path.exists():
                continue
            rows, _ = _rows("Davlan/sib200", config, split)
            out = [{"id": f"sib-{language}-{split}-{r['index_id']}", "text": r["text"], "label": r["category"]} for r in rows]
            path.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
            print(f"{path.name}: {len(out)}")

    for language, url in CONLL.items():
        sentences = _conll_sentences(language, url)
        usable = [(tokens, tags) for tokens, tags in sentences if len(tokens) >= 3 and tokens[0] != "-DOCSTART-"]
        sample = random.Random(SEED).sample(usable, CONLL_SAMPLE)
        out = [
            {"id": f"conll-{language}-{n:03d}", "text": " ".join(tokens), "entities": conll_entities(tokens, tags)}
            for n, (tokens, tags) in enumerate(sample)
        ]
        path = BENCH / f"conll_{language}_test{CONLL_SAMPLE}.jsonl"
        path.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
        print(f"{path.name}: {len(out)} of {len(usable)} sentences, {sum(len(o['entities']) for o in out)} PER/ORG/LOC")

    return 0


BENCH_TOPIC_SYSTEM = (
    "You classify a sentence into exactly one of these topics: " + ", ".join(SIB_LABELS) + ". "
    "Answer with one JSON object only: {\"topic\": \"<one topic, written exactly as listed>\"}."
)

# CoNLL's own conventions, stated: what counts as each type is where a
# zero-shot model and the annotators part ways (nationalities are MISC there).
BENCH_NER_SYSTEM = (
    "Extract the named entities of three types from the sentence: "
    "PER (people), ORG (organisations: companies, institutions, parties, teams, agencies), "
    "LOC (locations: countries, cities, regions, geographic places). "
    "Nationalities, events and products are none of these. Copy each entity exactly as written in the sentence. "
    "Answer with one JSON object only: {\"entities\": [[\"PER\", \"...\"], [\"LOC\", \"...\"]]}, "
    "an empty list when there are none."
)


def cmd_bench_llm(args) -> int:

    from src.evaluation.headless_claude import UsageCeiling, llm_client
    from src.services.concurrency import bounded_map
    from src.services.llms import LLMUnavailableError

    client = llm_client(args.model, timeout=300)
    slug = args.model.replace(":", "-").replace("/", "-")
    BENCH_OUT.mkdir(parents=True, exist_ok=True)

    for language in args.language or ["en", "es"]:

        if args.task == "topics":
            items = read_jsonl(BENCH / f"sib200_{language}_test.jsonl")
            system = BENCH_TOPIC_SYSTEM
        else:
            items = read_jsonl(BENCH / f"conll_{language}_test{CONLL_SAMPLE}.jsonl")
            system = BENCH_NER_SYSTEM

        out = BENCH_OUT / f"{args.task}_{language}_{slug}.jsonl"
        done = {r["id"] for r in read_jsonl(out)}
        todo = [item for item in items if item["id"] not in done][: args.limit or None]
        print(f"{args.model} {args.task} {language}: {len(todo)} to do, {len(done)} done", flush=True)

        lock = __import__("threading").Lock()

        def one(item: dict) -> None:
            started = time.perf_counter()
            # A refusal (Haiku declined one SIB-200 science sentence as
            # `[bio]`, 11 Nov) or an unreachable model is an unusable
            # answer, counted wrong - not the end of the run.
            try:
                answer = client.complete_json(system, item["text"]) or {}
            except LLMUnavailableError:
                answer = {}
            call = client.last_call() or {}
            row = {"id": item["id"], "seconds": round(time.perf_counter() - started, 3),
                   "promptTokens": call.get("promptTokens"), "completionTokens": call.get("completionTokens")}
            if args.task == "topics":
                topic = answer.get("topic")
                row.update(label=item["label"], predicted=topic, unusable=topic not in SIB_LABELS)
            else:
                found = answer.get("entities")
                ok = isinstance(found, list)
                row.update(gold=item["entities"], unusable=not ok,
                           predicted=[[e[0], e[1]] for e in (found if ok else []) if isinstance(e, list) and len(e) == 2 and e[0] in ENTITY_TYPES and isinstance(e[1], str)])
            with lock, out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        try:
            bounded_map(one, todo, max_workers=args.workers)
        except UsageCeiling as stop:
            raise SystemExit(f"stopped: {stop}")

    return 0


# ----------------------------------------------------------------------
# scoring the standard sets
# ----------------------------------------------------------------------

def _norm(text: str) -> str:

    return " ".join(str(text).casefold().replace(" ,", ",").replace(" .", ".").split()).strip(" .,;:\"'()")


def score_bench_topics(rows: list[dict]) -> dict:

    labels = sorted({r["label"] for r in rows})
    f1s = []
    for label in labels:
        tp = sum(1 for r in rows if r["predicted"] == label and r["label"] == label)
        fp = sum(1 for r in rows if r["predicted"] == label and r["label"] != label)
        fn = sum(1 for r in rows if r["predicted"] != label and r["label"] == label)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return {
        "n": len(rows),
        "accuracy": interval([1.0 if r["predicted"] == r["label"] else 0.0 for r in rows]),
        "macroF1": rounded(sum(f1s) / len(f1s)) if f1s else None,
        "unusable": sum(1 for r in rows if r.get("unusable")),
    }


def score_bench_ner(rows: list[dict]) -> dict:

    def counts(typed: bool, only: str | None = None) -> tuple[int, int, int]:
        tp = fp = fn = 0
        for r in rows:
            key = (lambda e: (e[0], _norm(e[1]))) if typed else (lambda e: _norm(e[1]))
            gold = {key(e) for e in r["gold"] if only is None or e[0] == only}
            found = {key(e) for e in r["predicted"] if only is None or e[0] == only}
            tp += len(gold & found)
            fp += len(found - gold)
            fn += len(gold - found)
        return tp, fp, fn

    def prf(tp, fp, fn) -> dict:
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        return {"precision": rounded(p), "recall": rounded(r), "f1": rounded(2 * p * r / (p + r) if p + r else 0.0)}

    return {
        "n": len(rows),
        "typed": prf(*counts(True)),
        "untyped": prf(*counts(False)),
        **{kind: prf(*counts(True, kind))["f1"] for kind in ENTITY_TYPES},
        "unusable": sum(1 for r in rows if r.get("unusable")),
    }


def _bench_timing(path: Path, rows: list[dict]) -> dict:

    meta_path = path.with_suffix(".meta.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    per_item = [r["seconds"] for r in rows if r.get("seconds") is not None]
    return {
        "medianSeconds": rounded(statistics.median(per_item)) if per_item else rounded(meta.get("perItemSeconds")),
        "trainSeconds": rounded(meta.get("trainSeconds")) if meta.get("trainSeconds") is not None else None,
        "tokens": (sum(r.get("promptTokens") or 0 for r in rows), sum(r.get("completionTokens") or 0 for r in rows)) if any(r.get("promptTokens") for r in rows) else None,
    }


def bench_section() -> tuple[list[str], dict]:

    results: dict = {"topics": {}, "ner": {}}
    lines = []

    for task, scorer in (("topics", score_bench_topics), ("ner", score_bench_ner)):
        for path in sorted(BENCH_OUT.glob(f"{task}_*.jsonl")):
            language, contender = path.stem.split("_", 2)[1:]
            rows = read_jsonl(path)
            if rows:
                results[task].setdefault(contender, {})[language] = {**scorer(rows), **_bench_timing(path, rows)}

    def tokens(t) -> str:
        return f"{t[0]:,} / {t[1]:,}" if t else "-"

    if results["topics"]:
        lines += [
            "", "# Topics on a standard set: SIB-200", "",
            "SIB-200 test, 204 sentences per language, the same sentences in English and Spanish, 7 topics. "
            "Trained contenders learn from the language's own 701 training sentences. Accuracy with a 95% bootstrap interval.", "",
            "| Contender | en accuracy | en macro-F1 | es accuracy | es macro-F1 | Unusable | Median s / sentence | Train s | Tokens in / out (both) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for contender, by in sorted(results["topics"].items()):
            en, es = by.get("en") or {}, by.get("es") or {}
            both = [x["tokens"] for x in (en, es) if x.get("tokens")]
            t = (sum(a for a, _ in both), sum(b for _, b in both)) if both else None
            lines.append(
                f"| {contender} | {_interval(en.get('accuracy'))} | {en.get('macroF1', 'n/a')} | {_interval(es.get('accuracy'))} | {es.get('macroF1', 'n/a')} | "
                f"{(en.get('unusable') or 0) + (es.get('unusable') or 0)} | {en.get('medianSeconds')} / {es.get('medianSeconds')} | {en.get('trainSeconds') or '-'} | {tokens(t)} |"
            )

    if results["ner"]:
        lines += [
            "", "# Entities on a standard set: CoNLL", "",
            f"A seeded sample (seed {SEED}) of {CONLL_SAMPLE} test sentences each from CoNLL-2003 (en) and CoNLL-2002 (es). "
            "Scored as each sentence's set of (type, name) against the annotators', PER/ORG/LOC only, names compared case- and spacing-blind; "
            "untyped counts a name found under any type. Micro-averaged.", "",
            "| Contender | Lang | Precision | Recall | F1 | PER | ORG | LOC | Untyped F1 | Unusable | Median s / sentence | Tokens in / out |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for contender, by in sorted(results["ner"].items()):
            for language in ("en", "es"):
                m = by.get(language)
                if not m:
                    continue
                lines.append(
                    f"| {contender} | {language} | {m['typed']['precision']} | {m['typed']['recall']} | **{m['typed']['f1']}** | {m['PER']} | {m['ORG']} | {m['LOC']} | "
                    f"{m['untyped']['f1']} | {m['unusable']} | {m['medianSeconds']} | {tokens(m.get('tokens'))} |"
                )

    return lines, results


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------

def _claude_cost(model_prefix: str, since: str | None = None, until: str | None = None) -> dict:
    """API-equivalent dollars and calls of the headless log, for one model alias, in a time span."""

    calls = [
        c for c in read_jsonl(OUT / "claude-calls.jsonl")
        if (since is None or c["at"] >= since) and (until is None or c["at"] <= until)
    ]
    return {"calls": len(calls), "apiEquivalentUsd": round(sum(c.get("apiEquivalentUsd") or 0 for c in calls), 4)}


def _interval(m: dict) -> str:

    return f"{m['mean']:.2f} [{m['low']:.2f}, {m['high']:.2f}]" if m and m.get("mean") is not None else "n/a"


def factcheck_rows(run: Path, limit: int) -> dict:
    """One harness run's first `limit` claims, scored against AVeriTeC's gold."""

    meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
    rows = read_jsonl(run / "results.jsonl")[:limit]
    right = [1.0 if r.get("verdict") == r.get("label") else 0.0 for r in rows]
    seconds = [r["latency"]["total"] for r in rows if (r.get("latency") or {}).get("total") is not None]
    llm = [r["latency"]["llmCall"] for r in rows if (r.get("latency") or {}).get("llmCall") is not None]
    usage = [r.get("usage") or {} for r in rows]

    return {
        "run": str(run.relative_to(BACKEND)),
        "model": meta["model"],
        "mode": meta["mode"],
        "label": meta.get("label"),
        "gitCommit": meta.get("gitCommit"),
        "claims": len(rows),
        "accuracy": interval(right),
        "unverified": sum(1 for r in rows if r.get("verdict") == "UNVERIFIED"),
        "verdicts": {r["id"]: [r.get("label"), r.get("verdict")] for r in rows},
        "medianSeconds": rounded(statistics.median(seconds)) if seconds else None,
        "medianLlmSeconds": rounded(statistics.median(llm)) if llm else None,
        "promptTokens": sum(u.get("promptTokens") or 0 for u in usage) or None,
        "completionTokens": sum(u.get("completionTokens") or 0 for u in usage) or None,
    }


def factcheck_section(runs: list[str], limit: int) -> tuple[list[str], list[dict]]:

    found = [factcheck_rows(BACKEND / run, limit) for run in runs]

    if not found:
        return [], []

    ids = list(found[0]["verdicts"])
    gold = [found[0]["verdicts"][i][0] for i in ids]
    majority = Counter(gold).most_common(1)[0]

    lines = [
        "", "# Fact-checking: the verifier on the same evidence", "",
        f"AVeriTeC dev, the first {limit} claims. Every replay reads the evidence the knowledge-store run kept; "
        "closed-book reads none (what the model already knows). "
        f"Always answering {majority[0]} gets {majority[1]} of {len(gold)} here.", "",
        "| Run | Model | Mode | Right | Accuracy [95% CI] | UNVERIFIED | Median s / claim | Median model s | Tokens in / out |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for f in found:
        right = round(f["accuracy"]["mean"] * f["claims"])
        tokens = f"{f['promptTokens']:,} / {f['completionTokens']:,}" if f["promptTokens"] else "-"
        lines.append(
            f"| {f['label']} `{Path(f['run']).name}` | {f['model']} | {f['mode']} | {right}/{f['claims']} | {_interval(f['accuracy'])} | "
            f"{f['unverified']} | {f['medianSeconds']} | {f['medianLlmSeconds']} | {tokens} |"
        )

    lines += ["", "| Claim | Gold | " + " | ".join(f"{f['model']} {f['mode']}" for f in found) + " |", "|---|---|" + "---|" * len(found)]
    for i, g in zip(ids, gold):
        lines.append(f"| {i} | {g} | " + " | ".join((f["verdicts"].get(i) or [None, "-"])[1] or "-" for f in found) + " |")

    return lines, found


def review_section() -> list[str]:

    path = OUT / "review" / "comparison.md"

    if not path.exists():
        return []

    body = path.read_text(encoding="utf-8").split("\n", 1)[1]
    return ["", "# Review: the corrector as editor over 36 planted-defect texts", body]


def resources_section() -> list[str]:
    """What each model needs in order to be used (scripts/standard_benchmarks.py resources)."""

    path = OUT / "resources.json"

    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    machine = data["machine"]

    def params(value) -> str:
        if isinstance(value, (int, float)):
            return f"{value / 1e6:,.0f} M" if value >= 1e6 else f"{value:,}"
        return value or "n/a"

    def mb(value) -> str:
        return "n/a" if value is None else (f"{value / 1000:.1f} GB" if value >= 1000 else f"{value:.0f} MB")

    lines = [
        "", "# Resources: what each model needs in order to be used", "",
        f"Measured {data['measuredAt'][:10]} on {machine['cpu']}, {machine['threads']} threads, {machine['ramGb']} GB RAM, no GPU used. "
        "Each local model in a process of its own: memory once loaded and at its peak over 100 sentences, above the bare interpreter; "
        "cores is CPU time over wall time while it worked. Ollama models: the file's size and the memory Ollama reports once loaded.", "",
        "| Model | What it is | Runs on | Parameters | On disk | RAM loaded | RAM peak | Load s | Cores used |",
        "|---|---|---|---|---|---|---|---|---|",
    ]

    for name, m in data["models"].items():
        if "error" in m:
            lines.append(f"| {name} | not measured: {m['error']} | | | | | | | |")
            continue
        lines.append(
            f"| {name} | {m['model']} | {m['runsOn']} | {params(m['parameters'])} | {mb(m['diskMb'])} | {mb(m['loadedMb'])} | {mb(m['peakMb'])} | "
            f"{m['loadSeconds'] if m['loadSeconds'] is not None else 'n/a'} | {m['coresUsed'] if m['coresUsed'] is not None else 'n/a'} |"
        )

    lines += [
        "",
        "- The embedding model is shared: the topic classifiers (untrained and trained) and the pipeline's duplicate search all use the one loaded bge-m3; "
        "the trained classifier adds 7 x 1,024 weights to it. Its folder on disk holds several copies of the weights (about 2.3 GB is the one loaded).",
        "- Claude needs nothing held locally and cannot be run without the network and a plan; its size is not published.",
        "- An Ollama figure is Ollama's own report (`/api/ps`), not a measurement of the process; gemma4's is lower than its file, as reported.",
    ]

    return lines


def cmd_report(args) -> int:

    lines = ["# Topic classification: the frameworks side by side", ""]
    lines.append(f"Gold: {GOLD.relative_to(BACKEND)} (the annotator's topic per article). "
                 f"Each LLM reads the title and the first {CHARS} characters; the embedding classifier the whole body. "
                 "95% bootstrap intervals.")
    lines += ["", "| Contender | n | Top-1 | Gold in top 3 | Top-1 group | Unusable | Median s / article | Tokens in / out |", "|---|---|---|---|---|---|---|---|"]

    results = {}
    for path in sorted(TOPICS_OUT.glob("*.jsonl")):
        if path.name == "articles.jsonl":
            continue
        rows = read_jsonl(path)
        if not rows:
            continue
        m = score_topics(rows)
        results[path.stem] = m
        tokens = f"{m['promptTokens']:,} / {m['completionTokens']:,}" if m["promptTokens"] else "-"
        lines.append(f"| {path.stem} | {m['articles']} | {_interval(m['top1'])} | {_interval(m['top3'])} | {_interval(m['group'])} | {m['unusable']} | {m['medianSeconds']} | {tokens} |")

    lines += ["", "Caveat: many of these topic labels came from an AI pass and none has been reviewed by a person; a Claude contender's agreement with them is not yet accuracy."]

    (TOPICS_OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    checks, found = factcheck_section(args.factcheck_run or [], args.limit)
    standard, bench = bench_section()
    lines += standard + checks + review_section() + resources_section()
    results = {"topics": results, "factCheck": found, "standard": bench}

    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "metrics.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))

    return 0


def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("topics-fetch", help="the labelled articles' text, frozen once")
    commands.add_parser("bench-fetch", help="SIB-200 (en, es) and a seeded CoNLL sample (en, es), frozen once")

    bench = commands.add_parser("bench-llm", help="an LLM contender on SIB-200 topics or CoNLL entities (resumes)")
    bench.add_argument("--task", required=True, choices=["topics", "ner"])
    bench.add_argument("--model", required=True, help="an Ollama model, or claude-headless:<alias>")
    bench.add_argument("--language", action="append", choices=["en", "es"])
    bench.add_argument("--limit", type=int)
    bench.add_argument("--workers", type=int, default=1, help="calls at once (LLM_MAX_CONCURRENCY caps it too)")

    topics = commands.add_parser("topics", help="one contender over the frozen articles (resumes)")
    topics.add_argument("--model", required=True, help="embedding, an Ollama model, or claude-headless:<alias>")
    topics.add_argument("--limit", type=int)

    report = commands.add_parser("report", help="every contender of every phase side by side")
    report.add_argument("--factcheck-run", action="append", help="a harness run directory (repeat)")
    report.add_argument("--limit", type=int, default=10, help="claims per fact-check run")

    args = parser.parse_args(argv)

    return {
        "topics-fetch": cmd_topics_fetch, "topics": cmd_topics, "report": cmd_report,
        "bench-fetch": cmd_bench_fetch, "bench-llm": cmd_bench_llm,
    }[args.command](args)


if __name__ == "__main__":

    sys.exit(main())

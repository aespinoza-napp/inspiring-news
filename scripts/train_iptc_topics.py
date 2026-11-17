"""
A topic classifier trained on MN-DS, in English and Spanish (2026-11-17).

The rule it is judged by was written first:
backend/data/evaluation/experiments/topics_iptc/rule.md. MN-DS (Petukhova &
Fachada, Data 2023, CC BY 4.0): 10,917 English news articles, each labelled by
hand with one of 17 first-level IPTC Media Topics. Its Spanish half is the same
articles machine-translated (OPUS-MT en-es, translate-train). bge-m3 embeds each
article's title and first 80 words; multinomial logistic regression learns the
17 categories; the app reads them as its five groups through the rule's table.

Runs in inference/'s environment (bge-m3, Marian and scikit-learn are there),
from the repository root:

    cd inference && uv run python ../scripts/train_iptc_topics.py all --mnds <train.jsonl> --cache <dir>

Steps, each cached in --cache and resumable: `translate`, `embed`, `train`
(writes backend/data/models/iptc_topics.npz and the held-out figures), `app`
(the app's 56 labelled articles against the embedding classifier, written to
backend/data/evaluation/experiments/topics_iptc/). `all` runs them in order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "inference"))

BACKEND = ROOT / "backend"
MODEL_OUT = BACKEND / "data" / "models" / "iptc_topics.npz"
EXPERIMENT = BACKEND / "data" / "evaluation" / "experiments" / "topics_iptc"
APP_ARTICLES = BACKEND / "data" / "evaluation" / "experiments" / "frameworks" / "topics" / "articles.jsonl"
APP_EMBEDDING_RUN = BACKEND / "data" / "evaluation" / "experiments" / "frameworks" / "topics" / "embedding.jsonl"
APP_GOLD = BACKEND / "data" / "evaluation" / "experiments" / "topics" / "20261020T093630Z" / "result.json"

LEAD_WORDS = 80

# The rule's table, fixed before any result.
GROUP_OF_IPTC = {
    "environment": "environment",
    "weather": "environment",
    "science and technology": "science",
    "health": "health",
    "arts, culture, entertainment and media": "culture",
    "human interest": "culture",
    "education": "society",
    "society": "society",
    "labour": "society",
}

# The app's 23 topics by group (backend/src/config/topics.py), read here
# rather than imported: this script runs in inference/'s environment.
APP_GROUP_OF = {
    topic: group
    for group, topics in {
        "society": ["education", "community", "employment", "cities"],
        "science": ["space", "technology", "research", "biology"],
        "environment": ["climate", "nature", "energy", "sustainability", "food"],
        "culture": ["arts", "entertainment", "heritage", "literature", "inspiration"],
        "health": ["medicine", "mental_health", "nutrition", "fitness", "public_health"],
    }.items()
    for topic in topics
}


def lead(title: str | None, body: str | None) -> str:
    words = (body or "").split()[:LEAD_WORDS]
    return f"{(title or '').strip()}. {' '.join(words)}".strip(" .")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mnds_rows(path: Path) -> list[dict]:
    rows = read_jsonl(path)
    return [
        {"key": f"{row['data_id']}", "id": row["id"], "label": row["category_level_1"], "text": lead(row.get("title"), row.get("content"))}
        for row in rows
    ]


def split_of(row: dict) -> str:
    """By article id, so the same article listed twice, and its translation, stay on one side."""
    return "test" if int(hashlib.sha256(row["id"].encode("utf-8")).hexdigest(), 16) % 5 == 0 else "train"


# ----------------------------------------------------------------------


def cmd_translate(args) -> None:
    """English leads to Spanish, cached line by line in --cache/es.jsonl."""

    import torch
    from transformers import MarianMTModel, MarianTokenizer

    rows = mnds_rows(Path(args.mnds))
    out = Path(args.cache) / "es.jsonl"
    done = {r["key"] for r in read_jsonl(out)} if out.exists() else set()
    todo = [r for r in rows if r["key"] not in done]
    print(f"translate: {len(done)} cached, {len(todo)} to go", flush=True)

    name = "Helsinki-NLP/opus-mt-en-es"
    tokenizer, model = MarianTokenizer.from_pretrained(name), MarianMTModel.from_pretrained(name).eval()

    started = time.perf_counter()
    with out.open("a", encoding="utf-8") as handle:
        for start in range(0, len(todo), 16):
            batch = todo[start:start + 16]
            encoded = tokenizer([r["text"] for r in batch], return_tensors="pt", padding=True, truncation=True, max_length=256)
            with torch.inference_mode():
                generated = model.generate(**encoded, max_new_tokens=256, num_beams=1)
            for row, text in zip(batch, tokenizer.batch_decode(generated, skip_special_tokens=True)):
                handle.write(json.dumps({"key": row["key"], "text": text}, ensure_ascii=False) + "\n")
            handle.flush()
            if (start // 16) % 50 == 0:
                print(f"  {start + len(batch)} / {len(todo)} in {time.perf_counter() - started:.0f} s", flush=True)


def cmd_embed(args) -> None:
    """bge-m3 vectors of every English lead and Spanish translation: --cache/{en,es}.npy with their keys."""

    from src.embeddings import embedding_model

    embedding_model.load()
    rows = mnds_rows(Path(args.mnds))
    spanish = {r["key"]: r["text"] for r in read_jsonl(Path(args.cache) / "es.jsonl")}

    for language, texts in (("en", [(r["key"], r["text"]) for r in rows]), ("es", [(r["key"], spanish[r["key"]]) for r in rows if r["key"] in spanish])):
        target = Path(args.cache) / f"{language}.npy"
        if target.exists():
            print(f"embed {language}: cached", flush=True)
            continue
        started = time.perf_counter()
        vectors = []
        for start in range(0, len(texts), 256):
            vectors.extend(embedding_model.encode_many([text for _, text in texts[start:start + 256]]))
            print(f"  {language} {start + 256} / {len(texts)} in {time.perf_counter() - started:.0f} s", flush=True)
        np.save(target, np.asarray(vectors, dtype=np.float32))
        (Path(args.cache) / f"{language}.keys.json").write_text(json.dumps([key for key, _ in texts]))


def _dataset(args):
    rows = {r["key"]: r for r in mnds_rows(Path(args.mnds))}
    X, y, side, lang = [], [], [], []
    for language in ("en", "es"):
        vectors = np.load(Path(args.cache) / f"{language}.npy")
        keys = json.loads((Path(args.cache) / f"{language}.keys.json").read_text())
        for key, vector in zip(keys, vectors):
            X.append(vector)
            y.append(rows[key]["label"])
            side.append(split_of(rows[key]))
            lang.append(language)
    return np.asarray(X), np.asarray(y), np.asarray(side), np.asarray(lang)


def _macro_f1(gold, predicted) -> float:
    labels = sorted(set(gold))
    scores = []
    for label in labels:
        tp = sum(1 for g, p in zip(gold, predicted) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, predicted) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, predicted) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return float(np.mean(scores))


def cmd_train(args) -> None:

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GridSearchCV, StratifiedKFold

    X, y, side, lang = _dataset(args)
    train = side == "train"

    search = GridSearchCV(
        LogisticRegression(max_iter=3000),
        {"C": [0.5, 1.0, 2.0, 5.0, 10.0]},
        cv=StratifiedKFold(5, shuffle=True, random_state=0),
        scoring="f1_macro",
        n_jobs=4,
    )
    started = time.perf_counter()
    search.fit(X[train], y[train])
    model = search.best_estimator_

    held = {}
    for language in ("en", "es"):
        mask = (~train) & (lang == language)
        predicted = model.predict(X[mask])
        gold = y[mask]
        held[language] = {
            "articles": int(mask.sum()),
            "accuracy": round(float(np.mean(predicted == gold)), 4),
            "macroF1": round(_macro_f1(list(gold), list(predicted)), 4),
            "groupAccuracy": round(float(np.mean([GROUP_OF_IPTC.get(p, "none") == GROUP_OF_IPTC.get(g, "none") for p, g in zip(predicted, gold)])), 4),
        }

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        MODEL_OUT,
        coef=model.coef_.astype(np.float32),
        intercept=model.intercept_.astype(np.float32),
        classes=np.asarray(model.classes_),
        lead_words=np.asarray([LEAD_WORDS]),
    )

    EXPERIMENT.mkdir(parents=True, exist_ok=True)
    result = {
        "trainedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "data": "MN-DS (textminr/mn-ds mirror) + its OPUS-MT en-es translation",
        "trainArticles": {language: int((train & (lang == language)).sum()) for language in ("en", "es")},
        "C": search.best_params_["C"],
        "cvMacroF1": round(float(search.best_score_), 4),
        "heldOut": held,
        "paperLevel1F1": {"tfidfLogisticRegression": 0.774, "distilbert": 0.844},
        "trainSeconds": round(time.perf_counter() - started, 1),
        "model": str(MODEL_OUT.relative_to(ROOT)),
    }
    (EXPERIMENT / "train.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def _bootstrap_diff(a: list[float], b: list[float], seed: int = 0, n: int = 10000) -> list[float]:
    rng = random.Random(seed)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        diffs.append(sum(a[i] - b[i] for i in idx) / k)
    diffs.sort()
    return [round(diffs[int(0.025 * n)], 3), round(diffs[int(0.975 * n)], 3)]


def cmd_app(args) -> None:
    """The app's labelled articles: this classifier's group against the embedding classifier's, paired."""

    from src.embeddings import embedding_model

    embedding_model.load()
    bundle = np.load(MODEL_OUT, allow_pickle=False)
    coef, intercept, classes = bundle["coef"], bundle["intercept"], [str(c) for c in bundle["classes"]]

    gold = {r["url"]: r for r in json.loads(APP_GOLD.read_text(encoding="utf-8"))["rows"]}
    baseline = {r["url"]: r for r in read_jsonl(APP_EMBEDDING_RUN)}
    articles = [a for a in read_jsonl(APP_ARTICLES) if a.get("text") and a["url"] in baseline]

    rows = []
    for article in articles:
        started = time.perf_counter()
        vector = np.asarray(embedding_model.encode(lead(article.get("title"), article.get("text"))), dtype=np.float32)
        scores = coef @ vector + intercept
        order = np.argsort(-scores)
        top = classes[int(order[0])]
        seconds = time.perf_counter() - started
        gold_group = APP_GROUP_OF[gold[article["url"]]["gold"]]
        embedding_group = APP_GROUP_OF.get((baseline[article["url"]]["predicted"] or [None])[0])
        rows.append({
            "url": article["url"],
            "language": article["language"],
            "gold": gold[article["url"]]["gold"],
            "goldGroup": gold_group,
            "iptc": top,
            "iptcTop3": [classes[int(i)] for i in order[:3]],
            "iptcGroup": GROUP_OF_IPTC.get(top, "none"),
            "embeddingGroup": embedding_group,
            "seconds": round(seconds, 3),
        })

    def right(row, key):
        return 1.0 if row[key] == row["goldGroup"] else 0.0

    summary = {}
    for name, subset in (("all", rows), ("en", [r for r in rows if r["language"] == "en"]), ("es", [r for r in rows if r["language"] == "es"])):
        a = [right(r, "iptcGroup") for r in subset]
        b = [right(r, "embeddingGroup") for r in subset]
        summary[name] = {
            "articles": len(subset),
            "iptcRight": int(sum(a)),
            "embeddingRight": int(sum(b)),
            "iptcGroupAccuracy": round(sum(a) / len(a), 3) if a else None,
            "embeddingGroupAccuracy": round(sum(b) / len(b), 3) if b else None,
            "difference95": _bootstrap_diff(a, b) if a else None,
        }

    rule = (
        summary["all"]["iptcRight"] >= summary["all"]["embeddingRight"]
        and all(summary[lang]["embeddingRight"] - summary[lang]["iptcRight"] <= 2 for lang in ("en", "es"))
    )

    result = {
        "evaluatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": summary,
        "adoptedByTheRule": rule,
        "iptcCategoriesPredicted": Counter(r["iptc"] for r in rows),
        "medianSeconds": float(np.median([r["seconds"] for r in rows])),
        "rows": rows,
    }
    EXPERIMENT.mkdir(parents=True, exist_ok=True)
    (EXPERIMENT / "app.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["translate", "embed", "train", "app", "all"])
    parser.add_argument("--mnds", required=True, help="MN-DS as JSON lines (textminr/mn-ds train.jsonl)")
    parser.add_argument("--cache", required=True, help="a folder for the translations and vectors")
    args = parser.parse_args()
    Path(args.cache).mkdir(parents=True, exist_ok=True)

    steps = {"translate": cmd_translate, "embed": cmd_embed, "train": cmd_train, "app": cmd_app}
    for step in (["translate", "embed", "train", "app"] if args.step == "all" else [args.step]):
        steps[step](args)


if __name__ == "__main__":
    main()

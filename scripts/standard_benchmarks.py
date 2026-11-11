#!/usr/bin/env python3
"""
The deterministic contenders on the standard sets, in inference/'s
environment - the only one allowed torch, transformers and GLiNER
(CLAUDE.md, invariant 13). The LLM contenders and the scoring live in
backend/src/evaluation/frameworks.py (`bench-llm`, `report`), over the same
frozen files.

    cd inference && uv run \
      --with 'spacy>=3.8,<3.9' \
      --with https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl \
      --with https://github.com/explosion/spacy-models/releases/download/es_core_news_sm-3.8.0/es_core_news_sm-3.8.0-py3-none-any.whl \
      python ../scripts/standard_benchmarks.py

(spaCy rides along with --with, so inference/'s pyproject is not touched.)

Topics, SIB-200 test (204 sentences, en and es, 7 labels):
  embedding-zeroshot  bge-m3, the sentence against "This text is about <label>." -
                      the method of the pipeline's TopicClassifier, untrained
  embedding-logreg    logistic regression on bge-m3 vectors, trained on SIB-200's
                      701 training sentences of the same language
  tfidf-logreg        the classic baseline: word and character n-grams, same training

Entities, the seeded CoNLL samples (300 sentences each, PER/ORG/LOC):
  gliner              the pipeline's own: inference/'s EntityModel, the backend's
                      DEFAULT_LABELS and ENTITY_THRESHOLD (0.50), labels mapped
  xlmr-ner            Davlan/xlm-roberta-base-ner-hrl, fine-tuned on CoNLL-2003 and
                      CoNLL-2002 *training* sets: the supervised reference
  spacy-sm            en_core_web_sm (OntoNotes) / es_core_news_sm (WikiNER)

All are deterministic: the same input gives the same output.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "backend/data/evaluation/benchmarks"
OUT = REPO / "backend/data/evaluation/experiments/frameworks/standard"

LANGUAGES = ("en", "es")

# backend/src/processors/nlp/entities.py DEFAULT_LABELS and settings.ENTITY_THRESHOLD,
# copied rather than imported: this runs in inference/'s environment.
GLINER_LABELS = ["person", "organization", "location", "country", "city", "company", "product", "event"]
GLINER_THRESHOLD = 0.50
GLINER_TYPE = {"person": "PER", "organization": "ORG", "company": "ORG", "location": "LOC", "country": "LOC", "city": "LOC"}

SPACY_TYPE = {"PERSON": "PER", "PER": "PER", "ORG": "ORG", "GPE": "LOC", "LOC": "LOC"}
SPACY_MODELS = {"en": "en_core_web_sm", "es": "es_core_news_sm"}


def read(path: Path) -> list[dict]:

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(name: str, rows: list[dict], meta: dict) -> None:

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (OUT / f"{name}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"{name}: {len(rows)} rows, {meta['seconds']:.1f} s", flush=True)


# ----------------------------------------------------------------------
# topics
# ----------------------------------------------------------------------

def topics() -> None:

    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline, make_union

    from src.embeddings import embedding_model

    embedding_model.load()

    for language in LANGUAGES:

        train = read(BENCH / f"sib200_{language}_train.jsonl")
        test = read(BENCH / f"sib200_{language}_test.jsonl")
        labels = sorted({r["label"] for r in train})

        started = time.perf_counter()
        test_vectors = np.array(embedding_model.encode_many([r["text"] for r in test]))
        embed_test = time.perf_counter() - started

        # Untrained: the sentence against each label's own sentence.
        started = time.perf_counter()
        prototypes = np.array(embedding_model.encode_many([f"This text is about {label}." for label in labels]))
        scores = test_vectors @ prototypes.T
        rows = [{"id": r["id"], "label": r["label"], "predicted": labels[int(i)]} for r, i in zip(test, scores.argmax(axis=1))]
        write(f"topics_{language}_embedding-zeroshot", rows, {"seconds": embed_test + time.perf_counter() - started, "trainSeconds": 0, "perItemSeconds": (embed_test + time.perf_counter() - started) / len(test)})

        # Trained on the same language's training split.
        started = time.perf_counter()
        train_vectors = np.array(embedding_model.encode_many([r["text"] for r in train]))
        model = LogisticRegression(max_iter=2000, C=4.0, random_state=0)
        model.fit(train_vectors, [r["label"] for r in train])
        train_seconds = time.perf_counter() - started
        started = time.perf_counter()
        predicted = model.predict(test_vectors)
        rows = [{"id": r["id"], "label": r["label"], "predicted": p} for r, p in zip(test, predicted)]
        predict_seconds = embed_test + time.perf_counter() - started
        write(f"topics_{language}_embedding-logreg", rows, {"seconds": predict_seconds, "trainSeconds": train_seconds, "perItemSeconds": predict_seconds / len(test)})

        started = time.perf_counter()
        tfidf = make_pipeline(
            make_union(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
            LogisticRegression(max_iter=2000, C=10.0, random_state=0),
        )
        tfidf.fit([r["text"] for r in train], [r["label"] for r in train])
        train_seconds = time.perf_counter() - started
        started = time.perf_counter()
        predicted = tfidf.predict([r["text"] for r in test])
        rows = [{"id": r["id"], "label": r["label"], "predicted": p} for r, p in zip(test, predicted)]
        write(f"topics_{language}_tfidf-logreg", rows, {"seconds": time.perf_counter() - started, "trainSeconds": train_seconds, "perItemSeconds": (time.perf_counter() - started) / len(test)})


# ----------------------------------------------------------------------
# entities
# ----------------------------------------------------------------------

def _timed(sentences: list[dict], extract) -> tuple[list[dict], float]:

    rows = []
    started = time.perf_counter()

    for s in sentences:
        one = time.perf_counter()
        rows.append({"id": s["id"], "gold": s["entities"], "predicted": extract(s["text"]), "seconds": round(time.perf_counter() - one, 4)})

    return rows, time.perf_counter() - started


def entities() -> None:

    from src.entities import entity_model

    entity_model.load()

    def gliner(text: str) -> list[list[str]]:
        found = entity_model.extract(text, GLINER_THRESHOLD, GLINER_LABELS)
        return [[GLINER_TYPE[label], name] for label, names in found.items() if label in GLINER_TYPE for name in names]

    from transformers import pipeline

    started = time.perf_counter()
    xlmr = pipeline("ner", model="Davlan/xlm-roberta-base-ner-hrl", aggregation_strategy="first", device=-1)  # word-level: "simple" split words into sub-pieces ("cl" + "eveland"), 11 Nov
    xlmr_load = time.perf_counter() - started

    def xlmr_ner(text: str) -> list[list[str]]:
        # Word-level labels, then adjacent words of one type joined here:
        # this model's B-/I- tags left "first" giving one entity per word
        # (a first name and a surname apart; PER F1 0.33 on 11 Nov).
        spans: list[list] = []
        for e in xlmr(text):
            if spans and spans[-1][0] == e["entity_group"] and not text[spans[-1][2]:e["start"]].strip():
                spans[-1][2] = e["end"]
            else:
                spans.append([e["entity_group"], e["start"], e["end"]])
        return [[kind, text[start:end].strip()] for kind, start, end in spans if kind in ("PER", "ORG", "LOC")]

    try:
        import spacy
    except ImportError:
        spacy = None
        print("spaCy not installed: run with the --with lines in the docstring to include it", flush=True)

    for language in LANGUAGES:

        sentences = read(BENCH / f"conll_{language}_test300.jsonl")

        rows, seconds = _timed(sentences, gliner)
        write(f"ner_{language}_gliner", rows, {"seconds": seconds, "perItemSeconds": seconds / len(rows), "model": "urchade/gliner_small-v2.1"})

        rows, seconds = _timed(sentences, xlmr_ner)
        write(f"ner_{language}_xlmr-ner", rows, {"seconds": seconds, "perItemSeconds": seconds / len(rows), "loadSeconds": xlmr_load, "model": "Davlan/xlm-roberta-base-ner-hrl"})

        if spacy is not None:
            nlp = spacy.load(SPACY_MODELS[language])
            rows, seconds = _timed(sentences, lambda text: [[SPACY_TYPE[e.label_], e.text] for e in nlp(text).ents if e.label_ in SPACY_TYPE])
            write(f"ner_{language}_spacy-sm", rows, {"seconds": seconds, "perItemSeconds": seconds / len(rows), "model": SPACY_MODELS[language]})


# ----------------------------------------------------------------------
# resources: what each model needs in order to be used
# ----------------------------------------------------------------------

RESOURCES = OUT.parent / "resources.json"

OLLAMA = "http://localhost:11434"
OLLAMA_MODELS = ["llama3.2:3b-bench", "qwen3.5:4b-bench", "phi4-mini:bench", "granite3.3:8b-bench", "gemma4:e4b-bench", "qwen3.5:9b-bench"]

LOCAL_MODELS = {
    "embedding (bge-m3)": "BAAI/bge-m3",
    "gliner": "urchade/gliner_small-v2.1",
    "xlmr-ner": "Davlan/xlm-roberta-base-ner-hrl",
    "spacy-sm en": "en_core_web_sm",
    "spacy-sm es": "es_core_news_sm",
    "tfidf-logreg": None,
}


def _rss_mb() -> float:
    """This process's resident memory now, from /proc (no psutil in inference/)."""

    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def _disk_mb(path: Path) -> float | None:

    if not path.exists():
        return None
    # A Hugging Face cache snapshot is symlinks into blobs: follow them.
    return round(sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6, 1)


def _hf_disk_mb(repo: str) -> float | None:

    cache = Path.home() / ".cache/huggingface/hub" / ("models--" + repo.replace("/", "--")) / "blobs"
    return _disk_mb(cache)


def resources_one(name: str) -> dict:
    """One model, in a process that loads nothing else: its memory is its own."""

    import resource

    sentences = [r["text"] for r in read(BENCH / "conll_en_test300.jsonl")][:100]
    before = _rss_mb()
    parameters = disk = None

    started = time.perf_counter()

    if name.startswith("embedding"):
        from src.embeddings import embedding_model
        embedding_model.load()
        parameters = sum(p.numel() for p in embedding_model._model.parameters())
        disk = _hf_disk_mb(LOCAL_MODELS[name])
        run = lambda: embedding_model.encode_many(sentences)
    elif name == "gliner":
        from src.entities import entity_model
        entity_model.load()
        parameters = sum(p.numel() for p in entity_model._model.parameters())
        disk = _hf_disk_mb(LOCAL_MODELS[name])
        run = lambda: [entity_model.extract(t, GLINER_THRESHOLD, GLINER_LABELS) for t in sentences]
    elif name == "xlmr-ner":
        from transformers import pipeline
        ner = pipeline("ner", model=LOCAL_MODELS[name], aggregation_strategy="first", device=-1)
        parameters = sum(p.numel() for p in ner.model.parameters())
        disk = _hf_disk_mb(LOCAL_MODELS[name])
        run = lambda: [ner(t) for t in sentences]
    elif name.startswith("spacy-sm"):
        import spacy
        nlp = spacy.load(LOCAL_MODELS[name])
        disk = _disk_mb(Path(nlp.path))
        run = lambda: [nlp(t) for t in sentences]
    else:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline, make_union
        train = read(BENCH / "sib200_en_train.jsonl")
        model = make_pipeline(
            make_union(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
            LogisticRegression(max_iter=2000, C=10.0, random_state=0),
        )
        model.fit([r["text"] for r in train], [r["label"] for r in train])
        parameters = int(model[-1].coef_.size)
        import pickle
        disk = round(len(pickle.dumps(model)) / 1e6, 1)
        run = lambda: model.predict(sentences)

    load_seconds = time.perf_counter() - started
    loaded = _rss_mb()

    wall, cpu = time.perf_counter(), time.process_time()
    run()
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu

    return {
        "model": LOCAL_MODELS[name] or "trained here on SIB-200 (en)",
        "runsOn": "this machine, CPU",
        "parameters": parameters,
        "diskMb": disk,
        "loadedMb": round(loaded - before, 1),
        "peakMb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 - before, 1),
        "loadSeconds": round(load_seconds, 1),
        "coresUsed": round(cpu / wall, 1) if wall > 0.01 else None,
    }


def _ollama(path: str, body: dict | None = None) -> dict:

    import urllib.request

    request = urllib.request.Request(OLLAMA + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read().decode("utf-8"))


def resources() -> None:

    import subprocess

    found: dict = {}

    for name in LOCAL_MODELS:
        result = subprocess.run([sys.executable, __file__, "resources-one", name], capture_output=True, text=True)
        try:
            found[name] = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            found[name] = {"error": (result.stderr.strip().splitlines() or ["no output"])[-1][:200]}
        print(name, found[name], flush=True)

    try:
        tags = {m["name"]: m for m in _ollama("/api/tags")["models"]}
    except OSError:
        tags = {}
        print("Ollama is not reachable: its models are left out", flush=True)

    for name in OLLAMA_MODELS if tags else []:
        if name not in tags:
            continue
        started = time.perf_counter()
        _ollama("/api/generate", {"model": name, "prompt": "OK", "stream": False, "options": {"num_predict": 1}})
        load_seconds = time.perf_counter() - started
        running = next((m for m in _ollama("/api/ps").get("models", []) if m["name"] == name), {})
        # One model in Ollama at a time (docs/decisions/deployment.md): unload it.
        _ollama("/api/generate", {"model": name, "keep_alive": 0})
        details = tags[name].get("details") or {}
        found[name] = {
            "model": f"{details.get('family')} {details.get('parameter_size')} {details.get('quantization_level')}",
            "runsOn": "this machine, CPU" if not running.get("size_vram") else "this machine, GPU",
            "parameters": details.get("parameter_size"),
            "diskMb": round(tags[name]["size"] / 1e6, 1),
            "loadedMb": round(running.get("size", 0) / 1e6, 1) or None,
            "peakMb": None,
            "loadSeconds": round(load_seconds, 1),
            "coresUsed": None,
        }
        print(name, found[name], flush=True)

    for alias in ("claude-headless:haiku", "claude-headless:sonnet"):
        found[alias] = {
            "model": "not published", "runsOn": "Anthropic's servers, through the claude.ai subscription",
            "parameters": None, "diskMb": None, "loadedMb": None, "peakMb": None, "loadSeconds": None, "coresUsed": None,
            "note": "nothing to hold locally but the `claude` CLI process per call; needs the network and a plan",
        }

    import os
    import platform

    machine = {
        "cpu": next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name")), platform.processor()),
        "threads": os.cpu_count(),
        "ramGb": round(int(Path("/proc/meminfo").read_text().split()[1]) / 1e6, 1),
        "gpu": "none used",
    }

    RESOURCES.write_text(json.dumps({"measuredAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "machine": machine, "models": found}, indent=2) + "\n", encoding="utf-8")
    print(f"written {RESOURCES}")


if __name__ == "__main__":

    if sys.argv[1:2] == ["resources-one"]:
        print(json.dumps(resources_one(sys.argv[2])))
        sys.exit(0)

    if sys.argv[1:2] == ["resources"]:
        resources()
        sys.exit(0)

    which = sys.argv[1:] or ["topics", "entities"]

    if "topics" in which:
        topics()

    if "entities" in which:
        entities()

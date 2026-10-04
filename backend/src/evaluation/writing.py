"""
The writing-model benchmark (Sprint 6): the corrector's five LLM metrics
- grammar, factConsistency, seo, hallucinationIndex, style - per model.

    uv run python -m src.evaluation.cli writing run --model llama3.2:3b [--repeats 2]
    uv run python -m src.evaluation.cli writing report --run <dir> --run <dir> [--prices ...]

What is measured
----------------

The corrector does not write: it *judges* writing, five scores and a
summary each, from one LLM call. So the model is benchmarked as an
editor, and an editor is good when it notices what is wrong. Human
scores for "how good is this text's SEO" would be an opinion per text;
a planted defect is not. The committed set
(`data/evaluation/writing/texts_en_es.jsonl`) is six short news texts,
three English and three Spanish, each in a clean version and in five
versions with exactly one planted defect, each aimed at one metric:

    grammar        -> grammar             agreement, spelling, tense errors
    contradiction  -> factConsistency     a figure or date contradicting an earlier one
    fabrication    -> hallucinationIndex  an invented authority and sweeping claims
    seo            -> seo                 a vague headline, the subject gone from the lead
    style          -> style               a casual, repetitive, exclamatory register

Each defect version against its own clean text is a pair whose right
answer is known: the targeted score should go down. The rubric
(docs/decisions/evaluation.md §Writing-model benchmark) is built on that.

Only `TextCorrector.llm_metrics` runs - readability and
coverageVerification are deterministic and do not depend on the model.
It is the corrector's own method, prompt included: benchmarking a copy
would measure the copy.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.config.settings import settings
from src.evaluation.dataset import lf
from src.evaluation.runner import git_commit, model_slug, now, provider_of, without_credentials
from src.evaluation.stats import bootstrap_mean, mean, paired_bootstrap_mean, rounded
from src.evaluation.store import ResultsFile, read_json, write_json
from src.evaluation.usage import UsageMeter, cost, price_for, summarise, totals
from src.services.concurrency import bounded_map
from src.services.corrector.text_corrector import (
    LLM_METRIC_KEYS,
    SYSTEM_PROMPT,
    UNAVAILABLE_SUMMARY,
)
from src.services.llms import LLMUnavailableError

logger = logging.getLogger(__name__)

# Bump when a change alters what a run produces or how a record reads.
WRITING_VERSION = 1

CLEAN = "clean"

VARIANT_TARGETS = {
    "grammar": "grammar",
    "contradiction": "factConsistency",
    "fabrication": "hallucinationIndex",
    "seo": "seo",
    "style": "style",
}

OK = "ok"
UNREACHABLE = "unreachable"
ERROR = "error"

DEFAULT_SEED = 2026
DEFAULT_RESAMPLES = 10_000

MANIFEST = "run.json"
RESULTS = "results.jsonl"


def default_texts() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "writing" / "texts_en_es.jsonl"


def default_writing_runs() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "writing" / "runs"


def default_writing_reports() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "writing" / "reports"


def prompt_sha256() -> str:

    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------
# The text set
# ----------------------------------------------------------------------


class TextSetError(ValueError):
    """The text set cannot be benchmarked as it stands."""


@dataclass(frozen=True)
class Text:

    id: str

    # The clean text this one is a version of.
    base: str

    language: str

    variant: str

    # The metric a defect version is aimed at; None for a clean text.
    target: str | None

    # Strings, any of which in the target metric's summary or issues
    # means the model named the defect rather than only scoring it down.
    # Whole words; `*` at the end makes a stem (see `mentioned`).
    mentions: tuple[str, ...]

    text: str


@dataclass(frozen=True)
class TextSet:

    path: Path

    stem: str

    sha256: str

    texts: tuple[Text, ...]

    def by_id(self) -> dict[str, Text]:

        return {text.id: text for text in self.texts}


def load_texts(path: str | Path | None = None) -> TextSet:
    """
    Refuses a set that cannot be scored: a defect version without its
    clean text, a target that is not the variant's, two versions of one
    kind, or a duplicate id.
    """

    path = Path(path or default_texts())

    data = path.read_bytes()

    texts = []

    for number, line in enumerate(data.decode("utf-8").splitlines(), start=1):

        if not line.strip():
            continue

        raw = json.loads(line)

        variant = raw.get("variant")

        expected = None if variant == CLEAN else VARIANT_TARGETS.get(variant)

        if variant != CLEAN and expected is None:
            raise TextSetError(f"{path.name}:{number}: unknown variant {variant!r}")

        if raw.get("target") != expected:
            raise TextSetError(
                f"{path.name}:{number}: a {variant} text targets {expected}, not {raw.get('target')!r}"
            )

        if not raw.get("text", "").strip():
            raise TextSetError(f"{path.name}:{number}: empty text")

        texts.append(Text(
            id=raw["id"],
            base=raw["base"],
            language=raw["language"],
            variant=variant,
            target=expected,
            mentions=tuple(raw.get("mentions") or ()),
            text=raw["text"],
        ))

    ids = [text.id for text in texts]

    if len(ids) != len(set(ids)):
        raise TextSetError(f"{path.name}: duplicate ids")

    seen: set[tuple[str, str]] = set()

    for text in texts:
        if (text.base, text.variant) in seen:
            raise TextSetError(f"{path.name}: two {text.variant} versions of {text.base}")
        seen.add((text.base, text.variant))

    for text in texts:
        if text.variant != CLEAN and (text.base, CLEAN) not in seen:
            raise TextSetError(f"{path.name}: {text.id} has no clean version of {text.base}")

    if not texts:
        raise TextSetError(f"{path.name}: no texts")

    return TextSet(path=path, stem=path.stem, sha256=hashlib.sha256(lf(data)).hexdigest(), texts=tuple(texts))


def writing_key(texts_sha256: str, model: str, prompt: str) -> str:
    """
    The text set, the model, the corrector's prompt and WRITING_VERSION.
    Not the repeat count: `--repeats 3` after a run of 1 adds repeats to
    the same run.
    """

    canonical = json.dumps(
        {"texts": texts_sha256, "model": model, "prompt": prompt, "writingVersion": WRITING_VERSION},
        sort_keys=True,
    )

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


# ----------------------------------------------------------------------
# Running
# ----------------------------------------------------------------------


def unit_id(text_id: str, repeat: int) -> str:

    return f"{text_id}#{repeat}"


class WritingRunner:
    """
    Runs `corrector.llm_metrics` over every text, `repeats` times,
    resumably: one fsynced line per (text, repeat), ok units are done,
    errors and unreachable ones run again. The first Ctrl-C starts no new
    unit. `corrector` needs only `llm_metrics(text)`.
    """

    def __init__(
        self,
        texts: TextSet,
        model: str,
        *,
        corrector,
        meter: UsageMeter | None = None,
        provider: str = "",
        root: Path | None = None,
        max_workers: int | None = None,
        commit: str | None = None,
        on_record: Callable[[dict], None] | None = None,
    ):
        self.texts = texts
        self.model = model
        self.corrector = corrector
        self.meter = meter or UsageMeter()
        self.provider = provider
        self.max_workers = max_workers or settings.LLM_MAX_CONCURRENCY
        self.commit = commit or git_commit()
        self.on_record = on_record

        self.prompt = prompt_sha256()
        self.key = writing_key(texts.sha256, model, self.prompt)
        self.directory = Path(root or default_writing_runs()) / texts.stem / model_slug(model) / self.key
        self.results = ResultsFile(self.directory / RESULTS)

        self._stop = threading.Event()
        self._written: list[dict] = []
        self._lock = threading.Lock()

    def stop(self) -> None:

        self._stop.set()

    def pending(self, *, repeats: int = 1, limit: int | None = None) -> list[tuple[Text, int]]:

        texts = list(self.texts.texts)[:limit] if limit else list(self.texts.texts)

        done = self.results.latest(lambda record: record["id"])

        return [
            (text, repeat)
            for repeat in range(repeats)
            for text in texts
            if (done.get(unit_id(text.id, repeat)) or {}).get("status") != OK
        ]

    def run(self, *, repeats: int = 1, limit: int | None = None, fresh: bool = False) -> dict:

        self.directory.mkdir(parents=True, exist_ok=True)

        set_aside = self.results.set_aside() if fresh else None

        todo = self.pending(repeats=repeats, limit=limit)

        session = {
            "startedAt": now(),
            "gitCommit": self.commit,
            "provider": self.provider,
            "repeats": repeats,
            "limit": limit,
            "fresh": fresh,
            "setAside": str(set_aside) if set_aside else None,
            "tornLinesDropped": self.results.torn,
            "pending": len(todo),
        }

        self._write_manifest(session)

        self._written = []

        statuses = bounded_map(
            self._run_one,
            todo,
            max_workers=self.max_workers,
            thread_name_prefix="eval-writing",
        )

        session.update({
            "finishedAt": now(),
            "ran": sum(1 for status in statuses if status is not None),
            "ok": sum(1 for status in statuses if status == OK),
            "unreachable": sum(1 for status in statuses if status == UNREACHABLE),
            "errors": sum(1 for status in statuses if status == ERROR),
            "stopped": self._stop.is_set(),
            "usage": totals(self._written),
        })

        self._write_manifest(session, finished=True)

        return session

    def _run_one(self, unit: tuple[Text, int]) -> str | None:

        if self._stop.is_set():
            return None

        text, repeat = unit

        started_at = now()
        started = time.perf_counter()

        metrics: dict | None = None
        status, error = OK, None

        with self.meter.attribute() as calls:

            try:
                metrics = {
                    key: {
                        "score": metric.score,
                        "summary": metric.summary,
                        "issues": list(metric.issues),
                        # The corrector scores an unusable entry 0; that
                        # zero is a format failure, not a judgement, and
                        # must not be averaged as one.
                        "usable": metric.summary != UNAVAILABLE_SUMMARY,
                    }
                    for key, metric in self.corrector.llm_metrics(text.text).items()
                }
            except LLMUnavailableError as exc:
                status, error = UNREACHABLE, f"{type(exc).__name__}: {exc}"
            except Exception as exc:
                logger.exception("writing benchmark unit %s failed", text.id)
                status, error = ERROR, f"{type(exc).__name__}: {exc}"

        record = {
            "id": unit_id(text.id, repeat),
            "textId": text.id,
            "base": text.base,
            "variant": text.variant,
            "target": text.target,
            "language": text.language,
            "repeat": repeat,
            "status": status,
            "error": error,
            "metrics": metrics,
            "usable": sum(1 for metric in (metrics or {}).values() if metric["usable"]),
            "latency": {"total": round(time.perf_counter() - started, 4)},
            "usage": summarise(calls),
            "model": self.model,
            "provider": self.provider,
            "writingVersion": WRITING_VERSION,
            "promptSha256": self.prompt,
            "gitCommit": self.commit,
            "startedAt": started_at,
            "finishedAt": now(),
        }

        self.results.append(record)

        with self._lock:
            self._written.append({"usage": record["usage"], "latency": record["latency"]})

        if self.on_record is not None:
            self.on_record(record)

        return status

    def _write_manifest(self, session: dict, finished: bool = False) -> None:

        path = self.directory / MANIFEST

        manifest = read_json(path) if path.exists() else {
            "key": self.key,
            "writingVersion": WRITING_VERSION,
            "texts": {
                "path": str(self.texts.path),
                "stem": self.texts.stem,
                "sha256": self.texts.sha256,
                "count": len(self.texts.texts),
            },
            "model": self.model,
            "provider": self.provider,
            "promptSha256": self.prompt,
            "gitCommit": self.commit,
            "startedAt": now(),
            "settings": {
                "LLM_BASE_URL": without_credentials(settings.LLM_BASE_URL),
                "LLM_TIMEOUT": settings.LLM_TIMEOUT,
                "LLM_MAX_CONCURRENCY": settings.LLM_MAX_CONCURRENCY,
            },
        }

        sessions = manifest.setdefault("sessions", [])

        if finished and sessions and sessions[-1].get("startedAt") == session["startedAt"]:
            sessions[-1] = session
        else:
            sessions.append(session)

        write_json(path, manifest)


def build_writing_runner(texts: TextSet, model: str, root: Path | None = None) -> WritingRunner:
    """
    The corrector with a metered client for `model`. The provider is
    LLM_BASE_URL / LLM_API_KEY, as everywhere else.
    """

    from src.evaluation.usage import metered
    from src.services.corrector.text_corrector import TextCorrector
    from src.services.llms import LLMClient

    meter = UsageMeter()

    corrector = TextCorrector(llm=metered(LLMClient(model=model), meter))

    return WritingRunner(
        texts,
        model,
        corrector=corrector,
        meter=meter,
        provider=provider_of(settings.LLM_BASE_URL),
        root=root,
    )


# ----------------------------------------------------------------------
# Scoring: the rubric
# ----------------------------------------------------------------------


@dataclass
class WritingRun:

    directory: Path

    manifest: dict

    records: list[dict]


def load_writing_run(directory: str | Path) -> WritingRun:

    directory = Path(directory)

    latest = ResultsFile(directory / RESULTS).latest(lambda record: record["id"])

    return WritingRun(
        directory=directory,
        manifest=read_json(directory / MANIFEST),
        records=[latest[key] for key in sorted(latest)],
    )


def text_scores(records: list[dict]) -> dict[str, dict[str, float | None]]:
    """Each text's mean score per metric over its usable repeats."""

    collected: dict[str, dict[str, list[float]]] = {}

    for record in records:

        if record.get("status") != OK:
            continue

        per_metric = collected.setdefault(record["textId"], {key: [] for key in LLM_METRIC_KEYS})

        for key, metric in (record.get("metrics") or {}).items():
            if metric.get("usable") and key in per_metric:
                per_metric[key].append(metric["score"])

    return {
        text_id: {key: mean(values) for key, values in per_metric.items()}
        for text_id, per_metric in collected.items()
    }


def pairs(texts: TextSet, scores: dict[str, dict[str, float | None]]) -> list[dict]:
    """
    Every defect version against its clean text, on the targeted metric:
    `detected` is 1 when the defect version scored lower, 0.5 on a tie
    and 0 when it scored higher - so a model that gives every text the
    same score sits at 0.5, chance, not at 0. A pair either side of which
    has no usable score is unscorable, and kept so it can be counted.
    """

    # By (base, variant), not by an id spelt "<base>-clean": load_texts
    # guarantees the clean version exists, not what it is called.
    clean_ids = {text.base: text.id for text in texts.texts if text.variant == CLEAN}

    result = []

    for text in texts.texts:

        if text.variant == CLEAN:
            continue

        clean = scores.get(clean_ids[text.base]) or {}
        defect = scores.get(text.id) or {}

        target = text.target

        before, after = clean.get(target), defect.get(target)

        if before is None or after is None:
            result.append({"id": text.id, "target": target, "language": text.language,
                           "scorable": False, "detected": None, "drop": None, "offTarget": None})
            continue

        others = [
            abs(defect[key] - clean[key])
            for key in LLM_METRIC_KEYS
            if key != target and defect.get(key) is not None and clean.get(key) is not None
        ]

        result.append({
            "id": text.id,
            "target": target,
            "language": text.language,
            "scorable": True,
            "detected": 1.0 if after < before else 0.5 if after == before else 0.0,
            "drop": before - after,
            "offTarget": mean(others),
        })

    return result


def mentioned(mention: str, words: str) -> bool:
    """
    `mention` appears in `words` as a whole word or phrase. A trailing `*`
    makes it a stem (`repetit*` for repetitive, repetition, repetitivo).
    An all-capitals mention is matched as written: lowercased, the
    fabricated "WHO" is the pronoun in every other summary, and "a
    probado" sat inside the correct "ha probado" until whole words were
    required.
    """

    stem = mention.rstrip("*")

    pattern = r"(?<!\w)" + re.escape(stem) + ("" if mention.endswith("*") else r"(?!\w)")

    return re.search(pattern, words, 0 if stem.isupper() else re.IGNORECASE) is not None


def named(record: dict, text: Text) -> bool:
    """The model named the planted defect in the targeted metric's own words."""

    metric = (record.get("metrics") or {}).get(text.target) or {}

    words = " ".join([metric.get("summary") or "", *(metric.get("issues") or [])])

    return any(mentioned(mention, words) for mention in text.mentions)


def score(
    texts: TextSet,
    records: list[dict],
    *,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> dict:
    """One model's results against the rubric."""

    by_id = texts.by_id()

    ok = [record for record in records if record.get("status") == OK]

    scores = text_scores(records)

    scored_pairs = pairs(texts, scores)

    scorable = [pair for pair in scored_pairs if pair["scorable"]]

    detection = [pair["detected"] for pair in scorable]

    defect_records = [
        record for record in ok
        if by_id.get(record["textId"]) and by_id[record["textId"]].variant != CLEAN
    ]

    named_flags = [named(record, by_id[record["textId"]]) for record in defect_records]

    per_metric = {}

    for target in LLM_METRIC_KEYS:

        group = [pair for pair in scorable if pair["target"] == target]

        group_records = [
            flag for record, flag in zip(defect_records, named_flags)
            if by_id[record["textId"]].target == target
        ]

        per_metric[target] = {
            "pairs": len(group),
            "detection": mean([pair["detected"] for pair in group]),
            "meanDrop": rounded(mean([pair["drop"] for pair in group]), 2),
            "named": mean([1.0 if flag else 0.0 for flag in group_records]),
            "unusable": sum(
                1 for record in ok
                if not ((record.get("metrics") or {}).get(target) or {}).get("usable")
            ),
            "cleanMean": rounded(mean([
                scores[text.id][target]
                for text in texts.texts
                if text.variant == CLEAN and scores.get(text.id, {}).get(target) is not None
            ]), 2),
        }

    by_language = {}

    for language in sorted({text.language for text in texts.texts}):
        values = [pair["detected"] for pair in scorable if pair["language"] == language]
        by_language[language] = {"pairs": len(values), "detection": mean(values)}

    run_totals = totals(records)

    return {
        "units": {
            "total": len(records),
            "ok": len(ok),
            "unreachable": sum(1 for record in records if record.get("status") == UNREACHABLE),
            "errors": sum(1 for record in records if record.get("status") == ERROR),
            "repeats": len({record.get("repeat") for record in records}),
        },
        # The rubric's first criterion: a model that cannot return the five
        # metrics as asked is not usable, whatever it scores when it does.
        "formatCompliance": (
            mean([1.0 if record.get("usable") == len(LLM_METRIC_KEYS) else 0.0 for record in ok])
        ),
        "detection": {
            "value": mean(detection),
            **bootstrap_mean(detection, seed=seed, resamples=resamples),
            "pairs": len(scorable),
            "unscorable": len(scored_pairs) - len(scorable),
        },
        "named": mean([1.0 if flag else 0.0 for flag in named_flags]),
        "offTargetDrift": rounded(mean([pair["offTarget"] for pair in scorable if pair["offTarget"] is not None]), 2),
        "consistency": consistency(records),
        "perMetric": per_metric,
        "byLanguage": by_language,
        "pairs": scored_pairs,
        "usage": run_totals,
        "bootstrap": {"seed": seed, "resamples": resamples},
    }


def consistency(records: list[dict]) -> dict:
    """
    How far apart a text's repeats score, per metric: the mean range
    (max - min) over texts run more than once. 0 is a model that gives
    the same answer twice. None until a run has repeats.
    """

    collected: dict[tuple[str, str], list[float]] = {}

    for record in records:

        if record.get("status") != OK:
            continue

        for key, metric in (record.get("metrics") or {}).items():
            if metric.get("usable"):
                collected.setdefault((record["textId"], key), []).append(metric["score"])

    ranges: dict[str, list[float]] = {key: [] for key in LLM_METRIC_KEYS}

    for (text_id, key), values in collected.items():
        if len(values) > 1 and key in ranges:
            ranges[key].append(max(values) - min(values))

    every = [value for values in ranges.values() for value in values]

    return {
        "meanRange": rounded(mean(every), 2),
        "perMetric": {key: rounded(mean(values), 2) for key, values in ranges.items()},
        "textsRepeated": len({text_id for (text_id, _), values in collected.items() if len(values) > 1}),
    }


# ----------------------------------------------------------------------
# The comparison
# ----------------------------------------------------------------------


def compare_runs(
    run_directories: list[str | Path],
    *,
    texts: TextSet | None = None,
    prices: dict | None = None,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
) -> dict:
    """
    Every run scored against the rubric, side by side, and each later run
    against the first on detection, paired over the pairs both scored.
    All runs must be over the same text set and the same corrector prompt.
    """

    runs = [load_writing_run(directory) for directory in run_directories]

    shas = {(run.manifest.get("texts") or {}).get("sha256") for run in runs}
    prompts = {run.manifest.get("promptSha256") for run in runs}

    if len(shas) != 1:
        raise ValueError("every run in a comparison must be over the same text set (sha256 differs)")

    if len(prompts) != 1:
        raise ValueError("every run in a comparison must use the same corrector prompt")

    texts = texts or load_texts((runs[0].manifest.get("texts") or {}).get("path"))

    if texts.sha256 not in shas:
        raise ValueError("the text set on disk is not the one these runs used")

    rows = []

    for run in runs:

        scored = score(texts, run.records, seed=seed, resamples=resamples)

        model = run.manifest.get("model")
        provider = run.manifest.get("provider")

        scored["usage"]["cost"] = cost(scored["usage"], price_for(prices, model, provider))

        rows.append({"model": model, "provider": provider, "key": run.manifest.get("key"),
                     "directory": str(run.directory), **scored})

    baseline = rows[0]

    for row in rows[1:]:

        a = {pair["id"]: pair["detected"] for pair in baseline["pairs"] if pair["scorable"]}
        b = {pair["id"]: pair["detected"] for pair in row["pairs"] if pair["scorable"]}

        shared = sorted(set(a) & set(b))

        row["vsBaseline"] = {
            "baseline": baseline["model"],
            "pairs": len(shared),
            **paired_bootstrap_mean(
                [a[key] for key in shared], [b[key] for key in shared], seed=seed, resamples=resamples,
            ),
        }

    return {
        "texts": {"path": str(texts.path), "stem": texts.stem, "sha256": texts.sha256, "count": len(texts.texts)},
        "promptSha256": prompts.pop(),
        "bootstrap": {"seed": seed, "resamples": resamples},
        "runs": rows,
    }


def write_comparison(
    run_directories: list[str | Path],
    *,
    prices: dict | None = None,
    seed: int = DEFAULT_SEED,
    resamples: int = DEFAULT_RESAMPLES,
    root: Path | None = None,
) -> Path:

    result = compare_runs(run_directories, prices=prices, seed=seed, resamples=resamples)

    target = Path(root or default_writing_reports()) / result["texts"]["stem"]

    target.mkdir(parents=True, exist_ok=True)

    write_json(target / "comparison.json", result)

    (target / "comparison.md").write_text(render(result), encoding="utf-8", newline="\n")

    return target


def _pct(value) -> str:

    return "n/a" if value is None else f"{value * 100:.0f}%"


def _num(value, digits: int = 1) -> str:

    return "n/a" if value is None else f"{value:.{digits}f}"


def _row(cells) -> str:

    return "| " + " | ".join(str(cell) for cell in cells) + " |"


def render(result: dict) -> str:

    texts = result["texts"]
    boot = result["bootstrap"]

    lines = [
        f"# Writing models compared: {texts['stem']}",
        "",
        f"{texts['count']} texts (sha256 `{texts['sha256'][:12]}`), corrector prompt "
        f"`{result['promptSha256'][:12]}`. The rubric is docs/decisions/evaluation.md "
        "§Writing-model benchmark. Detection intervals: percentile 95% bootstrap over pairs, "
        f"{boot['resamples']} resamples, seed {boot['seed']}.",
        "",
        "## Rubric",
        "",
        _row(["Model", "Provider", "Format compliance", "Detection [95% CI]", "Defect named",
              "Off-target drift", "Repeat range", "Median s/text", "Completion tok/text", "Tok/s",
              "Cost per 100 texts"]),
        _row(["---"] * 11),
    ]

    for row in result["runs"]:

        detection = row["detection"]
        usage = row["usage"]
        priced = usage.get("cost")

        lines.append(_row([
            f"`{row['model']}`", row["provider"], _pct(row["formatCompliance"]),
            f"{_pct(detection['value'])} [{_pct(detection['low'])}, {_pct(detection['high'])}]"
            f" ({detection['pairs']} pairs)",
            _pct(row["named"]), _num(row["offTargetDrift"]),
            _num(row["consistency"]["meanRange"]),
            _num(usage["unitLatency"]["median"]), _num(usage["completionTokensPerUnit"], 0),
            _num(usage["completionTokensPerSecond"]),
            f"{priced['per100Units']:.4f} {priced['currency']}" if priced else "n/a",
        ]))

    lines += [
        "",
        "## Detection per metric (defect scored lower than its clean text)",
        "",
        _row(["Model", *LLM_METRIC_KEYS]),
        _row(["---"] * (len(LLM_METRIC_KEYS) + 1)),
    ]

    for row in result["runs"]:
        lines.append(_row([
            f"`{row['model']}`",
            *(f"{_pct(row['perMetric'][key]['detection'])} (drop {_num(row['perMetric'][key]['meanDrop'])})"
              for key in LLM_METRIC_KEYS),
        ]))

    lines += [
        "",
        "## Clean texts: mean score per metric (calibration)",
        "",
        _row(["Model", *LLM_METRIC_KEYS]),
        _row(["---"] * (len(LLM_METRIC_KEYS) + 1)),
    ]

    for row in result["runs"]:
        lines.append(_row([
            f"`{row['model']}`", *(_num(row["perMetric"][key]["cleanMean"]) for key in LLM_METRIC_KEYS),
        ]))

    later = [row for row in result["runs"] if row.get("vsBaseline")]

    if later:

        lines += [
            "",
            "## Against the first run, paired over the pairs both scored",
            "",
            _row(["Model", "Baseline", "Pairs", "Detection B − A", "95% CI"]),
            _row(["---"] * 5),
        ]

        for row in later:
            vs = row["vsBaseline"]
            lines.append(_row([
                f"`{row['model']}`", f"`{vs['baseline']}`", vs["pairs"],
                "n/a" if vs["difference"] is None else f"{vs['difference'] * 100:+.0f} pts",
                "n/a" if vs["low"] is None else f"[{vs['low'] * 100:+.0f}, {vs['high'] * 100:+.0f}] pts",
            ]))

    lines += ["", "## Units", ""]

    for row in result["runs"]:
        units = row["units"]
        lines.append(
            f"- `{row['model']}`: {units['ok']} of {units['total']} ok, {units['unreachable']} unreachable, "
            f"{units['errors']} errors, {units['repeats']} repeat(s); "
            f"{row['detection']['unscorable']} pairs unscorable (no usable score on one side)."
        )

    return "\n".join(lines).rstrip() + "\n"

"""
Runs the pipeline's own `check_claim` over a labelled set, resumably.

What a run is
-------------

One dataset, one model, one effective set of thresholds, the
environment's scoring weights, one corpus mode: those five (and
HARNESS_VERSION) hash into the run's key, and the key names its
directory. Same five, same directory - so starting the same
command again *resumes*, and changing any of them starts a new run
rather than mixing two configurations in one results file.

The git commit is recorded on every record, not keyed: keying it would
throw a run away on every commit.

How a claim is run
------------------

Exactly as `POST /verify-claim` runs one: `ClaimService.build_claim` (the
GLiNER pass, confidence 1.0) then `FactChecker.check_claim`. The harness
adds only what an article run would have handed the claim and the
endpoint cannot: the row's `language` always, and for a custom-set row
the article it came from as `context.url`, so that article cannot be
retrieved as evidence for its own claim. x-fact rows get no context: the
harness hands the pipeline nothing from the gold row that production
would not have.

docs/decisions/evaluation.md §How one claim is run, §Run layout.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from src.config.settings import WEIGHT_GROUPS, settings
from src.config.thresholds import SEARCH_QUERY_KINDS, PipelineThresholds
from src.evaluation.dataset import CUSTOM, Dataset, DatasetRow
from src.evaluation.record import (
    HARNESS_VERSION,
    OK,
    Provenance,
    Timing,
    build_record,
    error_record,
    jsonable,
)
from src.evaluation.store import ResultsFile, read_json, write_json
from src.evaluation.usage import UsageMeter, summarise, totals
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.second_look import doubt

logger = logging.getLogger(__name__)

SNAPSHOT = "snapshot"
NONE = "none"
CORPUS_MODES = (SNAPSHOT, NONE)

# What a run asks of the pipeline. `retrieval` stops before the model: a
# stand-in verifier answers UNVERIFIED without a call, so a retrieval
# strategy is measured for its search and fetch time alone. Its verdicts
# mean nothing and its report has no classification metrics.
FULL = "full"
RETRIEVAL = "retrieval"
# `oracle` gives the model the annotator's own pages instead of a search
# (FactChecker.check_against): the gold-evidence condition of FEVER and
# AVeriTeC, RQ2's third condition (P0.5). Two models given the same pages
# differ by their reading alone, which a search, different on every run,
# never allows. A row with no reference link, or none readable, reaches
# the model with no evidence and is UNVERIFIED, as the pipeline would be.
ORACLE = "oracle"
# `closed_book` asks the model about the claim alone, no evidence and no
# pipeline (closed_book.py): RQ2's first condition. Its own prompt, since
# the pipeline never asks the model without evidence.
CLOSED_BOOK = "closed_book"
MODES = (FULL, RETRIEVAL, ORACLE, CLOSED_BOOK)

# The "model" of a retrieval-only run: its directory and its records say
# no model was asked.
RETRIEVAL_ONLY_MODEL = "retrieval-only"

RETRIEVAL_ONLY_EXPLANATION = "Retrieval-only run: the model was not asked."

# What the tuning loop (`--loop`) made of a claim, the first that applies.
LOOP_UNAVAILABLE = "unavailable"      # the first pass's search or model was never reached
LOOP_AGREED = "agreed"                # the first verdict is the gold label
LOOP_FIXED = "fixed"                  # the second look reached the gold label
LOOP_NO_REFERENCE = "no_reference"    # still wrong; the row has no links to check against
LOOP_UNREADABLE = "unreadable"        # still wrong; none of its links could be read
LOOP_RETRIEVAL = "retrieval"          # the annotator's pages give gold: the search never found them
LOOP_ADJUDICATE = "adjudicate"        # the annotator's pages give the pipeline's verdict: a person decides
LOOP_REASONING = "reasoning"          # the annotator's pages give a third verdict
LOOP_OUTCOMES = (
    LOOP_AGREED, LOOP_FIXED, LOOP_RETRIEVAL, LOOP_ADJUDICATE, LOOP_REASONING,
    LOOP_UNREADABLE, LOOP_NO_REFERENCE, LOOP_UNAVAILABLE,
)

MANIFEST = "run.json"
RESULTS = "results.jsonl"
CORPUS_DIR = "vector_db"


def default_runs_root() -> Path:

    return Path(settings.STORAGE_PATH) / "evaluation" / "runs"


def model_slug(model: str) -> str:
    """`llama3.2:3b` -> `llama3.2-3b`: a directory name on every OS."""

    return re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-") or "model"


def provider_of(base_url: str) -> str:
    """The endpoint's host and port: who served the model, without secrets."""

    parts = urlsplit(base_url)

    if not parts.hostname:
        return base_url

    return f"{parts.hostname}:{parts.port}" if parts.port else parts.hostname


# What the verifier read of each source before it was a threshold.
_EXCERPT_BEFORE = {"verifier_excerpt": "head", "verifier_excerpt_chars": 1500}


def keyed_thresholds(thresholds: PipelineThresholds) -> dict:
    """
    The thresholds as a run's key and hash see them. A field added after
    runs were made counts only when it differs from what those runs did,
    so they keep their keys and still resume: `query_kinds` (2026-10-20)
    when it is not all three, the only plan there was before; the
    verifier's excerpt (2026-10-21) when it is the first 1,500 characters
    of each source, which every earlier run read.
    """

    dumped = thresholds.model_dump()

    if tuple(dumped.get("query_kinds") or ()) == SEARCH_QUERY_KINDS:
        dumped.pop("query_kinds")

    for name, before in _EXCERPT_BEFORE.items():
        if dumped.get(name) == before:
            dumped.pop(name)

    return dumped


def thresholds_hash(thresholds: PipelineThresholds) -> str:

    return _digest(keyed_thresholds(thresholds))[:12]


# The scoring constants that are environment-only, not per-run thresholds
# (invariant 1's declared exception): read once at import by the ranker,
# the retriever's funnel and the scorer. They change what a run produces,
# so they are part of its key. Otherwise a run with CONFIDENCE_LLM_WEIGHT
# changed in the environment would "resume" the run made before the
# change - the tuning phase's whole method.
_SCORING_CONSTANTS = (
    *(name for names in WEIGHT_GROUPS.values() for name in names),
    "RANKING_DEFAULT_RELIABILITY",
    "EVIDENCE_RECENCY_HALF_LIFE_DAYS",
)


def scoring_weights() -> dict[str, float]:

    return {name: getattr(settings, name) for name in _SCORING_CONSTANTS}


def run_key(
    dataset_sha256: str,
    model: str,
    thresholds: PipelineThresholds,
    corpus: str,
    weights: dict[str, float] | None = None,
    mode: str = FULL,
    label: str | None = None,
    loop: bool = False,
    reasoning_effort: str | None = None,
) -> str:
    """
    The mode, the label, the loop and the reasoning effort count only
    when set, so a full, unlabelled run keeps the key it had before any
    existed. The label is what separates two strategies the settings
    cannot tell apart - the same thresholds over two commits of the
    retriever. The reasoning effort (LLM_REASONING_EFFORT for this model)
    separates a hybrid model told not to think from the same model
    thinking: one name, two answers, minutes apart per claim on a CPU.
    """

    keyed = {
        "dataset": dataset_sha256,
        "model": model,
        "thresholds": keyed_thresholds(thresholds),
        "weights": weights if weights is not None else scoring_weights(),
        "corpus": corpus,
        "harnessVersion": HARNESS_VERSION,
    }

    if mode != FULL:
        keyed["mode"] = mode

    if label:
        keyed["label"] = label

    if loop:
        keyed["loop"] = True

    if reasoning_effort:
        keyed["reasoningEffort"] = reasoning_effort

    return _digest(keyed)[:12]


def _digest(value) -> str:

    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# How long git may take to say whether the tree is clean. In compose the
# checkout is a read-only Windows bind mount: git cannot refresh the
# index there, so every `git status` re-reads every tracked file across
# it. Measured 2026-10-13: 5.0-5.3 s, against a timeout of 5. One of the
# pilot's sessions lost the race and recorded `unknown` for 49 claims
# whose HEAD was known.
GIT_STATUS_TIMEOUT = 60


def git_commit() -> str:
    """
    HEAD, with `-dirty` when the tree has changes: a result from
    uncommitted code should say so. `-unchecked` when HEAD is known but
    whether the tree was clean could not be found out in time: the
    commit is still worth recording, and the suffix says it was not
    verified. `unknown` when there is no repository at all (the image
    without the compose layer's mount).
    """

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=GIT_STATUS_TIMEOUT, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return f"{head}-unchecked"

    return f"{head}-dirty" if dirty else head


def now() -> str:

    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass(frozen=True)
class RunConfig:

    dataset: Dataset

    model: str

    thresholds: PipelineThresholds = field(default_factory=PipelineThresholds)

    corpus: str = SNAPSHOT

    root: Path = field(default_factory=default_runs_root)

    # The environment's scoring weights when the run was configured.
    weights: dict = field(default_factory=scoring_weights)

    mode: str = FULL

    # A name for the strategy this run measures (`--label`), keyed.
    label: str | None = None

    # The tuning loop (`--loop`): after each claim, a second look when the
    # verdict disagrees with gold (or is in doubt), then the annotator's
    # own pages when it still disagrees. Keyed: its records hold more.
    loop: bool = False

    @property
    def key(self) -> str:

        return run_key(
            self.dataset.sha256, self.model, self.thresholds, self.corpus, self.weights,
            mode=self.mode, label=self.label, loop=self.loop,
            # The mapping LLMClient reads for the same model, so the key
            # says what every call was sent.
            reasoning_effort=settings.LLM_REASONING_EFFORT.get(self.model),
        )

    @property
    def directory(self) -> Path:

        return Path(self.root) / self.dataset.stem / model_slug(self.model) / self.key


def is_done(record: dict | None, retry_unavailable: bool = False) -> bool:
    """
    `ok` is done; an error is retried. With `--retry-unavailable`, so is
    a claim whose search or LLM was never reached: those are
    infrastructure outcomes, and the search fix exists to change them.
    """

    if record is None or record.get("status") != OK:
        return False

    if retry_unavailable and (record.get("searchUnavailable") or record.get("llmUnreachable")):
        return False

    return True


def latest_records(directory: Path) -> dict[str, dict]:
    """The last record written for each claim id."""

    return ResultsFile(Path(directory) / RESULTS).latest(lambda record: record["id"])


def context_for(row: DatasetRow) -> ArticleContext | None:
    """
    The custom set's article, so its URL is excluded from its own
    evidence. Nothing else from the row: title and lead stay empty.
    """

    if row.dataset != CUSTOM or not row.article_url:
        return None

    return ArticleContext(url=row.article_url, title="", lead="", keywords=[], entities={})


def reference_urls(row: DatasetRow) -> list[str]:
    """
    The row's reference links an oracle run reads: web addresses only,
    each once. x-fact's "<LINK NOT AVAILABLE>" placeholders are not pages.
    """

    return list(dict.fromkeys(
        link for link in row.reference_links
        if link.lower().startswith(("http://", "https://"))
    ))


class HarnessRunner:
    """
    The run loop. Collaborators are passed in so the tests can hand it a
    real FactChecker over the shared fakes; `build_runner` assembles the
    real ones.

    `checker` needs `check_claim(claim, on_phase, thresholds, *, context,
    language)`; `claims` needs `build_claim(text, on_phase, thresholds)`
    - a FactChecker and a ClaimService.
    """

    def __init__(
        self,
        config: RunConfig,
        *,
        checker,
        claims,
        meter: UsageMeter | None = None,
        provider: str = "",
        max_workers: int | None = None,
        manifest_extra: dict | None = None,
        on_record: Callable[[dict], None] | None = None,
        commit: str | None = None,
        closed_book=None,
    ):
        self.config = config
        self.checker = checker
        self.claims = claims
        # A ClosedBookJudge for a closed-book run; None otherwise.
        self.closed_book = closed_book
        self.meter = meter or UsageMeter()
        self.provider = provider
        self.max_workers = max_workers or settings.CLAIM_MAX_CONCURRENCY
        self.manifest_extra = manifest_extra or {}
        self.on_record = on_record
        self.commit = commit or git_commit()

        self.directory = config.directory
        self.results = ResultsFile(self.directory / RESULTS)

        self._stop = threading.Event()

        # What this session wrote, for its totals in run.json: usage and
        # time only, not whole records.
        self._written: list[dict] = []
        self._written_lock = threading.Lock()

        self._provenance = Provenance(
            model=config.model,
            provider=provider,
            thresholds_hash=thresholds_hash(config.thresholds),
            git_commit=self.commit,
        )

    def stop(self) -> None:
        """
        Start no new claim; the ones in flight finish and are written.
        What Ctrl-C does in the CLI: a resumed run then picks up exactly
        where this one stopped.
        """

        self._stop.set()

    def pending(self, *, limit: int | None = None, retry_unavailable: bool = False) -> list[DatasetRow]:
        """
        The rows still to run. `limit` is the first N rows of the dataset,
        not N more claims: the same `--limit` always means the same rows.
        """

        rows = list(self.config.dataset.rows)

        if limit is not None:
            rows = rows[:limit]

        done = self.results.latest(lambda record: record["id"])

        return [row for row in rows if not is_done(done.get(row.id), retry_unavailable)]

    def run(
        self,
        *,
        limit: int | None = None,
        retry_unavailable: bool = False,
        fresh: bool = False,
    ) -> dict:

        self.directory.mkdir(parents=True, exist_ok=True)

        set_aside = self.results.set_aside() if fresh else None

        todo = self.pending(limit=limit, retry_unavailable=retry_unavailable)

        session = {
            "startedAt": now(),
            "gitCommit": self.commit,
            "provider": self.provider,
            "limit": limit,
            "retryUnavailable": retry_unavailable,
            "fresh": fresh,
            "setAside": str(set_aside) if set_aside else None,
            "tornLinesDropped": self.results.torn,
            "pending": len(todo),
            # Per session, not only in the manifest: none of these is keyed,
            # so a resume may run with a longer timeout or fewer claims at
            # once. The pilot did (2026-10-13), after inference timed out
            # under four concurrent claims, and the manifest alone would
            # have said the whole run used the first session's values.
            "settings": self._settings(),
        }

        self._write_manifest(session)

        logger.info(
            "evaluation run %s: %d claim(s) to run in %s",
            self.config.key, len(todo), self.directory,
        )

        unattributed_before = len(self.meter.unattributed)

        self._written = []

        statuses = bounded_map(
            self._run_one,
            todo,
            max_workers=self.max_workers,
            thread_name_prefix="eval-claim",
        )

        session.update({
            "finishedAt": now(),
            "ran": sum(1 for status in statuses if status is not None),
            "ok": sum(1 for status in statuses if status == OK),
            "errors": sum(1 for status in statuses if status not in (None, OK)),
            "stopped": self._stop.is_set(),
            # LLM calls made off the claim's own thread, so not on any
            # record. Zero unless the pipeline moved its LLM call.
            "unattributedLlmCalls": len(self.meter.unattributed) - unattributed_before,
            # This session's LLM calls, tokens and time. The report sums
            # the whole run; this says what each resume cost.
            "usage": totals(self._written),
        })

        self._write_manifest(session, finished=True)

        return session

    def _run_one(self, row: DatasetRow) -> str | None:

        if self._stop.is_set():
            return None

        started_at = now()
        started = time.perf_counter()

        events: list[dict] = []
        events_lock = threading.Lock()

        def collect(name: str, data: dict) -> None:
            with events_lock:
                events.append({
                    "phase": name,
                    "t": round(time.perf_counter() - started, 4),
                    "data": jsonable(data),
                })

        entities = None

        closed_book = None

        with self.meter.attribute() as calls:

            try:
                if self.config.mode == CLOSED_BOOK:
                    # The claim alone: no entities, no search, no pipeline,
                    # so no inference/ either. The two events time the
                    # model's span as in any other run (record.latency_from).
                    collect("verifying_claim", {"claim": row.claim, "evidence": 0})
                    check, closed_book = self.closed_book.judge(row.claim)
                    collect("claim_checked", {"verdict": check.verdict.value})

                    record = build_record(
                        row,
                        check,
                        events=events,
                        timing=self._timing(started_at, started, None),
                        provenance=self._provenance,
                        usage=summarise(calls),
                        closed_book=closed_book,
                    )

                    return self._keep(record)

                claim = self.claims.build_claim(row.claim, collect, self.config.thresholds)

                entities = round(time.perf_counter() - started, 4)

                if self.config.mode == ORACLE:
                    check, read = self.checker.check_against(
                        claim,
                        reference_urls(row),
                        collect,
                        self.config.thresholds,
                        context=context_for(row),
                        language=row.language,
                    )
                    # The pipeline says claim_checked in _check_claim, which
                    # check_against does not pass through; said here, the
                    # model's span (verifying_claim -> claim_checked) is timed
                    # as in a run that searched.
                    collect("claim_checked", {"verdict": check.verdict.value, "pagesRead": read})
                else:
                    check = self.checker.check_claim(
                        claim,
                        collect,
                        self.config.thresholds,
                        context=context_for(row),
                        language=row.language,
                    )

                timing = self._timing(started_at, started, entities)
                first_calls = len(calls)

                loop = self._loop(row, claim, check) if self.config.loop else None

                if loop is not None:
                    # Its own cost, apart: the record's `usage` stays the
                    # first pass's, comparable with a run without the loop.
                    loop["usage"] = summarise(calls[first_calls:])

                record = build_record(
                    row,
                    check,
                    events=events,
                    timing=timing,
                    provenance=self._provenance,
                    usage=summarise(calls[:first_calls]),
                    loop=loop,
                )

            except Exception as exc:

                logger.exception("evaluation claim %s failed", row.id)

                record = error_record(
                    row,
                    exc,
                    events=events,
                    timing=self._timing(started_at, started, entities),
                    provenance=self._provenance,
                    usage=summarise(calls),
                )

        return self._keep(record)

    def _keep(self, record: dict) -> str:
        """Append one finished record, count it for the session, report it."""

        self.results.append(record)

        with self._written_lock:
            self._written.append({"usage": record["usage"], "latency": record["latency"]})

        if self.on_record is not None:
            self.on_record(record)

        return record["status"]

    def _loop(self, row: DatasetRow, claim, check) -> dict:
        """
        The tuning loop on one claim (docs/decisions/evaluation.md, "The
        second look"). The record's verdict stays the first pass's; this
        says what a second look and the annotator's own pages made of it.

        A second look is taken when the verdict disagrees with gold, and
        also when the pipeline's own trigger would fire (`doubt`), so the
        report can say what that trigger would do without gold. When the
        claim still disagrees, it is judged once more against the row's
        reference links: if those settle it, the error was the search's
        (`retrieval`); if the model still answers what the pipeline did,
        a person decides between the model and the gold label
        (`adjudicate`).
        """

        thresholds = self.config.thresholds
        context = context_for(row)
        gold = row.label

        loop = {
            "firstVerdict": _verdict(check.verdict),
            "disagrees": _verdict(check.verdict) != gold,
            "trigger": doubt(check, thresholds.second_look_below_confidence),
            "secondLook": None,
            "reference": None,
            "outcome": None,
            "seconds": None,
        }

        started = time.perf_counter()

        if check.llm_unreachable or check.search_unavailable:
            loop["outcome"] = LOOP_UNAVAILABLE
            return loop

        if not loop["disagrees"] and not loop["trigger"]:
            loop["outcome"] = LOOP_AGREED
            return loop

        second = self.checker.second_look(
            claim,
            check,
            None,
            thresholds,
            context=context,
            language=row.language,
            trigger=loop["trigger"] or "disagreement",
        )

        trace = second.second_look

        loop["secondLook"] = _judgement(second) | {
            "queries": trace.queries if trace else [],
            "newEvidence": trace.new_evidence if trace else 0,
            "searchUnavailable": bool(trace and trace.search_unavailable),
        }

        final = _verdict(second.verdict)

        if not loop["disagrees"]:
            loop["outcome"] = LOOP_AGREED
        elif final == gold:
            loop["outcome"] = LOOP_FIXED
        elif not row.reference_links:
            loop["outcome"] = LOOP_NO_REFERENCE
        else:
            reference, read = self.checker.check_against(
                claim,
                list(row.reference_links),
                None,
                thresholds,
                context=context,
                language=row.language,
            )

            loop["reference"] = _judgement(reference) | {
                "links": len(row.reference_links),
                "pagesRead": read,
            }

            if not read:
                loop["outcome"] = LOOP_UNREADABLE
            elif _verdict(reference.verdict) == gold:
                loop["outcome"] = LOOP_RETRIEVAL
            elif _verdict(reference.verdict) == final:
                loop["outcome"] = LOOP_ADJUDICATE
            else:
                loop["outcome"] = LOOP_REASONING

        loop["seconds"] = round(time.perf_counter() - started, 4)

        return loop

    @staticmethod
    def _timing(started_at: str, started: float, entities: float | None) -> Timing:

        return Timing(
            started_at=started_at,
            finished_at=now(),
            total=time.perf_counter() - started,
            entities=entities,
        )

    def _write_manifest(self, session: dict, finished: bool = False) -> None:
        """
        run.json: what produced this run, written at start and updated at
        the end of each session. A resumed run appends a session instead
        of overwriting the first one's provenance.
        """

        path = self.directory / MANIFEST

        manifest = read_json(path) if path.exists() else self._new_manifest()

        sessions = manifest.setdefault("sessions", [])

        if finished and sessions and sessions[-1].get("startedAt") == session["startedAt"]:
            sessions[-1] = session
        else:
            sessions.append(session)

        write_json(path, manifest)

    def _settings(self) -> dict:
        """
        The environment a session ran in: endpoints, timeouts and the
        concurrency ceilings. Not keyed (they change how fast and how
        reliably claims are answered, not what the pipeline decides), so
        recorded instead.
        """

        return {
            "LLM_BASE_URL": without_credentials(settings.LLM_BASE_URL),
            "LLM_TIMEOUT": settings.LLM_TIMEOUT,
            "LLM_REASONING_EFFORT": settings.LLM_REASONING_EFFORT.get(self.config.model),
            "SEARXNG_URL": settings.SEARXNG_URL,
            "INFERENCE_URL": settings.INFERENCE_URL,
            "INFERENCE_TIMEOUT": settings.INFERENCE_TIMEOUT,
            "DUCKDUCKGO_FALLBACK_ENABLED": settings.DUCKDUCKGO_FALLBACK_ENABLED,
            # What this runner was built with, which is the setting unless
            # a caller passed its own.
            "CLAIM_MAX_CONCURRENCY": self.max_workers,
            "LLM_MAX_CONCURRENCY": settings.LLM_MAX_CONCURRENCY,
            "QUERY_MAX_CONCURRENCY": settings.QUERY_MAX_CONCURRENCY,
            "SEARXNG_MAX_CONCURRENCY": settings.SEARXNG_MAX_CONCURRENCY,
            "SCRAPE_MAX_CONCURRENCY": settings.SCRAPE_MAX_CONCURRENCY,
            "INFERENCE_MAX_CONCURRENCY": settings.INFERENCE_MAX_CONCURRENCY,
        }

    def _new_manifest(self) -> dict:

        config = self.config
        dataset = config.dataset

        return {
            "key": config.key,
            "harnessVersion": HARNESS_VERSION,
            "dataset": {
                "path": str(dataset.path),
                "stem": dataset.stem,
                "sha256": dataset.sha256,
                "rows": len(dataset.rows),
                "kinds": dataset.kinds,
            },
            "model": config.model,
            "provider": self.provider,
            "thresholds": config.thresholds.model_dump(),
            "thresholdsHash": thresholds_hash(config.thresholds),
            "thresholdsOverridden": config.thresholds.overridden_from_defaults(),
            "weights": config.weights,
            "corpus": {"mode": config.corpus},
            "mode": config.mode,
            "label": config.label,
            "loop": config.loop,
            "gitCommit": self.commit,
            "startedAt": now(),
            "settings": self._settings(),
            **self.manifest_extra,
        }


def _verdict(value) -> str:

    return value.value if hasattr(value, "value") else str(value)


def _judgement(check) -> dict:
    """A verdict and what it rested on, without any page's text."""

    cited = set(check.cited_evidence_indices)

    return {
        "verdict": _verdict(check.verdict),
        "confidence": check.confidence,
        "rawVerdict": _verdict(check.raw_verdict) if check.raw_verdict else None,
        "explanation": check.explanation,
        "evidence": [
            {
                "url": item.url,
                "domain": item.domain,
                "foundBy": list(item.found_by),
                "stance": _verdict(item.stance) if item.stance else None,
                "cited": index in cited,
            }
            for index, item in enumerate(check.evidence)
        ],
    }


def without_credentials(url: str) -> str:

    parts = urlsplit(url)

    if not parts.username and not parts.password:
        return url

    host = parts.hostname or ""
    netloc = f"{host}:{parts.port}" if parts.port else host

    return parts._replace(netloc=netloc).geturl()


# ----------------------------------------------------------------------
# The corpus
# ----------------------------------------------------------------------


def prepare_corpus(directory: Path, mode: str, source: Path | None = None) -> Path:
    """
    The run's own copy of the internal corpus, at `<run>/vector_db`.

    Never the live store: QdrantClient's local mode takes an exclusive
    file lock that any running backend holds, and the live store grows
    with every ingestion, so a run against it could not be repeated.
    `snapshot` copies `data/vector_db` once, when the run starts; a
    resumed run keeps the copy it started with. `none` is an empty store:
    web only, for the ablation.
    """

    if mode not in CORPUS_MODES:
        raise ValueError(f"corpus must be one of {CORPUS_MODES}, not {mode!r}")

    target = Path(directory) / CORPUS_DIR

    if target.exists():
        return target

    source = Path(source or settings.QDRANT_PATH)

    if mode == SNAPSHOT and source.exists():
        # The lock file is the live backend's, not data.
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(".lock"))
    else:
        if mode == SNAPSHOT:
            logger.warning("no corpus at %s: the snapshot is an empty store", source)
        target.mkdir(parents=True, exist_ok=True)

    return target


def build_runner(config: RunConfig) -> tuple[HarnessRunner, Callable[[], None]]:
    """
    The real pipeline over the run's corpus copy, with the model as a
    constructor argument rather than an `.env` edit per run, and every
    LLM call metered. The provider is whatever LLM_BASE_URL / LLM_API_KEY
    say: Ollama and Groq differ by environment only.

    Returns the runner and a function that closes the corpus store.
    """

    # Imported here: building any of these is what a test never does.
    from src.database.qdrant import QdrantDatabase
    from src.processors.nlp.entities import EntityExtractor
    from src.repositories.vector_repository import VectorRepository
    from src.services.claim_service import ClaimService
    from src.services.fact_checker.fact_checker import FactChecker
    from src.services.fact_checker.verification.llm_verification import (
        SYSTEM_PROMPT,
        LLMVerifier,
    )
    from src.services.llms import LLMClient
    from src.evaluation.usage import metered

    directory = config.directory

    directory.mkdir(parents=True, exist_ok=True)

    corpus_path = prepare_corpus(directory, config.corpus)

    database = QdrantDatabase(path=corpus_path)
    repository = VectorRepository(database)

    meter = UsageMeter()

    closed_book = None

    if config.mode == RETRIEVAL:
        verifier = RetrievalOnlyVerifier()
    else:
        verifier = LLMVerifier(client=metered(LLMClient(model=config.model), meter))

    if config.mode == CLOSED_BOOK:
        from src.evaluation.closed_book import ClosedBookJudge
        closed_book = ClosedBookJudge(metered(LLMClient(model=config.model), meter))

    checker = FactChecker(repository, verifier=verifier)

    claims = ClaimService(checker, entity_extractor=EntityExtractor())

    runner = HarnessRunner(
        config,
        checker=checker,
        claims=claims,
        meter=meter,
        provider=provider_of(settings.LLM_BASE_URL),
        closed_book=closed_book,
        manifest_extra={
            "corpus": {"mode": config.corpus, "points": repository.count()},
            # The verifier's prompt is the pipeline's, not the harness's,
            # so it is recorded rather than keyed: the commit already
            # says which prompt ran, and this says it at a glance.
            "verifierPromptSha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        },
    )

    return runner, database.close


class RetrievalOnlyVerifier:
    """
    Stands in for LLMVerifier in a retrieval-only run: no call, an
    UNVERIFIED that says why. Everything before it - queries, search,
    fetch, ranking, the pertinence gate - is the real pipeline's.
    """

    def verify(self, claim, evidence, context=None, *, thresholds=None, language=None):

        from src.models.fact_checker.fact_check import Verdict
        from src.services.fact_checker.verification.llm_verification import LLMVerificationResult

        return LLMVerificationResult(
            verdict=Verdict.UNVERIFIED,
            confidence=0.0,
            explanation=RETRIEVAL_ONLY_EXPLANATION,
        )

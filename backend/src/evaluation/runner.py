"""
Runs the pipeline's own `check_claim` over a labelled set, resumably.

What a run is
-------------

One dataset, one model, one effective set of thresholds, one corpus
mode: those four (and HARNESS_VERSION) hash into the run's key, and the
key names its directory. Same four, same directory - so starting the same
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

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
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

logger = logging.getLogger(__name__)

SNAPSHOT = "snapshot"
NONE = "none"
CORPUS_MODES = (SNAPSHOT, NONE)

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


def thresholds_hash(thresholds: PipelineThresholds) -> str:

    return _digest(thresholds.model_dump())[:12]


def run_key(
    dataset_sha256: str,
    model: str,
    thresholds: PipelineThresholds,
    corpus: str,
) -> str:

    return _digest({
        "dataset": dataset_sha256,
        "model": model,
        "thresholds": thresholds.model_dump(),
        "corpus": corpus,
        "harnessVersion": HARNESS_VERSION,
    })[:12]


def _digest(value) -> str:

    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def git_commit() -> str:
    """
    HEAD, with `-dirty` when the tree has changes: a result from
    uncommitted code should say so. `unknown` inside the container, which
    has no .git.
    """

    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"

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

    @property
    def key(self) -> str:

        return run_key(self.dataset.sha256, self.model, self.thresholds, self.corpus)

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
    ):
        self.config = config
        self.checker = checker
        self.claims = claims
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

        with self.meter.attribute() as calls:

            try:
                claim = self.claims.build_claim(row.claim, collect, self.config.thresholds)

                entities = round(time.perf_counter() - started, 4)

                check = self.checker.check_claim(
                    claim,
                    collect,
                    self.config.thresholds,
                    context=context_for(row),
                    language=row.language,
                )

                record = build_record(
                    row,
                    check,
                    events=events,
                    timing=self._timing(started_at, started, entities),
                    provenance=self._provenance,
                    usage=summarise(calls),
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

        self.results.append(record)

        with self._written_lock:
            self._written.append({"usage": record["usage"], "latency": record["latency"]})

        if self.on_record is not None:
            self.on_record(record)

        return record["status"]

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
            "corpus": {"mode": config.corpus},
            "gitCommit": self.commit,
            "startedAt": now(),
            "settings": {
                "LLM_BASE_URL": _without_credentials(settings.LLM_BASE_URL),
                "LLM_TIMEOUT": settings.LLM_TIMEOUT,
                "SEARXNG_URL": settings.SEARXNG_URL,
                "INFERENCE_URL": settings.INFERENCE_URL,
                "DUCKDUCKGO_FALLBACK_ENABLED": settings.DUCKDUCKGO_FALLBACK_ENABLED,
                "CLAIM_MAX_CONCURRENCY": settings.CLAIM_MAX_CONCURRENCY,
                "LLM_MAX_CONCURRENCY": settings.LLM_MAX_CONCURRENCY,
                "QUERY_MAX_CONCURRENCY": settings.QUERY_MAX_CONCURRENCY,
                "SEARXNG_MAX_CONCURRENCY": settings.SEARXNG_MAX_CONCURRENCY,
                "SCRAPE_MAX_CONCURRENCY": settings.SCRAPE_MAX_CONCURRENCY,
                "INFERENCE_MAX_CONCURRENCY": settings.INFERENCE_MAX_CONCURRENCY,
            },
            **self.manifest_extra,
        }


def _without_credentials(url: str) -> str:

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

    llm = metered(LLMClient(model=config.model), meter)

    checker = FactChecker(repository, verifier=LLMVerifier(client=llm))

    claims = ClaimService(checker, entity_extractor=EntityExtractor())

    runner = HarnessRunner(
        config,
        checker=checker,
        claims=claims,
        meter=meter,
        provider=provider_of(settings.LLM_BASE_URL),
        manifest_extra={
            "corpus": {"mode": config.corpus, "points": repository.count()},
            # The verifier's prompt is the pipeline's, not the harness's,
            # so it is recorded rather than keyed: the commit already
            # says which prompt ran, and this says it at a glance.
            "verifierPromptSha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        },
    )

    return runner, database.close

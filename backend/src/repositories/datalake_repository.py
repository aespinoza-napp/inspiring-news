from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.news import News
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.storage.lineage import (
    DataLayer,
    Lineage,
    RunContext,
    build_record_id,
)
from src.models.storage.records import (
    ExploitationRecord,
    ProcessedRecord,
    RawRecord,
)
from src.repositories.lake_backend import JsonFileLakeBackend, LakeBackend

logger = getLogger(__name__)

PIPELINE_VERSION = "1"

# Verdicts that block publication. UNVERIFIED does not: "we could not
# find evidence either way" is not the same as "this is wrong", and with
# a local model and a self-hosted search index it is the common case.
_BLOCKING_VERDICTS = (Verdict.FALSE, Verdict.MISLEADING)


def content_hash(text: str) -> str:

    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _code_revision() -> Optional[str]:
    """
    Short git revision of the running code, or None outside a checkout.
    Resolved once per process - shelling out per record would add a
    subprocess to every write.
    """

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip() or None


_CODE_REVISION = _code_revision()


@dataclass
class LakeWriteResult:
    """Ids of the three records written for one run, for the API/logs."""

    run_id: str

    raw_record_id: str

    processed_record_id: str

    exploitation_record_id: str

    content_hash: str

    publishable: bool


class DataLakeRepository:
    """
    Writes one analysed article into the three storage layers and keeps
    them linked.

    Each layer is derived from the previous one and carries a Lineage
    pointing at it, so trace(article_id) can reassemble the full chain:
    which exploitation document came from which processed record came
    from which raw fetch, under which run, with which model versions.

    Persisting is deliberately fail-soft at the call site (see
    AnalysisService): storage is a side effect of analysis, and a full
    disk should not turn a successful analysis into a failed job.
    """

    def __init__(
        self,
        backend: LakeBackend | None = None,
        pipeline_version: str = PIPELINE_VERSION,
    ):
        self.backend = backend or JsonFileLakeBackend(settings.LAKE_PATH)

        self.pipeline_version = pipeline_version

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def start_run(
        self,
        url: str,
        thresholds: PipelineThresholds | None = None,
    ) -> RunContext:

        return RunContext(
            run_id=uuid4().hex,
            url=url,
            pipeline_version=self.pipeline_version,
            code_revision=_CODE_REVISION,
            threshold_overrides=(
                thresholds.overridden_from_defaults() if thresholds else {}
            ),
            components={
                "embedding_model": settings.EMBEDDING_MODEL,
                "sentiment_model": settings.SENTIMENT_MODEL,
                "llm_model": settings.LLM_MODEL,
            },
        )

    # ------------------------------------------------------------------
    # Layers
    # ------------------------------------------------------------------

    def persist_raw(
        self,
        run: RunContext,
        news: News,
        extractor: str = "trafilatura",
    ) -> RawRecord:

        digest = content_hash(news.content)

        record = RawRecord(
            record_id=build_record_id(DataLayer.RAW, news.id, run.run_id),
            lineage=self._lineage(
                run=run,
                layer=DataLayer.RAW,
                article_id=news.id,
                url=news.url,
                digest=digest,
            ),
            article=news,
            extractor=extractor,
            content_length=len(news.content),
        )

        self._write(DataLayer.RAW, record)

        return record

    def persist_processed(
        self,
        run: RunContext,
        article: EnrichedArticle,
        parent: RawRecord | None = None,
        report: FactCheckReport | None = None,
    ) -> ProcessedRecord:
        """
        Layer 2: the enrichment output - entities, topics, claims,
        sentiment, quality and the embedding.

        Called at the end of enrichment, *before* fact-checking, with
        `report=None`. Once the fact-check finishes, the caller calls it
        again with the report to attach the full evidence trail. That
        second call rewrites the same record rather than adding one:
        record ids are `uuid5(layer, article, run)`, so both writes
        address the same document. The manifest still logs both, so the
        audit trail shows "written after enrichment, updated after
        verification" - which is exactly the history worth keeping.

        Writing after enrichment rather than only at the very end means a
        fact-check that crashes (or a SearXNG outage) no longer discards
        an enrichment that already cost the full NLP stack.

        `parent` is optional so this layer stays independently writable:
        if the raw write failed, the enrichment is still worth keeping,
        just without a parent link. The content hash is derived from the
        body rather than from the raw record for the same reason.
        """

        record = ProcessedRecord(
            record_id=build_record_id(
                DataLayer.PROCESSED, article.id, run.run_id
            ),
            lineage=self._lineage(
                run=run,
                layer=DataLayer.PROCESSED,
                article_id=article.id,
                url=article.url,
                digest=content_hash(article.body),
                parent=parent,
            ),
            article=article,
            fact_check=report,
        )

        self._write(DataLayer.PROCESSED, record)

        return record

    def persist_exploitation(
        self,
        run: RunContext,
        article: EnrichedArticle,
        report: FactCheckReport | None = None,
        parent: ProcessedRecord | None = None,
    ) -> ExploitationRecord:
        """
        Layer 3: the verified, ready-to-serve document, written once the
        fact-check has decided. Flat by design - the evidence and the
        rejected candidates stay in layer 2; what lands here is the
        decision (`publishable`, `verdict`) plus the fields a reader or a
        serving query actually needs.
        """

        record = ExploitationRecord(
            record_id=build_record_id(
                DataLayer.EXPLOITATION, article.id, run.run_id
            ),
            lineage=self._lineage(
                run=run,
                layer=DataLayer.EXPLOITATION,
                article_id=article.id,
                url=article.url,
                digest=content_hash(article.body),
                parent=parent,
            ),
            article_id=article.id,
            url=article.url,
            source_id=article.source_id,
            title=article.title,
            language=article.language,
            published_at=article.published_at,
            summary=article.body[:500],
            primary_topic=self._primary_topic(article),
            topics=article.topics or [],
            keywords=article.keywords or [],
            entities=article.entities or {},
            sentiment_label=article.sentiment.label,
            sentiment_positive=article.sentiment.positive,
            sentiment_negative=article.sentiment.negative,
            readability=article.quality.readability,
            objectivity=article.quality.objectivity,
            constructiveness=article.quality.constructiveness,
            inspirational_score=article.quality.inspirational_score,
            societal_impact=article.quality.societal_impact,
            impact_score=report.impact_score if report else 0.0,
            publishable=self._is_publishable(report),
            validation_passed=bool(report and report.validation_passed),
            rejection_reasons=self._rejection_reasons(report),
            is_duplicate=bool(report and report.duplicate),
            verdict=report.overall_verdict if report else Verdict.UNVERIFIED,
            verdict_confidence=report.overall_confidence if report else 0.0,
            claims_total=report.claims_total if report else 0,
            claims_checked=report.claims_selected if report else 0,
            cited_evidence_urls=self._cited_urls(report),
            vector_collection="news",
            embedding_model=article.embedding_model,
            embedding_dimension=article.embedding_dimension,
        )

        self._write(DataLayer.EXPLOITATION, record)

        return record

    def persist_all(
        self,
        run: RunContext,
        news: News,
        article: EnrichedArticle,
        report: FactCheckReport | None,
        extractor: str = "trafilatura",
    ) -> LakeWriteResult:
        """
        All three layers in one call, for callers that already have the
        finished result (batch re-processing, tests). The live pipeline
        does not use this - it writes each layer as its stage completes,
        see AnalysisService.
        """

        raw = self.persist_raw(run, news, extractor=extractor)

        processed = self.persist_processed(run, article, parent=raw, report=report)

        exploitation = self.persist_exploitation(
            run, article, report=report, parent=processed
        )

        return LakeWriteResult(
            run_id=run.run_id,
            raw_record_id=raw.record_id,
            processed_record_id=processed.record_id,
            exploitation_record_id=exploitation.record_id,
            content_hash=raw.lineage.content_hash,
            publishable=exploitation.publishable,
        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get(self, layer: DataLayer, record_id: str) -> dict | None:

        return self.backend.read(layer, record_id)

    def list(self, layer: DataLayer, limit: int | None = None) -> list[dict]:

        return self.backend.list(layer, limit=limit)

    def trace(self, article_id: str) -> dict:
        """
        The full lineage chain for one article across all three layers,
        newest run first, plus the manifest entries that recorded the
        writes. This is the question the layering exists to answer:
        where did this served document come from?
        """

        return {
            "articleId": article_id,
            "layers": {
                layer.value: self.backend.find_by_article(layer, article_id)
                for layer in DataLayer
            },
            "manifest": [
                entry
                for entry in self.backend.manifest()
                if entry.get("article_id") == article_id
            ],
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _write(self, layer: DataLayer, record) -> None:

        self.backend.write(
            layer,
            record.record_id,
            record.model_dump(mode="json"),
        )

    def _lineage(
        self,
        run: RunContext,
        layer: DataLayer,
        article_id: str,
        url: str,
        digest: str,
        parent=None,
    ) -> Lineage:

        return Lineage(
            run_id=run.run_id,
            article_id=article_id,
            layer=layer,
            source_url=url,
            content_hash=digest,
            parent_layer=parent.layer if parent else None,
            parent_record_id=parent.record_id if parent else None,
            pipeline_version=run.pipeline_version,
            code_revision=run.code_revision,
            threshold_overrides=run.threshold_overrides,
            components=run.components,
        )

    @staticmethod
    def _primary_topic(article: EnrichedArticle) -> Optional[str]:

        if not article.topics:
            return None

        return max(
            article.topics,
            key=lambda topic: topic.confidence,
        ).topic

    @staticmethod
    def _is_publishable(report: FactCheckReport | None) -> bool:

        if report is None or not report.validation_passed:
            return False

        return report.overall_verdict not in _BLOCKING_VERDICTS

    @staticmethod
    def _rejection_reasons(report: FactCheckReport | None) -> list[str]:

        if report is None:
            return ["no_fact_check_report"]

        if report.validation_passed:

            if report.overall_verdict in _BLOCKING_VERDICTS:
                return [f"verdict_{report.overall_verdict.value.lower()}"]

            return []

        return report.skipped_reason.split(",") if report.skipped_reason else []

    @staticmethod
    def _cited_urls(report: FactCheckReport | None) -> list[str]:

        if report is None:
            return []

        urls: list[str] = []

        for check in report.claim_checks:

            for index in check.cited_evidence_indices:

                if 0 <= index < len(check.evidence):

                    url = check.evidence[index].url

                    if url not in urls:
                        urls.append(url)

        return urls

"""
A throwaway lake filled the way the pipeline fills it: every record goes
through DataLakeRepository.persist_all, so the reader is tested against
what the writer actually writes rather than a hand-made imitation of it.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from uuid import uuid4

from src.models.core.claim import RejectedClaim
from src.models.fact_checker.evidence import EvidenceStance, RejectedEvidence
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.models.nlp.topic_prediction import TopicPrediction
from src.models.storage.lineage import DataLayer
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend

from tests.factories import create_article, create_evidence
from tests.repositories.test_datalake_repository import make_news, make_report

# Stands in for a scraped evidence page. Must never reach a reader.
SCRAPED_BODY = "FULL SCRAPED PAGE BODY - a third party's whole article"

BODY = (
    "Volunteers in the valley planted forty thousand native trees this spring, "
    "restoring a wetland that had been drained for farmland in the 1960s. "
) * 6


def make_lake(tmp_path) -> DataLakeRepository:

    return DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))


def checked(
    claim: str = "Volunteers planted forty thousand native trees.",
    verdict: Verdict = Verdict.TRUE,
    **kwargs,
) -> FactCheck:
    """A claim checked against two sources, the first one cited."""

    defaults = dict(
        verdict=verdict,
        explanation="Two regional outlets report the planting and its size.",
        confidence=0.82,
        claim=claim,
        evidence=[
            create_evidence(
                url="https://rated.example/planting",
                title="Forty thousand trees for the valley",
                domain="rated.example",
                content=SCRAPED_BODY,
                snippet="s" * 600,
                relevance_score=0.74,
                semantic_score=0.8,
                lexical_score=0.6,
                pertinence_score=0.71,
                recency_score=0.9,
                reliability_score=0.85,
                reliability_known=True,
                stance=EvidenceStance.SUPPORTS,
                quote="q" * 900,
                found_by=["anchor", "proposition"],
            ),
            create_evidence(
                url="https://unrated.example/valley",
                title="Valley news roundup",
                domain="unrated.example",
                content=SCRAPED_BODY,
                relevance_score=0.51,
                reliability_score=0.5,
                reliability_known=False,
                stance=EvidenceStance.UNRELATED,
            ),
        ],
        cited_evidence_indices=[0],
        evidence_count=2,
        rejected_sources=[
            # Already among the evidence (ranked, not cited): not listed twice.
            RejectedEvidence(
                url="https://unrated.example/valley",
                title="Valley news roundup",
                origin="web",
                stage=PipelineStage.LLM_VERIFICATION,
                reason="retrieved and ranked, but not cited by the LLM",
            ),
            RejectedEvidence(
                url="https://elsewhere.example/etymology",
                title="Where the word 'valley' comes from",
                origin="web",
                stage=PipelineStage.EVIDENCE_RANKING,
                reason="does not address the claim (pertinence 0.12 < 0.25)",
            ),
        ],
        raw_verdict=verdict,
        raw_confidence=0.85,
        independent_domains=1,
        agreements=["rated.example: forty thousand trees"],
    )

    defaults.update(kwargs)

    return FactCheck(**defaults)


def publish(
    lake: DataLakeRepository,
    url: str = "https://www.bbc.com/news/valley-trees-planted-by-volunteers",
    *,
    title: str = "Volunteers plant 40,000 trees",
    topic: str = "Environment",
    language: str = "en",
    published_at: datetime | None = datetime(2026, 9, 1, 8, 0),
    verdict: Verdict = Verdict.TRUE,
    checks: list[FactCheck] | None = None,
    validation_passed: bool = True,
    source_id: str = "bbc",
    author: str | None = "A. Reporter",
):
    """
    One analysed article, written into all three layers. Returns what
    persist_all returned (record ids, run id, publishable).
    """

    article_id = uuid4().hex

    checks = [checked()] if checks is None else checks

    news = make_news(
        id=article_id,
        url=url,
        source_id=source_id,
        title=title,
        author=author,
        published_at=published_at,
        content=BODY,
    )

    article = create_article(
        id=article_id,
        url=url,
        source_id=source_id,
        title=title,
        body=BODY,
        language=language,
        published_at=published_at,
        topics=[
            TopicPrediction(topic=topic, confidence=0.6, probability=0.05),
            TopicPrediction(topic="Community", confidence=0.4, probability=0.04),
        ],
    )

    report = make_report(
        article_id=article_id,
        validation_passed=validation_passed,
        skipped_reason=None if validation_passed else "topic_not_relevant",
        claims_total=len(checks) + 1,
        claims_selected=len(checks),
        claim_checks=checks,
        overall_verdict=verdict,
        overall_confidence=0.7,
        unselected_claims=[
            RejectedClaim(text="The valley is beautiful.", confidence=0.2, reason="opinion"),
        ],
    )

    run = lake.start_run(url)

    return lake.persist_all(run, news, article, report)


def restamp(lake: DataLakeRepository, record_id: str, produced_at: str) -> None:
    """
    Sets when an exploitation record was stored. Runs written one after
    another inside a test can share a timestamp; which run is "newest"
    is the thing under test, so it is set explicitly rather than hoped for.
    """

    document = lake.get(DataLayer.EXPLOITATION, record_id)
    document["lineage"]["produced_at"] = produced_at
    lake.backend.write(DataLayer.EXPLOITATION, record_id, document)


class CountingLake:
    """The lake, counting what the reader reads from it."""

    def __init__(self, lake: DataLakeRepository, stamps: bool = True):

        self.lake = lake
        self.has_stamps = stamps
        self.reads: Counter = Counter()

    def get(self, layer: DataLayer, record_id: str):

        self.reads[layer] += 1

        return self.lake.get(layer, record_id)

    def list(self, layer: DataLayer, limit: int | None = None):

        self.reads[f"list:{layer.value}"] += 1

        return self.lake.list(layer, limit=limit)

    def stamps(self, layer: DataLayer):

        return self.lake.stamps(layer) if self.has_stamps else None

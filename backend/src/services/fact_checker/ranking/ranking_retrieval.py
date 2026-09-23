import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.repositories.source_repository import SourceRepository
from src.services.embeddings.service import EmbeddingService
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.terms import (
    claim_terms,
    contextualised_claim,
    coverage,
)

# How much of a source is read when judging it. Enough to cover a lead
# and the paragraphs under it; past that a long page's tail dilutes both
# scores without adding anything the claim is about.
JUDGED_CHARS = 2000


@dataclass
class RankingResult:

    kept: list[Evidence]

    rejected: list[RejectedEvidence] = field(default_factory=list)


class EvidenceRanker:

    SEMANTIC_WEIGHT = settings.RANKING_SEMANTIC_WEIGHT
    LEXICAL_WEIGHT = settings.RANKING_LEXICAL_WEIGHT
    RECENCY_WEIGHT = settings.RANKING_RECENCY_WEIGHT
    RELIABILITY_WEIGHT = settings.RANKING_RELIABILITY_WEIGHT

    DEFAULT_RELIABILITY = settings.RANKING_DEFAULT_RELIABILITY

    PERTINENCE_SEMANTIC_WEIGHT = settings.PERTINENCE_SEMANTIC_WEIGHT
    PERTINENCE_LEXICAL_WEIGHT = settings.PERTINENCE_LEXICAL_WEIGHT

    RECENCY_HALF_LIFE_DAYS = settings.EVIDENCE_RECENCY_HALF_LIFE_DAYS

    def __init__(
        self,
        embeddings: EmbeddingService | None = None,
        source_repository: SourceRepository | None = None,
    ):
        self.embeddings = embeddings or EmbeddingService()
        self._reliability_by_domain = self._load_domain_reliability(
            source_repository or SourceRepository()
        )

    def rank(
        self,
        claim: Claim,
        evidence: list[Evidence],
        thresholds: PipelineThresholds | None = None,
        claim_embedding=None,
        language: str | None = None,
        context: ArticleContext | None = None,
    ) -> RankingResult:
        """
        Scores, gates and orders a claim's evidence.

        `claim_embedding` is the claim's vector when the caller already
        has it. It does: EvidenceRetriever computed the same vector a
        moment ago to decide which candidates were worth scraping, and
        re-encoding it here was a second HTTP round trip to inference/
        for an answer already in memory - per claim, on the critical
        path.

        `context` is the article the claim came from. With it, a subject
        the sentence lost counts as an anchor a source must carry, so a
        page about the right city and the wrong event scores as what it
        is.
        """

        thresholds = thresholds or PipelineThresholds()

        max_evidence = thresholds.max_evidence_per_claim

        if not evidence:
            return RankingResult(kept=[])

        if claim_embedding is None:
            claim_embedding = self.embeddings.encode(
                contextualised_claim(claim, context, language)
            )

        anchors, content = claim_terms(claim, language, context)

        texts = [self._judged_text(item) for item in evidence]

        # One batched call, not one per source. This was the single
        # worst offender in the pipeline: `encode()` inside a list
        # comprehension, so ranking five sources meant five sequential
        # HTTP round trips to inference/ for work the service does in
        # one pass.
        vectors = self.embeddings.encode_many(texts)

        scored = [
            item.model_copy(update=self._score(
                text, vector, claim_embedding, anchors, content, item,
            ))
            for item, text, vector in zip(evidence, texts, vectors)
        ]

        # The pertinence gate, before the ranking cap and before the LLM.
        #
        # Ranking orders sources; it cannot refuse one. That gap is how a
        # claim about the Coyote and ACME ended up FALSE at 83%: three
        # pages explaining the Greek etymology of "acme" were the three
        # best-ranked things retrieved, so they were the three the model
        # was shown, and it dutifully judged the claim against them. They
        # were never evidence about the claim. Cutting them here means
        # the honest answer - UNVERIFIED, nothing found - is what comes
        # back, because min_evidence_for_verdict now counts sources that
        # actually address the assertion.
        pertinent = []
        rejected = []

        for item in scored:

            if (item.pertinence_score or 0.0) >= thresholds.evidence_min_pertinence:
                pertinent.append(item)
                continue

            rejected.append(RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.EVIDENCE_RANKING,
                reason=(
                    f"on-topic but does not address the claim "
                    f"(pertinence {item.pertinence_score:.2f} < "
                    f"{thresholds.evidence_min_pertinence:.2f})"
                ),
                score=item.pertinence_score,
            ))

        pertinent.sort(key=lambda item: item.relevance_score, reverse=True)

        kept = pertinent[:max_evidence]
        cut = pertinent[max_evidence:]

        rejected += [
            RejectedEvidence(
                url=item.url,
                title=item.title,
                origin=item.origin,
                stage=PipelineStage.EVIDENCE_RANKING,
                reason=(
                    f"cut by final ranking cap (rank {rank} of {len(pertinent)}, "
                    f"top {max_evidence} kept)"
                ),
                score=item.relevance_score,
            )
            for rank, item in enumerate(cut, start=len(kept) + 1)
        ]

        return RankingResult(kept=kept, rejected=rejected)

    @staticmethod
    def _judged_text(evidence: Evidence) -> str:

        return (evidence.content or f"{evidence.title}. {evidence.snippet}")[:JUDGED_CHARS]

    def _score(
        self,
        text: str,
        vector,
        claim_embedding,
        anchors: list[str],
        content: list[str],
        evidence: Evidence,
    ) -> dict:
        """
        The composite score *and* the four factors that produced it.

        The factors used to be summed and discarded, which left the
        interface with a single opaque number and no way to answer the
        only question a reader actually has about a ranking: why is this
        source above that one. Same idea, nothing thrown away.

        `lexical` is the newest factor and the one that changed the other
        weights. Embedding similarity answers "is this about the same
        subject", which a page titled "What does ACME mean?" answers yes
        to for a claim mentioning ACME. Only term coverage can tell that
        the claim's assertion - consumerism, post-war, representation -
        appears nowhere on it.
        """

        semantic = max(0.0, min(
            self.embeddings.similarity(claim_embedding, vector), 1.0
        ))

        lexical = coverage(f"{evidence.title}. {text}", anchors, content)

        recency = self._recency_score(evidence.published_at)
        reliability = self._reliability(evidence)

        return {
            "semantic_score": semantic,
            "lexical_score": lexical,
            "recency_score": recency,
            "reliability_score": reliability,
            "reliability_known": self._reliability_known(evidence),
            # Deliberately free of recency and reliability: a recent,
            # reliable page about something else is still about something
            # else, and letting those two lift it over the gate is
            # exactly the mistake the gate exists to stop.
            "pertinence_score": (
                semantic * self.PERTINENCE_SEMANTIC_WEIGHT
                + lexical * self.PERTINENCE_LEXICAL_WEIGHT
            ),
            "relevance_score": (
                semantic * self.SEMANTIC_WEIGHT
                + lexical * self.LEXICAL_WEIGHT
                + recency * self.RECENCY_WEIGHT
                + reliability * self.RELIABILITY_WEIGHT
            ),
        }

    def _recency_score(self, published_at) -> float:

        if published_at is None:
            return 0.5

        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        age_days = max((datetime.now(timezone.utc) - published_at).days, 0)

        return math.exp(-age_days / self.RECENCY_HALF_LIFE_DAYS)

    def _reliability(self, evidence: Evidence) -> float:

        if evidence.source_reliability is not None:
            return evidence.source_reliability

        domain = urlparse(evidence.url).netloc.replace("www.", "")

        return self._reliability_by_domain.get(domain, self.DEFAULT_RELIABILITY)

    def _reliability_known(self, evidence: Evidence) -> bool:

        if evidence.source_reliability is not None:
            return True

        domain = urlparse(evidence.url).netloc.replace("www.", "")

        return domain in self._reliability_by_domain

    def _load_domain_reliability(self, source_repository: SourceRepository) -> dict[str, float]:

        try:
            sources = source_repository.list()
        except Exception:
            return {}

        return {
            urlparse(str(source.base_url)).netloc.replace("www.", ""): source.reliability_index
            for source in sources
        }

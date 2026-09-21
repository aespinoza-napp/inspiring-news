from dataclasses import dataclass, field

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim, RejectedClaim
from src.services.embeddings.service import EmbeddingService


@dataclass
class ArticleContext:
    """
    What the selector needs to know about the article a claim came from.

    Passed explicitly rather than handing over the whole EnrichedArticle:
    selection depends on the thesis and the main subjects, and saying so
    in the signature keeps the scoring honest about its inputs.
    """

    title: str = ""

    lead: str = ""

    # Lets internal-evidence retrieval skip the article's own stored copy.
    url: str = ""

    keywords: list[str] = field(default_factory=list)

    entities: dict[str, list[str]] = field(default_factory=dict)

    def thesis(self) -> str:
        return f"{self.title}. {self.lead}".strip()

    def subjects(self) -> set[str]:
        """The article's main subjects, lowercased, as one flat set."""

        names = {
            value.lower()
            for values in self.entities.values()
            for value in values
        }

        return names | {keyword.lower() for keyword in self.keywords}


@dataclass
class ClaimSelectionResult:

    selected: list[Claim]

    rejected: list[RejectedClaim] = field(default_factory=list)


class ClaimSelector:
    """
    Picks the *anchor* claims: the two-to-four assertions the article's
    credibility actually rests on.

    This used to be "the N highest-scoring sentences", which is a
    different question. Sentence-level check-worthiness measures whether
    a sentence *could* be verified - it rewards any sentence carrying a
    figure and a reporting verb, including incidental background. What
    matters for judging an article is whether its load-bearing claims
    hold: the ones that, if false, take the rest of the piece down with
    them.
    """

    # How the three anchor signals combine. Not per-run tunable for the
    # same reason the ranking weights are not: they are a normalised
    # group, and letting a caller set one alone silently de-normalises
    # the score.
    CENTRALITY_WEIGHT = 0.5
    SUBJECT_WEIGHT = 0.3
    SPECIFICITY_WEIGHT = 0.2

    def __init__(self, embeddings: EmbeddingService | None = None):

        self.embeddings = embeddings or EmbeddingService()

    def select(
        self,
        claims: list[Claim],
        thresholds: PipelineThresholds | None = None,
        context: ArticleContext | None = None,
    ) -> ClaimSelectionResult:

        thresholds = thresholds or PipelineThresholds()

        if not claims:
            return ClaimSelectionResult(selected=[])

        context = context or ArticleContext()

        # Every embedding this method needs, in one batched call: the
        # article's thesis and each claim's text. It used to encode each
        # claim twice - once to score it against the thesis, once again
        # in the loop below to dedupe it - each as its own HTTP round
        # trip to inference/. A ten-claim article paid twenty-one
        # sequential calls before any evidence was looked up.
        embeddings = self._embed(claims, context)

        scored = self._score_all(claims, context, embeddings)

        ordered = sorted(
            scored,
            key=lambda claim: claim.anchor_score or 0.0,
            reverse=True,
        )

        selected: list[Claim] = []
        selected_embeddings = []
        rejected: list[RejectedClaim] = []

        for claim in ordered:

            text = claim.text.strip()

            if not text:
                continue

            if len(selected) >= thresholds.anchor_claims_max:
                rejected.append(RejectedClaim(
                    text=claim.text,
                    confidence=claim.confidence,
                    reason="outside_anchor_band",
                ))
                continue

            embedding = embeddings[text]

            if self._is_duplicate(
                embedding,
                selected_embeddings,
                thresholds.claim_dedup_threshold,
            ):
                rejected.append(RejectedClaim(
                    text=claim.text,
                    confidence=claim.confidence,
                    reason="semantic_duplicate",
                ))
                continue

            selected.append(claim)
            selected_embeddings.append(embedding)

        return ClaimSelectionResult(selected=selected, rejected=rejected)

    ##########################################################

    def _embed(
        self,
        claims: list[Claim],
        context: ArticleContext,
    ) -> dict[str, object]:
        """
        `text -> vector` for the thesis and every claim, from one call.

        Keyed by text rather than by position because the loop above
        works on a re-sorted copy of the list and looks its claims up by
        the stripped text it already has in hand.
        """

        thesis = context.thesis()

        texts = [claim.text.strip() for claim in claims]

        wanted = [text for text in dict.fromkeys(texts) if text]

        if thesis:
            wanted.append(thesis)

        if not wanted:
            return {}

        vectors = self.embeddings.encode_many(wanted)

        return dict(zip(wanted, vectors))

    def _score_all(
        self,
        claims: list[Claim],
        context: ArticleContext,
        embeddings: dict[str, object],
    ) -> list[Claim]:

        thesis = context.thesis()

        thesis_embedding = embeddings.get(thesis) if thesis else None

        subjects = context.subjects()

        return [
            claim.model_copy(update={
                "anchor_score": round(
                    self._anchor_score(
                        claim,
                        thesis_embedding,
                        subjects,
                        embeddings.get(claim.text.strip()),
                    ),
                    3,
                ),
            })
            for claim in claims
        ]

    def _anchor_score(
        self,
        claim: Claim,
        thesis_embedding,
        subjects: set[str],
        claim_embedding,
    ) -> float:

        centrality = 0.0

        if thesis_embedding is not None and claim_embedding is not None:
            centrality = max(0.0, min(
                self.embeddings.similarity(
                    thesis_embedding,
                    claim_embedding,
                ),
                1.0,
            ))

        return (
            centrality * self.CENTRALITY_WEIGHT
            + self._subject_overlap(claim, subjects) * self.SUBJECT_WEIGHT
            + self._specificity(claim) * self.SPECIFICITY_WEIGHT
        )

    @staticmethod
    def _subject_overlap(claim: Claim, subjects: set[str]) -> float:
        """
        Whether this claim is about what the article is about. A claim
        naming none of the article's main subjects is usually background
        or an aside, however quotable it looks.
        """

        if not subjects:
            return 0.0

        claim_names = {
            value.lower()
            for values in claim.entities.values()
            for value in values
        }

        if not claim_names:
            # Fall back to a substring sweep: the claim may name the
            # subject without GLiNER having tagged it in this sentence.
            lowered = claim.text.lower()
            return 1.0 if any(s in lowered for s in subjects) else 0.0

        return min(len(claim_names & subjects) / len(claim_names), 1.0)

    @staticmethod
    def _specificity(claim: Claim) -> float:
        """
        Concrete beats vague. A claim carrying a figure and a date is
        falsifiable - there is something definite to go and check - while
        an unquantified assertion mostly is not.
        """

        facts = claim.facts

        present = sum([
            bool(facts.figures),
            bool(facts.dates),
            bool(facts.quotes),
        ])

        return present / 3.0

    def _is_duplicate(self, embedding, existing, dedup_threshold: float) -> bool:

        return any(
            self.embeddings.similarity(embedding, other) >= dedup_threshold
            for other in existing
        )

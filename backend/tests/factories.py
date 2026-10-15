from datetime import datetime

from src.models.core.claim import Claim
from src.models.core.enriched_article import EnrichedArticle
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.models.nlp.quality import Quality
from src.models.nlp.sentiment_result import SentimentResult
from src.models.nlp.topic_prediction import TopicPrediction

def create_article(**kwargs) -> EnrichedArticle:

    article = EnrichedArticle(
        id="11111111-1111-1111-1111-111111111111",
        source_id="bbc",
        url="https://bbc.com/test",
        title="Test article",
        body="This is a test article.",
        language="en",
        published_at=datetime.now(),

        keywords=["test"],
        entities={},

        topics=[TopicPrediction(topic="environment", confidence=0.71, probability=0.71)],
        claims=[],

        sentiment=SentimentResult(
            label="neutral",
            positive=0.2,
            neutral=0.7,
            negative=0.1,
            polarity=0.1,
            subjectivity=0.3,
            confidence=0.95,
            emotional_intensity=0.2,
        ),

        quality=Quality(
            readability=0.8,
            objectivity=0.8,
            constructiveness=0.8,
            inspirational_score=0.8,
            hopefulness=0.8,
            societal_impact=0.8,
            novelty=0.5,
        ),

        embedding=[0.1] * 1024,
        embedding_model="bge-m3",
        embedding_dimension=1024,
    )

    article = article.model_copy(update=kwargs)

    return article


def create_claim(**kwargs) -> Claim:

    claim = Claim(
        text="NASA discovered water on Mars in 2024.",
        entities={"ORG": ["NASA"]},
        confidence=0.8,
    )

    claim = claim.model_copy(update=kwargs)

    return claim


def create_evidence(**kwargs) -> Evidence:

    evidence = Evidence(
        url="https://example.com/article",
        title="Example evidence article",
        snippet="This is a snippet of evidence.",
        origin=EvidenceOrigin.WEB,
    )

    evidence = evidence.model_copy(update=kwargs)

    return evidence

def create_draft(**kwargs):
    """
    A draft as the writer leaves it: one generated revision, two sources
    the body cites as [1] and [2], one fact-check. Override any field.
    """

    from src.models.writer.draft import (
        ArticleDraft,
        DraftContent,
        DraftFactCheck,
        DraftRevision,
        DraftSource,
    )
    from src.services.writer.draft_store import new_draft_id, now

    content = kwargs.pop("content", None) or DraftContent(
        title="Seagrass meadows return to the bay",
        subtitle="Ten years of replanting doubled the meadow's area",
        body="The meadow has doubled since 2015 [1], and fish counts rose with it [2].",
    )

    stamp = now()

    draft = ArticleDraft(
        id=new_draft_id(),
        source_article_id="0123456789abcdef",
        language="en",
        instructions="Short, constructive, for a general audience.",
        content=content,
        sources=[
            DraftSource(
                url="https://example.org/seagrass",
                title="Seagrass restoration report",
                domain="example.org",
                origin="analysed",
                excerpt="The restored meadow covered twice its 2015 area.",
            ),
            DraftSource(
                url="https://example.com/fish",
                title="Fish return to restored meadows",
                domain="example.com",
                origin="related",
                excerpt="Surveys found more juvenile fish in the restored area.",
            ),
        ],
        fact_checks=[
            DraftFactCheck(
                claim="The meadow has doubled in area since 2015.",
                verdict="TRUE",
                confidence=0.82,
                source_urls=["https://example.org/seagrass"],
            ),
        ],
        revisions=[DraftRevision(content=content, reason="generated", model="test-model", at=stamp)],
        model="test-model",
        created_at=stamp,
        updated_at=stamp,
    )

    return draft.model_copy(update=kwargs)

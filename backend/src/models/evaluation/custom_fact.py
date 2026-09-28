from datetime import date
from enum import Enum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from src.config.topics import TOPICS
from src.models.fact_checker.fact_check import Verdict


# The keys of one x-fact row, in the order scripts/prepare_xfact_eval.py
# writes them. A custom fact carries every one of them, first and in this
# order, so whatever reads backend/data/evaluation/xfact_en_es.jsonl reads
# the custom set unchanged. Everything a custom fact adds comes after.
XFACT_FIELDS = (
    "language",
    "site",
    "claimant",
    "claim",
    "claimDate",
    "reviewDate",
    "labelRaw",
    "label",
    "referenceEvidenceLinks",
    "split",
)

# x-fact keeps the fact-checker's own label in labelRaw and the mapped
# Verdict in label. The custom set does the same: labelRaw is the label as
# the annotation guide names it (AVeriTeC's vocabulary, plus the one
# bucket AVeriTeC does not have), label is the Verdict the pipeline
# returns. docs/final_document/sections/custom_dataset.tex has the why.
LABEL_RAW = {
    Verdict.TRUE: "supported",
    Verdict.PARTIALLY_TRUE: "partially supported",
    Verdict.MISLEADING: "conflicting evidence/cherrypicking",
    Verdict.FALSE: "refuted",
    Verdict.UNVERIFIED: "not enough evidence",
}

# Every custom fact is held out: nothing is ever trained on it. x-fact's
# own held-out split carries this name, so a harness filtering on it
# treats both sets alike.
CUSTOM_SPLIT = "test"


class ClaimType(str, Enum):
    # A checkable event, date, name or relation.
    FACTUAL = "factual"
    # A figure, where the numeric tolerance rule applies.
    NUMERICAL = "numerical"
    # A reading of the facts - what the paper's evaluation section says
    # x-fact cannot measure, and the reason this set exists.
    INTERPRETIVE = "interpretive"


class SourceTier(str, Enum):
    # The strongest source behind the verdict, in the guide's hierarchy:
    # primary > reference media > press release > social media.
    PRIMARY = "primary"
    REFERENCE_MEDIA = "reference_media"
    PRESS_RELEASE = "press_release"
    SOCIAL_MEDIA = "social_media"


class CustomFactInput(BaseModel):
    """What the annotator types. Names match x-fact's keys where one exists."""

    claim: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "es"]
    # The outlet the claim was read in (its domain). x-fact puts the
    # fact-checker here; for this set the outlet is the useful attribution.
    site: str | None = Field(default=None, max_length=200)
    claimant: str | None = Field(default=None, max_length=200)
    # The article's publication date. Evidence published after it is not
    # admissible (the temporal rule), so it is required.
    claimDate: date
    label: Verdict
    referenceEvidenceLinks: list[str] = Field(default_factory=list, max_length=10)

    topic: str
    claimType: ClaimType
    sourceTier: SourceTier
    # Only the organisation the story is about backs the claim (its own
    # press release, report or post). The guide's rule: not enough evidence.
    onlyOwnSource: bool = False
    # The newest evidence used. Optional, but when given it must not be
    # later than claimDate.
    evidenceDate: date | None = None
    articleUrl: str | None = Field(default=None, max_length=2000)
    annotatorNote: str | None = Field(default=None, max_length=2000)

    @field_validator("claim", "site", "claimant", "annotatorNote", "articleUrl")
    @classmethod
    def _strip(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("referenceEvidenceLinks")
    @classmethod
    def _http_links(cls, links: list[str]) -> list[str]:

        cleaned = []

        for link in links:
            link = link.strip()
            if not link:
                continue
            if urlparse(link).scheme not in ("http", "https"):
                raise ValueError(f"Not an http(s) URL: {link}")
            if link not in cleaned:
                cleaned.append(link)

        return cleaned

    @field_validator("articleUrl")
    @classmethod
    def _http_article(cls, value):
        if value and urlparse(value).scheme not in ("http", "https"):
            raise ValueError(f"Not an http(s) URL: {value}")
        return value

    @field_validator("topic")
    @classmethod
    def _known_topic(cls, value: str) -> str:
        if value not in TOPICS:
            raise ValueError(f"Unknown topic: {value}")
        return value

    @model_validator(mode="after")
    def _guide_rules(self):

        # The tie-break rules that can be checked mechanically are checked
        # here rather than remembered: self-agreement drops on exactly the
        # cases a rule was written for.
        if self.label != Verdict.UNVERIFIED and not self.referenceEvidenceLinks:
            raise ValueError(
                "A verdict other than UNVERIFIED needs at least one evidence link."
            )

        if self.onlyOwnSource:
            if self.label != Verdict.UNVERIFIED:
                raise ValueError(
                    "Only the organisation's own source backs it: the guide "
                    "labels that UNVERIFIED (not enough evidence)."
                )
            if not self.annotatorNote:
                raise ValueError(
                    "Only the organisation's own source backs it: say which "
                    "source in the annotator note."
                )

        if self.evidenceDate and self.evidenceDate > self.claimDate:
            raise ValueError(
                "The evidence is newer than the article. Use only evidence "
                "available on the publication date."
            )

        if not self.site and self.articleUrl:
            self.site = _domain(self.articleUrl)

        if not self.site:
            raise ValueError("Give the outlet (site) or the article URL.")

        return self


class CustomFactReview(BaseModel):
    """The blind second label, for the 20% self-agreement sample."""

    label: Verdict
    note: str | None = Field(default=None, max_length=2000)


class CustomFact(BaseModel):
    """One stored row: x-fact's keys first and in x-fact's order, then the rest."""

    language: str
    site: str
    claimant: str | None
    claim: str
    claimDate: str
    reviewDate: str
    labelRaw: str
    label: Verdict
    referenceEvidenceLinks: list[str]
    split: str = CUSTOM_SPLIT

    id: str
    topic: str
    claimType: ClaimType
    sourceTier: SourceTier
    onlyOwnSource: bool
    evidenceDate: str | None
    articleUrl: str | None
    annotatorNote: str | None
    createdAt: str
    review: dict | None = None

    @classmethod
    def from_input(
        cls, fact_id: str, data: CustomFactInput, now: str, created_at: str | None = None
    ) -> "CustomFact":

        return cls(
            language=data.language,
            site=data.site,
            claimant=data.claimant,
            claim=data.claim,
            claimDate=data.claimDate.isoformat(),
            # x-fact's reviewDate is when the fact-checker published the
            # verdict; here it is when the annotator last set it.
            reviewDate=now,
            labelRaw=LABEL_RAW[data.label],
            label=data.label,
            referenceEvidenceLinks=data.referenceEvidenceLinks,
            id=fact_id,
            topic=data.topic,
            claimType=data.claimType,
            sourceTier=data.sourceTier,
            onlyOwnSource=data.onlyOwnSource,
            evidenceDate=data.evidenceDate.isoformat() if data.evidenceDate else None,
            articleUrl=data.articleUrl,
            annotatorNote=data.annotatorNote,
            createdAt=created_at or now,
        )


def _domain(url: str) -> str | None:

    host = urlparse(url).hostname or ""

    return host.removeprefix("www.") or None

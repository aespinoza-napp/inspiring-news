"""
A constructive angle for a story from a trend, found and checked
(docs/decisions/trends.md, "The angle").

What is trending is rarely good news: on 2026-10-26 not one of Spain's and
the US's twenty rising searches was. When a draft is written from a
trend's article, the writer model is asked for at most
`angle_max_proposals` constructive angles the trend points to - a
solution, a discovery, people helping, a measurable improvement - each as
a question, a news query and one checkable claim. **An angle is found,
never invented**: each claim goes through the fact-checker's own
`check_claim` (the path POST /verify-claim takes), with the analysed
article as its context so it cannot confirm its own angle, and is kept
only when the verdict is TRUE and the cited sources that support it come
from at least `angle_min_domains` domains other than the article's own
outlet. An angle that fails stays on the draft, refused, with why. If
none is kept, the draft is written as it would have been: no "bright
side" without sources.

Never for a disaster, a war, a crime or a death. The article passed the
mission screen to be offered at all, and is read by it again here (its
headline and lead), because a seed's news link or a round whose screen
was down may not have been. When the screen cannot be asked, no angle is
looked for: conservative before viral.

Inside the writing flow, not the analysis: no new `on_phase` stage
(CLAUDE.md, invariant 6), and the analysis cache is untouched. The
minimums are WriterThresholds fields, passed per call (invariant 1).
Free, like everything in the trends work: the writer model in the local
Ollama, the project's own search. The cost is time - one writer call and
a fact-check per angle, ~44 s a claim on this machine's CPU.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds, WriterThresholds
from src.models.fact_checker.evidence import EvidenceStance
from src.models.fact_checker.fact_check import FactCheck
from src.models.writer.draft import DraftAngle, DraftSource
from src.services.concurrency import bounded_map
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.llms import LLMUnavailableError
from src.services.scraper.request_stats import domain_of
from src.services.writer.analysed_article import AnalysedArticle

logger = logging.getLogger(__name__)

# What the screen may say an article is for no angle to be looked for.
REFUSED_KINDS = {"disaster", "conflict", "crime", "obituary"}

# The proposals' answer: a few short angles, not an article.
PROPOSAL_TOKENS = 800

# How much of the article the model reads to propose: its headline and lead.
LEAD_CHARS = 1200

# A claim is one sentence a search can confirm.
CLAIM_CHARS = 300

SYSTEM_PROMPT = """\
You are an editor at Inspiring News, a publication of constructive, solutions-focused journalism. \
A story is trending, and an article explains it. Most trends are not good news. Your job is to say \
whether this trend points to a constructive story that other sources could confirm: a solution that \
works, a discovery with a use, people helping others, a measurable improvement - something that \
happened, not a wish, a hope or an opinion.

Rules:
1. Propose at most {limit} angles, and none at all if the article gives no constructive thread. \
An empty list is a good answer: never invent a bright side, and never for an accident, a war, a \
crime, a death or a scandal.
2. Each angle has a question a reader would ask, a short news search query, and one claim: one \
plain sentence that would have to be true for the angle to stand, naming who did what, where, with \
a figure or a date where the article gives one. The claim must be checkable by a news search, not a \
judgement.
3. Never about a private person or a child: an angle is about what changed, not about someone who \
went viral.
4. Write the question, the query and the claim in {language}.

Answer with JSON only:
{{"angles": [{{"question": "...", "query": "...", "claim": "..."}}]}}"""


class ClaimChecker(Protocol):
    """What the angle step needs of the fact-checker: one claim, judged with its context."""

    def check(self, text: str, language: str | None, context: ArticleContext) -> FactCheck: ...


class FactCheckerClaims:
    """
    The /verify-claim path: ClaimService builds the claim (its entities),
    FactChecker.check_claim retrieves, ranks, asks the verifier and
    recalibrates. Built on first use: most drafts are not from a trend.
    """

    def __init__(self, claim_service=None):

        self._claim_service = claim_service

    @property
    def claim_service(self):

        if self._claim_service is None:
            from src.container import get_claim_service

            self._claim_service = get_claim_service()

        return self._claim_service

    def check(self, text: str, language: str | None, context: ArticleContext) -> FactCheck:

        thresholds = PipelineThresholds()
        claim = self.claim_service.build_claim(text, lambda phase, data: None, thresholds)

        return self.claim_service.fact_checker.check_claim(
            claim, thresholds=thresholds, context=context, language=language,
        )


@dataclass
class AngleResult:

    # Every angle proposed, kept or refused.
    angles: list[DraftAngle] = field(default_factory=list)

    # The kept angles' supporting sources, each once: the draft's
    # "angle" sources.
    sources: list[DraftSource] = field(default_factory=list)

    # Why none was looked for, or what went wrong looking.
    note: str | None = None

    model: str | None = None

    elapsed_ms: int = 0


class AngleFinder:

    def __init__(self, llm=None, checker: ClaimChecker | None = None, screen=None):

        # Each built on first use: the container builds this for every
        # draft, and most are not from a trend.
        self._llm = llm
        self._checker = checker
        self._screen = screen

    @property
    def llm(self):

        if self._llm is None:
            from src.services.llms import LLMClient

            self._llm = LLMClient(
                model=settings.WRITER_LLM_MODEL or settings.LLM_MODEL,
                timeout=settings.WRITER_LLM_TIMEOUT,
            )

        return self._llm

    @property
    def checker(self) -> ClaimChecker:

        if self._checker is None:
            self._checker = FactCheckerClaims()

        return self._checker

    @property
    def screen(self):

        if self._screen is None:
            from src.services.selection.mission_screen import MissionScreen

            self._screen = MissionScreen()

        return self._screen

    # ------------------------------------------------------------------

    def find(self, article: AnalysedArticle, trend: dict, thresholds: WriterThresholds | None = None) -> AngleResult:

        thresholds = thresholds or WriterThresholds()
        started = time.perf_counter()

        def done(result: AngleResult) -> AngleResult:
            result.elapsed_ms = round((time.perf_counter() - started) * 1000)
            if result.note:
                logger.info("Angles for %s: %s", article.url, result.note)
            return result

        if thresholds.angle_max_proposals == 0:
            return done(AngleResult(note="No angle was looked for (angle_max_proposals is 0)."))

        refusal = self._refusal(article)

        if refusal:
            return done(AngleResult(note=refusal))

        model = getattr(self.llm, "model", None)

        try:
            answer = self.llm.complete_json(
                SYSTEM_PROMPT.format(limit=thresholds.angle_max_proposals, language=_language_name(article.language)),
                proposal_prompt(article, trend),
                max_retries=0,
                max_tokens=PROPOSAL_TOKENS,
            )
        except LLMUnavailableError as exc:
            return done(AngleResult(note=f"The writer model could not be reached to propose an angle ({exc}).", model=model))

        if answer is None:
            return done(AngleResult(note="The writer model's answer had no usable angles.", model=model))

        proposals = parse_proposals(answer, thresholds.angle_max_proposals)

        if not proposals:
            return done(AngleResult(note="The writer model saw no constructive angle in this trend.", model=model))

        context = ArticleContext(
            title=article.headline,
            lead=article.lead,
            url=article.url,
            keywords=list(article.keywords),
        )

        checks = bounded_map(
            lambda proposal: self._check(proposal, article, context),
            proposals,
            max_workers=settings.CLAIM_MAX_CONCURRENCY,
            thread_name_prefix="angle-check",
        )

        angles: list[DraftAngle] = []
        sources: list[DraftSource] = []
        seen: set[str] = set()

        for proposal, check in zip(proposals, checks):

            angle, supporting = judge(proposal, check, article, thresholds)
            angles.append(angle)

            for source in supporting if angle.kept else []:
                if source.url not in seen:
                    seen.add(source.url)
                    sources.append(source)

        kept = sum(angle.kept for angle in angles)

        note = None if kept else f"None of the {len(angles)} proposed angles was confirmed: the draft takes none."

        return done(AngleResult(angles=angles, sources=sources, note=note, model=model))

    def _refusal(self, article: AnalysedArticle) -> str | None:
        """Why no angle may be looked for, by the screen's reading of the headline and lead; None to go on."""

        from src.services.selection.mission_screen import Candidate

        try:
            [assessment] = self.screen.assess(
                [Candidate(title=article.headline, summary=(article.lead or "")[:400], language=article.language)],
            )
        except Exception as exc:  # noqa: BLE001 - unable to ask is a refusal, not a pass
            return f"No angle was looked for: the mission screen could not read the article ({exc})."

        kind = assessment.verdict.off_mission if assessment.verdict else None

        if kind in REFUSED_KINDS:
            return f"No angle was looked for: the article reads as {kind}, and no bright side is written for one."

        return None

    def _check(self, proposal: dict, article: AnalysedArticle, context: ArticleContext) -> FactCheck | Exception:

        try:
            return self.checker.check(proposal["claim"], article.language, context)
        except Exception as exc:  # noqa: BLE001 - one angle, not the draft
            logger.warning("Checking an angle for %s failed: %s", article.url, exc)
            return exc


def _language_name(code: str | None) -> str:

    from src.services.writer.article_writer import language_name

    return language_name(code) if code else "the article's language"


def proposal_prompt(article: AnalysedArticle, trend: dict) -> str:
    """What the model reads to propose: the trend, and the article that explains it with its verdicts."""

    traffic = trend.get("traffic")
    lead = (article.lead or "")[:LEAD_CHARS]

    lines = [
        f'TRENDING: "{trend.get("name")}"'
        + (f" ({trend.get('signalName') or trend.get('signal')}" if trend.get("signal") else "")
        + (f", about {traffic}+ searches" if traffic else "")
        + (")" if trend.get("signal") else ""),
        "",
        f'THE ARTICLE THAT EXPLAINS IT: "{article.headline}" ({article.source_name})',
        "<<<",
        lead or "(no lead)",
        ">>>",
    ]

    if article.claims:
        lines += ["", "ITS CLAIMS, AS CHECKED:"]
        lines += [f'- "{claim.text}" - {claim.verdict}' for claim in article.claims]

    lines += ["", "Propose the angles as JSON."]

    return "\n".join(lines)


def parse_proposals(answer: dict | None, limit: int) -> list[dict]:
    """The model's angles that can be checked: a question and a claim each, at most `limit`, each claim once."""

    entries = (answer or {}).get("angles")
    proposals: list[dict] = []
    seen: set[str] = set()

    for entry in entries if isinstance(entries, list) else []:

        if not isinstance(entry, dict):
            continue

        question = " ".join(str(entry.get("question") or "").split())
        claim = " ".join(str(entry.get("claim") or "").split())[:CLAIM_CHARS]
        query = " ".join(str(entry.get("query") or "").split())

        if not question or len(claim.split()) < 4 or claim.lower() in seen:
            continue

        seen.add(claim.lower())
        proposals.append({"question": question, "claim": claim, "query": query})

        if len(proposals) >= limit:
            break

    return proposals


def judge(
    proposal: dict,
    check: FactCheck | Exception,
    article: AnalysedArticle,
    thresholds: WriterThresholds,
) -> tuple[DraftAngle, list[DraftSource]]:
    """
    Kept only when the claim came back TRUE and its cited, supporting
    sources span `angle_min_domains` domains other than the article's own
    outlet. Every other outcome is a refusal that says why.
    """

    angle = DraftAngle(question=proposal["question"], claim=proposal["claim"], query=proposal.get("query") or "")

    if isinstance(check, Exception):
        angle.reason = f"The claim could not be checked ({check})."
        return angle, []

    angle.verdict = str(getattr(check.verdict, "value", check.verdict))
    angle.confidence = check.confidence

    if check.llm_unreachable:
        angle.reason = "The verifier could not be reached: not checked."
        return angle, []

    if check.search_unavailable:
        angle.reason = "The search could not be done: not checked."
        return angle, []

    cited = set(check.cited_evidence_indices)
    own = (article.domain or "").lower()

    supporting = [
        evidence
        for index, evidence in enumerate(check.evidence)
        if index in cited and evidence.stance == EvidenceStance.SUPPORTS
        and (evidence.domain or domain_of(evidence.url)).lower() != own
    ]

    domains = sorted({(evidence.domain or domain_of(evidence.url)).lower() for evidence in supporting})
    angle.domains = domains

    if angle.verdict != "TRUE":
        angle.reason = f"The fact-check found it {angle.verdict}, not TRUE."
        return angle, []

    if len(domains) < thresholds.angle_min_domains:
        angle.reason = (
            f"TRUE, but supported by {len(domains)} domain{'s' if len(domains) != 1 else ''} other than the article's "
            f"own outlet; {thresholds.angle_min_domains} are needed."
        )
        return angle, []

    from src.services.writer.draft_writer import window

    sources = [
        DraftSource(
            url=evidence.url,
            title=evidence.title or "",
            domain=(evidence.domain or domain_of(evidence.url)),
            origin="angle",
            published_at=evidence.published_at.isoformat() if evidence.published_at else None,
            excerpt=window(evidence.content or evidence.quote or evidence.snippet, evidence.quote, thresholds.evidence_excerpt_chars),
            reliability_known=bool(evidence.reliability_known),
        )
        for evidence in supporting
    ]

    angle.kept = True
    angle.source_urls = [source.url for source in sources]
    angle.reason = (
        f"TRUE at {round(check.confidence * 100)}%, supported by {len(domains)} domains: {', '.join(domains)}."
    )

    return angle, sources

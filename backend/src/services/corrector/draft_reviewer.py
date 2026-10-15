"""
The corrector's review of a draft (docs/decisions/writing.md, "Review").

Nine metrics, each a CorrectionMetric on 0-100 where higher is better -
hallucinationIndex included, as on /correct:

- **title** and **subtitle**, which free text does not have: clarity,
  accuracy to the body, length, and how they work as a headline and a
  standfirst on the web;
- the corrector's seven: readability and coverageVerification
  (deterministic, as on /correct, but in the draft's declared language),
  grammar, factConsistency, seo, hallucinationIndex and style.

Then a proposed correction of title, subtitle and body, which a person
accepts or not (`POST /drafts/{id}/accept-correction`).

What differs from /correct is the grounding. Free text has nothing to be
held to; a draft has the excerpts the writer was given and the
pipeline's verdicts on the original article's claims. So
factConsistency and hallucinationIndex are judged against those, by the
model and by the checks in grounding.py, which bind the model's score
where they are certain.

**Two model calls, not one.** The review, then the correction:

- the correction is *guided* by the review - it is handed the issues
  found, the way an editor's notes go to the copy desk;
- each prompt asks one thing. The local models this runs on lose the
  thread of a prompt that asks for nine scores and a rewritten article in
  one JSON object, and a long body inside JSON is where they truncate;
- one failing does not lose the other: a correction that comes back
  unusable still leaves the metrics, as `corrected=None`;
- the correction needs no excerpts (it may add no facts), so its prompt
  is the draft and the notes - shorter, on a model that reads at CPU
  speed.

`TextCorrector.llm_metrics` and its SYSTEM_PROMPT are untouched: the
writing benchmark (src/evaluation/writing.py) measures exactly that
prompt, and this one is a different instrument.
"""

from __future__ import annotations

import logging

from src.config.lexicons import Lexicon, writing_lexicon_for
from src.models.corrector.correction_metric import CorrectionMetric
from src.models.nlp.quality import Quality
from src.models.writer.draft import ArticleDraft, DraftContent, DraftReview
from src.processors.nlp.quality import QualityAnalyzer
from src.processors.nlp.sentiment import SentimentAnalyzer
from src.services.admission.positive_impact import PositiveImpactScorer
from src.services.corrector import draft_language, grounding
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY, normalize_metric
from src.services.llms import LLMClient, LLMUnavailableError
from src.services.writer.draft_store import now

logger = logging.getLogger(__name__)

# What the review model scores, in the order the prompt lists them.
REVIEW_LLM_KEYS = ("title", "subtitle", "grammar", "factConsistency", "seo", "hallucinationIndex", "style")

# Every metric of a draft review, in the order a person reads them.
METRIC_ORDER = (
    "title",
    "subtitle",
    "grammar",
    "factConsistency",
    "coverageVerification",
    "seo",
    "readability",
    "hallucinationIndex",
    "style",
)

# ---- what the prompts carry ---------------------------------------------

# The excerpts share one budget, so a draft with many sources still fits
# a local model's context; each gets at most MAX_EXCERPT_CHARS of it.
SOURCES_BUDGET_CHARS = 14_000
MAX_EXCERPT_CHARS = 1_500

MAX_FACT_CHECKS = 20

# The notes handed to the correction: enough to guide it, not a second
# article.
MAX_NOTES = 40

# ---- headline and standfirst --------------------------------------------

# Search results show about 60 characters of a title; 70 leaves room for
# a news headline's specifics before the cut lands mid-word.
TITLE_MAX_CHARS = 70
TITLE_MIN_CHARS = 20
# One or two sentences; search snippets cut at about 160.
SUBTITLE_MAX_CHARS = 200
# A missing standfirst is a fact, not a judgement: no model is asked.
NO_SUBTITLE_CEILING = 20.0

# ---- readability ----------------------------------------------------------

# The readability metric lists the longest sentences past this many words.
LONG_SENTENCE_WORDS = 35
MAX_LONG_SENTENCES = 3

# ---- grounding ------------------------------------------------------------

# A citation to a source that does not exist is certain, and each one
# costs factConsistency this much of its ceiling.
DANGLING_CITATION_PENALTY = 20.0

# ---- the proposal -----------------------------------------------------------

# A proposal is checked before a person is offered it. Below half the
# body's length it was cut off or summarised; above this it added
# something. Only for bodies long enough for the ratio to mean anything.
MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 1.8
LENGTH_CHECK_MIN_CHARS = 400

# A proposal whose share of the language's stopwords falls below half
# the draft's came back in another language. Only when the draft has
# enough of them to compare.
MIN_STOPWORD_SHARE = 0.02
MIN_STOPWORD_RATIO = 0.5


REVIEW_SYSTEM_PROMPT = (
    "You are the senior editor of Inspiring, a news publication that reports "
    "constructive, solutions-focused, positive-impact stories accurately and "
    "without hype. You review a draft article before it is published.\n\n"
    "You receive the draft (a title, a subtitle and a Markdown body that cites "
    "its sources as [n]), the numbered sources the writer was given (an excerpt "
    "of each: the only text of it the writer saw), and the fact-checks of the "
    "original article, with the verdict our verification pipeline reached on "
    "each claim.\n\n"
    "Score the draft on each dimension from 0 to 100. Higher is ALWAYS better, "
    "INCLUDING hallucinationIndex: a high hallucinationIndex means every "
    "statement is grounded in the sources, a low one means the draft states "
    "things the sources do not support.\n"
    "- title: the headline. Clear and specific; accurate to the body (it "
    "promises nothing the body does not support); about 50-70 characters; the "
    "main subject and keyword near the start; no clickbait.\n"
    "- subtitle: the standfirst under the headline. Adds to the title instead of "
    "repeating it; accurate to the body; one or two sentences (about 120-160 "
    "characters); works as the snippet a search result shows.\n"
    "- grammar: grammar, spelling, punctuation and agreement, in the draft's "
    "language.\n"
    "- factConsistency: every factual sentence agrees with the source(s) it "
    "cites; figures, names, dates and places match the excerpts; each [n] "
    "points at a source that says what the sentence says; nothing contradicts "
    "another part of the draft or the fact-checks. A claim the fact-checks "
    "judged FALSE or MISLEADING, stated as fact, is a serious error.\n"
    "- seo: for the web. A clear headline with the main keyword; the subject "
    "named in the first paragraph; descriptive subheadings in a long body; no "
    "keyword stuffing.\n"
    "- hallucinationIndex: every factual sentence cites a source [n] whose "
    "excerpt supports it. Penalise a figure, name, quote, date or claim that is "
    "in no source; a citation to a source that does not say it; a claim the "
    "fact-checks judged UNVERIFIED stated as established fact.\n"
    "- style: Inspiring's voice. Constructive and hopeful but sober; a precise "
    "news register; active voice; no sensationalism, promotional tone or "
    "moralising; follows the editor's instructions.\n\n"
    "In every issue, quote the exact words of the draft it is about. Write the "
    "summaries and issues in English, quoting the draft in its own language. "
    "List only real problems; an empty list is fine.\n\n"
    "Respond with ONLY a JSON object of this exact shape, one entry per "
    "dimension above:\n"
    '{"title": {"score": <0-100>, "summary": "<1-2 sentences>", "issues": ["..."]}, '
    '"subtitle": {...}, "grammar": {...}, "factConsistency": {...}, "seo": {...}, '
    '"hallucinationIndex": {...}, "style": {...}}'
)


def correction_system_prompt(language: str) -> str:

    name = draft_language.language_name(language)

    return (
        "You are the copy editor of Inspiring, a news publication of "
        "constructive, positive-impact stories. Propose a corrected version of "
        "a draft article.\n\n"
        "Fix grammar, spelling and punctuation. Make it easier to read (shorter "
        "sentences, plain words) and improve the style (a sober, constructive "
        "news register, active voice, no hype). Improve the title and the "
        "subtitle: clear, specific and accurate to the body; the title about "
        "50-70 characters with the main subject near the start; the subtitle "
        "one or two sentences. Make it work on the web: the main keyword in the "
        "title and the first paragraph. Fix the problems the review found.\n\n"
        "Rules you must not break:\n"
        f"- Write in {name}, the draft's language. Never translate it.\n"
        "- Add no facts: no figure, name, date, place, quote, claim or source "
        "that is not already in the draft.\n"
        "- Keep every citation [n] with the statement it supports, with the same "
        "number. Never renumber, merge, move to another statement or invent a "
        "citation.\n"
        "- Where the review found a sentence unsupported, or contradicted by the "
        "fact-checks, you may soften it or remove it; never add support for it.\n"
        '- Keep the Markdown: paragraphs separated by a blank line, "## " '
        'subheadings, "- " lists, **bold**.\n'
        "- Keep about the same length.\n\n"
        'Respond with ONLY a JSON object: {"title": "...", "subtitle": "...", '
        '"body": "..."}'
    )


class DraftReviewer:

    def __init__(
        self,
        llm: LLMClient | None = None,
        sentiment_analyzer=None,
        quality_analyzer: QualityAnalyzer | None = None,
        impact_scorer: PositiveImpactScorer | None = None,
    ):
        self.llm = llm or LLMClient()
        self.sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self.quality_analyzer = quality_analyzer or QualityAnalyzer()
        self.impact_scorer = impact_scorer or PositiveImpactScorer()

    @property
    def model(self) -> str | None:

        return getattr(self.llm, "model", None)

    # ------------------------------------------------------------------
    # The review
    # ------------------------------------------------------------------

    def review(self, draft: ArticleDraft) -> DraftReview:
        """
        Review `draft.content` as it is now. Raises when the review cannot
        be made at all - an unknown language, inference/ or the model
        unreachable - so the caller records a failure rather than a
        review of zeros. A model that answers with something unusable is
        not that: those metrics come back as UNAVAILABLE_SUMMARY.
        """

        language = draft.language
        lexicon = writing_lexicon_for(language)
        content = draft.content

        body = grounding.plain(content.body)
        whole = "\n\n".join(part for part in (content.title, content.subtitle, body) if part.strip())

        metrics: dict[str, CorrectionMetric] = {}

        # Deterministic first. Coverage needs inference/ (sentiment), and
        # when that is down the review fails here, before minutes of the
        # model's time - rather than reporting a coverage score of 0 that
        # the rewrite loop would read as a failing metric.
        reading_ease = draft_language.readability(body, language, lexicon, self.quality_analyzer)
        metrics["readability"] = self._readability(content.body, language, reading_ease)
        metrics["coverageVerification"] = self._coverage(whole, language, lexicon, reading_ease)

        # Raises LLMUnavailableError when the model was never reached.
        answer = self.llm.complete_json(REVIEW_SYSTEM_PROMPT, review_prompt(draft))

        for key in REVIEW_LLM_KEYS:
            metrics[key] = normalize_metric(answer, key)

        found = grounding.check(content.body, len(draft.sources), draft.fact_checks, lexicon)
        apply_grounding(metrics, found, len(draft.sources))
        apply_headline_checks(metrics, content)

        corrected = self._propose(draft, metrics, lexicon)

        return DraftReview(
            metrics={key: metrics[key] for key in METRIC_ORDER},
            corrected=corrected,
            model=self.model,
            reviewed_at=now(),
        )

    # ------------------------------------------------------------------
    # Deterministic metrics
    # ------------------------------------------------------------------

    def _readability(self, markdown: str, language: str, reading_ease: float) -> CorrectionMetric:

        sentences = [grounding.plain(sentence) for sentence in grounding.body_sentences(markdown)]

        long_ones = sorted(
            (sentence for sentence in sentences if len(sentence.split()) > LONG_SENTENCE_WORDS),
            key=lambda sentence: len(sentence.split()),
            reverse=True,
        )

        return CorrectionMetric(
            score=round(reading_ease * 100, 1),
            summary=draft_language.readability_summary(language),
            issues=[
                f"A {len(sentence.split())}-word sentence: {grounding.quote(sentence)}"
                for sentence in long_ones[:MAX_LONG_SENTENCES]
            ],
        )

    def _coverage(self, text: str, language: str, lexicon: Lexicon, reading_ease: float) -> CorrectionMetric:
        """
        How well the draft fits Inspiring's mission: the admission
        filter's positive-impact score, as /correct computes it.

        QualityAnalyzer's metrics are called one by one with the lexicon
        object, not through `process(language=...)`: that resolves the
        code with `lexicon_for`, which answers English for Catalan.
        """

        # The model reads natural text; the word lists read it prepared.
        sentiment = self.sentiment_analyzer.process(text)

        prepared = draft_language.prepare_for_scoring(text, language)
        analyzer = self.quality_analyzer

        quality = Quality(
            readability=reading_ease,
            objectivity=analyzer.objectivity(prepared, None, lexicon),
            constructiveness=analyzer.constructiveness(prepared, lexicon),
            inspirational_score=analyzer.inspiration(prepared, sentiment, lexicon),
            hopefulness=analyzer.hopefulness(prepared, lexicon),
            societal_impact=analyzer.societal_impact(prepared, None, lexicon),
            novelty=0.5,
        )

        result = self.impact_scorer.score(sentiment, quality)

        summary = (
            "Aligns well with Inspiring's positive-impact criteria."
            if result.passed
            else "Does not fully align with Inspiring's positive-impact criteria."
        )

        if language == "ca":
            summary += (
                " Scored with the Catalan lexicon; the sentiment model in inference/ "
                "was not fine-tuned on Catalan, so its share of the score rests on "
                "multilingual pretraining."
            )

        return CorrectionMetric(
            score=round(result.score * 100, 1),
            summary=summary,
            issues=list(result.reasons),
        )

    # ------------------------------------------------------------------
    # The proposal
    # ------------------------------------------------------------------

    def _propose(self, draft: ArticleDraft, metrics: dict[str, CorrectionMetric], lexicon: Lexicon) -> DraftContent | None:

        try:
            answer = self.llm.complete_json(
                correction_system_prompt(draft.language),
                correction_prompt(draft, metrics),
            )
        except LLMUnavailableError as exc:
            # The metrics are already in hand; a review without a proposal
            # is still a review. Not always a dead socket: Ollama answers
            # 500 "token repeat limit reached" when a small model loops on
            # a long answer, and the client reports that as unreachable too.
            logger.warning("Draft %s: no correction proposed, the model call failed: %s", draft.id, exc)
            return None

        proposal, reason = read_proposal(answer, draft.content, lexicon)

        if proposal is None:
            logger.warning("Draft %s: correction discarded: %s", draft.id, reason)

        return proposal


# ----------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------


def _draft_block(content: DraftContent) -> str:

    return (
        f"TITLE: {content.title}\n"
        f"SUBTITLE: {content.subtitle or '(none)'}\n"
        f"BODY:\n{content.body}"
    )


def _clip(text: str, limit: int) -> str:

    text = " ".join(text.split())

    return text if len(text) <= limit else text[:limit].rstrip() + " [...]"


def review_prompt(draft: ArticleDraft) -> str:

    sources = draft.sources
    per_source = min(MAX_EXCERPT_CHARS, SOURCES_BUDGET_CHARS // max(len(sources), 1))

    source_lines = [
        f"[{index}] {source.domain or source.url} - {source.title or '(untitled)'}\n"
        f"{_clip(source.excerpt, per_source) if source.excerpt.strip() else '(no excerpt)'}"
        for index, source in enumerate(sources, start=1)
    ]

    check_lines = [
        f"- {fact_check.verdict.upper()}"
        + (f" (confidence {fact_check.confidence:.2f})" if fact_check.confidence is not None else "")
        + f": {fact_check.claim}"
        for fact_check in draft.fact_checks[:MAX_FACT_CHECKS]
    ]

    return (
        f"Language of the draft: {draft_language.language_name(draft.language)} ({draft.language})\n\n"
        f"Editor's instructions to the writer: {draft.instructions.strip() or '(none)'}\n\n"
        f"=== DRAFT ===\n{_draft_block(draft.content)}\n\n"
        f"=== SOURCES (the body cites them as [n]) ===\n"
        f"{chr(10).join(source_lines) if source_lines else '(none)'}\n\n"
        f"=== FACT-CHECKS of the original article ===\n"
        f"{chr(10).join(check_lines) if check_lines else '(none)'}"
    )


def correction_prompt(draft: ArticleDraft, metrics: dict[str, CorrectionMetric]) -> str:

    notes = [
        f"- [{key}] {issue}"
        for key in METRIC_ORDER
        if key in metrics
        for issue in metrics[key].issues
    ][:MAX_NOTES]

    return (
        f"Language: {draft_language.language_name(draft.language)} ({draft.language})\n\n"
        f"Problems the review found:\n{chr(10).join(notes) if notes else '(none recorded)'}\n\n"
        f"=== DRAFT ===\n{_draft_block(draft.content)}"
    )


# ----------------------------------------------------------------------
# Binding the model's scores to what the checks found
# ----------------------------------------------------------------------


def _bind(metric: CorrectionMetric, issues: list[str], ceiling: float | None = None, why: str = "") -> CorrectionMetric:
    """
    The checks' issues first - they are certain, or say what they are -
    then the model's. A ceiling lowers the model's score and says so; an
    unavailable metric keeps its UNAVAILABLE_SUMMARY and its 0, and still
    gets the issues, which did not need the model.
    """

    update: dict = {"issues": [*issues, *metric.issues]}

    available = metric.summary != UNAVAILABLE_SUMMARY

    if available and ceiling is not None and metric.score > ceiling:
        update["score"] = max(0.0, round(ceiling, 1))
        update["summary"] = f"{metric.summary} Capped at {round(max(ceiling, 0.0))}: {why}"

    return metric.model_copy(update=update)


def apply_grounding(metrics: dict[str, CorrectionMetric], found: grounding.Grounding, source_count: int) -> None:

    consistency: list[str] = []
    hallucination: list[str] = []

    for sentence, number in found.dangling:
        consistency.append(
            f"Cites [{number}], but the draft has {source_count} source{'s' if source_count != 1 else ''}: "
            f"{grounding.quote(sentence)}"
        )

    for echo in found.echoes:

        rule = (
            "it may be reported only as unconfirmed, never as fact"
            if echo.verdict == "UNVERIFIED"
            else "it must not be stated as fact"
        )

        issue = (
            f"Repeats a claim the fact-check judged {echo.verdict} - {rule}: "
            f"{grounding.quote(echo.sentence)} (the claim checked: “{echo.claim}”)"
        )

        (hallucination if echo.verdict == "UNVERIFIED" else consistency).append(issue)

    for sentence in found.uncited:
        hallucination.append(f"States a fact and cites no source: {grounding.quote(sentence)}")

    dangling_ceiling = 100.0 - DANGLING_CITATION_PENALTY * len(found.dangling) if found.dangling else None

    metrics["factConsistency"] = _bind(
        metrics["factConsistency"],
        consistency,
        dangling_ceiling,
        f"{len(found.dangling)} citation(s) point at no source.",
    )

    uncited_ceiling = (
        100.0 * (1 - len(found.uncited) / found.factual)
        if found.uncited and found.factual
        else None
    )

    metrics["hallucinationIndex"] = _bind(
        metrics["hallucinationIndex"],
        hallucination,
        uncited_ceiling,
        f"{len(found.uncited)} of {found.factual} factual sentences cite no source.",
    )


def apply_headline_checks(metrics: dict[str, CorrectionMetric], content: DraftContent) -> None:

    title = content.title.strip()
    subtitle = content.subtitle.strip()

    title_issues: list[str] = []

    if len(title) > TITLE_MAX_CHARS:
        title_issues.append(
            f"The title is {len(title)} characters; search results show about 60, so its end will be cut."
        )
    elif len(title) < TITLE_MIN_CHARS:
        title_issues.append(f"The title is only {len(title)} characters: too short to say what happened.")

    if grounding.CITATION.search(title):
        title_issues.append("The title carries a citation marker; citations belong in the body.")

    metrics["title"] = _bind(metrics["title"], title_issues)

    subtitle_issues: list[str] = []
    ceiling = None

    if not subtitle:
        subtitle_issues.append(
            "There is no subtitle: the standfirst is what search results and link previews show under the title."
        )
        ceiling = NO_SUBTITLE_CEILING
    elif len(subtitle) > SUBTITLE_MAX_CHARS:
        subtitle_issues.append(
            f"The subtitle is {len(subtitle)} characters; a standfirst reads best in one or two sentences, "
            "and search snippets cut at about 160."
        )

    if grounding.CITATION.search(subtitle):
        subtitle_issues.append("The subtitle carries a citation marker; citations belong in the body.")

    metrics["subtitle"] = _bind(metrics["subtitle"], subtitle_issues, ceiling, "the draft has no subtitle.")


# ----------------------------------------------------------------------
# Reading the proposal
# ----------------------------------------------------------------------


def read_proposal(answer, original: DraftContent, lexicon: Lexicon) -> tuple[DraftContent | None, str | None]:
    """
    The proposed content, or None and why. Checked before a person is
    offered it, because accepting replaces the article. Not offered: a
    proposal that cites a source the draft never cited or no longer cites
    one it did, moved a citation onto a statement its source was never
    cited for, carries a figure the draft does not have, came back cut
    short or padded, or came back translated.

    The figure, dropped-source and moved-citation rules come from the
    first live run (2026-10-15, llama3.2:3b, a Catalan draft): its
    proposal turned "deu anys" into "6 anys", dropped [2] and moved [1]
    onto "the bay is no longer free of plastics" - and passed every
    other check. A number written out in words ("ten" for "10") is not
    caught; a figure merely reformatted ("1,200" for "1200") is refused,
    which is the safe side.

    A missing or non-string subtitle keeps the draft's; a missing title
    or body is no proposal.

    Each rule is its own function below, in the order applied here, so
    the rewrite stage (src/services/writer/rewriter.py) holds a rewrite
    to the same rules - with the sources it has and a proposal does not.
    """

    proposal, reason = proposal_content(answer, original)

    if proposal is None:
        return None, reason

    reason = (
        citation_set_problem(original.body, proposal.body)
        or length_problem(original.body, proposal.body)
        or language_problem(original.body, proposal.body, lexicon)
        # Compared only once the proposal is known to be in the same
        # language: across languages no figure or word lines up.
        or figure_problem(original, proposal)
        or moved_citation_problem(original.body, proposal.body, lexicon.language)
    )

    if reason:
        return None, reason

    return proposal, None


def proposal_content(answer, original: DraftContent) -> tuple[DraftContent | None, str | None]:
    """
    A model's answer as content: a title and a body that are non-empty
    strings, or None and why. A missing or non-string subtitle keeps the
    draft's. Nothing is judged here but the shape.
    """

    if not isinstance(answer, dict):
        return None, "the model returned no JSON object"

    title = answer.get("title")
    body = answer.get("body")
    subtitle = answer.get("subtitle")

    if not isinstance(title, str) or not title.strip():
        return None, "no title"

    if not isinstance(body, str) or not body.strip():
        return None, "no body"

    if not isinstance(subtitle, str):
        subtitle = original.subtitle

    body = body.replace("\r\n", "\n").strip()

    return DraftContent(title=title.strip(), subtitle=subtitle.strip(), body=body), None


def citation_set_problem(original: str, proposed: str, *, allow_new: bool = False) -> str | None:
    """
    A source the draft cited that the new body no longer cites - or, unless
    `allow_new`, one it cites that the draft never did. A rewrite allows
    new ones (it reads the sources; `moved_citation_problem` holds each to
    its source's text); a proposal, which never saw them, does not.
    """

    before = set(grounding.citations(original))
    after = set(grounding.citations(proposed))

    if after - before and not allow_new:
        return f"it cites {sorted(after - before)}, which the draft does not"

    if before - after:
        return f"it no longer cites {sorted(before - after)}"

    return None


def length_problem(original: str, proposed: str) -> str | None:

    if len(original) < LENGTH_CHECK_MIN_CHARS:
        return None

    ratio = len(proposed) / len(original)

    if ratio < MIN_LENGTH_RATIO:
        return f"it is {ratio:.0%} of the draft's length: cut off or summarised"

    if ratio > MAX_LENGTH_RATIO:
        return f"it is {ratio:.0%} of the draft's length: something was added"

    return None


def language_problem(original: str, proposed: str, lexicon: Lexicon) -> str | None:

    share_before = draft_language.stopword_share(original, lexicon)
    share_after = draft_language.stopword_share(proposed, lexicon)

    if share_before >= MIN_STOPWORD_SHARE and share_after < MIN_STOPWORD_RATIO * share_before:
        return f"it is not in {draft_language.language_name(lexicon.language)}"

    return None


def figure_problem(original: DraftContent, proposed: DraftContent, sources: list[str] | None = None) -> str | None:
    """
    A figure (a run of digits) in the new text that the draft does not
    have - nor, when `sources` are given (the rewrite's case), any of
    them. A rewrite may put right a figure the draft got wrong, from the
    source; it may not bring one from anywhere else.
    """

    known = " ".join((original.title, original.subtitle, original.body, *(sources or [])))

    added = grounding.figures(" ".join((proposed.title, proposed.subtitle, proposed.body))) - grounding.figures(known)

    if not added:
        return None

    figures = ", ".join(sorted(added, key=int))

    if sources is None:
        return f"it has figures the draft does not: {figures}"

    return f"it has figures neither the draft nor its sources have: {figures}"


def moved_citation_problem(original: str, proposed: str, language: str, sources: dict[int, str] | None = None) -> str | None:

    moved = grounding.repointed(original, proposed, language, sources)

    if not moved:
        return None

    sentence, number = moved[0]

    return f"it moved [{number}] onto a statement that source was not cited for: {grounding.quote(sentence)}"

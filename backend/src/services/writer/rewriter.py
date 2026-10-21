"""
The rewrite stage (docs/decisions/writing.md, "Rewriting"): when a
draft's review falls short of the metrics expected, the writer's model
rewrites it, guided by what the review found, and the new text is
reviewed at once.

`POST /drafts/{id}/rewrite` (src/api/rewrite_routes.py) hands `run` to
`DraftStore.run_in_background`; the draft is `busy: "rewriting"` until it
returns. Each round:

1. the current text is rewritten - closed-world, under the writer's own
   rules (article_writer.CLOSED_WORLD_RULES), from the sources and
   fact-checks the draft holds, guided by the metrics below their
   targets (RewriteTargets): their summaries and issues;
2. the answer goes through the writer's repairs (draft_checks.py) and the
   review's proposal checks (draft_reviewer.py) - a rewrite that drops or
   moves a citation, brings a figure from nowhere, or switches language
   is not kept, and the draft stays as it was;
3. a kept rewrite is a `"rewritten"` revision, and the reviewer reviews
   it, so its own review is on it - kept even when it scores worse than
   the text it replaced: the history has the older text, and restoring
   it is one step (`POST /drafts/{id}/restore`).

Rounds repeat while a target is unmet, up to the request's `maxRounds`.
A metric the reviewer could not score (`UNAVAILABLE_SUMMARY`) is neither
met nor unmet: it counts for nothing, either way.

The model is the writer's (ArticleWriter.complete: WRITER_LLM_MODEL or
LLM_MODEL, WRITER_LLM_TIMEOUT, no retry, the answer capped). Temperature
is 0, so a rejected rewrite is not tried again in the next round: the
same prompt would get the same answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from src.config.lexicons import writing_lexicon_for
from src.config.thresholds import RewriteTargets, WriterThresholds
from src.models.writer.draft import ArticleDraft, DraftContent, DraftReview
from src.services.corrector.draft_reviewer import (
    METRIC_ORDER,
    DraftReviewer,
    citation_set_problem,
    figure_problem,
    language_problem,
    moved_citation_problem,
    proposal_content,
)
from src.services.corrector.text_corrector import UNAVAILABLE_SUMMARY
from src.services.writer.article_writer import (
    CLOSED_WORLD_RULES,
    NEWSROOM,
    ArticleWriter,
    fact_check_lines,
    fit_excerpts,
    language_name,
    one_line,
    reminders,
    source_lines,
)
from src.services.writer.draft_checks import check, repair_citations
from src.services.writer.draft_store import DraftStore, revise

logger = logging.getLogger(__name__)

# One round unless asked for more. A round is three calls to a model on
# the process's one LLM permit - the rewrite, then the review and its
# proposed correction - which on the production VM's CPU is estimated at
# tens of minutes for a 7B model (writing.md, "The model"), with
# fact-checking paused behind it. And the person should see what one
# rewrite did to the scores before paying for another.
DEFAULT_ROUNDS = 1

# Three at most: past that a model that has not met the targets is not
# converging, and the person's own edit is the better next step.
MAX_ROUNDS = 3

# The extra guidance for one rewrite. Notes for a rewrite, not a second
# brief: the draft's own instructions (up to 4,000 characters,
# draft_routes.MAX_INSTRUCTIONS_CHARS) still apply and go into the prompt
# beside them.
MAX_EXTRA_INSTRUCTIONS_CHARS = 2000

# Issues handed to the model, at most - the review's correction stops at
# the same number (draft_reviewer.MAX_NOTES): enough to guide it, not a
# second article.
MAX_GUIDANCE_ISSUES = 40

Standing = Literal["met", "below", "unscored"]

REWRITE_SYSTEM_PROMPT = (
    NEWSROOM
    + "\n\nAn editor reviewed an article written under the rules below and found it short of what "
    "the newsroom expects. You rewrite it: the same story, from the same numbered sources and "
    "fact-checks, fixing what the review found.\n\n"
    + CLOSED_WORLD_RULES
    + """

Rewriting. These too, always:
10. The SOURCES are the ones the article was written from, numbered as the article cites them. \
Keep every citation [n] with the statement it supports, under the same number. Never renumber, \
merge or move a citation onto a statement its source does not make. Keep citing every source \
the article cites now.
11. A sentence with no citation gets one only if a source says what the sentence says; \
otherwise cut it, or reduce it to what a source does say.
12. Fix every problem under WHAT THE REVIEW FOUND. A sentence the review found unsupported, or \
contradicted by the fact-checks, is corrected from the sources or removed.
13. No new figures: every number you write is already in the article or in a source.

Answer with JSON only, in this shape - every key filled:
{"title": "...", "subtitle": "one sentence", \
"body": "A first paragraph, every sentence ending with its source [1].\\n\\n## A subheading\\n\\nMore, \
from two sources [2][3]."}"""
)


class RewriteRejected(RuntimeError):
    """The model's rewrite broke a rule a rewrite must keep; nothing was saved."""


class RewriteRefused(RuntimeError):
    """The draft cannot be rewritten as it stands (no review, published)."""


class StaleRewrite(RuntimeError):
    """The text a rewrite or its review started from is not the draft's any more."""


NO_REVIEW = "There is no review of the current text to guide a rewrite. Review the draft first."

PUBLISHED = "This draft is published; unpublish it before changing it."

STALE = (
    "The draft changed while it was being rewritten, so the rewrite of the older text "
    "was not kept. Rewrite it again."
)


# ----------------------------------------------------------------------
# The targets
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MetricStanding:
    """One review metric against its target."""

    key: str

    target: float

    # None when the reviewer could not score it.
    score: float | None

    standing: Standing

    summary: str

    issues: list[str] = field(default_factory=list)


def scored(metric) -> bool:
    """
    Whether the reviewer scored the metric at all. An unscored one carries
    UNAVAILABLE_SUMMARY and a 0 that is not a judgement (normalize_metric):
    read as a score, it would fail every target and send every rewrite
    after a metric nothing measured.
    """

    return metric.summary != UNAVAILABLE_SUMMARY


def standings(review: DraftReview, targets: RewriteTargets) -> list[MetricStanding]:
    """Every metric of the review that has a target, in the order a person reads them."""

    by_metric = targets.by_metric()

    ordered = [key for key in METRIC_ORDER if key in review.metrics] + [
        key for key in review.metrics if key not in METRIC_ORDER
    ]

    result = []

    for key in ordered:

        if key not in by_metric:
            continue

        metric = review.metrics[key]
        target = by_metric[key]

        if not scored(metric):
            standing: Standing = "unscored"
            score = None
        else:
            score = metric.score
            standing = "met" if score >= target else "below"

        result.append(MetricStanding(
            key=key,
            target=target,
            score=score,
            standing=standing,
            summary=metric.summary,
            issues=list(metric.issues),
        ))

    return result


def below_target(review: DraftReview, targets: RewriteTargets) -> list[MetricStanding]:

    return [standing for standing in standings(review, targets) if standing.standing == "below"]


# ----------------------------------------------------------------------
# The prompt
# ----------------------------------------------------------------------


def _fmt(score: float) -> str:

    return f"{score:.0f}" if float(score).is_integer() else f"{score:.1f}"


def guidance_lines(review: DraftReview, targets: RewriteTargets) -> list[str]:
    """
    What the rewrite is asked to fix: each metric below its target with
    its score, summary and issues. When nothing is below target - a
    rewrite asked for the editor's instructions alone - the issues of
    every scored metric. The issues of an unscored metric always: they
    came from the checks that need no model (a sentence citing nothing,
    a citation pointing nowhere), which are certain.
    """

    every = standings(review, targets)
    below = [standing for standing in every if standing.standing == "below"]

    lines: list[str] = []
    budget = MAX_GUIDANCE_ISSUES

    def issues(items: list[str]) -> list[str]:
        nonlocal budget
        taken = items[:max(budget, 0)]
        budget -= len(taken)
        return [f"  - {issue}" for issue in taken]

    if below:
        lines.append("Below the editor's targets (0-100, higher is better):")
        for standing in below:
            lines.append(f"- {standing.key}: {_fmt(standing.score)}, target {_fmt(standing.target)}. {standing.summary}")
            lines += issues(standing.issues)
    else:
        lines.append(
            "Every scored metric meets its target. Rewrite as the editor's instructions ask, "
            "and fix these notes if any:"
        )
        for standing in every:
            if standing.standing == "met" and standing.issues:
                lines.append(f"- {standing.key}:")
                lines += issues(standing.issues)

    unscored = [standing for standing in every if standing.standing == "unscored" and standing.issues]

    if unscored:
        lines.append("Found without a model (the reviewer gave no score for these):")
        for standing in unscored:
            lines.append(f"- {standing.key}:")
            lines += issues(standing.issues)

    return lines


def rewrite_prompt(
    draft: ArticleDraft,
    review: DraftReview,
    targets: RewriteTargets,
    instructions: str,
    sources=None,
) -> str:
    """Everything the rewrite is given. `sources` are the draft's, fitted to the budget."""

    sources = draft.sources if sources is None else sources
    language = language_name(draft.language)

    parts = [
        f"LANGUAGE: {language}",
        "",
        "EDITOR'S INSTRUCTIONS, given when the article was written:",
        "<<<",
        draft.instructions.strip() or "(none)",
        ">>>",
        "",
        "EDITOR'S INSTRUCTIONS for this rewrite:",
        "<<<",
        instructions.strip() or "(none: fix what the review found)",
        ">>>",
        "",
        "WHAT THE REVIEW FOUND:",
        *guidance_lines(review, targets),
        "",
        "FACT-CHECKS of claims in the analysed article [1]:",
        *(fact_check_lines(draft.fact_checks, sources) or ["(none: no claim of it was checked)"]),
        "",
        "SOURCES (the article cites them by these numbers, which never change):",
        *source_lines(sources),
        "THE ARTICLE TO REWRITE:",
        f"TITLE: {draft.content.title}",
        f"SUBTITLE: {draft.content.subtitle or '(none)'}",
        "BODY:",
        "<<<",
        draft.content.body,
        ">>>",
        "",
        *reminders(sources, draft.fact_checks),
        "Keep citing every source the article cites now, each [n] on the statement it supports.",
        f"Now rewrite the article in {language}, as JSON.",
    ]

    return "\n".join(parts)


# ----------------------------------------------------------------------
# The rewriter
# ----------------------------------------------------------------------


@dataclass
class Rewritten:

    content: DraftContent

    model: str

    # What the writer's checks found and could not repair (draft_checks.py).
    findings: list[str] = field(default_factory=list)


class DraftRewriter:

    def __init__(self, writer: ArticleWriter, reviewer: DraftReviewer):

        self.writer = writer
        self.reviewer = reviewer

    @property
    def model(self) -> str:

        return self.writer.model

    # ------------------------------------------------------------------
    # One rewrite
    # ------------------------------------------------------------------

    def rewrite(
        self,
        draft: ArticleDraft,
        targets: RewriteTargets | None = None,
        instructions: str = "",
        thresholds: WriterThresholds | None = None,
    ) -> Rewritten:
        """
        The draft's current content, rewritten and checked. Raises
        RewriteRefused with no review to guide it, WriterError when the
        model cannot be reached, RewriteRejected when its answer cannot be
        kept - the draft itself is never touched here.
        """

        if draft.review is None:
            raise RewriteRefused(NO_REVIEW)

        targets = targets or RewriteTargets()
        thresholds = thresholds or WriterThresholds()

        review = draft.review

        def size(candidates) -> int:
            return len(REWRITE_SYSTEM_PROMPT) + len(rewrite_prompt(draft, review, targets, instructions, candidates))

        # Never drops a source, unlike the writer's fit: the numbering is
        # the draft's, and the article cites every one of them.
        fitted = fit_excerpts(draft.sources, size, thresholds.prompt_max_chars, drop=False)

        prompt = rewrite_prompt(draft, review, targets, instructions, fitted)

        logger.info(
            "Rewriting draft %s in %s with %s: %d metric(s) below target, %d prompt characters",
            draft.id,
            draft.language,
            self.model,
            len(below_target(review, targets)),
            len(REWRITE_SYSTEM_PROMPT) + len(prompt),
        )

        answer = self.writer.complete(REWRITE_SYSTEM_PROMPT, prompt, thresholds.max_output_tokens)

        return self.read(answer, draft, thresholds)

    def read(self, answer, draft: ArticleDraft, thresholds: WriterThresholds | None = None) -> Rewritten:
        """
        The model's answer as content, after the writer's repairs, or
        RewriteRejected with the rule it broke.
        """

        thresholds = thresholds or WriterThresholds()

        content, reason = proposal_content(answer, draft.content)

        if content is None:
            raise RewriteRejected(
                f"The rewrite was not kept: the model ({self.model}) answered without a usable "
                f"title and body ({reason}) - possibly cut off at {thresholds.max_output_tokens} tokens."
            )

        count = len(draft.sources)

        excerpts = [source.excerpt for source in draft.sources]

        known = (
            excerpts
            + [source.title for source in draft.sources]
            + [fact_check.claim for fact_check in draft.fact_checks]
        )

        title = one_line(content.title)

        # The writer's repairs, as on its own answer: the Markdown the page
        # renders, every [n] pointing at a source that exists.
        checked = check(
            content.body,
            title,
            count,
            original=next((source.excerpt for source in draft.sources if source.origin == "analysed"), None),
            texts=known + [draft.content.title, draft.content.subtitle, draft.content.body],
        )

        rewritten = DraftContent(title=title, subtitle=one_line(content.subtitle), body=checked.body)

        if not rewritten.title or not rewritten.body.strip():
            raise RewriteRejected("The rewrite was not kept: it came back with no title or no body.")

        # Compared with the draft's body as the same repairs leave it, so a
        # citation the draft had to a source that does not exist is not
        # counted as one the rewrite dropped.
        original, _ = repair_citations(draft.content.body, count)

        lexicon = writing_lexicon_for(draft.language)

        problem = (
            citation_set_problem(original, rewritten.body, allow_new=True)
            or language_problem(original, rewritten.body, lexicon)
            or figure_problem(draft.content, rewritten, sources=known)
            or moved_citation_problem(
                original,
                rewritten.body,
                lexicon.language,
                {number: text for number, text in enumerate(excerpts, start=1)},
            )
        )

        if problem:
            raise RewriteRejected(f"The rewrite was not kept: {problem}.")

        if rewritten == draft.content:
            raise RewriteRejected("The rewrite came back identical to the current text; nothing changed.")

        return Rewritten(content=rewritten, model=self.model, findings=checked.findings)

    # ------------------------------------------------------------------
    # The rounds
    # ------------------------------------------------------------------

    def start(
        self,
        store: DraftStore,
        draft_id: str,
        targets: RewriteTargets | None = None,
        instructions: str = "",
        rounds: int = DEFAULT_ROUNDS,
        *,
        wait: bool = False,
    ) -> ArticleDraft:
        """Rewriting in the background. Raises DraftBusy or DraftNotFound now."""

        return store.run_in_background(
            draft_id,
            "rewriting",
            lambda: self.run(store, draft_id, targets, instructions, rounds),
            wait=wait,
        )

    def run(
        self,
        store: DraftStore,
        draft_id: str,
        targets: RewriteTargets | None = None,
        instructions: str = "",
        rounds: int = DEFAULT_ROUNDS,
        thresholds: WriterThresholds | None = None,
    ) -> None:
        """
        Up to `rounds` rewrites, each reviewed. The first always runs - the
        person asked for it, perhaps for their instructions alone; the
        next only while a scored metric is below its target. A failure is
        raised with what was kept, for `run_in_background` to put in the
        draft's `error`.
        """

        targets = targets or RewriteTargets()
        rounds = max(1, min(rounds, MAX_ROUNDS))

        for number in range(1, rounds + 1):

            draft = store.get(draft_id)

            if draft is None:
                return

            if draft.status == "published":
                raise RewriteRefused(PUBLISHED)

            if draft.review is None:
                raise RewriteRefused(NO_REVIEW)

            if number > 1 and not below_target(draft.review, targets):
                logger.info("Draft %s: every scored target met after %d rewrite(s)", draft_id, number - 1)
                return

            read = draft.content.model_copy(deep=True)

            try:
                rewritten = self.rewrite(draft, targets, instructions, thresholds)
            except RewriteRejected as exc:
                logger.warning("Draft %s: rewrite %d of %d not kept: %s", draft_id, number, rounds, exc)
                raise RewriteRejected(self._so_far(number, rounds, str(exc))) from exc

            for finding in rewritten.findings:
                logger.warning("Draft %s: rewrite %d: %s", draft_id, number, finding)

            def keep(current: ArticleDraft) -> None:

                # Edits are refused while the draft is busy; this guards
                # whatever else changes it meanwhile, as the review's
                # stale check does (review_routes.py).
                if current.content != read:
                    raise StaleRewrite(STALE)

                if current.status == "published":
                    raise RewriteRefused(PUBLISHED)

                revise(current, rewritten.content, "rewritten", rewritten.model)

                # What was approved was the older text. Publishing trusts
                # `status`, so text nobody approved must not stay approved.
                current.status = "draft"

            store.update(draft_id, keep)

            self._review(store, draft_id, rewritten.content, number, rounds, targets)

    def _review(
        self,
        store: DraftStore,
        draft_id: str,
        content: DraftContent,
        number: int,
        rounds: int,
        targets: RewriteTargets,
    ) -> None:
        """
        The rewritten text's own review, attached only if it is still the
        text. Without a proposed correction when the loop's own test says
        another round follows - a round left and a scored metric below its
        target: that round rewrites this text, so a correction of it is
        minutes of the model spent on a proposal nobody is shown. If that
        next rewrite is then refused, the draft keeps this text with a
        review that proposes nothing; reviewing it again proposes one.
        """

        draft = store.get(draft_id)

        if draft is None:
            return

        def propose_if(review: DraftReview) -> bool:
            return number >= rounds or not below_target(review, targets)

        try:
            review = self.reviewer.review(draft, propose_if=propose_if)
        except Exception as exc:  # noqa: BLE001 - reported on the draft
            logger.exception("Draft %s: the review of rewrite %d failed", draft_id, number)
            raise RuntimeError(
                f"Rewrite {number} of {rounds} was kept, but its review failed ({exc}). "
                "Review the draft to score the new text."
            ) from exc

        def attach(current: ArticleDraft) -> None:

            if current.content != content:
                raise StaleRewrite(
                    "The draft changed before the rewrite's review finished, so the review "
                    "was not kept. Review it again."
                )

            current.review = review

        store.update(draft_id, attach)

    @staticmethod
    def _so_far(number: int, rounds: int, reason: str) -> str:

        if number == 1:
            return f"{reason} The draft keeps its current text and review."

        return (
            f"Round {number} of {rounds}: {reason} The draft keeps round {number - 1}'s rewrite "
            "and its review."
        )

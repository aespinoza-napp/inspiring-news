"""
The draft's own fact-check: the second check of the pipeline (2026-11-17).

The order the newsroom asked for: fetch -> fact-check the article -> only
if it checks out, extract its entities -> write the draft with them ->
fact-check the draft -> review -> publish. The first check asks the open
web whether the analysed article is right. This one asks something
narrower and closed: does each sentence of the draft say only what the
sources it cites say? The writer is held to its sources (CLOSED_WORLD_RULES,
draft_checks.py) by rules a model may break; this checks the result.

Every prose sentence carrying a citation [n] is scored by MiniCheck (Tang,
Laban & Durrett, EMNLP 2024; inference/ /grounding) against the excerpt of
each source it cites - the text the writer actually saw - and its support
is the best of them. That is the task MiniCheck was built for: a sentence
against its grounding document. A draft in Spanish, or a source in
another language than the sentence, is read in English translation
(inference/src/translation.py), since MiniCheck was trained on English.

Below `threshold` a sentence is unsupported: listed for the reviewer, not
removed. A sentence citing nothing is listed apart, unchecked. A model
that cannot be reached leaves the check with an `error` and no verdicts,
never a pass.
"""

from __future__ import annotations

import re
from logging import getLogger

from src.models.writer.draft import ArticleDraft, DraftCheck, DraftSentenceCheck
from src.processors.nlp.language import LanguageDetector
from src.services.inference_client import InferenceClient, InferenceUnavailable
from src.services.writer.draft_checks import CITATION, _numbers, _plain, uncited_sentences
from src.services.writer.draft_store import now

logger = getLogger(__name__)

# MiniCheck's own threshold (its authors', untuned here).
DEFAULT_THRESHOLD = 0.5

# A sentence ends, and a capitalised one begins: the split draft_checks.py
# uses, so the two agree on what a sentence is.
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý¿¡\"“«])")

_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def cited_sentences(body: str) -> list[tuple[str, list[int]]]:
    """Each prose sentence that cites a source, as plain text with the numbers it cites."""

    found: list[tuple[str, list[int]]] = []

    for block in body.split("\n\n"):

        if block.lstrip().startswith("#"):
            continue

        for line in block.split("\n"):

            text = line[2:] if line.startswith("- ") else line

            for sentence in _SENTENCE.split(text):

                numbers: list[int] = []
                for match in CITATION.finditer(sentence):
                    for number in _numbers(match.group(1)) or []:
                        if number not in numbers:
                            numbers.append(number)

                # A citation removed leaves its space: "since 2015 ." -> "since 2015."
                plain = re.sub(r"\s+([.,;:!?])", r"\1", " ".join(_plain(sentence).split()))

                if numbers and len(_WORD.findall(plain)) >= 3:
                    found.append((plain, numbers))

    return found


class DraftFactChecker:

    def __init__(self, grounding: InferenceClient | None = None, threshold: float = DEFAULT_THRESHOLD):

        self._grounding = grounding
        self.threshold = threshold

    def check(self, draft: ArticleDraft) -> DraftCheck:

        sentences = cited_sentences(draft.content.body)
        uncited = uncited_sentences(draft.content.body)

        pairs: list[tuple[str, str]] = []
        languages: list[tuple[str, str]] = []
        owners: list[tuple[int, int]] = []

        sentence_language = draft.language if draft.language in ("en", "es") else LanguageDetector.detect(draft.content.body)

        for index, (text, numbers) in enumerate(sentences):
            for number in numbers:
                if 1 <= number <= len(draft.sources):
                    excerpt = draft.sources[number - 1].excerpt or draft.sources[number - 1].title
                    if excerpt:
                        pairs.append((excerpt, text))
                        languages.append((LanguageDetector.detect(excerpt, fallback=sentence_language), sentence_language))
                        owners.append((index, number))

        if self._grounding is None:
            self._grounding = InferenceClient()

        try:
            answer = self._grounding.grounding(pairs, languages=languages, translate=True) if pairs else {"model": None, "scores": []}
        except InferenceUnavailable as exc:
            logger.warning("Draft %s: the grounding model was unreachable: %s", draft.id, exc)
            return DraftCheck(
                checked_at=now(),
                threshold=self.threshold,
                uncited=uncited,
                error="The grounding model (inference/, /grounding) could not be reached: the draft is not checked.",
            )

        best: dict[int, tuple[float, int, bool]] = {}

        for (index, number), score in zip(owners, answer.get("scores") or []):
            support = float(score.get("support") or 0.0)
            translated = bool(score.get("translated"))
            if index not in best or support > best[index][0]:
                best[index] = (support, number, translated)

        checked = []

        for index, (text, numbers) in enumerate(sentences):
            support, number, translated = best.get(index, (0.0, None, False))
            checked.append(DraftSentenceCheck(
                text=text,
                sources=numbers,
                support=round(support, 4),
                supported=support > self.threshold,
                best_source=number,
                translated=translated,
            ))

        return DraftCheck(
            checked_at=now(),
            model=answer.get("model"),
            threshold=self.threshold,
            sentences=checked,
            uncited=uncited,
        )


class StaleCheck(RuntimeError):
    """The text a check read is not the draft's text any more."""


def check_and_attach(store, draft_id: str, checker: DraftFactChecker) -> DraftCheck | None:
    """
    Check the draft's current text and attach the result, only if the text
    is still the one read: a check describes the text it read, as a review
    does (review_routes.py). Returns the check, or None for a draft gone.
    """

    draft = store.get(draft_id)

    if draft is None:
        return None

    read = draft.content.model_copy(deep=True)
    result = checker.check(draft)

    def attach(current: ArticleDraft) -> None:
        if current.content != read:
            raise StaleCheck("The draft changed while it was being fact-checked, so the check was not kept. Check it again.")
        current.check = result

    store.update(draft_id, attach)

    return result

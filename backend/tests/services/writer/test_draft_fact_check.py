"""
The draft's own fact-check (services/writer/draft_fact_check.py, 2026-11-17):
each cited sentence against the excerpts of the sources it cites, by
MiniCheck - stubbed here; the real model is tested in inference/.
"""

from src.models.writer.draft import DraftContent, DraftSource
from src.services.inference_client import InferenceUnavailable
from src.services.writer.draft_fact_check import DraftFactChecker, check_and_attach, cited_sentences
from src.services.writer.draft_store import DraftStore, revise
from tests.factories import create_draft


class StubGrounding:

    def __init__(self, supports=None, raises=None):
        self.supports = list(supports or [])
        self.raises = raises
        self.calls = []

    def grounding(self, pairs, languages=None, translate=True):
        self.calls.append((pairs, languages, translate))
        if self.raises:
            raise self.raises
        return {"model": "lytang/MiniCheck-Flan-T5-Large", "scores": [
            {"support": self.supports[i] if i < len(self.supports) else 0.0, "chunk": 0, "chunks": 1, "translated": []}
            for i in range(len(pairs))
        ]}


def draft_with(body, sources=None, language="en"):

    return create_draft(
        language=language,
        content=DraftContent(title="T", body=body),
        sources=sources or [
            DraftSource(url="https://a/1", origin="analysed", excerpt="The meadow doubled in size since 2015."),
            DraftSource(url="https://b/2", origin="related", excerpt="Fish counts in the bay rose by a third."),
        ],
    )


def test_each_cited_sentence_is_found_with_its_sources():

    found = cited_sentences("## Heading [1]\n\nThe meadow has doubled since 2015 [1]. Fish counts rose with it [1][2].\n\nNo citation here at all, none.")

    # The heading and the uncited sentence are not in it.
    assert found == [("The meadow has doubled since 2015.", [1]), ("Fish counts rose with it.", [1, 2])]


def test_a_sentence_is_supported_by_its_best_cited_source():

    grounding = StubGrounding([0.2, 0.91])
    draft = draft_with("Fish counts in the bay rose by a third [1][2].")

    check = DraftFactChecker(grounding).check(draft)

    [sentence] = check.sentences
    assert sentence.supported and sentence.best_source == 2 and sentence.support == 0.91
    assert check.unsupported == []


def test_an_unsupported_sentence_is_listed_not_removed():

    draft = draft_with("The meadow has doubled since 2015 [1]. The mayor resigned over it [2].")

    check = DraftFactChecker(StubGrounding([0.95, 0.03])).check(draft)

    assert [s.supported for s in check.sentences] == [True, False]
    assert [s.text for s in check.unsupported] == [check.sentences[1].text]


def test_a_spanish_draft_tells_minicheck_its_language():

    grounding = StubGrounding([0.9])
    draft = draft_with("La pradera se ha duplicado desde 2015 [1].", language="es")

    DraftFactChecker(grounding).check(draft)

    [(pairs, languages, translate)] = grounding.calls
    assert languages[0][1] == "es" and translate is True


def test_an_unreachable_model_is_an_error_never_a_pass():

    draft = draft_with("The meadow has doubled since 2015 [1].")

    check = DraftFactChecker(StubGrounding(raises=InferenceUnavailable("down"))).check(draft)

    assert check.error and check.sentences == []


def test_a_check_is_attached_to_the_text_it_read_and_cleared_by_an_edit(tmp_path):

    store = DraftStore(tmp_path)
    draft = store.save(draft_with("The meadow has doubled since 2015 [1]."))

    check_and_attach(store, draft.id, DraftFactChecker(StubGrounding([0.9])))
    assert store.get(draft.id).check is not None

    store.update(draft.id, lambda current: revise(current, DraftContent(title="T", body="Edited [1]."), "edited"))
    assert store.get(draft.id).check is None

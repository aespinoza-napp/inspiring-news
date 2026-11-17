"""
/grounding: MiniCheck's support score (src/grounding.py).

Asks the real checkpoint, as the rest of this suite asks the real models
(its first run downloads ~3 GB for Flan-T5-Large).
"""

import pytest
from fastapi.testclient import TestClient
from huggingface_hub import try_to_load_from_cache

from src.grounding import GroundingModel, grounding_model
from src.main import app

# The checkpoint is ~3 GB: a suite that started that download unasked would
# hold ./scripts/check.sh for as long as the network takes (2026-11-17: it
# came at 0.1-2 MB/s). Fetch it once, deliberately:
#   cd inference && HF_HUB_DISABLE_XET=1 uv run python -c "from huggingface_hub import \
#     snapshot_download; snapshot_download('lytang/MiniCheck-Flan-T5-Large')"
_CACHED = isinstance(try_to_load_from_cache(grounding_model.name, "pytorch_model.bin"), str) or \
    isinstance(try_to_load_from_cache(grounding_model.name, "model.safetensors"), str)

needs_checkpoint = pytest.mark.skipif(not _CACHED, reason=f"{grounding_model.name} is not downloaded (see this file's comment)")

DOCUMENT = (
    "A group of students gather in the school library to study for their upcoming final exams. "
    "The library closes at nine."
)


@needs_checkpoint
def test_the_authors_token_ids_are_support_and_no_support():

    grounding_model.load()

    if grounding_model._seq2seq:
        # The authors' code comments 3 as "no support" and 209 as "support".
        # T5 writes "0" as "▁" then "0", and "1" as the one piece "▁1", so
        # the first decoding step tells them apart by "▁" against "▁1".
        # Checked on 2026-11-17, not assumed.
        assert grounding_model._tokenizer.convert_ids_to_tokens([3, 209]) == ["▁", "▁1"]
        assert grounding_model._tokenizer.convert_ids_to_tokens(grounding_model._tokenizer("0 1")["input_ids"])[:3] == ["▁", "0", "▁1"]


@needs_checkpoint
def test_a_supported_claim_scores_high_and_an_unsupported_one_low():

    response = TestClient(app).post("/grounding", json={"pairs": [
        {"document": DOCUMENT, "claim": "The students are preparing for an examination."},
        {"document": DOCUMENT, "claim": "The students are on vacation."},
    ]})

    assert response.status_code == 200

    supported, unsupported = response.json()["scores"]

    assert supported["support"] > 0.5 > unsupported["support"]


@needs_checkpoint
def test_a_long_document_is_cut_into_chunks_and_scored_by_its_best():

    padding = " ".join(f"Sentence number {i} is about the weather in another town." for i in range(120))
    document = f"{padding} The students are studying for their final exams in the library."

    [score] = grounding_model.score_many([(document, "The students are preparing for exams.")])

    assert score.chunks > 1
    assert score.chunk == score.chunks - 1
    assert score.support > 0.5


def test_sentences_are_packed_up_to_the_chunk_size():

    model = GroundingModel()
    model._seq2seq = True

    chunks = model.chunks("One two three. " * 400)

    assert len(chunks) > 1 and all(len(chunk.split()) <= 500 for chunk in chunks)


# ----------------------------------------------------------------------
# Not English (2026-11-17): translated first (src/translation.py)
# ----------------------------------------------------------------------

_TRANSLATOR_CACHED = isinstance(try_to_load_from_cache("Helsinki-NLP/opus-mt-es-en", "pytorch_model.bin"), str)

needs_translator = pytest.mark.skipif(
    not (_CACHED and _TRANSLATOR_CACHED), reason="MiniCheck or Helsinki-NLP/opus-mt-es-en is not downloaded",
)

DOCUMENTO = (
    "El ayuntamiento aprobó el martes el nuevo presupuesto tras un largo debate. "
    "La biblioteca municipal cierra a las nueve."
)


@needs_translator
def test_a_spanish_pair_is_read_in_english_and_scored_as_one():

    supported, unsupported = grounding_model.score_many(
        [
            (DOCUMENTO, "El ayuntamiento aprobó el presupuesto el martes."),
            (DOCUMENTO, "El ayuntamiento rechazó el presupuesto."),
        ],
        languages=[("es", "es"), ("es", "es")],
    )

    assert supported.translated == ("document", "claim")
    assert supported.support > 0.5 > unsupported.support


@needs_translator
def test_a_spanish_claim_against_an_english_page():

    [score] = grounding_model.score_many(
        [("The city council approved the new budget on Tuesday after a long debate.",
          "El ayuntamiento aprobó el presupuesto el martes.")],
        languages=[("en", "es")],
    )

    assert score.translated == ("claim",)
    assert score.support > 0.5


@needs_checkpoint
def test_a_language_with_no_model_is_left_as_it_is():

    [score] = grounding_model.score_many([(DOCUMENT, "Les étudiants préparent un examen.")], languages=[("en", "fr")])

    assert score.translated == ()


def test_without_languages_nothing_is_translated():

    pairs = [("Uno.", "Dos.")]

    assert GroundingModel._in_english(pairs, None) == (pairs, [()])

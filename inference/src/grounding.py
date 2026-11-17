"""
MiniCheck: does a document support a claim? (Tang, Laban & Durrett,
"MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents",
EMNLP 2024.) Added 2026-11-17 as another way to judge a claim against
its sources: a 0.4-0.8B classifier trained for exactly that question,
in place of asking a 3B chat model per source.

Reimplemented from the authors' own inference code (github.com/Liyan06/
MiniCheck, minicheck/inference.py, Apache-2.0; the checkpoints are MIT)
rather than installing their package, which pulls vLLM for its 7B:

- the document is split into sentences and packed greedily into chunks
  of at most 400 tokens (RoBERTa, DeBERTa) or 500 words (Flan-T5);
- each chunk is scored against the whole claim, joined as
  `chunk + eos + claim` (Flan-T5: prefixed "predict: ");
- the encoders' support probability is the softmax's column 1; Flan-T5's
  is the softmax over the first decoder step's logits of tokens 3 (no
  support) and 209 (support);
- a document's score is the **max over its chunks**: supported if any
  part of it supports the claim. Supported means a score above 0.5 -
  the threshold is the backend's (`grounding_min_support`), not this
  service's.

What it cannot say: there is no "contradicted" class. The paper drops it,
"as contradictions are rare in our benchmark"; a score below the
threshold means *not supported*, never *refuted*. The models were trained
on English only.

Loaded on the first request, not at warm-up: no stage of the default
pipeline asks for it, and the Flan-T5 checkpoint is ~3 GB in memory.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from .config import settings
from .loading import LOADING

# Flan-T5's vocabulary ids the authors read at the first decoding step.
_T5_NO_SUPPORT, _T5_SUPPORT = 3, 209

# The authors split with nltk's punkt; a full stop, question or
# exclamation mark followed by space and a capital or a digit does as
# well for packing chunks, and needs no data download.
_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[\"“«(¿¡A-ZÁÉÍÓÚÑÜ\d])")


@dataclass(frozen=True)
class GroundingScore:

    # Probability, 0-1, that the best chunk supports the claim.
    support: float

    # Which chunk gave it, and how many the document was cut into.
    chunk: int
    chunks: int

    # "document" and/or "claim": read in English translation.
    translated: tuple[str, ...] = ()


class GroundingModel:

    def __init__(self):
        self._lock = threading.Lock()
        self._model = None
        self._tokenizer = None
        self._seq2seq = False
        self._max_tokens = 512

    @property
    def name(self) -> str:
        return settings.GROUNDING_MODEL

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:

        with self._lock, LOADING:

            if self._model is not None:
                return

            import torch
            from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoModelForSequenceClassification, AutoTokenizer

            config = AutoConfig.from_pretrained(self.name)
            self._seq2seq = bool(getattr(config, "is_encoder_decoder", False))

            if self._seq2seq:
                model = AutoModelForSeq2SeqLM.from_pretrained(self.name)
            else:
                model = AutoModelForSequenceClassification.from_pretrained(self.name, num_labels=2)

            self._tokenizer = AutoTokenizer.from_pretrained(self.name, use_fast=True)

            # The authors' lengths: RoBERTa's 512 positions; 2048 for
            # Flan-T5 and DeBERTa, whose attention is relative.
            self._max_tokens = 512 if config.model_type == "roberta" else 2048
            self._model = model.eval()

    # ------------------------------------------------------------------

    def score_many(
        self,
        pairs: list[tuple[str, str]],
        languages: list[tuple[str | None, str | None]] | None = None,
    ) -> list[GroundingScore]:
        """
        (document, claim) pairs, each scored by its best chunk, in input
        order. With `languages` - each pair's (document, claim) language -
        a text not in English is first translated into it (translation.py):
        the models read English only.
        """

        self.load()

        pairs, translated = self._in_english(pairs, languages)

        flat: list[tuple[int, str, str]] = []
        counts: list[int] = []

        for index, (document, claim) in enumerate(pairs):
            chunks = self.chunks(document)
            counts.append(len(chunks))
            flat.extend((index, chunk, claim) for chunk in chunks)

        probabilities = self._support([(chunk, claim) for _, chunk, claim in flat])

        scores: list[GroundingScore] = []
        at = 0

        for count in counts:
            mine = probabilities[at:at + count]
            best = max(range(count), key=lambda i: mine[i])
            scores.append(GroundingScore(
                support=float(mine[best]), chunk=best, chunks=count, translated=translated[len(scores)],
            ))
            at += count

        return scores

    @staticmethod
    def _in_english(
        pairs: list[tuple[str, str]],
        languages: list[tuple[str | None, str | None]] | None,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, ...]]]:
        """
        Every text the caller marked as another language than English, in
        English, each distinct text translated once (a claim is the same in
        all its pairs). Unmarked, English, or with no model: as it was.
        """

        if not languages:
            return pairs, [()] * len(pairs)

        from .translation import translator

        wanted: dict[tuple[str, str], str] = {}

        for (document, claim), (document_language, claim_language) in zip(pairs, languages):
            for text, language in ((document, document_language), (claim, claim_language)):
                if language and language != "en" and translator.available(language):
                    wanted[(language, text)] = text

        done: dict[tuple[str, str], str] = {}

        for language in {language for language, _ in wanted}:
            keys = [key for key in wanted if key[0] == language]
            for key, english in zip(keys, translator.to_english([text for _, text in keys], language)):
                done[key] = english

        out, flags = [], []

        for (document, claim), (document_language, claim_language) in zip(pairs, languages):
            document_key, claim_key = (document_language, document), (claim_language, claim)
            out.append((done.get(document_key, document), done.get(claim_key, claim)))
            flags.append(tuple(
                name for name, key in (("document", document_key), ("claim", claim_key)) if key in done
            ))

        return out, flags

    def chunks(self, document: str) -> list[str]:
        """Sentences packed greedily up to the chunk size; a longer sentence stays whole."""

        sentences = [
            piece.strip()
            for block in (document or "").split("\n")
            for piece in _SENTENCE.split(block)
            if piece.strip()
        ] or [""]

        limit = settings.GROUNDING_CHUNK_WORDS if self._seq2seq else settings.GROUNDING_CHUNK_TOKENS

        def size(sentence: str) -> int:
            if self._seq2seq:
                return len(sentence.split())
            return len(self._tokenizer(sentence, add_special_tokens=False)["input_ids"])

        chunks: list[list[str]] = [[]]
        used = 0

        for sentence in sentences:

            length = size(sentence)

            if chunks[-1] and used + length > limit:
                chunks.append([])
                used = 0

            chunks[-1].append(sentence)
            used += length

        return [" ".join(chunk) for chunk in chunks]

    def _support(self, pairs: list[tuple[str, str]]) -> list[float]:

        import torch

        out: list[float] = []
        eos = self._tokenizer.eos_token or ""
        size = max(1, settings.GROUNDING_BATCH_SIZE)

        for start in range(0, len(pairs), size):

            batch = [f"{chunk}{eos}{claim}" for chunk, claim in pairs[start:start + size]]

            if self._seq2seq:
                batch = [f"predict: {text}" for text in batch]

            encoded = self._tokenizer(
                batch,
                max_length=self._max_tokens,
                truncation=True,
                padding=True,
                return_tensors="pt",
            )

            # Per call, not once at load: grad mode is thread-local, and
            # FastAPI answers each request from a pool thread.
            with torch.inference_mode():

                if self._seq2seq:
                    start_ids = torch.zeros((encoded["input_ids"].size(0), 1), dtype=torch.long)
                    logits = self._model(
                        input_ids=encoded["input_ids"],
                        attention_mask=encoded["attention_mask"],
                        decoder_input_ids=start_ids,
                    ).logits.squeeze(1)[:, [_T5_NO_SUPPORT, _T5_SUPPORT]]
                else:
                    logits = self._model(**encoded).logits

            out.extend(torch.softmax(logits, dim=-1)[:, 1].tolist())

        return out


grounding_model = GroundingModel()

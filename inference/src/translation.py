"""
Into English, for a model that reads only English (2026-11-17).

MiniCheck was trained on English alone (Tang et al., EMNLP 2024, its
Limitations). The app checks Spanish articles, and a Spanish claim's
evidence is often an English page or the other way round, so before
grounding.py scores a pair, any text the backend says is not English is
translated: "translate-test", the usual way to run an English-only
classifier on another language.

One Marian model per source language (Helsinki-NLP's OPUS-MT, Tiedemann &
Thottingal, EAMT 2020; Apache-2.0, ~300 MB each, ~77M parameters),
loaded on first use. Only Spanish is configured, the one other language
the pipeline supports (invariant 8). A language without a model is left
as it is and reported, never refused: a score on untranslated text is
still a score, and the caller is told.

A long text is translated sentence by sentence in groups, since Marian
reads at most 512 tokens and silently drops the rest.
"""

from __future__ import annotations

import re
import threading

from .config import settings
from .loading import LOADING

_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[\"“«(¿¡A-ZÁÉÍÓÚÑÜ\d])")

# Words per group sent to the model at once: well under its 512 tokens,
# since a Spanish word is often two or three sentencepiece tokens.
_GROUP_WORDS = 120


class Translator:

    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[str, tuple] = {}

    def available(self, language: str | None) -> bool:
        return bool(language) and language in settings.TRANSLATION_MODELS

    def to_english(self, texts: list[str], language: str) -> list[str]:
        """`texts` in `language`, in English, in input order."""

        if not texts or not self.available(language):
            return list(texts)

        tokenizer, model = self._load(language)

        import torch

        out: list[str] = []

        for text in texts:

            groups = self._groups(text)
            translated: list[str] = []

            for start in range(0, len(groups), settings.TRANSLATION_BATCH_SIZE):

                batch = groups[start:start + settings.TRANSLATION_BATCH_SIZE]
                encoded = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)

                with torch.inference_mode():
                    generated = model.generate(**encoded, max_new_tokens=512, num_beams=1)

                translated.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))

            out.append(" ".join(piece.strip() for piece in translated if piece.strip()))

        return out

    def _groups(self, text: str) -> list[str]:

        sentences = [
            piece.strip()
            for block in (text or "").split("\n")
            for piece in _SENTENCE.split(block)
            if piece.strip()
        ]

        groups: list[list[str]] = [[]]
        words = 0

        for sentence in sentences:
            length = len(sentence.split())
            if groups[-1] and words + length > _GROUP_WORDS:
                groups.append([])
                words = 0
            groups[-1].append(sentence)
            words += length

        return [" ".join(group) for group in groups if group] or [""]

    def _load(self, language: str):

        with self._lock, LOADING:

            if language not in self._models:

                from transformers import MarianMTModel, MarianTokenizer

                name = settings.TRANSLATION_MODELS[language]
                self._models[language] = (
                    MarianTokenizer.from_pretrained(name),
                    MarianMTModel.from_pretrained(name).eval(),
                )

            return self._models[language]


translator = Translator()

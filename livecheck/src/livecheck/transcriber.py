"""
Words from sound, in sentences that each carry their own times.
"""

import re
from dataclasses import dataclass
from typing import Callable

import numpy as np

# Words ending in a full stop that do not end a sentence.
ABBREVIATIONS = {
    "dr.", "mr.", "mrs.", "ms.", "prof.", "st.", "vs.", "etc.", "e.g.", "i.e.",
    "u.s.", "u.k.", "sr.", "sra.", "ud.", "uds.", "no.",
}

# A speaker change inside one long run of words cannot be heard by a voice
# model looking at the whole run, and Whisper does not always punctuate.
LONGEST_SENTENCE = 15.0


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class TimedSentence:
    start: float
    end: float
    text: str


def _ends_sentence(word: str) -> bool:

    bare = word.strip().lower()

    if bare in ABBREVIATIONS:
        return False

    return bool(re.search(r"[.?!…][\"'»”)]*$", bare))


def _sentence(words: list[Word]) -> TimedSentence:

    return TimedSentence(
        start=words[0].start,
        end=words[-1].end,
        text="".join(word.text for word in words).strip(),
    )


def _split_long(words: list[Word]) -> list[list[Word]]:

    if words[-1].end - words[0].start <= LONGEST_SENTENCE or len(words) < 2:
        return [words]

    widest = max(
        range(len(words) - 1),
        key=lambda index: words[index + 1].start - words[index].end,
    )

    return _split_long(words[: widest + 1]) + _split_long(words[widest + 1 :])


def to_sentences(words: list[Word]) -> list[TimedSentence]:

    sentences, current = [], []

    for word in words:

        current.append(word)

        if _ends_sentence(word.text):
            sentences.extend(_sentence(part) for part in _split_long(current))
            current = []

    if current:
        sentences.extend(_sentence(part) for part in _split_long(current))

    return [sentence for sentence in sentences if sentence.text]


def is_invented(seconds: float, probability: float, longest: float, lowest: float) -> bool:
    return seconds < longest and probability < lowest


class Transcriber:

    # Whisper writes something for music and applause too. These are its
    # own measures of having heard no speech and of repeating itself.
    NO_SPEECH = 0.6
    LOW_LOGPROB = -1.0
    REPETITIVE = 2.4

    # Whisper closes a stretch of sound with words nobody said ("Thank you.",
    # "you"), with its own no-speech measure at 0.00 to 0.33. On a real
    # interview these were all under a second with a mean word probability of
    # 0.17-0.49, and every real segment had 0.78 or more.
    INVENTED_SECONDS = 1.0
    INVENTED_PROBABILITY = 0.5

    # A language guessed from one short utterance is often wrong and then
    # flips sentence to sentence, so the first confident guess stays.
    LOCK_LANGUAGE = 0.85

    def __init__(
        self,
        model: str = "small",
        language: str | None = None,
        threads: int = 4,
    ):
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            model, device="cpu", compute_type="int8", cpu_threads=threads
        )
        self.language = language
        self.heard_so_far = ""

    def __call__(self, audio: np.ndarray, offset: float) -> list[TimedSentence]:

        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            word_timestamps=True,
            vad_filter=False,
            condition_on_previous_text=False,
            # Heard alone, a short clip loses its capital and question mark:
            # "who was the first person to walk on the moon." The last words
            # show Whisper the sentence it is in and how it is written.
            initial_prompt=self.heard_so_far or None,
        )

        words = []

        for segment in segments:

            if segment.compression_ratio > self.REPETITIVE:
                continue

            if (
                segment.no_speech_prob > self.NO_SPEECH
                and segment.avg_logprob < self.LOW_LOGPROB
            ):
                continue

            heard = segment.words or []

            if heard and is_invented(
                segment.end - segment.start,
                sum(word.probability for word in heard) / len(heard),
                self.INVENTED_SECONDS,
                self.INVENTED_PROBABILITY,
            ):
                continue

            words.extend(
                Word(offset + word.start, offset + word.end, word.word)
                for word in heard
            )

        if self.language is None and info.language_probability >= self.LOCK_LANGUAGE:
            self.language = info.language

        sentences = to_sentences(words)

        if sentences:
            self.heard_so_far = f"{self.heard_so_far} {' '.join(s.text for s in sentences)}"[-200:].strip()

        return sentences


TranscribeFn = Callable[[np.ndarray, float], list[TimedSentence]]

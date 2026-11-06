"""
Cuts a stream of sound into utterances, at the pauses, as it arrives.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

from livecheck.audio import SAMPLE_RATE


@dataclass
class Utterance:
    start: float
    end: float
    audio: np.ndarray


def silero_speech(audio: np.ndarray) -> list[tuple[int, int]]:

    from faster_whisper.vad import VadOptions, get_speech_timestamps

    spans = get_speech_timestamps(
        audio,
        VadOptions(min_silence_duration_ms=200, speech_pad_ms=60),
    )

    return [(span["start"], span["end"]) for span in spans]


class Segmenter:
    """
    Holds the sound since the last cut and looks for speech in it about
    once a second.

    An utterance ends at a pause of `pause` seconds, or by force at
    `longest` seconds: a fluent speaker can talk for a minute without one,
    and nothing would reach the screen until they stopped.
    """

    CHECK_EVERY = 1.0

    def __init__(
        self,
        speech: Callable[[np.ndarray], list[tuple[int, int]]] = silero_speech,
        pause: float = 0.6,
        longest: float = 15.0,
    ):
        self.speech = speech
        self.pause = pause
        self.longest = longest
        self.buffer = np.zeros(0, dtype=np.float32)
        self.offset = 0
        self.since_check = 0

    def feed(self, chunk: np.ndarray) -> list[Utterance]:

        self.buffer = np.concatenate([self.buffer, chunk])
        self.since_check += len(chunk)

        if self.since_check < self.CHECK_EVERY * SAMPLE_RATE:
            return []

        self.since_check = 0

        return self._cut(final=False)

    def flush(self) -> list[Utterance]:
        return self._cut(final=True)

    def _cut(self, final: bool) -> list[Utterance]:

        spans = self.speech(self.buffer)

        if not spans:
            # Keep half a second: a word may be starting at the very end.
            self._drop(max(0, len(self.buffer) - SAMPLE_RATE // 2))
            return []

        utterances = []

        # A pause can lie anywhere in what is held, not only at its end: with
        # a look once a second, the next speaker has often begun by then. Cut
        # at the end only, and whole turns of two people stayed in one piece.
        pause = int(self.pause * SAMPLE_RATE)
        first = spans[0][0]

        for (_, end), (following, _) in zip(spans, spans[1:]):

            if following - end >= pause:
                utterances.append(self._utterance(first, end))
                first = following

        last_end = spans[-1][1]
        silence = len(self.buffer) - last_end
        held = (last_end - first) / SAMPLE_RATE

        if final or silence >= pause:
            cut = last_end
        elif held >= self.longest:
            cut = self._best_cut([span for span in spans if span[0] >= first])
        else:
            cut = None

        if cut is not None:
            utterances.append(self._utterance(first, cut))
            self._drop(cut)
        elif utterances:
            self._drop(first)

        return utterances

    def _utterance(self, start: int, end: int) -> Utterance:

        return Utterance(
            start=(self.offset + start) / SAMPLE_RATE,
            end=(self.offset + end) / SAMPLE_RATE,
            audio=self.buffer[start:end].copy(),
        )

    @staticmethod
    def _best_cut(spans: list[tuple[int, int]]) -> int:
        """The end of the span before the widest gap, or all of it."""

        if len(spans) == 1:
            return spans[0][1]

        widest = max(
            range(len(spans) - 1),
            key=lambda index: spans[index + 1][0] - spans[index][1],
        )

        return spans[widest][1]

    def _drop(self, samples: int) -> None:

        self.buffer = self.buffer[samples:]
        self.offset += samples

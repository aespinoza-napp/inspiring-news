"""
Tells voices apart from their sound alone, as they arrive.

Nobody says beforehand who is talking or how many there are, so this is
online clustering: a voice close enough to a known one is that person,
otherwise it is someone new.
"""

import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np

from livecheck.audio import SAMPLE_RATE

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    "speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx"
)

CACHE = Path.home() / ".cache" / "livecheck"


def _unit(vector: np.ndarray) -> np.ndarray:

    norm = np.linalg.norm(vector)

    return vector / norm if norm else vector


class SherpaEmbedder:

    def __init__(self, threads: int = 2):

        import sherpa_onnx

        path = CACHE / MODEL_URL.rsplit("/", 1)[1]

        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_suffix(".partial")
            urllib.request.urlretrieve(MODEL_URL, partial)
            partial.rename(path)

        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(path), num_threads=threads
            )
        )

    def __call__(self, audio: np.ndarray) -> np.ndarray:

        stream = self.extractor.create_stream()
        stream.accept_waveform(SAMPLE_RATE, audio)
        stream.input_finished()

        # Too little sound for even one frame of the model. A zero vector
        # is near nobody, so it cannot start anyone new (see min_new).
        if not self.extractor.is_ready(stream):
            return np.zeros(self.extractor.dim, dtype=np.float32)

        return np.array(self.extractor.compute(stream), dtype=np.float32)


class SpeakerTracker:
    """
    `threshold` is the cosine above which a voice counts as a known one.
    Swept on two recordings: at 0.72 a scripted two-voice dialogue came out
    exactly right, and it merged into one voice at 0.65 and below, because two
    voices of one synthesiser are alike (up to 0.72). A real interview's guest
    stayed one voice from 0.55 to 0.75; there different voices scored up to
    0.57 and one voice 0.7-0.93. The 0.42 this began with merged two people.

    Sound shorter than `min_new` seconds cannot start a new speaker and
    does not move a speaker's average: a "yes" holds too little voice to
    be trusted. Under `too_short` it is not looked at, and stays with the
    last speaker.
    """

    def __init__(
        self,
        embed: Callable[[np.ndarray], np.ndarray],
        threshold: float = 0.72,
        max_speakers: int = 4,
        min_new: float = 1.5,
        too_short: float = 0.5,
    ):
        self.embed = embed
        self.threshold = threshold
        self.max_speakers = max_speakers
        self.min_new = min_new
        self.too_short = too_short
        self.sums: list[np.ndarray] = []
        self.last: int | None = None

        # (sentence id, embedding, seconds): kept for the second pass.
        self.history: list[tuple[int, np.ndarray, float]] = []

        # Sentences too short to look at, and whose lead they follow.
        self.followers: dict[int, int] = {}

    def assign(self, sentence_id: int, audio: np.ndarray) -> int:

        seconds = len(audio) / SAMPLE_RATE

        if seconds < self.too_short:

            if self.history:
                self.followers[sentence_id] = self.history[-1][0]

            return self.last or 0

        vector = _unit(self.embed(audio))

        self.history.append((sentence_id, vector, seconds))

        speaker = self._nearest(vector, seconds)

        self.last = speaker

        return speaker

    def _nearest(self, vector: np.ndarray, seconds: float) -> int:

        if not self.sums:
            self.sums.append(vector * seconds)
            return 0

        similarity = [float(_unit(total) @ vector) for total in self.sums]
        best = int(np.argmax(similarity))

        known = similarity[best] >= self.threshold
        may_be_new = seconds >= self.min_new and len(self.sums) < self.max_speakers

        if not known and may_be_new:
            self.sums.append(vector * seconds)
            return len(self.sums) - 1

        if seconds >= self.min_new:
            self.sums[best] = self.sums[best] + vector * seconds

        return best

    def settle(self, merge_above: float = 0.8) -> dict[int, int]:
        """
        A second look at the whole conversation, once it is over.

        Early on a speaker's average rests on a few seconds, so early
        sentences are the likeliest to be wrong; and one person heard in a
        different mood can have become two. Merges speakers whose averages
        turned out alike, then gives every sentence to its nearest final
        speaker. Returns {sentence id: speaker}.
        """

        groups = [[index] for index in range(len(self.sums))]

        while len(groups) > 1:

            means = [_unit(sum(self.sums[i] for i in group)) for group in groups]

            pairs = [
                (float(means[a] @ means[b]), a, b)
                for a in range(len(groups))
                for b in range(a + 1, len(groups))
            ]

            best, a, b = max(pairs)

            if best < merge_above:
                break

            groups[a].extend(groups.pop(b))

        means = [_unit(sum(self.sums[i] for i in group)) for group in groups]

        settled = {
            sentence_id: int(np.argmax([float(mean @ vector) for mean in means]))
            for sentence_id, vector, _ in self.history
        }

        for sentence_id, lead in self.followers.items():
            settled[sentence_id] = settled[lead]

        return settled

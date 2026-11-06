import numpy as np

from livecheck.audio import SAMPLE_RATE, find_stream
from livecheck.segmenter import Segmenter
from livecheck.speakers import SpeakerTracker
from livecheck.transcriber import Transcriber, Word, is_invented, to_sentences

LISTING = """Sink Input #71
\tDriver: protocol-native.c
\tCorked: yes
\tProperties:
\t\tapplication.name = "Brave"
\t\tapplication.process.binary = "brave"

Sink Input #72
\tDriver: protocol-native.c
\tCorked: no
\tProperties:
\t\tapplication.name = "Brave"
\t\tapplication.process.binary = "brave"

Sink Input #73
\tCorked: no
\tProperties:
\t\tapplication.name = "Spotify"
"""


def test_find_stream_takes_the_playing_one_of_the_named_application():
    assert find_stream("brave", LISTING) == "72"
    assert find_stream("SPOTIFY", LISTING) == "73"
    assert find_stream("vlc", LISTING) is None


def test_sentences_split_at_their_ends_and_not_at_abbreviations():
    words = [
        Word(0, 1, " Dr."), Word(1, 2, " Smith"), Word(2, 3, " left."),
        Word(3, 4, " Why"), Word(4, 5, " now?"), Word(5, 6, " Because"),
    ]

    sentences = to_sentences(words)

    assert [s.text for s in sentences] == ["Dr. Smith left.", "Why now?", "Because"]
    assert (sentences[1].start, sentences[1].end) == (3, 5)


def test_a_long_run_without_punctuation_splits_at_its_widest_pause():
    words = [Word(float(i), i + 0.9, f" w{i}") for i in range(10)]
    words += [Word(12.0 + i, 12.9 + i, f" x{i}") for i in range(10)]

    sentences = to_sentences(words)

    assert len(sentences) == 2
    assert sentences[1].text.startswith("x0")


def _speech_where_loud(audio):
    """Stands in for the voice detector: speech is what is not zero."""

    loud = np.flatnonzero(audio)

    if not len(loud):
        return []

    breaks = np.flatnonzero(np.diff(loud) > SAMPLE_RATE // 10)
    starts = [loud[0]] + [loud[b + 1] for b in breaks]
    ends = [loud[b] + 1 for b in breaks] + [loud[-1] + 1]

    return [(int(a), int(b)) for a, b in zip(starts, ends)]


def _sound(*parts):
    return np.concatenate(
        [np.full(int(seconds * SAMPLE_RATE), level, dtype=np.float32) for seconds, level in parts]
    )


def test_segmenter_cuts_at_a_pause_keeping_true_times():
    segmenter = Segmenter(speech=_speech_where_loud)

    found = segmenter.feed(_sound((1, 0), (2, 0.5), (1, 0)))

    assert len(found) == 1
    assert round(found[0].start, 2) == 1.0
    assert round(found[0].end, 2) == 3.0

    found = segmenter.feed(_sound((1, 0.5), (1, 0)))

    assert round(found[0].start, 2) == 4.0


def test_segmenter_does_not_wait_forever_for_a_fluent_speaker():
    segmenter = Segmenter(speech=_speech_where_loud, longest=5)

    assert segmenter.feed(_sound((3, 0.5))) == []
    assert len(segmenter.feed(_sound((3, 0.5)))) == 1


def test_segmenter_finds_a_pause_inside_what_it_holds():
    # The next speaker has already begun when the segmenter looks. Found on a
    # recording where twelve turns came out as six pieces.
    segmenter = Segmenter(speech=_speech_where_loud)

    found = segmenter.feed(_sound((2, 0.5), (0.8, 0), (2, 0.5)))

    assert [(round(u.start, 2), round(u.end, 2)) for u in found] == [(0.0, 2.0)]

    found = segmenter.flush()

    assert [(round(u.start, 2), round(u.end, 2)) for u in found] == [(2.8, 4.8)]


def test_segmenter_flush_gives_what_is_still_held():
    segmenter = Segmenter(speech=_speech_where_loud)

    segmenter.feed(_sound((0.5, 0.5)))

    assert len(segmenter.flush()) == 1


def _seconds(seconds, voice):
    """Audio whose first sample names a voice, for an embedder made to read it."""

    audio = np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)
    audio[0] = voice

    return audio


VOICES = {
    1.0: np.array([1.0, 0.0, 0.0]),
    2.0: np.array([0.0, 1.0, 0.0]),
    3.0: np.array([0.7, 0.7, 0.14]),
}


def _tracker(**options):
    return SpeakerTracker(lambda audio: VOICES[float(audio[0])], **options)


def test_tracker_recognises_a_returning_voice_and_a_new_one():
    tracker = _tracker()

    assert [tracker.assign(i, _seconds(3, v)) for i, v in enumerate([1.0, 2.0, 1.0, 2.0])] == [0, 1, 0, 1]


def test_a_short_sound_cannot_start_a_new_speaker():
    tracker = _tracker()

    tracker.assign(0, _seconds(3, 1.0))

    assert tracker.assign(1, _seconds(1, 2.0)) == 0
    assert len(tracker.sums) == 1


def test_a_very_short_sound_stays_with_the_last_speaker_unlooked_at():
    tracker = _tracker()

    tracker.assign(0, _seconds(3, 1.0))
    tracker.assign(1, _seconds(3, 2.0))

    assert tracker.assign(2, _seconds(0.2, 1.0)) == 1


def test_never_more_speakers_than_allowed():
    tracker = _tracker(max_speakers=1)

    assert [tracker.assign(i, _seconds(3, v)) for i, v in enumerate([1.0, 2.0])] == [0, 0]


def test_settle_gives_a_short_sentence_to_whoever_it_followed():
    tracker = _tracker()

    tracker.assign(0, _seconds(3, 1.0))
    tracker.assign(1, _seconds(3, 2.0))
    tracker.assign(2, _seconds(0.2, 2.0))

    assert tracker.settle() == {0: 0, 1: 1, 2: 1}


def test_a_short_sound_with_nobody_heard_yet_needs_no_voice_model():
    assert SpeakerTracker(lambda audio: 1 / 0).assign(0, _seconds(0.2, 1.0)) == 0


def test_settle_merges_one_person_heard_as_two():
    tracker = _tracker(threshold=0.9)

    for index, voice in enumerate([1.0, 3.0, 1.0]):
        tracker.assign(index, _seconds(3, voice))

    assert len(tracker.sums) == 2

    assert set(tracker.settle(merge_above=0.6).values()) == {0}


def test_only_short_doubtful_segments_count_as_invented():
    def invented(seconds, probability):
        return is_invented(
            seconds, probability, Transcriber.INVENTED_SECONDS, Transcriber.INVENTED_PROBABILITY
        )

    # The measures of "Thank you." and of the shortest real segment on a real
    # interview, and a long passage Whisper is unsure of: that is speech.
    assert invented(0.0, 0.49)
    assert not invented(1.4, 0.97)
    assert not invented(6.0, 0.40)

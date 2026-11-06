"""
One conversation, from the first sound to the report.

Four jobs that run at very different speeds, so each has its own thread and
none holds up the one before: hearing never stops, words take a fraction of
real time, a model's judgement some seconds, a fact-check most of a minute.
The transcript stays live while the checks fall behind, and the checks catch
up after the conversation ends.

Everything that happens is appended to events.jsonl as it happens, so a crash
or a closed terminal loses nothing: `livecheck report <dir>` rebuilds the
report from that file alone.
"""

import json
import queue
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from livecheck.conversation import (
    Exchange,
    Sentence,
    assign_roles,
    build_exchanges,
    merge_fragments,
)
from livecheck.judge import extract_claims, judge_answer
from livecheck.segmenter import Utterance
from livecheck.verifier import NOT_CHECKED

_DONE = object()


def _normalised_claim(text: str) -> str:
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


class EventLog:

    def __init__(self, directory: Path):
        self.path = directory / "events.jsonl"
        self.lock = threading.Lock()
        directory.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **data) -> None:

        with self.lock, self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n")


class Session:

    def __init__(
        self,
        source,
        segmenter,
        transcribe,
        tracker,
        chat,
        verify,
        directory: Path,
        show: Callable[[str, dict], None] = lambda kind, data: None,
        max_claims: int = 30,
        max_lag: float = 60.0,
    ):
        self.source = source
        self.segmenter = segmenter
        self.transcribe = transcribe
        self.tracker = tracker
        self.chat = chat
        self.verify = verify
        self.log = EventLog(directory)
        self.show = show
        self.max_claims = max_claims
        self.max_lag = max_lag

        self.utterances: queue.Queue = queue.Queue()
        self.turns: queue.Queue = queue.Queue()
        self.claims: queue.Queue = queue.Queue()

        self.sentences: list[Sentence] = []
        self.lock = threading.Lock()
        self.judged: set[str] = set()
        self.extracted: set[str] = set()
        self.seen_claims: set[str] = set()
        self.claims_queued = 0
        self.spoken_until = 0.0

        self.heard_seconds = 0.0
        self.skipped_seconds = 0.0
        self.silent_since = 0.0
        self.abandon = threading.Event()

    # ---- hearing -------------------------------------------------------

    def _hear(self) -> None:

        heard = 0

        # `finally`: if capture dies, the rest must still finish and report,
        # not wait for sound that will never come.
        try:
            for chunk in self.source.chunks():

                heard += len(chunk)
                self.heard_seconds = heard / 16_000

                if chunk.size and float(abs(chunk).max()) > 0.001:
                    self.silent_since = self.heard_seconds
                elif self.heard_seconds - self.silent_since >= 30:
                    # Muted tab, or the wrong sink. Better said than a report
                    # of a conversation that seems to have gone quiet.
                    self.show("silence", {"seconds": self.heard_seconds - self.silent_since})
                    self.silent_since = self.heard_seconds

                for utterance in self.segmenter.feed(chunk):
                    self.utterances.put(utterance)

            for utterance in self.segmenter.flush():
                self.utterances.put(utterance)

        finally:
            self.utterances.put(_DONE)

    # ---- transcribing --------------------------------------------------

    def _listen(self) -> None:

        while True:

            item = self.utterances.get()

            if item is _DONE:
                return

            utterance: Utterance = item

            lag = self.heard_seconds - utterance.end

            # Falling further and further behind a live stream is worse than
            # a hole that the report declares: the words on screen would
            # stop being the words being said.
            if lag > self.max_lag and not getattr(self.source, "pre_recorded", False):
                self.skipped_seconds += utterance.end - utterance.start
                self.log.write("skipped", start=utterance.start, end=utterance.end)
                self.show("skipped", {"start": utterance.start, "end": utterance.end})
                continue

            try:
                self._transcribe(utterance)
            except Exception as exc:
                self.skipped_seconds += utterance.end - utterance.start
                self.log.write("skipped", start=utterance.start, end=utterance.end, error=str(exc))
                self.show("skipped", {"start": utterance.start, "end": utterance.end})

    def _transcribe(self, utterance: Utterance) -> None:

        for part in self.transcribe(utterance.audio, utterance.start):

            first = int((part.start - utterance.start) * 16_000)
            last = int((part.end - utterance.start) * 16_000)

            sentence_id = len(self.sentences)

            speaker = self.tracker.assign(sentence_id, utterance.audio[first:last])

            sentence = Sentence(sentence_id, part.start, part.end, speaker, part.text)

            with self.lock:
                self.sentences.append(sentence)
                snapshot = list(self.sentences)

            roles = assign_roles(merge_fragments(snapshot))

            self.log.write("sentence", **asdict(sentence))
            self.show("sentence", {"sentence": sentence, "role": roles.get(speaker)})

            self.turns.put("sentence")

        self.spoken_until = utterance.end

    # ---- judging -------------------------------------------------------

    def _judge(self) -> None:

        while True:

            item = self.turns.get()

            if item is _DONE:
                try:
                    self._review(final=True)
                finally:
                    self.claims.put(_DONE)
                return

            # A burst of sentences needs only one look at the newest state.
            while not self.turns.empty():
                following = self.turns.queue[0]

                if following is _DONE:
                    break

                self.turns.get()

            try:
                self._review(final=False)
            except Exception as exc:
                self.show("stage", {"text": f"Could not review the conversation: {exc}"})

    def _review(self, final: bool) -> None:

        with self.lock:
            snapshot = merge_fragments(self.sentences)

        roles = assign_roles(snapshot)
        exchanges, unprompted = build_exchanges(snapshot, roles)

        for exchange in exchanges:

            if self.abandon.is_set():
                return

            if exchange.closed or final:
                self._judge_exchange(exchange)

        if final and unprompted:
            self._extract(
                ",".join(str(s.id) for s in unprompted),
                "",
                " ".join(s.text for s in unprompted),
                unprompted[0].start,
                unprompted[0].speaker,
            )

    def _judge_exchange(self, exchange: Exchange) -> None:

        if exchange.key not in self.judged:

            self.judged.add(exchange.key)

            judgement = judge_answer(
                self.chat,
                exchange.question_text,
                exchange.answer_text,
                exchange.context_text,
            )

            self.log.write(
                "judged",
                key=exchange.key,
                at=exchange.questions[0].start,
                question=exchange.question_text,
                answer=exchange.answer_text,
                **asdict(judgement),
            )
            self.show(
                "judged",
                {"at": exchange.questions[0].start, "question": exchange.question_text, "judgement": judgement},
            )

        if exchange.answer:
            self._extract(
                exchange.key,
                exchange.question_text,
                exchange.answer_text,
                exchange.answer[0].start,
                exchange.answer[0].speaker,
            )

    def _extract(self, key: str, question: str, answer: str, at: float, speaker: int) -> None:

        if key in self.extracted:
            return

        self.extracted.add(key)

        found = extract_claims(self.chat, question, answer)

        if found.error:
            self.log.write("extraction_failed", key=key, at=at, error=found.error)

        for claim in found.invented:
            self.log.write("claim_discarded", at=at, claim=claim)

        # Not a gap: the statement it was cut from is kept, or was never one.
        for claim in found.fragments:
            self.log.write("claim_fragment", at=at, claim=claim)

        for item in found.claims:

            normal = _normalised_claim(item["claim"])

            if normal in self.seen_claims:
                continue

            self.seen_claims.add(normal)

            record = {**item, "at": at, "speaker": speaker}

            # Past the cap a claim is still listed, as not checked. A claim
            # takes most of a minute: without a cap a two-hour stream queues
            # a day of work.
            if self.claims_queued >= self.max_claims:
                self._record_check(
                    record,
                    {
                        "outcome": NOT_CHECKED,
                        "verdict": None,
                        "confidence": None,
                        "explanation": f"Past this session's limit of {self.max_claims} claims.",
                        "note": "limit",
                        "sources": [],
                    },
                )
                continue

            self.claims_queued += 1
            self.claims.put(record)
            self.show("claim_queued", {"claim": item["claim"], "waiting": self.claims.qsize()})

    # ---- checking ------------------------------------------------------

    def _check(self) -> None:

        while True:

            item = self.claims.get()

            if item is _DONE:
                return

            if self.abandon.is_set():
                result = {
                    "outcome": NOT_CHECKED,
                    "verdict": None,
                    "confidence": None,
                    "explanation": "The session was closed before this claim's turn.",
                    "note": "abandoned",
                    "sources": [],
                }
            else:
                result = self.verify(item["claim"])

            self._record_check(item, result)

    def _record_check(self, claim: dict, result: dict) -> None:

        self.log.write("checked", **claim, **result)
        self.show("checked", {**claim, **result, "waiting": self.claims.qsize()})

    # ---- the whole run -------------------------------------------------

    def run(self) -> None:

        self.log.write("started", at=time.time())

        threads = [
            threading.Thread(target=target, name=name, daemon=True)
            for name, target in [
                ("hear", self._hear),
                ("listen", self._listen),
                ("judge", self._judge),
                ("check", self._check),
            ]
        ]

        for thread in threads:
            thread.start()

        self.threads = threads

        try:
            self._wait(threads[0])
            self.show("stage", {"text": "No more sound. Finishing the words."})
            self._wait(threads[1])
            # Before the last look at the exchanges, so that it judges them
            # as the report will read them.
            self._settle()
            self.turns.put(_DONE)
            self.show("stage", {"text": "Finishing the judgements and fact-checks."})
            self._wait(threads[2])
            self._wait(threads[3])
        except KeyboardInterrupt:
            self.abandon.set()
            self.source.stop()
            self.show("stage", {"text": "Closing now: what was not checked is reported so."})
            self._settle()
            self.turns.put(_DONE)
            for thread in threads:
                thread.join(timeout=5)

        self.log.write(
            "finished",
            at=time.time(),
            heard_seconds=self.heard_seconds,
            skipped_seconds=self.skipped_seconds,
        )

    @staticmethod
    def _wait(thread: threading.Thread) -> None:

        # A timed join: a plain one blocks Ctrl-C until the thread ends.
        while thread.is_alive():
            thread.join(timeout=0.5)

    def _settle(self) -> None:
        """Speakers as heard across the whole conversation, for the report."""

        changed = self.tracker.settle()

        self.log.write(
            "speakers_settled",
            speakers={str(key): value for key, value in changed.items()},
        )

        with self.lock:
            for sentence in self.sentences:
                sentence.speaker = changed.get(sentence.id, sentence.speaker)


def stop_on_interrupt(session: Session) -> None:
    """The first Ctrl-C stops listening; the checks already queued still run."""

    import signal

    previous = signal.getsignal(signal.SIGINT)

    def handler(signum, frame):

        session.source.stop()
        session.show("stage", {"text": "Stopped listening. Ctrl-C again to skip the remaining checks."})
        signal.signal(signal.SIGINT, previous)

    signal.signal(signal.SIGINT, handler)

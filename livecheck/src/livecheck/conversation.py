"""
Who asks, who answers, and which words answer which question.

No models here: this works on sentences that already have a speaker, so
every rule can be tested with text. It is rerun over the whole conversation
as it grows, because a role can change once more of it has been heard.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Sentence:
    id: int
    start: float
    end: float
    speaker: int
    text: str


@dataclass
class Exchange:
    questions: list[Sentence] = field(default_factory=list)
    answer: list[Sentence] = field(default_factory=list)
    context: list[Sentence] = field(default_factory=list)
    closed: bool = False

    @property
    def key(self) -> str:
        """What this exchange is: judged again only if its words change."""

        ids = [s.id for s in self.questions] + ["a"] + [s.id for s in self.answer]

        return ",".join(str(i) for i in ids)

    @property
    def question_text(self) -> str:
        return " ".join(s.text for s in self.questions)

    @property
    def answer_text(self) -> str:
        return " ".join(s.text for s in self.answer)

    @property
    def context_text(self) -> str:
        return " ".join(s.text for s in self.context)


# "..., right?" asks nothing that needs an answer. The comma or the opening
# mark is what makes it a tag: "Did you vote no?" and "Is that right?" ask.
_TAG = re.compile(
    r"(?:,\s*¿?|\s¿)(right|you know|you see|ok|okay|isn't it|no|yeah|huh|eh|"
    r"verdad|sabes|vale|cierto|entiendes|no crees|sí)\s*\?\s*$",
    re.IGNORECASE,
)

# Whisper leaves out a question mark now and then, mostly on short
# questions. Only forms that cannot begin a statement: "How we did it was..."
# stays a statement because "how" is not followed by an auxiliary.
_FORM = re.compile(
    r"^¿?\s*(?:(?:and|so|but|or|y|pero|entonces)\s+)?("
    r"(what|why|how|when|where|who|which)\s+(is|are|was|were|do|does|did|can|could|would|should|will|has|have)\b"
    r"|(do|does|did|are|can|could|would|should|will)\s+(you|we|they|he|she)\b"
    r"|(qué|por qué|cómo|cuándo|dónde|quién|quiénes|cuál|cuáles|cuánto|cuánta|cuántos|cuántas)\b"
    r")",
    re.IGNORECASE,
)

# An interviewer's question is often not one, grammatically.
_PROMPT = re.compile(
    r"^(tell (me|us)|explain|describe|walk (me|us) through|talk (to )?(me|us) about"
    r"|cuéntame|cuéntanos|cuénteme|cuéntenos|háblame|háblanos|explícame|explícanos|explíquenos)\b",
    re.IGNORECASE,
)


def is_question(text: str) -> bool:

    text = text.strip()

    if text.endswith("?"):
        return not _TAG.search(text)

    if _PROMPT.match(text):
        return True

    # The form counts only where Whisper left the end open. Where it closed
    # the sentence with a stop it heard a statement: "What was striking to me
    # about Jobs is how influential..." was on a real recording.
    #
    # A small letter is the exception. It means Whisper heard this as the rest
    # of a sentence, and a real continuation of the same voice was already
    # joined to its start by merge_fragments: "who was the first person to walk
    # on the moon." was a question, heard alone.
    if not _FORM.match(text):
        return False

    return text[0].islower() or not re.search(r"[.!…]$", text)


def merge_fragments(sentences: list[Sentence]) -> list[Sentence]:
    """
    One sentence said across a pause arrives as two, because sound is cut at
    pauses and Whisper hears each piece alone and closes it: "He sees Stuart
    as" / "an actor." Judged apart, neither says anything. A piece joins the
    one before when it is the same voice, soon after, and either starts in
    lower case or follows something left open.
    """

    merged: list[Sentence] = []

    for sentence in sentences:

        last = merged[-1] if merged else None

        if last and _continues(last, sentence):
            merged[-1] = Sentence(
                last.id, last.start, sentence.end, last.speaker,
                f"{last.text} {sentence.text}",
            )
        else:
            merged.append(sentence)

    return merged


def _continues(before: Sentence, after: Sentence) -> bool:

    if before.speaker != after.speaker or after.start - before.end > 1.5:
        return False

    if before.text.rstrip().endswith(("?", "!")):
        return False

    open_ended = not re.search(r"[.…]$", before.text.rstrip()) or before.text.rstrip().endswith(("...", "…"))

    return open_ended or after.text.lstrip()[:1].islower()


def assign_roles(sentences: list[Sentence]) -> dict[int, str]:
    """
    {speaker: "asks" | "answers"}.

    Nobody is introduced, so a role is read from what each voice does. The
    one who asks most asks; so does anyone else whose talk is mostly
    questions, as in a panel with two hosts, or a moderator heard only once,
    passing the microphone. A guest's rhetorical question
    does not make them an interviewer, because it is a small share of what
    they say. Alone in the room, nobody asks.
    """

    said: dict[int, int] = {}
    asked: dict[int, int] = {}

    for sentence in sentences:

        said[sentence.speaker] = said.get(sentence.speaker, 0) + 1

        if is_question(sentence.text):
            asked[sentence.speaker] = asked.get(sentence.speaker, 0) + 1

    if not said:
        return {}

    if len(said) == 1 or not asked:
        return {speaker: "answers" for speaker in said}

    top = max(asked, key=lambda speaker: (asked[speaker], asked[speaker] / said[speaker]))

    askers = {top} | {
        speaker
        for speaker, count in asked.items()
        if (count >= 2 and count / said[speaker] >= 0.25)
        or count / said[speaker] >= 0.5
    }

    # Two people questioning each other leave nobody answering: the one who
    # asks most keeps the role, so the other's answers are still judged.
    if len(askers) == len(said):
        askers = {top}

    return {speaker: "asks" if speaker in askers else "answers" for speaker in said}


def build_exchanges(
    sentences: list[Sentence], roles: dict[int, str]
) -> tuple[list[Exchange], list[Sentence]]:
    """
    The questions with what was said in reply, and the rest of what the
    answerers said, which came before any question.

    Questions in a row with no reply between them are one question asked
    in several sentences. An exchange is closed once a later question has
    begun: until then the answer may still be going on.
    """

    exchanges: list[Exchange] = []
    unprompted: list[Sentence] = []
    current: Exchange | None = None
    preamble: list[Sentence] = []

    for sentence in sentences:

        if roles.get(sentence.speaker) != "asks":

            if current is None:
                unprompted.append(sentence)
            else:
                current.answer.append(sentence)

            preamble = []
            continue

        if not is_question(sentence.text):
            preamble.append(sentence)
            continue

        if current is not None and not current.answer:
            current.questions.append(sentence)
            current.context.extend(preamble)
        else:
            if current is not None:
                current.closed = True

            current = Exchange(questions=[sentence], context=list(preamble))
            exchanges.append(current)

        preamble = []

    return exchanges, unprompted

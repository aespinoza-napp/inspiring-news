"""
The report, from events.jsonl and nothing else.
"""

import json
from dataclasses import asdict
from pathlib import Path

from livecheck.conversation import Sentence, assign_roles, build_exchanges, merge_fragments
from livecheck.judge import ANSWERED, NO_REPLY, NOT_ANSWERED, NOT_JUDGED, PARTIAL
from livecheck.verifier import FALSE, MIXED, NOT_CHECKED, TRUE, UNVERIFIED


def _clock(seconds: float) -> str:

    seconds = int(seconds)

    hours, minutes, rest = seconds // 3600, seconds % 3600 // 60, seconds % 60

    return f"{hours}:{minutes:02}:{rest:02}" if hours else f"{minutes:02}:{rest:02}"


def load_events(directory: Path) -> list[dict]:

    events = []

    with (directory / "events.jsonl").open(encoding="utf-8") as file:

        for line in file:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # The last line of a session killed mid-write.
                continue

    return events


def build(events: list[dict]) -> dict:

    sentences = [
        Sentence(e["id"], e["start"], e["end"], e["speaker"], e["text"])
        for e in events
        if e["type"] == "sentence"
    ]

    for event in events:
        if event["type"] == "speakers_settled":
            for sentence in sentences:
                sentence.speaker = event["speakers"].get(str(sentence.id), sentence.speaker)

    # Exactly what the session judged, or no judgement would match.
    sentences = merge_fragments(sentences)

    roles = assign_roles(sentences)
    exchanges, _ = build_exchanges(sentences, roles)

    # The newest judgement of each exchange as it finally stands. One whose
    # words changed when the speakers were settled has an older key, which
    # matches nothing here, and shows as not judged rather than as a verdict
    # about other words.
    judged = {e["key"]: e for e in events if e["type"] == "judged"}

    questions = []

    for exchange in exchanges:

        judgement = judged.get(exchange.key, {})

        questions.append(
            {
                "at": exchange.questions[0].start,
                "asked_by": exchange.questions[0].speaker,
                "question": exchange.question_text,
                "answer": exchange.answer_text,
                "status": judgement.get("status", NOT_JUDGED),
                "reason": judgement.get("reason", ""),
                "quote": judgement.get("quote", ""),
            }
        )

    speakers = {}

    for sentence in sentences:

        entry = speakers.setdefault(
            sentence.speaker,
            {"speaker": sentence.speaker, "role": roles.get(sentence.speaker), "words": 0, "seconds": 0.0},
        )

        entry["words"] += len(sentence.text.split())
        entry["seconds"] += sentence.end - sentence.start

    claims = [e for e in events if e["type"] == "checked"]

    def status(*wanted):
        return [q for q in questions if q["status"] in wanted]

    def outcome(wanted):
        return [c for c in claims if c["outcome"] == wanted]

    finished = next((e for e in reversed(events) if e["type"] == "finished"), {})

    return {
        "finished": bool(finished),
        "heard_seconds": finished.get("heard_seconds"),
        "skipped_seconds": sum(e["end"] - e["start"] for e in events if e["type"] == "skipped"),
        "words_total": sum(s["words"] for s in speakers.values()),
        "speakers": sorted(speakers.values(), key=lambda s: s["speaker"]),
        "questions": {
            "total": len(questions),
            "answered": status(ANSWERED),
            "partial": status(PARTIAL),
            "not_answered": status(NOT_ANSWERED),
            "no_reply": status(NO_REPLY),
            "not_judged": status(NOT_JUDGED),
        },
        "statements": {
            "total": len(claims),
            "true": outcome(TRUE),
            "false": outcome(FALSE),
            "mixed": outcome(MIXED),
            "unverified": outcome(UNVERIFIED),
            "not_checked": outcome(NOT_CHECKED),
        },
        "claims_discarded": [e["claim"] for e in events if e["type"] == "claim_discarded"],
        "claims_fragments": [e["claim"] for e in events if e["type"] == "claim_fragment"],
        "extraction_failures": sum(1 for e in events if e["type"] == "extraction_failed"),
        "transcript": [{**asdict(s), "role": roles.get(s.speaker)} for s in sentences],
    }


def _name(speaker: int, role: str | None) -> str:

    label = {"asks": "asks", "answers": "answers"}.get(role, "speaks")

    return f"Voice {speaker + 1} ({label})"


def _questions_md(items: list[dict]) -> list[str]:

    lines = []

    for item in items:

        lines.append(f"- **{_clock(item['at'])}** {item['question']}")

        if item["reason"]:
            lines.append(f"  - *Why:* {item['reason']}")

        if item["quote"]:
            lines.append(f"  - *Answering words:* \"{item['quote']}\"")
        elif item["answer"]:
            reply = item["answer"]
            lines.append(f"  - *Reply:* {reply[:300]}{'...' if len(reply) > 300 else ''}")

    return lines or ["None."]


def _claims_md(items: list[dict]) -> list[str]:

    lines = []

    for item in items:

        confidence = item.get("confidence")
        shown = f" (confidence {confidence:.2f})" if isinstance(confidence, (int, float)) else ""

        lines.append(f"- **{_clock(item['at'])}** {item['claim']}{shown}")

        if item.get("quote"):
            lines.append(f"  - *Words heard:* \"{item['quote']}\"")

        if item.get("explanation"):
            lines.append(f"  - *Why:* {item['explanation']}")

        for source in item.get("sources") or []:
            lines.append(f"  - [{source.get('title') or source.get('url')}]({source.get('url')})")

    return lines or ["None."]


def to_markdown(report: dict) -> str:

    questions = report["questions"]
    statements = report["statements"]
    not_explicit = questions["partial"] + questions["not_answered"] + questions["no_reply"]
    not_explicit.sort(key=lambda item: item["at"])

    lines = ["# Conversation report", ""]

    if not report["finished"]:
        lines += ["**This session did not finish normally: what follows is what was recorded.**", ""]

    lines += [
        "| | |",
        "|---|---|",
        f"| Words said | {report['words_total']} |",
    ]

    for speaker in report["speakers"]:
        lines.append(
            f"| {_name(speaker['speaker'], speaker['role'])} | "
            f"{speaker['words']} words, {_clock(speaker['seconds'])} of speech |"
        )

    lines += [
        f"| Questions asked | {questions['total']} |",
        f"| Questions answered | {len(questions['answered'])} |",
        f"| Questions not explicitly answered | {len(not_explicit)} "
        f"({len(questions['partial'])} in part, {len(questions['not_answered'])} avoided, "
        f"{len(questions['no_reply'])} with no reply) |",
        f"| Questions not judged | {len(questions['not_judged'])} |",
        f"| Statements checked | {statements['total'] - len(statements['not_checked'])} of {statements['total']} |",
        f"| True statements | {len(statements['true'])} |",
        f"| False statements | {len(statements['false'])} |",
        f"| Partly true or misleading | {len(statements['mixed'])} |",
        f"| No verdict from the evidence | {len(statements['unverified'])} |",
        f"| Could not be checked | {len(statements['not_checked'])} |",
        "",
        "**Read this before repeating anything below.** Every line is a machine's "
        "reading of a machine's transcript. A misheard word can turn a true statement "
        "into a false one, voices can be confused, and the fact-checker's verdicts are "
        "often wrong: a \"false\" here is a reason to read the sources and listen again "
        "at that timestamp, not a finding that the person said something untrue. "
        "Only the speaker's factual statements are checked, as worded by a model.",
        "",
    ]

    gaps = []

    if report["skipped_seconds"]:
        gaps.append(
            f"{_clock(report['skipped_seconds'])} of speech was skipped because transcription "
            "fell behind the stream, so the word count is too low."
        )

    if report["claims_discarded"]:
        gaps.append(
            f"{len(report['claims_discarded'])} statements the model wrote were dropped because "
            "they were not in the transcript."
        )

    if report["extraction_failures"]:
        gaps.append(
            f"For {report['extraction_failures']} replies the model could not be asked for "
            "statements, so they are in no count below."
        )

    if gaps:
        lines += ["**Gaps in this session:**", ""] + [f"- {gap}" for gap in gaps] + [""]

    lines += ["## False statements", ""] + _claims_md(statements["false"]) + [""]
    lines += ["## True statements", ""] + _claims_md(statements["true"]) + [""]
    lines += ["## Partly true or misleading", ""] + _claims_md(statements["mixed"]) + [""]
    lines += ["## No verdict from the evidence", ""] + _claims_md(statements["unverified"]) + [""]

    if statements["not_checked"]:
        lines += ["## Could not be checked", ""] + _claims_md(statements["not_checked"]) + [""]

    lines += ["## Questions answered", ""] + _questions_md(questions["answered"]) + [""]
    lines += ["## Questions not explicitly answered", ""] + _questions_md(not_explicit) + [""]

    if questions["not_judged"]:
        lines += ["## Questions not judged", ""] + _questions_md(questions["not_judged"]) + [""]

    lines += ["## Transcript", ""]

    previous = None

    for sentence in report["transcript"]:

        if sentence["speaker"] != previous:
            lines += ["", f"**{_name(sentence['speaker'], sentence['role'])}** {_clock(sentence['start'])}", ""]
            previous = sentence["speaker"]

        lines.append(sentence["text"])

    return "\n".join(lines) + "\n"


def write(directory: Path) -> Path:

    report = build(load_events(directory))

    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    path = directory / "report.md"
    path.write_text(to_markdown(report), encoding="utf-8")

    return path

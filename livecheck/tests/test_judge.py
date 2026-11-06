from livecheck.judge import (
    ANSWERED, NO_REPLY, NOT_ANSWERED, NOT_JUDGED, PARTIAL, extract_claims, judge_answer,
)


def replying(data):
    return lambda system, user, schema: data


def failing(system, user, schema):
    raise ConnectionError("refused")


def test_no_words_is_no_reply_and_asks_no_model():
    assert judge_answer(failing, "Why?", "  ").status == NO_REPLY


def test_a_model_that_cannot_be_asked_is_not_a_judgement():
    assert judge_answer(failing, "Why?", "Because.").status == NOT_JUDGED
    assert judge_answer(replying({"status": "maybe"}), "Why?", "Because.").status == NOT_JUDGED
    assert judge_answer(replying({"parts": []}), "Why?", "Because.").status == NOT_JUDGED


def parts(*words):
    return replying({"parts": [{"asks": f"part {i}", "words": w} for i, w in enumerate(words)]})


def test_the_status_is_counted_from_the_parts_given():
    question = "How much did it cost, and who paid?"
    answer = "It cost two million euros."

    assert judge_answer(parts("two million euros", "two million"), question, answer).status == ANSWERED
    assert judge_answer(parts("two million euros", ""), question, answer).status == PARTIAL
    assert judge_answer(parts("", ""), question, answer).status == NOT_ANSWERED


def test_a_wrong_answer_is_an_answer():
    # The 5 Nov failure: the 3B read truth into "answered".
    chat = parts("Yuri Gagarin was the first person")
    judgement = judge_answer(chat, "Who first walked on the moon?", "Yuri Gagarin was the first person to walk on the moon.")

    assert judgement.status == ANSWERED
    assert judgement.quote == "Yuri Gagarin was the first person"


def test_words_that_are_not_in_the_reply_give_nothing():
    chat = parts("It was the ministry")
    assert judge_answer(chat, "Who?", "The ministry of finance.").status == NOT_ANSWERED

    chat = parts("ministry of FINANCE")
    assert judge_answer(chat, "Who?", "The ministry of finance.").quote == "ministry of FINANCE"


def test_a_claim_the_speaker_did_not_make_is_never_kept():
    answer = "Unemployment fell to three percent in Spain during 2023 according to the ministry."

    chat = replying(
        {
            "claims": [
                {"claim": "Unemployment fell in Spain during 2023 according to the ministry.", "quote": ""},
                {"claim": "The president secretly resigned after several scandals last winter.", "quote": ""},
            ]
        }
    )

    found = extract_claims(chat, "What happened?", answer)

    assert [item["claim"] for item in found.claims] == [
        "Unemployment fell in Spain during 2023 according to the ministry."
    ]
    assert found.invented == ["The president secretly resigned after several scandals last winter."]


def test_a_figure_changed_by_the_model_makes_the_claim_invented():
    answer = "Unemployment in Spain fell to 300 thousand people during 2023."

    chat = replying({"claims": [{"claim": "Unemployment in Spain fell to 3000 thousand people during 2023.", "quote": ""}]})

    assert extract_claims(chat, "", answer).invented


def test_extraction_failure_is_reported_not_swallowed():
    assert extract_claims(failing, "Q?", "A long enough answer about budgets").error


def claims(*texts):
    return replying({"claims": [{"claim": t, "quote": ""} for t in texts]})


def test_a_phrase_is_not_a_claim():
    # What the 3B returned on 5 Nov for "Water boils at 100 degrees Celsius at sea level."
    answer = "Water boils at 100 degrees Celsius at sea level."

    found = extract_claims(claims("100 degrees Celsius", "sea level"), "What is the boiling point?", answer)

    assert found.claims == []
    assert found.fragments == ["100 degrees Celsius", "sea level"]


def test_a_piece_of_a_longer_claim_is_dropped_and_the_whole_kept():
    answer = "Yuri Gagarin was the first person to walk on the moon in 1975."

    found = extract_claims(
        claims(
            "Yuri Gagarin was the first person to walk on the moon in 1975.",
            "The first person to walk on the moon was in 1975",
        ),
        "Who was the first person to walk on the moon?",
        answer,
    )

    assert [item["claim"] for item in found.claims] == ["Yuri Gagarin was the first person to walk on the moon in 1975."]
    assert found.fragments == ["The first person to walk on the moon was in 1975"]


def test_two_statements_in_one_reply_are_both_kept():
    answer = "Unemployment fell to three percent in 2023, and exports rose by a fifth in 2023."

    found = extract_claims(
        claims("Unemployment fell to three percent in 2023.", "Exports rose by a fifth in 2023."),
        "How is the economy?",
        answer,
    )

    assert len(found.claims) == 2

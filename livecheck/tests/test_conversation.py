from livecheck.conversation import Sentence, assign_roles, build_exchanges, is_question, merge_fragments


def said(*lines):
    return [
        Sentence(index, float(index), index + 1.0, speaker, text)
        for index, (speaker, text) in enumerate(lines)
    ]


def test_questions_with_a_mark_or_a_form_that_can_only_ask():
    assert is_question("What did the minister sign?")
    assert is_question("¿Cuántas personas murieron?")
    assert is_question("Why did you do that")
    assert is_question("Tell me about the budget.")
    assert is_question("Cuéntame qué pasó.")
    assert is_question("Did you vote no?")
    assert is_question("Is that right?")
    # Heard alone, with no mark, on a recording.
    assert is_question("who was the first person to walk on the moon.")
    assert is_question("and which is the longest river in Africa.")


def test_statements_and_tags_are_not_questions():
    assert not is_question("How we did it was simple.")
    assert not is_question("What we did worked.")
    assert not is_question("We signed it in May, right?")
    assert not is_question("Lo firmamos en mayo, ¿verdad?")
    assert not is_question("Prices fell by three percent.")
    # From a real recording.
    assert not is_question("What was striking to me about interviewing Jobs is how influential...")


def test_who_asks_most_asks_and_a_rhetorical_question_does_not_make_a_host():
    sentences = said(
        (0, "What happened in May?"),
        (1, "We signed it. And why did we sign? Because it was due. It took weeks."),
        (0, "Who paid for it?"),
        (1, "The ministry paid. It cost a lot. Everyone agreed. Nobody objected."),
    )

    assert assign_roles(sentences) == {0: "asks", 1: "answers"}


def test_two_hosts_and_a_guest():
    sentences = said(
        (0, "What happened?"), (2, "A fire."), (2, "It spread fast."),
        (1, "Who called it in?"), (2, "A neighbour."), (2, "At noon."),
        (0, "Was anyone hurt?"), (2, "No."), (2, "Luckily."), (2, "Nobody at all."),
        (1, "When did it end?"), (2, "By night."),
    )

    assert assign_roles(sentences) == {0: "asks", 1: "asks", 2: "answers"}


def test_a_moderator_heard_once_asks():
    # From a real recording: three voices, the moderator with a single line.
    sentences = said(
        (2, "Are there any stories you want to talk about?"),
        (3, "You mentioned the bookshop."), (3, "It is gone now."),
        (3, "Is that surprising?"), (3, "Why was it forgotten?"),
        (1, "I think so."), (1, "People moved on."), (1, "It happens."),
    )

    assert assign_roles(sentences) == {2: "asks", 3: "asks", 1: "answers"}


def test_two_people_questioning_each_other_still_leave_someone_answering():
    sentences = said(
        (0, "Why did you vote no?"), (1, "Why did you vote yes?"),
        (0, "Who told you that?"), (1, "Who told you?"), (0, "Did you read it?"),
    )

    assert assign_roles(sentences) == {0: "asks", 1: "answers"}


def test_alone_nobody_asks():
    assert assign_roles(said((0, "Why does it matter?"), (0, "Because it does."))) == {0: "answers"}


def test_exchanges_join_questions_in_a_row_and_close_on_the_next_one():
    sentences = said(
        (0, "You said costs fell."),
        (0, "By how much did they fall?"),
        (0, "And who gained?"),
        (1, "By ten percent."),
        (1, "Farmers gained."),
        (0, "Interesting."),
        (0, "What comes next?"),
        (1, "An election."),
    )

    exchanges, unprompted = build_exchanges(sentences, {0: "asks", 1: "answers"})

    assert unprompted == []
    assert len(exchanges) == 2
    assert exchanges[0].context_text == "You said costs fell."
    assert exchanges[0].question_text == "By how much did they fall? And who gained?"
    assert exchanges[0].answer_text == "By ten percent. Farmers gained."
    assert exchanges[0].closed
    assert exchanges[1].answer_text == "An election."
    assert not exchanges[1].closed


def test_what_answerers_say_before_any_question_is_kept_apart():
    sentences = said((1, "Thanks for having me."), (0, "What happened?"), (1, "A fire."))

    exchanges, unprompted = build_exchanges(sentences, {0: "asks", 1: "answers"})

    assert [s.text for s in unprompted] == ["Thanks for having me."]
    assert len(exchanges) == 1


def test_a_sentence_said_across_a_pause_is_one_sentence():
    # From a real recording.
    sentences = said(
        (1, "I've thought about that and the problem..."),
        (1, "for me is that the territory has been well-trod."),
        (1, "He sees Stuart as"),
        (1, "an actor."),
        (1, "That is my view."),
    )

    assert [s.text for s in merge_fragments(sentences)] == [
        "I've thought about that and the problem... for me is that the territory has been well-trod.",
        "He sees Stuart as an actor.",
        "That is my view.",
    ]


def test_pieces_stay_apart_across_voices_and_after_a_question():
    assert len(merge_fragments(said((0, "We went to"), (1, "the shop.")))) == 2
    assert len(merge_fragments(said((0, "Why?"), (0, "because of it.")))) == 2


def test_merging_keeps_the_first_id_and_true_times():
    merged = merge_fragments(said((0, "We went to"), (0, "the shop.")))

    assert (merged[0].id, merged[0].start, merged[0].end) == (0, 0.0, 2.0)

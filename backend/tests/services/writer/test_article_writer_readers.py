"""
The positive edition's readers and parts (2026-11-10): articles of
800-1,200 words for readers aged 15 to 30, in five parts, extended from
the sources and never past them. Each edition's style is also a skill -
/write-constructive-article and /write-devastating-article
(.claude/skills/) - and this file keeps each skill and its edition's
prompt from drifting apart.
"""

from pathlib import Path

from src.services.writer.article_writer import (
    ARTICLE_PARTS,
    DEVASTATING_NEWSROOM,
    ARTICLE_WORDS,
    CLOSED_WORLD_RULES,
    DEFAULT_INSTRUCTIONS,
    newsroom,
    system_prompt,
    user_prompt,
)
from src.services.writer.analysed_article import AnalysedArticle
from src.services.writer.rewriter import rewrite_system_prompt

SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "skills"

CONSTRUCTIVE_SKILL = SKILLS / "write-constructive-article" / "SKILL.md"

DEVASTATING_SKILL = SKILLS / "write-devastating-article" / "SKILL.md"

# The opening words of the Devastating voice's rules A-E, as the writer is
# given them (DEVASTATING_NEWSROOM) and as its skill states them.
DEVASTATING_RULES = (
    "A. The irony aims up and inwards",
    "B. The irony lives in your asides, never in the facts.",
    "C. Do not invent a controversy.",
    "D. Suicide and self-harm",
    "E. Not the hopeful register.",
)

ARTICLE = AnalysedArticle(
    id="a1",
    url="https://example.org/news/trees",
    headline="Volunteers plant trees",
    lead="Volunteers planted trees.",
    language="en",
    topic=None,
    published_at=None,
    source_name="Example",
    domain="example.org",
    body="Volunteers planted trees.",
)


def test_the_positive_writer_is_told_the_readers_parts_and_length():

    prompt = system_prompt("positive")

    assert "15 to 30 years old" in prompt
    assert ARTICLE_WORDS in prompt

    for name, _ in ARTICLE_PARTS:
        assert f"{name}:" in prompt


def test_extending_never_loosens_the_closed_world():
    # The part on whom the news reaches is where a model guesses: the
    # prompt says what to do when the sources are silent, and every rule
    # of the closed world is still there, after the readers.

    prompt = system_prompt("positive")

    assert CLOSED_WORLD_RULES in prompt
    assert "an effect no source states is invented" in prompt
    assert prompt.index("15 to 30") < prompt.index(CLOSED_WORLD_RULES)


def test_the_devastating_edition_keeps_its_own_voice_and_default():

    assert "15 to 30" not in system_prompt("devastating")

    prompt = user_prompt(ARTICLE, [], [], "en", "", [], edition="devastating")

    assert "400 to 700 words" in prompt
    assert DEFAULT_INSTRUCTIONS not in prompt


def test_with_no_instructions_the_positive_default_is_the_full_article():

    prompt = user_prompt(ARTICLE, [], [], "es", "", [])

    assert DEFAULT_INSTRUCTIONS in prompt
    assert "400 to 700" not in prompt


def test_the_editors_instructions_still_win():

    prompt = user_prompt(ARTICLE, [], [], "en", "300 words, for teachers", [])

    assert "300 words, for teachers" in prompt
    assert DEFAULT_INSTRUCTIONS not in prompt


def test_a_rewrite_is_held_to_the_same_readers():

    assert newsroom("positive") in rewrite_system_prompt("positive")


def test_the_constructive_skill_names_the_same_parts_in_the_same_order():

    text = CONSTRUCTIVE_SKILL.read_text(encoding="utf-8")

    positions = [text.find(f"**{name}**") for name, _ in ARTICLE_PARTS]

    assert -1 not in positions, "every part of ARTICLE_PARTS is named in the skill, in bold"
    assert positions == sorted(positions)
    assert ARTICLE_WORDS in text
    assert "15 to 30" in text


def test_the_devastating_skill_states_the_writers_rules_a_to_e():

    text = DEVASTATING_SKILL.read_text(encoding="utf-8")

    for rule in DEVASTATING_RULES:
        assert rule in DEVASTATING_NEWSROOM
        assert rule in text, f"the Devastating skill states rule {rule[0]} as the writer is told it"


def test_each_skill_is_for_its_own_edition_and_names_the_other():

    constructive = CONSTRUCTIVE_SKILL.read_text(encoding="utf-8")
    devastating = DEVASTATING_SKILL.read_text(encoding="utf-8")

    assert "name: write-constructive-article" in constructive
    assert "name: write-devastating-article" in devastating

    assert "/write-devastating-article" in constructive
    assert "/write-constructive-article" in devastating

    # The constructive readers and parts are not the Devastating voice's.
    assert "15 to 30" not in devastating
    assert not any(f"**{name}**" in devastating for name, _ in ARTICLE_PARTS)

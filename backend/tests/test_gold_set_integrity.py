"""
The custom validation set is the ground truth every figure of the thesis is
measured against, and nothing checked it: eight AI-labelled facts lost their
marker and were counted as human (audit 2026-10-16). These read the committed
files, so a save that breaks one fails here, in seconds, not in the results.

Not checked on purpose: whether `custom_en_es.jsonl` has the current labels.
It is derived, `labeller/app.py join` rewrites it, and a test would fail on
every save during a review (audit 2026-10-28, N8). Its ids are held to the
set, which only changes when a fact is added.
"""

import json
from pathlib import Path

import pytest

EVALUATION = Path(__file__).resolve().parents[1] / "data" / "evaluation"
MANUAL = EVALUATION / "manual"

LABELS = {"TRUE", "PARTIALLY_TRUE", "FALSE", "MISLEADING", "UNVERIFIED"}
AI_MARKER = "[AI label:"


def _load() -> dict[str, dict]:
    return {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in sorted(MANUAL.glob("*.json"))}


FACTS = _load()


@pytest.fixture(scope="module")
def split() -> dict:
    return json.loads((EVALUATION / "split.json").read_text(encoding="utf-8"))


def bad(check) -> list[str]:
    return [fact_id for fact_id, fact in FACTS.items() if not check(fact_id, fact)]


def test_there_is_a_set_to_check():

    assert len(FACTS) >= 100


def test_a_fact_says_its_own_id():

    assert bad(lambda fact_id, fact: fact.get("id") == fact_id) == []


def test_every_fact_has_a_claim_a_label_and_a_language():

    assert bad(lambda _, fact: (fact.get("claim") or "").strip()) == []
    assert bad(lambda _, fact: fact.get("label") in LABELS) == []
    assert bad(lambda _, fact: fact.get("language") in {"en", "es"}) == []


def test_no_two_facts_are_the_same_claim():

    seen: dict[str, str] = {}
    repeated = []

    for fact_id, fact in FACTS.items():
        claim = " ".join(fact["claim"].lower().split())
        if claim in seen:
            repeated.append((seen[claim], fact_id))
        seen[claim] = fact_id

    assert repeated == []


def test_reference_links_are_links():

    def links_ok(_, fact):
        links = fact.get("referenceEvidenceLinks") or []
        return isinstance(links, list) and all(str(link).startswith(("http://", "https://")) for link in links)

    assert bad(links_ok) == []


def test_a_fact_is_on_the_side_the_frozen_split_says(split):

    sides = split["facts"]

    assert set(sides) == set(FACTS), "split.json and manual/ hold different facts"
    assert bad(lambda fact_id, fact: fact.get("split") == sides[fact_id]) == []


def test_the_recheck_comes_from_the_test_half(split):

    sides = split["facts"]

    assert [fact_id for fact_id in split["recheck"] if sides.get(fact_id) != "test"] == []


def test_an_altered_fact_stays_beside_the_one_it_was_made_from(split):
    """Or the test half would hold the true version of a claim the train half tuned on."""

    sides = split["facts"]

    def beside(fact_id, fact):
        source = fact.get("mutatedFrom")
        return not source or (source in FACTS and sides[source] == sides[fact_id])

    assert bad(beside) == []


def test_an_altered_fact_is_false_and_says_what_was_changed():

    def holds(_, fact):
        return not fact.get("mutatedFrom") or (fact.get("label") == "FALSE" and fact.get("mutation"))

    assert bad(holds) == []


def test_an_altered_fact_differs_from_its_source():

    def differs(_, fact):
        source = fact.get("mutatedFrom")
        return not source or fact["claim"].strip() != FACTS[source]["claim"].strip()

    assert bad(differs) == []


def test_a_fact_the_ai_made_says_so():
    """
    Altered facts are made by the AI pass, so each must carry the marker
    until a person has checked it - what the evaluation page counts as
    human depends on it.
    """

    def marked(_, fact):
        note = fact.get("annotatorNote") or ""
        return not fact.get("mutatedFrom") or AI_MARKER in note or fact.get("review")

    assert bad(marked) == []


def test_the_joined_file_holds_the_same_facts():

    joined = EVALUATION / "custom_en_es.jsonl"

    ids = {json.loads(line)["id"] for line in joined.read_text(encoding="utf-8").splitlines() if line.strip()}

    assert ids == set(FACTS), "run: python labeller/app.py join"

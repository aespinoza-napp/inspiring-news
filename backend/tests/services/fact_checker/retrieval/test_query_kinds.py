"""
The retrieval ablation's switch (roadmap, Thesis priorities P1.1): which
of the first search's three questions are sent, per run, through
`PipelineThresholds.query_kinds`.
"""

import pytest
from pydantic import ValidationError

from src.config.thresholds import SEARCH_QUERY_KINDS, PipelineThresholds, ThresholdOverrides
from src.services.fact_checker.retrieval.query_builder import PlannedQuery, QueryKind, plan_queries
from src.services.fact_checker.retrieval.search_provider import SearchProvider

from tests.factories import create_claim
from tests.services.fact_checker.fakes import FakeSearchProvider, FakeSearxngClient


def _claim():

    return create_claim(text="NASA discovered water on Mars in 2025.", entities={"ORG": ["NASA"]})


def test_the_config_names_the_kinds_the_planner_plans():
    """Named twice so config imports no service; held equal here."""

    first_pass = [kind.value for kind in QueryKind if kind != QueryKind.FOLLOW_UP]

    assert tuple(first_pass) == SEARCH_QUERY_KINDS
    assert [query.kind.value for query in plan_queries(_claim(), None, "en")] == first_pass


def test_every_kind_is_asked_by_default():

    assert PipelineThresholds().query_kinds == SEARCH_QUERY_KINDS
    assert plan_queries(_claim(), None, "en") == plan_queries(_claim(), None, "en", SEARCH_QUERY_KINDS)


@pytest.mark.parametrize("kinds", [("anchor",), ("anchor", "proposition"), ("proposition", "refutation")])
def test_only_the_kinds_asked_for_are_planned(kinds):

    plan = plan_queries(_claim(), None, "en", kinds)

    assert tuple(query.kind.value for query in plan) == kinds


def test_with_the_anchor_off_an_identical_proposition_is_still_sent(monkeypatch):
    """Filtered before duplicates are dropped, or switching one kind off could empty the plan."""

    from src.services.fact_checker.retrieval import query_builder

    monkeypatch.setattr(query_builder, "build_proposition_query", lambda claim, context, language: "same words")
    monkeypatch.setattr(query_builder, "build_query", lambda claim, context, language: "same words")

    assert [query.kind for query in plan_queries(_claim(), None, "en")] == [QueryKind.ANCHOR, QueryKind.REFUTATION]

    assert [query.kind for query in plan_queries(_claim(), None, "en", ("proposition",))] == [QueryKind.PROPOSITION]


def test_kinds_are_normalised_to_planning_order_and_a_typo_fails():

    assert PipelineThresholds(query_kinds=("refutation", "anchor")).query_kinds == ("anchor", "refutation")

    with pytest.raises(ValidationError, match="unknown query kind"):
        PipelineThresholds(query_kinds=("anchr",))

    with pytest.raises(ValidationError, match="at least one query kind"):
        PipelineThresholds(query_kinds=())

    # Follow-up queries are a second look's, never the first pass's.
    with pytest.raises(ValidationError, match="unknown query kind"):
        PipelineThresholds(query_kinds=("follow_up",))


def test_a_request_or_a_thresholds_file_sets_them_as_a_list():

    overrides = ThresholdOverrides.model_validate({"query_kinds": ["proposition", "anchor"]})

    resolved = PipelineThresholds.resolve(overrides)

    assert resolved.query_kinds == ("anchor", "proposition")
    assert resolved.overridden_from_defaults() == {"query_kinds": ("anchor", "proposition")}

    assert PipelineThresholds.resolve(ThresholdOverrides()).query_kinds == SEARCH_QUERY_KINDS

    with pytest.raises(ValidationError):
        ThresholdOverrides.model_validate({"query_kinds": ["nope"]})


def test_the_search_sends_only_the_runs_kinds():

    client = FakeSearxngClient(results=[])

    SearchProvider(client=client).search(
        _claim(), PipelineThresholds(query_kinds=("anchor",)), language="en",
    )

    assert len(client.queries) == 1

    client = FakeSearxngClient(results=[])

    SearchProvider(client=client).search(_claim(), language="en")

    assert len(client.queries) == 3


def test_the_retriever_announces_the_plan_it_will_send():
    """The live view's `searching_web` must list what the search sends, not all three."""

    from tests.services.fact_checker.retrieval.test_evidence_retriever import _retriever

    retriever, _, _ = _retriever([])

    asked = []

    class Recording(FakeSearchProvider):
        def plan(self, claim, context=None, language=None, kinds=None):
            asked.append(kinds)
            return [PlannedQuery(f"{kind} query", QueryKind(kind)) for kind in kinds or SEARCH_QUERY_KINDS]

    retriever.search_provider = Recording()

    events = []

    retriever.retrieve(
        _claim(),
        PipelineThresholds(query_kinds=("proposition",)),
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    assert asked == [("proposition",)]
    assert dict(events)["searching_web"]["queryKinds"] == ["proposition"]

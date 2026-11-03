"""What counts as one voice when sources are counted (fact_checker/outlets.py)."""

import pytest

from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, EvidenceStance
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.outlets import outlet_of, same_outlet
from src.services.fact_checker.verification.per_source import SourceAnswer, verdict_from


@pytest.mark.parametrize("left, right", [
    ("en.wikipedia.org", "es.wikipedia.org"),
    ("bbc.com", "bbc.co.uk"),
    ("edition.cnn.com", "cnn.com"),
    ("the-independent.com", "www.independent.co.uk"),
    ("web5.jamaica-gleaner.com", "jamaica-gleaner.com"),
    ("https://www.theguardian.com/world/a", "theguardian.com"),
])
def test_the_same_newsroom(left, right):

    assert same_outlet(left, right)


@pytest.mark.parametrize("left, right", [
    ("abc.es", "abc.net.au"),
    ("bbc.com", "cnn.com"),
    ("news.co.uk", "times.co.uk"),
])
def test_different_newsrooms(left, right):

    assert not same_outlet(left, right)


def test_nothing_is_no_outlet():

    assert outlet_of(None) == "" and not same_outlet(None, None)


def test_two_language_editions_of_one_site_do_not_outvote_a_third():
    """Two Wikipedias "supporting" against one source contradicting is one against one."""

    def source(domain):
        return Evidence(url=f"https://{domain}/a", title="t", domain=domain, origin=EvidenceOrigin.WEB)

    evidence = [source("en.wikipedia.org"), source("es.wikipedia.org"), source("example.org")]

    answers = [
        SourceAnswer(index=0, stance=EvidenceStance.SUPPORTS),
        SourceAnswer(index=1, stance=EvidenceStance.SUPPORTS),
        SourceAnswer(index=2, stance=EvidenceStance.CONTRADICTS),
    ]

    assert verdict_from(answers, evidence)[0] == Verdict.UNVERIFIED

"""
The whole of `AnalysisService.analyze`, from a URL to the response, with
only the network faked.

tests/test_real_pipeline_integration.py starts from a hand-built `News`
and stops at claim selection, so extraction, retrieval, ranking, the LLM
step and confidence scoring had never run *together* in a test - every
other test fakes the stage on at least one side of the boundary it is
about. This one wires the real classes exactly as the container does and
fakes only what sits on the far side of a socket:

| Stage | What runs |
|---|---|
| Extraction | the real `ExtractorService` cascade (trafilatura, then BeautifulSoup) over a saved HTML page, served by `FakeFetcher` |
| Enrichment | real, over `inference/` (`require_inference`: skips without it) |
| Admission | real, on the `repository` fixture's temporary Qdrant |
| Claim selection | real |
| Retrieval | the real `EvidenceRetriever` and `SearchProvider`; `FakeSearxngClient` answers, `FakeFetcher` serves the evidence pages to the real `EvidenceScraper` |
| Ranking | the real `EvidenceRanker`, pertinence gate included, on real embeddings |
| Verification | the real `LLMVerifier` over `FakeLLMClient`'s canned JSON verdict |
| Scoring | the real `ConfidenceScorer` |
| Storage | the lake and the `AnalysisCache` in `tmp_path`; the graph off |

The search is routed by a figure: a query quoting "87%" gets two pages
that report it, every other query gets nothing. The claims come out of
real extraction, so which ones they are is not hard-coded - but in one
run, at least one claim has evidence and goes to the LLM, and at least
one has none and must not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.pipeline_stage import PipelineStage
from src.models.storage.lineage import DataLayer
from src.repositories.datalake_repository import DataLakeRepository
from src.repositories.lake_backend import JsonFileLakeBackend
from src.services.admission.admission_filter import AdmissionFilter
from src.services.analysis_cache import AnalysisCache
from src.services.analysis_service import AnalysisService
from src.services.fact_checker.claim_selector import ClaimSelector
from src.services.fact_checker.fact_checker import FactChecker
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever
from src.services.fact_checker.retrieval.scraper import EvidenceScraper
from src.services.fact_checker.retrieval.search_provider import SearchProvider
from src.services.fact_checker.verification.confidence_scorer import ConfidenceScorer
from src.services.fact_checker.verification.llm_verification import LLMVerifier
from src.services.scraper.extractor import ExtractorService
from src.services.scraper.request_stats import RequestStats
from src.services.scraper.strategies.beautifulsoup import BeautifulSoupStrategy
from src.services.scraper.strategies.trafilatura import TrafilaturaStrategy
from src.workflows.enrichment import NewsEnrichmentPipeline

from src.database.qdrant import QdrantDatabase
from src.repositories.vector_repository import VectorRepository

from tests.conftest import pin_settings, skip_unless_inference
from tests.services.fact_checker.fakes import FakeFetcher, FakeLLMClient, FakeSearxngClient
from tests.test_invariants import ANALYZE_RESPONSE_SHAPE

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "seagrass_article.html"

ARTICLE_URL = "https://www.coastal-herald.example/environment/sado-seagrass-meadow"

# The figure the search is routed by. The anchor query quotes a claim's
# figures verbatim, so only the claim carrying it is asked about it.
ROUTED_FIGURE = "87%"

# Both evidence pages carry this sentence word for word, so the canned
# answer's quote must survive LLMVerifier's verbatim check whichever of
# the two ranks first.
QUOTED = "87% of the transplanted shoots survived their first winter"

EVIDENCE_PAGES = {
    "https://www.marine-science-daily.example/2025/sado-seagrass-survival": (
        "Seagrass transplants in the Sado estuary survive their first winter",
        """
        <p>Marine biologist Dr. Ana Ferreira of the Portuguese Institute for
        Ocean Restoration reported this week that 87% of the transplanted
        shoots survived their first winter in the Sado estuary.</p>
        <p>The shoots of Zostera marina were replanted by volunteer divers on
        4,200 square metres of seabed since 2021. Survival rates in earlier
        seagrass restoration projects in Europe were considerably lower, and
        Ferreira said the result shows that volunteer-led replanting of
        seagrass meadows can work at scale.</p>
        <p>The institute will publish the full monitoring data later this
        year, and plans to extend the project to three more towns.</p>
        """,
    ),
    "https://ocean-restoration-review.example/news/zostera-sado-results": (
        "Volunteer seagrass replanting in Portugal reports high survival",
        """
        <p>The Portuguese Institute for Ocean Restoration says 87% of the
        transplanted shoots survived their first winter after volunteers
        replanted a lost seagrass meadow in the Sado estuary.</p>
        <p>According to the project's marine biologist, Dr. Ana Ferreira,
        the survival of the Zostera marina shoots is well above what earlier
        European restoration attempts achieved. The meadow had all but
        vanished before volunteer divers began replanting it in 2021.</p>
        <p>Fishermen in the estuary have reported more young cuttlefish
        since the seagrass began to recover.</p>
        """,
    ),
}

# The canned verdict: what a model that did its job would answer for the
# routed claim. Indices are into the *ranked* list, as the real model's are.
CANNED_ANSWER = {
    "verdict": "TRUE",
    "confidence": 0.9,
    "explanation": "Two independent sources report the 87% first-winter survival rate.",
    "cited_evidence": [0, 1],
    "assessments": [
        {"index": 0, "stance": "supports", "quote": QUOTED},
        {"index": 1, "stance": "supports", "quote": QUOTED},
    ],
}

# Every stage of one claim, in order, by the literals the frontend's
# PhaseStepper and liveTrace match on.
STAGES_WITH_EVIDENCE = [
    "retrieving_evidence",
    "searching_web",
    "web_results",
    "scraping_sources",
    "sources_scraped",
    "evidence_retrieved",
    "evidence_ranked",
    "verifying_claim",
    "claim_checked",
]

# No candidates at all: nothing to scrape, and - the point - no LLM call.
STAGES_WITHOUT_EVIDENCE = [
    "retrieving_evidence",
    "searching_web",
    "web_results",
    "evidence_retrieved",
    "evidence_ranked",
    "claim_checked",
]

# The article's own stages, in order, around the per-claim ones.
ARTICLE_STAGES = [
    "scraping",
    "scraped",
    "enriching",
    "enriched",
    "validating",
    "validated",
    "selecting_claims",
    "claims_selected",
    "fact_check_done",
    "stored",
    "done",
]


def evidence_html(title: str, body: str) -> str:

    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body><main><article>"
        f"<h1>{title}</h1>{body}</article></main></body></html>"
    )


def search_hit(url: str, title: str) -> dict:

    return {
        "url": url,
        "title": title,
        "content": f"{title}. {QUOTED}.",
        "engines": ["bing", "brave"],
    }


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """
    One analysis of ARTICLE_URL, and everything needed to judge it.

    Once per module, not per test: a full analysis over real models takes
    ~15 s, and ten tests each re-running it took 156 s of every
    `./scripts/check.sh` with inference/ up. Every test below only reads
    what the run left behind. Module scope means the function-scoped
    fixtures are out of reach, so the settings pin, the inference check
    and the temporary Qdrant are done here by hand.

    Wired the way src/container.py wires it, collaborator for
    collaborator, so a constructor default that changed would change
    here too - except at the network, where a fake stands in.
    """

    skip_unless_inference()

    tmp_path = tmp_path_factory.mktemp("full_pipeline")

    with pytest.MonkeyPatch.context() as monkeypatch:

        pin_settings(monkeypatch)

        database = QdrantDatabase(path=str(tmp_path / "qdrant"))

        try:
            yield analyse(tmp_path, VectorRepository(database))
        finally:
            database.client.close()


def analyse(tmp_path: Path, repository: VectorRepository) -> dict:

    fetcher = FakeFetcher({
        ARTICLE_URL: FIXTURE.read_text(encoding="utf-8"),
        **{url: evidence_html(title, body) for url, (title, body) in EVIDENCE_PAGES.items()},
    })

    # Its own stats (the shared one persists into the lake's stats file)
    # and no configured sources (a URL must not be matched to a real
    # source's YAML). The browser step is left out rather than relied on
    # to be absent: it is the one strategy that fetches without the
    # Fetcher, so it would be the one way to reach a real network.
    extractor = ExtractorService(stats=RequestStats(), sources=[])
    extractor.strategies = [
        TrafilaturaStrategy(fetcher),
        BeautifulSoupStrategy(fetcher),
    ]

    searxng = FakeSearxngClient(results_by_term={
        ROUTED_FIGURE: [
            # The article itself, which a search for its own subject
            # naturally finds first: it must be dropped, not cited.
            search_hit(ARTICLE_URL, "Volunteer divers bring a seagrass meadow back to life"),
            *[search_hit(url, title) for url, (title, _) in EVIDENCE_PAGES.items()],
        ],
    })

    llm = FakeLLMClient(CANNED_ANSWER)

    fact_checker = FactChecker(
        repository,
        claim_selector=ClaimSelector(),
        evidence_retriever=EvidenceRetriever(
            repository,
            search_provider=SearchProvider(client=searxng),
            scraper=EvidenceScraper(extractor),
        ),
        ranker=EvidenceRanker(),
        verifier=LLMVerifier(client=llm),
        confidence_scorer=ConfidenceScorer(),
    )

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path / "lake"))

    cache = AnalysisCache(directory=tmp_path / "cache")

    service = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=NewsEnrichmentPipeline(settings),
        cache=cache,
        lake=lake,
        admission=AdmissionFilter(repository),
        graph=None,
    )

    events: list[tuple[str, dict]] = []

    result = service.analyze(
        ARTICLE_URL,
        on_phase=lambda phase, data: events.append((phase, data)),
        thresholds=PipelineThresholds(),
    )

    return {
        "service": service,
        "result": result,
        "events": events,
        "llm": llm,
        "searxng": searxng,
        "fetcher": fetcher,
        "lake": lake,
        "cache_dir": tmp_path / "cache",
    }


def claim_events(events: list[tuple[str, dict]]) -> dict[int, list[tuple[str, dict]]]:
    """Every per-claim event, grouped by the claimIndex it carries."""

    grouped: dict[int, list[tuple[str, dict]]] = {}

    for phase, data in events:
        if isinstance(data, dict) and "claimIndex" in data:
            grouped.setdefault(data["claimIndex"], []).append((phase, data))

    return grouped


def routed(per_claim: list[tuple[str, dict]]) -> bool:
    """Whether this claim's queries asked about the routed figure."""

    [searching] = [data for phase, data in per_claim if phase == "searching_web"]

    return any(ROUTED_FIGURE in query for query in searching["queries"])


def split_claims(run) -> tuple[dict, dict]:
    """claimIndex -> events, for the claims with evidence and without."""

    grouped = claim_events(run["events"])

    with_evidence = {index: per_claim for index, per_claim in grouped.items() if routed(per_claim)}
    without = {index: per_claim for index, per_claim in grouped.items() if not routed(per_claim)}

    # The test is only worth anything if the run had both kinds. If this
    # fails, extraction or selection changed what comes out of the
    # fixture - not the stage under test.
    assert with_evidence, f"no selected claim quoted {ROUTED_FIGURE}: {grouped.keys()}"
    assert without, "every selected claim was routed to evidence"

    return with_evidence, without


def checked(run, index: int) -> dict:
    """The claim_checked event of one claim."""

    [data] = [
        data
        for phase, data in claim_events(run["events"])[index]
        if phase == "claim_checked"
    ]

    return data


def response_claim(run, text: str) -> dict:

    [claim] = [claim for claim in run["result"]["claims"] if claim["text"] == text]

    return claim


# ----------------------------------------------------------------------


def test_the_article_was_extracted_from_the_saved_page_without_the_network(run):

    result = run["result"]

    assert "error" not in result, result.get("error")
    assert result["cached"] is False
    assert result["title"] == "Volunteer divers bring a seagrass meadow back to life on the Portuguese coast"

    # Every request the pipeline made went to a page the fake serves:
    # the article once, and each evidence page the search returned.
    assert run["fetcher"].requested.count(ARTICLE_URL) == 1
    assert set(run["fetcher"].requested) <= {ARTICLE_URL, *EVIDENCE_PAGES}


def test_the_article_was_admitted_and_its_claims_selected(run):

    result = run["result"]

    assert result["validity"]["isValid"] is True
    assert result["validity"]["isDuplicate"] is False
    assert result["factCheck"]["claimsChecked"] >= 2

    [selected] = [data for phase, data in run["events"] if phase == "claims_selected"]

    assert selected["count"] == result["factCheck"]["claimsChecked"]
    assert set(claim_events(run["events"])) == {claim["index"] for claim in selected["claims"]}


def test_the_article_stages_happen_in_order(run):

    phases = [phase for phase, _ in run["events"]]

    positions = [phases.index(stage) for stage in ARTICLE_STAGES]

    assert positions == sorted(positions), [
        stage for _, stage in sorted(zip(positions, ARTICLE_STAGES))
    ]

    # Every claim is checked between the selection and the verdict.
    claim_positions = [
        position
        for position, (_, data) in enumerate(run["events"])
        if isinstance(data, dict) and "claimIndex" in data
    ]

    assert phases.index("claims_selected") < min(claim_positions)
    assert max(claim_positions) < phases.index("fact_check_done")


def test_each_claim_names_every_stage_in_order(run):
    """
    Per claim, not overall: the claims run concurrently, so their events
    interleave on the wire, and each one carries claimIndex precisely so
    a client can take them apart again - which is what this does.
    """

    with_evidence, without = split_claims(run)

    for index, per_claim in with_evidence.items():
        assert [phase for phase, _ in per_claim] == STAGES_WITH_EVIDENCE, index

    for index, per_claim in without.items():
        assert [phase for phase, _ in per_claim] == STAGES_WITHOUT_EVIDENCE, index


def test_a_source_the_canned_answer_cites_survives_ranking(run):

    with_evidence, _ = split_claims(run)

    for index, per_claim in with_evidence.items():

        [ranked] = [data for phase, data in per_claim if phase == "evidence_ranked"]

        kept = [source["url"] for source in ranked["sources"]]

        # Both pages restate the claim, so the pertinence gate keeps both
        # and the canned citations [0, 1] land on them.
        assert set(kept) == set(EVIDENCE_PAGES), (index, ranked["cut"])

        verdict = checked(run, index)

        cited = [source["url"] for source in verdict["evidence"] if source["cited"]]

        assert set(cited) == set(EVIDENCE_PAGES)


def test_the_article_cannot_corroborate_itself(run):

    with_evidence, _ = split_claims(run)

    for index, per_claim in with_evidence.items():

        [retrieved] = [data for phase, data in per_claim if phase == "evidence_retrieved"]

        reasons = {source["url"]: source["reason"] for source in retrieved["rejectedSources"]}

        assert reasons.get(ARTICLE_URL) == "the article being checked cannot corroborate itself"


def test_the_verdict_and_citations_are_the_canned_answer(run):

    with_evidence, _ = split_claims(run)

    for index in with_evidence:

        verdict = checked(run, index)

        claim = response_claim(run, verdict["claim"])

        assert claim["verdict"] == Verdict.TRUE
        assert claim["rawVerdict"] == Verdict.TRUE
        assert claim["reachedStage"] == PipelineStage.AGGREGATION
        assert claim["stageNote"] is None
        assert claim["independentDomains"] == 2

        assert [source["cited"] for source in claim["evidence"]] == [True, True]
        assert [source["stance"] for source in claim["evidence"]] == ["supports", "supports"]

        # Kept, because both pages carry it word for word.
        assert [source["quote"] for source in claim["evidence"]] == [QUOTED, QUOTED]

        assert claim["llmUnreachable"] is False
        assert claim["searchUnavailable"] is False


def test_a_claim_with_no_evidence_is_unverified_without_an_llm_call(run):

    with_evidence, without = split_claims(run)

    for index in without:

        verdict = checked(run, index)

        claim = response_claim(run, verdict["claim"])

        assert claim["verdict"] == Verdict.UNVERIFIED
        assert claim["evidenceCount"] == 0
        assert claim["reachedStage"] == PipelineStage.CONFIDENCE_RECALIBRATION
        assert claim["stageNote"].startswith("No evidence could be retrieved")

        # The search ran and found nothing: that is not an outage.
        assert claim["searchUnavailable"] is False

    # One LLM call per claim that had evidence, none for the others, and
    # each call was about a routed claim.
    prompts = [user for _, user in run["llm"].calls]

    assert len(prompts) == len(with_evidence)

    for index in with_evidence:
        assert any(checked(run, index)["claim"] in prompt for prompt in prompts)

    for index in without:
        assert not any(checked(run, index)["claim"] in prompt for prompt in prompts)


def test_the_article_lands_in_all_three_lake_layers(run):

    storage = run["result"]["storage"]

    assert storage["persisted"] is True

    lake = run["lake"]

    raw = lake.get(DataLayer.RAW, storage["records"]["raw"])
    processed = lake.get(DataLayer.PROCESSED, storage["records"]["processed"])
    exploitation = lake.get(DataLayer.EXPLOITATION, storage["records"]["exploitation"])

    assert raw["article"]["url"] == ARTICLE_URL
    assert "87% of the transplanted shoots" in raw["article"]["content"]

    # The processed record was rewritten with the report attached, and
    # each layer points at the one it was derived from.
    assert processed["fact_check"]["claims_selected"] == run["result"]["factCheck"]["claimsChecked"]
    assert processed["lineage"]["parent_record_id"] == raw["record_id"]

    assert exploitation["title"] == run["result"]["title"]
    assert exploitation["lineage"]["parent_record_id"] == processed["record_id"]

    trace = lake.trace(processed["article"]["id"])

    # Processed twice: after enrichment, then again with the report.
    assert [entry["layer"] for entry in trace["manifest"]] == [
        "raw", "processed", "processed", "exploitation",
    ]


def test_the_response_has_the_cached_shape_and_the_cache_is_in_tmp_path(run):

    result = run["result"]

    assert set(result) == ANALYZE_RESPONSE_SHAPE[AnalysisCache.SCHEMA_VERSION]

    # Written where the test put it, not into the real data/cache, and
    # served from there on the next call without running anything again.
    assert len(list(run["cache_dir"].glob("*.json"))) == 1

    calls = len(run["llm"].calls)

    again = run["service"].analyze(ARTICLE_URL, thresholds=PipelineThresholds())

    assert again["cached"] is True
    assert len(run["llm"].calls) == calls

    # The same answer, as the cache's JSON round-trip renders it (dates
    # come back as strings, which is all that differs).
    def without_flag(response: dict) -> dict:
        return {key: value for key, value in response.items() if key != "cached"}

    assert without_flag(again) == json.loads(json.dumps(without_flag(result), default=str))

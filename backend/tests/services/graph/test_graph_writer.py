import inspect
import re

from src.database.neo4j_client import GraphClient
from src.models.core.source import NewsSource
from src.models.fact_checker.evidence import EvidenceStance
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.models.core.claim import RejectedClaim
from src.services.graph import graph_writer as gw
from src.services.graph.graph_writer import GraphWriter, claim_id, domain_of
from src.services.graph.schema import NODE_KEYS, RELATIONSHIPS, entity_label

from tests.factories import create_article, create_claim, create_evidence
from tests.services.graph.fake_graph_client import RecordingGraphClient


BBC = NewsSource(
    id="bbc",
    name="BBC News",
    base_url="https://www.bbc.com",
    reliability_index=0.9,
    language="en",
    country="GB",
)


def writer(client=None) -> GraphWriter:
    return GraphWriter(client or RecordingGraphClient(), sources=[BBC])


def checked_report(article, checks, **kwargs) -> FactCheckReport:
    values = dict(
        article_id=article.id,
        validation_passed=True,
        claim_checks=checks,
        claims_total=len(article.claims or []),
        claims_selected=len(checks),
        overall_verdict=Verdict.TRUE,
        overall_confidence=0.8,
    )
    values.update(kwargs)
    return FactCheckReport(**values)


def one_statement(statements, query):
    matches = [params for q, params in statements if q == query]
    assert len(matches) == 1, f"expected one {query.split()[0]}... statement, got {len(matches)}"
    return matches[0]


# ----------------------------------------------------------------------


def test_the_fake_client_matches_the_real_one():
    """
    The fake drifting from GraphClient is how a signature change passes
    every test here and fails in production - see test_fake_contracts.py
    for the five fakes that did exactly that at once.
    """

    for name in ("write", "read", "verify_connection", "close"):
        real = inspect.signature(getattr(GraphClient, name))
        fake = inspect.signature(getattr(RecordingGraphClient, name))
        assert list(real.parameters) == list(fake.parameters), name


def test_claim_ids_ignore_case_and_whitespace_but_nothing_else():

    assert claim_id("Spain  grew 3%.") == claim_id("spain grew 3%.")
    assert claim_id("Spain grew 3%.") != claim_id("Spain grew 4%.")


def test_domain_is_the_host_without_www():

    assert domain_of("https://www.bbc.com/news/1") == "bbc.com"
    assert domain_of("not a url") == "unknown"


def test_an_article_is_published_by_its_configured_source():

    article = create_article(url="https://www.bbc.com/news/1")

    statements = writer().analysis_statements(article, checked_report(article, []))

    upsert = one_statement(statements, gw.UPSERT_ARTICLE)

    assert upsert["url"] == "https://www.bbc.com/news/1"
    assert upsert["domain"] == "bbc.com"
    assert upsert["source"]["name"] == "BBC News"
    assert upsert["source"]["reliability"] == 0.9
    assert upsert["source"]["reliability_known"] is True
    assert upsert["props"]["overall_verdict"] == "TRUE"
    assert upsert["props"]["admitted"] is True


def test_an_unknown_publisher_gets_no_invented_rating():

    article = create_article(url="https://somewhere.example/story")

    upsert = one_statement(
        writer().analysis_statements(article, checked_report(article, [])),
        gw.UPSERT_ARTICLE,
    )

    # Empty: the node keeps ON CREATE's reliability_known = false.
    assert upsert["source"] == {}


def test_entities_are_written_once_per_type_with_the_type_as_a_label():

    article = create_article(entities={
        "person": ["Ada Lovelace", "ada  lovelace"],
        "country": ["Spain"],
    })

    statements = writer().analysis_statements(article, checked_report(article, []))

    people = [(q, p) for q, p in statements if p.get("type") == "person"]
    countries = [(q, p) for q, p in statements if p.get("type") == "country"]

    assert len(people) == 1 and len(countries) == 1
    assert "SET n:Person" in people[0][0]
    assert "SET n:Country" in countries[0][0]

    # Same person, differently spaced: one node.
    assert [e["name"] for e in people[0][1]["entities"]] == ["Ada Lovelace"]


def test_an_entity_type_that_is_not_a_safe_label_never_reaches_the_query_text():

    hostile = "x) DETACH DELETE (n"

    article = create_article(entities={hostile: ["Anything"]})

    statements = writer().analysis_statements(article, checked_report(article, []))

    (query, params), = [(q, p) for q, p in statements if p.get("type") == hostile]

    assert "DETACH DELETE (n" not in query
    assert "SET n:" not in query
    # Still written, as a plain Entity carrying its type as data.
    assert params["entities"][0]["name"] == "Anything"


def test_entity_labels_never_collide_with_a_node_label():

    assert entity_label("person") == "Person"
    assert entity_label("claim") is None
    assert entity_label("source") is None
    assert entity_label("") is None


def test_a_checked_claim_gets_its_verdict_and_every_evidence_page():

    claim = create_claim(text="Spain planted a million trees in 2024.")

    evidence = [
        create_evidence(url="https://www.bbc.com/a", title="BBC", stance=EvidenceStance.SUPPORTS),
        create_evidence(url="https://other.example/b", title="Other"),
    ]

    check = FactCheck(
        claim=claim.text,
        verdict=Verdict.PARTIALLY_TRUE,
        explanation="Mostly.",
        confidence=0.7,
        evidence=evidence,
        cited_evidence_indices=[0],
    )

    article = create_article(claims=[claim])

    statements = writer().analysis_statements(article, checked_report(article, [check]))

    verdicts = one_statement(statements, gw.LINK_VERDICTS)["checks"]

    assert verdicts == [{
        "claim_id": claim_id(claim.text),
        "verdict": "PARTIALLY_TRUE",
        "props": verdicts[0]["props"],
    }]
    assert verdicts[0]["props"]["confidence"] == 0.7

    linked = one_statement(statements, gw.LINK_EVIDENCE)

    assert linked["method"] == "pipeline"
    assert [e["url"] for e in linked["evidence"]] == ["https://www.bbc.com/a", "https://other.example/b"]
    assert [e["props"]["cited"] for e in linked["evidence"]] == [True, False]
    assert linked["evidence"][0]["props"]["stance"] == "supports"
    assert linked["evidence"][0]["source"]["name"] == "BBC News"
    assert linked["evidence"][1]["domain"] == "other.example"

    # The old pipeline verdict is cleared before the new one is written.
    kinds = [q for q, _ in statements]
    assert kinds.index(gw.CLEAR_PIPELINE_VERDICTS) < kinds.index(gw.LINK_VERDICTS)


def test_claims_record_whether_they_were_selected_and_why_not():

    kept = create_claim(text="Kept claim.")
    dropped = create_claim(text="Dropped claim.")

    article = create_article(claims=[kept, dropped])

    report = checked_report(
        article,
        [FactCheck(claim="Kept claim.", verdict=Verdict.TRUE, explanation="", confidence=0.9)],
        unselected_claims=[RejectedClaim(text="Dropped claim.", confidence=0.4, reason="low anchor")],
    )

    claims = one_statement(writer().analysis_statements(article, report), gw.LINK_CLAIMS)["claims"]

    by_text = {c["text"]: c["props"] for c in claims}

    assert by_text["Kept claim."]["selected"] is True
    assert by_text["Dropped claim."]["selected"] is False
    assert by_text["Dropped claim."]["stage_note"] == "low anchor"


def test_a_rejected_article_is_written_without_a_verdict():

    article = create_article(claims=[create_claim()])

    report = FactCheckReport(
        article_id=article.id,
        validation_passed=False,
        skipped_reason="off_topic",
    )

    statements = writer().analysis_statements(article, report)

    upsert = one_statement(statements, gw.UPSERT_ARTICLE)

    assert upsert["props"]["admitted"] is False
    assert upsert["props"]["overall_verdict"] is None
    assert gw.LINK_VERDICTS not in [q for q, _ in statements]

    claims = one_statement(statements, gw.LINK_CLAIMS)["claims"]
    assert claims[0]["props"]["stage_note"] == "off_topic"


def test_a_re_analysis_clears_what_the_last_run_wrote_before_writing():

    article = create_article()

    kinds = [q for q, _ in writer().analysis_statements(article, checked_report(article, []))]

    assert kinds[0] == gw.UPSERT_ARTICLE
    assert kinds[1] == gw.CLEAR_PIPELINE_ARTICLE_EDGES
    assert kinds[-1] == gw.PRUNE_ORPHANS


def test_the_schema_is_created_once_then_every_write_is_one_transaction():

    client = RecordingGraphClient()
    graph = writer(client)

    article = create_article()

    graph.write_analysis(article, checked_report(article, []))
    schema_writes = len(client.writes) - 1

    graph.write_analysis(article, checked_report(article, []))

    assert len(client.writes) == schema_writes + 2
    assert all("CONSTRAINT" in tx[0][0] or "Verdict" in tx[0][0] for tx in client.writes[:schema_writes])


# ----------------------------------------------------------------------
# Hand-labelled facts


FACT = {
    "id": "fact001",
    "language": "es",
    "site": "lacarabuenadelmundo.com",
    "claim": "Uno de cada tres niños vive en riesgo de pobreza",
    "label": "MISLEADING",
    "labelRaw": "conflicting evidence/cherrypicking",
    "referenceEvidenceLinks": ["https://ine.es/a", "https://www.bbc.com/b", ""],
    "topic": "community",
    "claimType": "numerical",
    "sourceTier": "primary",
    "articleUrl": "https://lacarabuenadelmundo.com/noticias/x/",
    "annotatorNote": "It is 1 in 4.",
    "createdAt": "2026-09-29T05:54:42",
    "review": None,
}


def test_a_fact_replaces_what_it_wrote_before():

    statements = writer().fact_statements(FACT)

    assert statements[0] == (gw.CLEAR_FACT, {"fact_id": "fact001"})


def test_a_fact_writes_its_article_claim_verdict_and_topic():

    link = one_statement(writer().fact_statements(FACT), gw.LINK_FACT)

    assert link["url"] == "https://lacarabuenadelmundo.com/noticias/x/"
    assert link["domain"] == "lacarabuenadelmundo.com"
    assert link["claim_id"] == claim_id(FACT["claim"])
    assert link["verdict"] == "MISLEADING"
    assert link["topic"] == "community"
    assert link["verdict_props"]["annotator_note"] == "It is 1 in 4."
    assert link["verdict_props"]["reviewed"] is False


def test_a_fact_links_its_reference_sources_as_manual_evidence():

    evidence = one_statement(writer().fact_statements(FACT), gw.LINK_EVIDENCE)

    assert evidence["method"] == "manual"
    # The empty link is dropped, not written as a node with no URL.
    assert [e["url"] for e in evidence["evidence"]] == ["https://ine.es/a", "https://www.bbc.com/b"]
    assert evidence["evidence"][1]["source"]["source_id"] == "bbc"
    assert all(e["props"]["fact_id"] == "fact001" for e in evidence["evidence"])


def test_an_unverified_fact_with_no_links_writes_no_evidence():

    fact = {**FACT, "label": "UNVERIFIED", "referenceEvidenceLinks": []}

    kinds = [q for q, _ in writer().fact_statements(fact)]

    assert gw.LINK_EVIDENCE not in kinds


def test_a_fact_without_an_article_url_still_hangs_off_an_article():

    fact = {**FACT, "articleUrl": None}

    link = one_statement(writer().fact_statements(fact), gw.LINK_FACT)

    assert link["url"] == "https://lacarabuenadelmundo.com/#fact001"


# ----------------------------------------------------------------------
# Everything written is declared


LABEL = re.compile(r"\(\s*\w*\s*:(\w+)")
REL_TYPE = re.compile(r"\[\s*\w*\s*:(\w+)")


def test_every_label_and_relationship_written_is_in_the_declared_schema():
    """
    schema.py is what the /graph page draws and what the constraints are
    made from. A label or relationship type written here but missing
    there would exist in the database and nowhere in the documentation.
    """

    claim = create_claim(text="A claim.", entities={"person": ["Ada"]})
    check = FactCheck(
        claim="A claim.", verdict=Verdict.TRUE, explanation="", confidence=0.9,
        evidence=[create_evidence()],
    )
    article = create_article(claims=[claim], entities={"person": ["Ada"]})

    graph = writer()

    statements = graph.analysis_statements(article, checked_report(article, [check]))
    statements += graph.fact_statements(FACT)

    declared_types = {rel["type"] for rel in RELATIONSHIPS}

    for query, _ in statements:
        for label in LABEL.findall(query):
            assert label in NODE_KEYS, f"undeclared label :{label}"
        for rel_type in REL_TYPE.findall(query):
            assert rel_type in declared_types, f"undeclared relationship :{rel_type}"

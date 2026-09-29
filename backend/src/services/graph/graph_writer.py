import hashlib
from datetime import datetime
from logging import getLogger
from urllib.parse import urlparse

from src.database.neo4j_client import GraphClient
from src.models.core.enriched_article import EnrichedArticle
from src.models.core.source import NewsSource
from src.models.fact_checker.fact_check import Verdict
from src.models.fact_checker.fact_check_report import FactCheckReport
from src.services.graph.schema import (
    MANUAL,
    PIPELINE,
    constraint_statements,
    entity_label,
)

logger = getLogger(__name__)

Statement = tuple[str, dict]


def domain_of(url: str) -> str:
    """
    Host minus `www.` - the same judgement of "same outlet" the ranker
    (ranking_retrieval.py) and the evidence independence count
    (search_provider.registrable_domain) already make, so a Source node
    means the same thing everywhere.
    """

    domain = urlparse(url or "").netloc.replace("www.", "").lower()

    return domain or "unknown"


def normalise(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def claim_id(text: str) -> str:
    """
    Same sentence, same claim - across articles, runs and the labeller.
    Whitespace and case only: anything looser would merge two claims that
    differ in exactly the figure being checked.
    """

    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:32]


def entity_key(entity_type: str, name: str) -> str:
    return f"{entity_type}:{normalise(name)}"


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# ----------------------------------------------------------------------
# Cypher
#
# Labels cannot be parameters, so the only thing ever formatted into these
# strings is an entity type label that passed schema.entity_label.
# ----------------------------------------------------------------------

UPSERT_SOURCE = """
MERGE (s:Source {domain: $domain})
ON CREATE SET s.name = $domain, s.configured = false, s.reliability_known = false
SET s += $props
"""

UPSERT_ARTICLE = """
MERGE (s:Source {domain: $domain})
ON CREATE SET s.name = $domain, s.configured = false, s.reliability_known = false
SET s += $source
MERGE (a:Article {url: $url})
SET a += $props
MERGE (a)-[:PUBLISHED_BY]->(s)
"""

# A re-analysis replaces what the previous pipeline run wrote about this
# article - never what the labeller wrote. Claims and entities left with
# nothing pointing at them are removed rather than kept as orphans: a
# claim is only ever reachable from an article.
CLEAR_PIPELINE_ARTICLE_EDGES = """
MATCH (a:Article {url: $url})
OPTIONAL MATCH (a)-[r:MENTIONS|ABOUT]->()
WHERE r.method = 'pipeline'
DELETE r
WITH DISTINCT a
OPTIONAL MATCH (a)-[c:CONTAINS_CLAIM {method: 'pipeline'}]->(claim:Claim)
DELETE c
WITH DISTINCT claim
WHERE claim IS NOT NULL AND NOT (claim)<-[:CONTAINS_CLAIM]-()
DETACH DELETE claim
"""

PRUNE_ORPHANS = """
MATCH (n)
WHERE (n:Entity OR n:Claim OR n:Evidence) AND NOT (n)--()
DELETE n
"""

LINK_TOPICS = """
MATCH (a:Article {url: $url})
UNWIND $topics AS t
MERGE (tp:Topic {name: t.name})
MERGE (a)-[r:ABOUT {method: 'pipeline'}]->(tp)
SET r.confidence = t.confidence, r.rank = t.rank
"""

LINK_ARTICLE_ENTITIES = """
MATCH (a:Article {{url: $url}})
UNWIND $entities AS e
MERGE (n:Entity {{key: e.key}})
ON CREATE SET n.name = e.name, n.type = $type
{set_label}
MERGE (a)-[r:MENTIONS {{method: $method}}]->(n)
"""

LINK_CLAIMS = """
MATCH (a:Article {url: $url})
UNWIND $claims AS c
MERGE (claim:Claim {id: c.id})
ON CREATE SET claim.text = c.text
SET claim.language = coalesce(claim.language, $language)
MERGE (a)-[r:CONTAINS_CLAIM {method: 'pipeline'}]->(claim)
SET r += c.props
"""

LINK_CLAIM_ENTITIES = """
UNWIND $entities AS e
MATCH (claim:Claim {{id: e.claim_id}})
MERGE (n:Entity {{key: e.key}})
ON CREATE SET n.name = e.name, n.type = $type
{set_label}
MERGE (claim)-[r:MENTIONS {{method: $method}}]->(n)
"""

CLEAR_PIPELINE_VERDICTS = """
UNWIND $claim_ids AS id
MATCH (claim:Claim {id: id})-[r:HAS_VERDICT|CHECKED_AGAINST]->()
WHERE r.method = 'pipeline'
DELETE r
"""

LINK_VERDICTS = """
UNWIND $checks AS k
MATCH (claim:Claim {id: k.claim_id})
MERGE (v:Verdict {name: k.verdict})
MERGE (claim)-[r:HAS_VERDICT {method: 'pipeline'}]->(v)
SET r += k.props
"""

# Shared by both methods: an evidence page and its publisher are the same
# node whichever of them found it.
LINK_EVIDENCE = """
UNWIND $evidence AS ev
MATCH (claim:Claim {id: ev.claim_id})
MERGE (e:Evidence {url: ev.url})
SET e.title = coalesce(ev.title, e.title),
    e.origin = coalesce(ev.origin, e.origin),
    e.published_at = coalesce(ev.published_at, e.published_at)
MERGE (s:Source {domain: ev.domain})
ON CREATE SET s.name = ev.domain, s.configured = false, s.reliability_known = false
SET s += ev.source
MERGE (e)-[:PUBLISHED_BY]->(s)
MERGE (claim)-[r:CHECKED_AGAINST {method: $method}]->(e)
SET r += ev.props
"""

# Everything one labelled fact wrote, found by its fact_id, so saving the
# fact again - with a new label, new links or even an edited claim -
# replaces it instead of leaving the old version beside the new one.
CLEAR_FACT = """
MATCH ()-[r {fact_id: $fact_id}]->()
DELETE r
"""

LINK_FACT = """
MERGE (a:Article {url: $url})
ON CREATE SET a.language = $language
SET a.labelled = true
WITH a
MERGE (s:Source {domain: $domain})
ON CREATE SET s.name = $domain, s.configured = false, s.reliability_known = false
SET s += $source
MERGE (a)-[:PUBLISHED_BY]->(s)
MERGE (claim:Claim {id: $claim_id})
ON CREATE SET claim.text = $claim_text
SET claim.language = coalesce(claim.language, $language),
    claim.claim_type = $claim_type,
    claim.fact_id = $fact_id
MERGE (a)-[c:CONTAINS_CLAIM {method: 'manual', fact_id: $fact_id}]->(claim)
MERGE (v:Verdict {name: $verdict})
MERGE (claim)-[r:HAS_VERDICT {method: 'manual', fact_id: $fact_id}]->(v)
SET r += $verdict_props
FOREACH (topic IN CASE WHEN $topic IS NULL THEN [] ELSE [$topic] END |
    MERGE (tp:Topic {name: topic})
    MERGE (a)-[:ABOUT {method: 'manual', fact_id: $fact_id}]->(tp)
)
"""


class GraphWriter:
    """
    Writes into Neo4j what the pipeline and the labeller produce. It
    decides nothing: every value comes from an EnrichedArticle and its
    FactCheckReport, or from a fact file, as-is.

    `sources` are the configured source YAMLs, used to give a Source node
    its name and reliability rating when its domain is one of ours.
    """

    def __init__(self, client: GraphClient, sources: list[NewsSource] | None = None):

        self.client = client

        self._sources = {
            domain_of(str(source.base_url)): source for source in (sources or [])
        }

        self._schema_ready = False

    # ------------------------------------------------------------------

    def ensure_schema(self) -> None:
        """
        Constraints and the fixed Verdict nodes. Idempotent (IF NOT
        EXISTS / MERGE), run once per process before the first write
        rather than at startup, so a Neo4j that comes up after the
        backend is still set up.
        """

        if self._schema_ready:
            return

        # Schema changes cannot share a transaction with data writes.
        for statement in constraint_statements():
            self.client.write([(statement, {})])

        self.client.write([(
            "UNWIND $names AS name MERGE (:Verdict {name: name})",
            {"names": [verdict.value for verdict in Verdict]},
        )])

        self._schema_ready = True

    def write_sources(self) -> int:
        """Every configured source, so the graph has them before any article."""

        self.ensure_schema()

        statements = [
            (UPSERT_SOURCE, {"domain": domain, "props": self._source_props(domain)})
            for domain in self._sources
        ]

        if statements:
            self.client.write(statements)

        return len(statements)

    def write_analysis(
        self,
        article: EnrichedArticle,
        report: FactCheckReport,
        run_id: str | None = None,
    ) -> dict:

        self.ensure_schema()

        statements = self.analysis_statements(article, report, run_id)

        self.client.write(statements)

        return {
            "url": article.url,
            "claims": len(article.claims or []),
            "verdicts": len(report.claim_checks),
            "evidence": sum(len(check.evidence) for check in report.claim_checks),
        }

    def write_labelled_fact(self, fact: dict) -> dict:

        self.ensure_schema()

        self.client.write(self.fact_statements(fact))

        return {"fact": fact.get("id"), "url": fact.get("articleUrl")}

    # ------------------------------------------------------------------
    # Statement builders. Pure, so what gets written can be tested without
    # a database (tests/services/graph/test_graph_writer.py).
    # ------------------------------------------------------------------

    def analysis_statements(
        self,
        article: EnrichedArticle,
        report: FactCheckReport,
        run_id: str | None = None,
    ) -> list[Statement]:

        url = article.url
        domain = domain_of(url)
        sentiment = article.sentiment

        props = {
            "id": article.id,
            "title": article.title or None,
            "language": article.language,
            "published_at": _iso(article.published_at),
            "analyzed_at": _iso(report.checked_at),
            "run_id": run_id,
            "admitted": report.validation_passed,
            "skipped_reason": report.skipped_reason,
            "duplicate": report.duplicate,
            "impact_score": report.impact_score,
            "overall_verdict": (
                report.overall_verdict.value if report.validation_passed else None
            ),
            "overall_confidence": (
                report.overall_confidence if report.validation_passed else None
            ),
            "claims_total": report.claims_total,
            "claims_selected": report.claims_selected,
            "sentiment_label": sentiment.label if sentiment else None,
            "sentiment_polarity": sentiment.polarity if sentiment else None,
            "content_hash": hashlib.sha256(article.body.encode("utf-8")).hexdigest(),
        }

        statements: list[Statement] = [
            (UPSERT_ARTICLE, {
                "url": url,
                "domain": domain,
                "source": self._source_props(domain),
                "props": props,
            }),
            (CLEAR_PIPELINE_ARTICLE_EDGES, {"url": url}),
        ]

        topics = [
            {"name": topic.topic, "confidence": topic.confidence, "rank": rank}
            for rank, topic in enumerate(article.topics or [], start=1)
        ]

        if topics:
            statements.append((LINK_TOPICS, {"url": url, "topics": topics}))

        statements += self._entity_statements(
            LINK_ARTICLE_ENTITIES,
            {"url": url},
            article.entities or {},
        )

        claims = self._claim_rows(article, report)

        if claims:
            statements.append((LINK_CLAIMS, {
                "url": url,
                "language": article.language,
                "claims": [{"id": c["id"], "text": c["text"], "props": c["props"]} for c in claims],
            }))

            # Claim entities, grouped by type across all claims so there
            # is one statement per type rather than per claim.
            by_type: dict[str, list[dict]] = {}

            for claim in claims:
                for entity_type, names in claim["entities"].items():
                    for name in names:
                        by_type.setdefault(entity_type, []).append({
                            "claim_id": claim["id"],
                            "key": entity_key(entity_type, name),
                            "name": name,
                        })

            for entity_type, rows in by_type.items():
                statements.append(self._typed_entity_statement(
                    LINK_CLAIM_ENTITIES, {}, entity_type, rows, PIPELINE
                ))

        checks = [check for check in report.claim_checks if check.claim]

        if checks:
            statements += self._verdict_statements(checks)

        statements.append((PRUNE_ORPHANS, {}))

        return statements

    def fact_statements(self, fact: dict) -> list[Statement]:
        """
        One hand-labelled fact (backend/data/evaluation/manual/factNNN.json,
        written by labeller/). Its article, claim, topic, verdict and
        reference links - each edge tagged method 'manual' and the fact id.
        """

        fact_id = fact["id"]
        url = fact.get("articleUrl") or ""

        # Very early facts may have no article URL; the site is then the
        # best we have, as a stand-in article node for its claim.
        if not url:
            url = f"https://{fact.get('site') or 'unknown'}/#{fact_id}"

        domain = domain_of(url)
        language = fact.get("language")
        review = fact.get("review") or None

        verdict_props = {
            "label_raw": fact.get("labelRaw"),
            "annotator_note": fact.get("annotatorNote"),
            "checked_at": fact.get("reviewDate") or fact.get("createdAt"),
            "reviewed": review is not None,
            "source_tier": fact.get("sourceTier"),
            "evidence_date": fact.get("evidenceDate"),
            "split": fact.get("split"),
        }

        statements: list[Statement] = [
            (CLEAR_FACT, {"fact_id": fact_id}),
            (LINK_FACT, {
                "url": url,
                "domain": domain,
                "source": self._source_props(domain),
                "language": language,
                "fact_id": fact_id,
                "claim_id": claim_id(fact["claim"]),
                "claim_text": fact["claim"],
                "claim_type": fact.get("claimType"),
                "verdict": fact["label"],
                "verdict_props": verdict_props,
                "topic": fact.get("topic"),
            }),
        ]

        links = [link for link in fact.get("referenceEvidenceLinks") or [] if link]

        if links:
            statements.append((LINK_EVIDENCE, {
                "method": MANUAL,
                "evidence": [
                    {
                        "claim_id": claim_id(fact["claim"]),
                        "url": link,
                        "title": None,
                        "origin": "reference",
                        "published_at": None,
                        "domain": domain_of(link),
                        "source": self._source_props(domain_of(link)),
                        "props": {"fact_id": fact_id, "cited": True},
                    }
                    for link in links
                ],
            }))

        statements.append((PRUNE_ORPHANS, {}))

        return statements

    # ------------------------------------------------------------------

    def _source_props(self, domain: str) -> dict:
        """
        What we know about a publisher. Empty for a domain that is not one
        of ours: `SET s += {}` leaves the node as ON CREATE made it
        (unconfigured, reliability unknown), and never downgrades one a
        configured source already filled in.
        """

        source = self._sources.get(domain)

        if source is None:
            return {}

        return {
            "name": source.name,
            "source_id": source.id,
            "configured": True,
            "reliability": source.reliability_index,
            "reliability_known": True,
            "language": source.language,
            "country": source.country,
            "source_type": source.source_type.value,
        }

    @staticmethod
    def _claim_rows(article: EnrichedArticle, report: FactCheckReport) -> list[dict]:

        checked = {normalise(check.claim) for check in report.claim_checks if check.claim}
        unselected = {normalise(rejected.text): rejected.reason for rejected in report.unselected_claims}

        rows = []
        seen = set()

        for claim in article.claims or []:

            cid = claim_id(claim.text)

            if cid in seen:
                continue

            seen.add(cid)

            key = normalise(claim.text)

            rows.append({
                "id": cid,
                "text": claim.text,
                "entities": claim.entities or {},
                "props": {
                    "confidence": claim.confidence,
                    "opinion_score": claim.opinion_score,
                    "anchor_score": claim.anchor_score,
                    "selected": key in checked,
                    "stage_note": (
                        report.skipped_reason
                        if not report.validation_passed
                        else unselected.get(key)
                    ),
                },
            })

        # A checked claim the article's own list does not contain (the
        # selector can rewrite a sentence) still needs a node to hang its
        # verdict on.
        for check in report.claim_checks:

            if not check.claim or claim_id(check.claim) in seen:
                continue

            seen.add(claim_id(check.claim))

            rows.append({
                "id": claim_id(check.claim),
                "text": check.claim,
                "entities": {},
                "props": {"selected": True, "confidence": check.confidence},
            })

        return rows

    def _verdict_statements(self, checks) -> list[Statement]:

        verdicts = []
        evidence = []

        for check in checks:

            cid = claim_id(check.claim)
            cited = set(check.cited_evidence_indices)

            verdicts.append({
                "claim_id": cid,
                "verdict": check.verdict.value,
                "props": {
                    "confidence": check.confidence,
                    "explanation": check.explanation,
                    "raw_verdict": check.raw_verdict.value if check.raw_verdict else None,
                    "raw_confidence": check.raw_confidence,
                    "reached_stage": getattr(check.reached_stage, "value", check.reached_stage),
                    "independent_domains": check.independent_domains,
                    "evidence_count": check.evidence_count,
                    "llm_unreachable": check.llm_unreachable,
                },
            })

            for index, item in enumerate(check.evidence):

                domain = item.domain or domain_of(item.url)

                evidence.append({
                    "claim_id": cid,
                    "url": item.url,
                    "title": item.title,
                    "origin": getattr(item.origin, "value", item.origin),
                    "published_at": _iso(item.published_at),
                    "domain": domain,
                    "source": self._source_props(domain),
                    "props": {
                        # The index is what the LLM cited by, and what
                        # `cited` below is computed from.
                        "index": index,
                        "cited": index in cited,
                        "stance": getattr(item.stance, "value", item.stance),
                        "quote": item.quote,
                        "relevance": item.relevance_score,
                        "pertinence": item.pertinence_score,
                        "reliability": item.reliability_score,
                    },
                })

        statements: list[Statement] = [
            (CLEAR_PIPELINE_VERDICTS, {"claim_ids": [v["claim_id"] for v in verdicts]}),
            (LINK_VERDICTS, {"checks": verdicts}),
        ]

        if evidence:
            statements.append((LINK_EVIDENCE, {"method": PIPELINE, "evidence": evidence}))

        return statements

    def _entity_statements(
        self,
        template: str,
        params: dict,
        entities: dict[str, list[str]],
    ) -> list[Statement]:

        statements = []

        for entity_type, names in entities.items():

            rows = []
            seen = set()

            for name in names:
                key = entity_key(entity_type, name)
                if not name or key in seen:
                    continue
                seen.add(key)
                rows.append({"key": key, "name": name})

            if rows:
                statements.append(self._typed_entity_statement(
                    template, params, entity_type, rows, PIPELINE
                ))

        return statements

    @staticmethod
    def _typed_entity_statement(
        template: str,
        params: dict,
        entity_type: str,
        rows: list[dict],
        method: str,
    ) -> Statement:

        label = entity_label(entity_type)

        query = template.format(set_label=f"SET n:{label}" if label else "")

        return (query, {**params, "entities": rows, "type": entity_type, "method": method})

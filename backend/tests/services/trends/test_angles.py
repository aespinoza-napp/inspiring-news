"""
The constructive angle of a story from a trend (src/services/trends/
angles.py, docs/decisions/trends.md "The angle"): proposed by a fake
model, checked by a fake fact-checker, never invented.
"""

from src.config.thresholds import WriterThresholds
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin, EvidenceStance
from src.models.fact_checker.fact_check import FactCheck, Verdict
from src.services.llms import LLMUnavailableError
from src.services.selection.mission_screen import Assessment, Verdict as ScreenVerdict
from src.services.trends.angles import AngleFinder, parse_proposals, proposal_prompt
from src.services.trends.ledger import TrendLedger
from src.services.writer.analysed_article import AnalysedArticle, CheckedClaim

TREND = {"id": "abc123", "name": "línea 10", "signal": "google_trends_es", "signalName": "Google Trends · Spain",
         "traffic": 200, "startedAt": "2026-10-26T13:40:00+00:00", "link": None, "video": None}

ARTICLE = AnalysedArticle(
    id="0123456789abcdef",
    url="https://elpais.com/espana/madrid/2026-10-26/linea-10-reabre",
    headline="El tramo de la Línea 10 de Metro de Madrid reabrirá a finales de noviembre",
    lead="Las obras de renovación, que cerraron el tramo en verano, terminan antes de lo previsto.",
    language="es",
    topic="Cities & Society",
    published_at="2026-10-26T08:00:00+00:00",
    source_name="El País",
    domain="elpais.com",
    keywords=("metro", "madrid"),
    claims=(CheckedClaim(text="El tramo reabrirá a finales de noviembre.", verdict="TRUE", confidence=0.8),),
)


class FakeLLM:

    model = "qwen3.5:4b"

    def __init__(self, answer=None, error=None):
        self.answer = answer
        self.error = error
        self.calls = []

    def complete_json(self, system_prompt, user_prompt, max_retries=1, max_tokens=None, timeout=None):
        self.calls.append((system_prompt, user_prompt, max_tokens))
        if self.error:
            raise self.error
        return self.answer


def evidence(url: str, stance=EvidenceStance.SUPPORTS, domain: str | None = None) -> Evidence:
    return Evidence(
        url=url, title=f"About {url}", snippet="The works finished early.", content="The works finished early. " * 30,
        origin=EvidenceOrigin.WEB,
        domain=domain, stance=stance, quote="The works finished early.",
    )


def fact_check(verdict=Verdict.TRUE, sources=(), cited=None, **extra) -> FactCheck:
    return FactCheck(
        verdict=verdict, explanation="", confidence=0.75, evidence=list(sources),
        cited_evidence_indices=list(range(len(sources))) if cited is None else cited, **extra,
    )


class FakeChecker:
    """Answers each claim from `answers` (a FactCheck or an exception); records the context it was given."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def check(self, text, language, context):
        self.asked.append((text, language, context.url))
        answer = self.answers[text]
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeScreen:

    def __init__(self, kind=None, error=None):
        self.kind = kind
        self.error = error

    def assess(self, candidates, exempt=None):
        if self.error:
            raise self.error
        return [Assessment(ScreenVerdict(off_mission=self.kind) if self.kind else None, None) for _ in candidates]


PROPOSED = {"angles": [
    {"question": "¿Se acabaron antes las obras?", "query": "línea 10 obras terminan antes",
     "claim": "Las obras de la Línea 10 de Metro de Madrid terminaron antes de lo previsto."},
    {"question": "¿Cuántos viajeros vuelven?", "query": "línea 10 viajeros",
     "claim": "La Línea 10 recupera 200.000 viajeros diarios con la reapertura."},
]}

EARLY = PROPOSED["angles"][0]["claim"]
RIDERS = PROPOSED["angles"][1]["claim"]


def finder(answer=PROPOSED, answers=None, screen=None, llm_error=None):
    return AngleFinder(
        llm=FakeLLM(answer, llm_error),
        checker=FakeChecker(answers or {}),
        screen=screen or FakeScreen(),
    )


def test_an_angle_true_from_two_other_domains_is_kept_with_its_sources():

    answers = {
        EARLY: fact_check(sources=[
            evidence("https://www.telemadrid.es/a", domain="telemadrid.es"),
            evidence("https://www.elmundo.es/b", domain="elmundo.es"),
            # The article's own outlet does not count towards the domains.
            evidence("https://elpais.com/c", domain="elpais.com"),
        ]),
        RIDERS: fact_check(verdict=Verdict.UNVERIFIED),
    }

    angles = finder(answers=answers)
    result = angles.find(ARTICLE, TREND, WriterThresholds())

    early, riders = result.angles
    assert early.kept and early.domains == ["elmundo.es", "telemadrid.es"]
    assert early.reason.startswith("TRUE at 75%, supported by 2 domains")
    assert [s.url for s in result.sources] == ["https://www.telemadrid.es/a", "https://www.elmundo.es/b"]
    assert all(s.origin == "angle" and s.excerpt for s in result.sources)
    assert not riders.kept and "UNVERIFIED" in riders.reason
    assert result.note is None and result.model == "qwen3.5:4b"

    # Checked in the article's language and context, so it cannot confirm itself.
    assert angles.checker.asked[0] == (EARLY, "es", ARTICLE.url)


def test_true_from_one_domain_is_not_enough():

    result = finder(answers={
        EARLY: fact_check(sources=[evidence("https://www.telemadrid.es/a", domain="telemadrid.es")]),
        RIDERS: fact_check(verdict=Verdict.FALSE),
    }).find(ARTICLE, TREND, WriterThresholds())

    assert not any(angle.kept for angle in result.angles)
    assert "supported by 1 domain other than" in result.angles[0].reason
    assert result.sources == []
    assert result.note.startswith("None of the 2 proposed angles was confirmed")


def test_one_domain_is_enough_when_a_run_asks_for_one():

    result = finder(answers={
        EARLY: fact_check(sources=[evidence("https://www.telemadrid.es/a", domain="telemadrid.es")]),
        RIDERS: fact_check(verdict=Verdict.FALSE),
    }).find(ARTICLE, TREND, WriterThresholds(angle_min_domains=1))

    assert result.angles[0].kept


def test_a_source_not_cited_or_not_supporting_does_not_count():

    result = finder(answers={
        EARLY: fact_check(sources=[
            evidence("https://www.telemadrid.es/a", domain="telemadrid.es"),
            evidence("https://www.elmundo.es/b", domain="elmundo.es", stance=EvidenceStance.UNRELATED),
            evidence("https://www.abc.es/c", domain="abc.es"),
        ], cited=[0, 1]),
        RIDERS: fact_check(verdict=Verdict.FALSE),
    }).find(ARTICLE, TREND, WriterThresholds())

    assert result.angles[0].domains == ["telemadrid.es"] and not result.angles[0].kept


def test_an_outage_is_not_a_verdict():

    result = finder(answers={
        EARLY: fact_check(verdict=Verdict.UNVERIFIED, search_unavailable=True),
        RIDERS: RuntimeError("inference down"),
    }).find(ARTICLE, TREND, WriterThresholds())

    early, riders = result.angles
    assert "search could not be done" in early.reason
    assert "could not be checked" in riders.reason


def test_no_angle_is_looked_for_in_a_disaster_or_when_the_screen_cannot_say():

    for screen, words in ((FakeScreen(kind="disaster"), "reads as disaster"),
                          (FakeScreen(error=ConnectionError("down")), "could not read the article")):
        angles = finder(answers={}, screen=screen)
        result = angles.find(ARTICLE, TREND, WriterThresholds())
        assert result.angles == [] and words in result.note
        assert angles.llm.calls == []


def test_a_politics_verdict_is_not_a_refusal():
    """Only disaster, war, crime and death refuse: the rest passed the round's screen as it was."""

    result = finder(answers={EARLY: fact_check(verdict=Verdict.FALSE), RIDERS: fact_check(verdict=Verdict.FALSE)},
                    screen=FakeScreen(kind="service")).find(ARTICLE, TREND, WriterThresholds())

    assert len(result.angles) == 2


def test_none_looked_for_when_a_run_asks_for_none():

    angles = finder()
    result = angles.find(ARTICLE, TREND, WriterThresholds(angle_max_proposals=0))

    assert result.angles == [] and "angle_max_proposals is 0" in result.note
    assert angles.llm.calls == []


def test_the_model_proposing_nothing_is_a_good_answer():

    result = finder(answer={"angles": []}).find(ARTICLE, TREND, WriterThresholds())

    assert result.angles == [] and "saw no constructive angle" in result.note


def test_an_unreachable_or_garbled_model_is_a_note_not_a_failure():

    unreachable = finder(llm_error=LLMUnavailableError("connection refused")).find(ARTICLE, TREND, WriterThresholds())
    garbled = finder(answer=None).find(ARTICLE, TREND, WriterThresholds())

    assert "could not be reached" in unreachable.note
    assert "no usable angles" in garbled.note


def test_proposals_are_held_to_a_question_a_real_claim_and_the_limit():

    proposals = parse_proposals({"angles": [
        {"question": "Q1", "claim": "Too short."},
        {"question": "", "claim": "A claim with no question at all here."},
        {"question": "Q2", "claim": "Volunteers planted nine thousand trees in the valley."},
        {"question": "Q3", "claim": "volunteers planted nine thousand trees in the valley."},
        {"question": "Q4", "claim": "The council opened two new libraries this year."},
        {"question": "Q5", "claim": "A third angle the limit leaves out of the list."},
        "not an angle",
    ]}, limit=2)

    assert [p["question"] for p in proposals] == ["Q2", "Q4"]
    assert parse_proposals({"angles": "nope"}, 3) == [] and parse_proposals(None, 3) == []


def test_the_model_is_told_the_trend_the_article_and_its_verdicts_in_its_language():

    angles = finder(answer={"angles": []})
    angles.find(ARTICLE, TREND, WriterThresholds(angle_max_proposals=2))

    system, prompt, max_tokens = angles.llm.calls[0]
    assert "at most 2 angles" in system and "Spanish" in system
    assert "never invent a bright side" in system
    assert prompt.startswith('TRENDING: "línea 10" (Google Trends · Spain, about 200+ searches)')
    assert ARTICLE.headline in prompt and '- "El tramo reabrirá a finales de noviembre." - TRUE' in prompt
    assert max_tokens == 800
    assert proposal_prompt(ARTICLE, {"name": "x"}).startswith('TRENDING: "x"')


# ----------------------------------------------------------------------
# A draft from a trend
# ----------------------------------------------------------------------


def test_a_draft_from_a_trend_records_it_and_cites_its_angles_sources(tmp_path, draft_store):

    from tests.services.writer.test_draft_writer import start
    from tests.services.writer.writer_fakes import ANALYSED_URL, make_writer, published_lake

    lake, article_id = published_lake(tmp_path)
    writer = make_writer(lake)

    ledger = TrendLedger()
    ledger.remember(ANALYSED_URL, {**TREND, "video": {"provider": "tiktok", "id": "671", "url": "https://www.tiktok.com/@a/video/671"}})
    writer.ledger = ledger

    class Angles:
        def find(self, article, trend, thresholds):
            from src.models.writer.draft import DraftAngle, DraftSource
            from src.services.trends.angles import AngleResult
            return AngleResult(
                angles=[DraftAngle(question="Q", claim="A claim that held.", kept=True, domains=["a.es", "b.es"],
                                   source_urls=["https://a.es/angle"], reason="TRUE")],
                sources=[DraftSource(url="https://a.es/angle", title="Angle", domain="a.es", origin="angle", excerpt="x")],
            )

    writer.angles = Angles()

    draft = start(writer, draft_store, article_id)

    assert draft.trend.name == "línea 10" and draft.trend.traffic == 200
    assert draft.trend.video["id"] == "671"
    assert draft.trend.angles[0].kept
    origins = [source.origin for source in draft.sources]
    assert origins[0] == "analysed" and "angle" in origins
    # After the related news, before the evidence.
    assert origins.index("angle") > max((i for i, o in enumerate(origins) if o == "related"), default=0)
    assert origins.index("angle") < min((i for i, o in enumerate(origins) if o == "evidence"), default=len(origins))


def test_a_draft_no_trend_brought_has_none(tmp_path, draft_store):

    from tests.services.writer.test_draft_writer import start
    from tests.services.writer.writer_fakes import make_writer, published_lake

    lake, article_id = published_lake(tmp_path)
    writer = make_writer(lake)
    writer.ledger = TrendLedger()
    writer.angles = None

    draft = start(writer, draft_store, article_id)

    assert draft.trend is None
    assert all(source.origin != "angle" for source in draft.sources)

import numpy as np
import pytest

from src.config.topics import TOPICS
from src.services.inference_client import InferenceUnavailable
from src.services.selection.mission_screen import (
    IMPACT,
    MARGIN,
    OFF_MISSION,
    Candidate,
    MissionScreen,
    reports_a_death,
    screen_text,
)


NAMES = [TOPICS[t].name for t in TOPICS] + [OFF_MISSION[o][0] for o in OFF_MISSION] + [IMPACT[0]]


def axis(name: str) -> np.ndarray:

    vector = np.zeros(len(NAMES))
    vector[NAMES.index(name)] = 1.0

    return vector


class FakeEmbeddings:
    """
    Every description on its own axis, so a candidate's similarity to
    each is whatever its vector says - the geometry is set by hand.
    """

    def __init__(self, candidates: dict[str, np.ndarray], fail: bool = False):
        self.candidates = candidates
        self.fail = fail
        self.calls: list[list[str]] = []

    def encode_many(self, texts):

        texts = list(texts)
        self.calls.append(texts)

        if self.fail:
            raise InferenceUnavailable("connection refused")

        # Any other text is plainly on a topic.
        return np.array([
            axis(text.strip().split("\n", 1)[0]) if text.startswith("\n")
            else self.candidates.get(text, axis(TOPICS["arts"].name))
            for text in texts
        ])


ELECTION = "Encuestas elecciones generales 29N"
MUSEUM = "Museum reopens with free entry for children"
NEAR_TIE = "A thriller about a court case wins at the film festival"
HOUSING_POLITICS = "La aritmética de la Diputación Permanente para convalidar un decreto de vivienda"
STRIKE = "UGT y CCOO convocan una huelga general de 24 horas"


def embeddings(**kwargs) -> FakeEmbeddings:

    return FakeEmbeddings({
        # Nearer politics than any topic by 0.10.
        ELECTION: 0.6 * axis("Politics") + 0.5 * axis(TOPICS["cities"].name),
        # Nearer a topic than anything off-mission, and near positive impact.
        MUSEUM: 0.7 * axis(TOPICS["arts"].name) + 0.68 * axis("Service pages") + 0.55 * axis(IMPACT[0]),
        # Off-mission ahead, but by less than MARGIN: kept.
        NEAR_TIE: (0.5 + MARGIN * 0.75) * axis("Crime") + 0.5 * axis(TOPICS["entertainment"].name),
        # Politics ahead by as little: politics needs no lead (MARGINS).
        HOUSING_POLITICS: (0.5 + MARGIN * 0.25) * axis("Politics") + 0.5 * axis(TOPICS["cities"].name),
        # 2026-10-06: a general strike, near "cities" by its housing demands.
        STRIKE: 0.62 * axis("Labour disputes and protests") + 0.5 * axis(TOPICS["cities"].name),
    }, **kwargs)


def titled(*titles: str, language: str = "en") -> list[Candidate]:

    return [Candidate(title=title, summary=None, language=language) for title in titles]


def test_a_candidate_nearer_something_off_mission_than_any_topic_is_left_out():

    screen = MissionScreen(embedding_service=embeddings())

    election, museum = screen.screen(titled(ELECTION, MUSEUM))

    assert election.off_mission == "politics"
    assert election.nearest_topic == "cities"
    assert election.margin == pytest.approx(0.1)
    assert museum is None


def test_a_strike_is_a_labour_dispute_not_a_story_about_housing():

    [verdict] = MissionScreen(embedding_service=embeddings()).screen(titled(STRIKE, language="es"))

    assert verdict.off_mission == "labour"


def test_only_a_lead_larger_than_the_margin_counts():

    [verdict] = MissionScreen(embedding_service=embeddings()).screen(titled(NEAR_TIE))

    assert verdict is None


def test_politics_needs_only_to_be_nearer_than_any_topic():
    """Housing politics sits close to "cities"; 14 of 15 such items under MARGIN were party politics."""

    [verdict] = MissionScreen(embedding_service=embeddings()).screen(titled(HOUSING_POLITICS, language="es"))

    assert verdict.off_mission == "politics"
    assert 0 < verdict.margin < MARGIN


def test_an_empty_candidate_is_kept_and_never_embedded():

    service = embeddings()

    verdicts = MissionScreen(embedding_service=service).screen(
        [Candidate(title=None, summary=None), *titled(ELECTION), Candidate(title="  ", summary="")]
    )

    assert verdicts[0] is None and verdicts[2] is None
    assert verdicts[1].off_mission == "politics"
    assert service.calls[-1] == [ELECTION]


def test_the_descriptions_are_embedded_once_per_screen():

    service = embeddings()
    screen = MissionScreen(embedding_service=service)

    screen.screen(titled(ELECTION))
    screen.screen(titled(MUSEUM))

    assert len(service.calls) == 3
    # IMPACT is read in the same pass, for the ranking.
    assert len(service.calls[0]) == len(TOPICS) + len(OFF_MISSION) + 1


def test_an_unreachable_model_raises_and_leaves_nothing_half_built():

    service = embeddings(fail=True)
    screen = MissionScreen(embedding_service=service)

    with pytest.raises(InferenceUnavailable):
        screen.screen(titled(ELECTION))

    service.fail = False

    assert screen.screen(titled(ELECTION))[0].off_mission == "politics"


# ----------------------------------------------------------------------
# The reading behind each verdict, for the ranking
# ----------------------------------------------------------------------


def test_each_kept_candidate_comes_with_what_the_embeddings_said():

    [museum] = MissionScreen(embedding_service=embeddings()).assess(titled(MUSEUM))

    assert museum.verdict is None
    assert (museum.reading.nearest_topic, museum.reading.nearest_off) == ("arts", "service")
    assert (museum.reading.topic, museum.reading.off, museum.reading.impact) == pytest.approx((0.7, 0.68, 0.55))
    assert museum.reading.margin == pytest.approx(-0.02)
    assert museum.reading.to_dict()["nearestOff"] == "service"
    # Its own embedding too, for telling one story told twice; never recorded.
    assert museum.reading.vector is not None and "vector" not in museum.reading.to_dict()


def test_an_exempt_candidate_is_read_but_never_left_out():
    """A positive outlet's: its editors chose; the ranking still needs its reading."""

    election, death = MissionScreen(embedding_service=embeddings()).assess(
        titled(ELECTION, "Muere un poeta", language="es"), exempt=[True, True],
    )

    assert election.verdict is None and election.reading.nearest_off == "politics"
    assert death.verdict is None and death.reading is not None


def test_a_death_report_has_no_reading():

    [death] = MissionScreen(embedding_service=embeddings()).assess(titled("Muere un poeta", language="es"))

    assert death.verdict.off_mission == "obituary" and death.reading is None


def test_a_candidate_is_judged_by_its_title_and_summary():

    assert screen_text("Title", "Summary.") == "Title. Summary."
    assert screen_text("Title", None) == "Title"
    assert screen_text(None, None) == ""


# ----------------------------------------------------------------------
# Death reports, by the headline
# ----------------------------------------------------------------------


@pytest.mark.parametrize("title, language", [
    ("Author and former politician Jeffrey Archer dies aged 86", "en"),
    ("Kwame Brathwaite, photographer of 'Black is Beautiful' movement, dies at 85", "en"),
    ("Muere Jeffrey Archer, el escritor británico superventas", "es"),
    ("Fallece a los 92 años el poeta que", "es"),
    ("Muere novelista politico conservador britanico jeffrey archer nt", "es"),
])
def test_a_headline_reporting_a_death_is_a_death_report(title, language):

    assert reports_a_death(title, language)


@pytest.mark.parametrize("title, language", [
    # History is told in the past tense, news of a death in the present.
    ("Carlos II, el último Habsburgo de España, reinó en una época convulsa y murió sin descendencia", "es"),
    ("These Soldiers Were Buried in an Unmarked Grave During the Revolutionary War", "en"),
    ("La edad del habla: lo que la voz humana revela sobre el envejecimiento cerebral", "es"),
    ("Why the dinosaurs died out", "en"),
    (None, "en"),
])
def test_history_and_research_about_ageing_are_not(title, language):

    assert not reports_a_death(title, language)


def test_a_death_report_is_left_out_without_asking_the_model():

    service = embeddings()

    [verdict] = MissionScreen(embedding_service=service).screen(
        titled("Muere Jeffrey Archer, el escritor británico superventas", language="es")
    )

    assert verdict.off_mission == "obituary"
    assert verdict.margin is None and verdict.nearest_topic is None
    assert service.calls == []


def test_the_death_report_is_read_in_the_headline_only():
    """A summary saying something "dies at" the end of the year is no obituary."""

    service = embeddings()

    [verdict] = MissionScreen(embedding_service=service).screen(
        [Candidate(title=MUSEUM, summary="Without it the town's museum dies at the end of the year.", language="en")]
    )

    assert verdict is None
    assert service.calls != []

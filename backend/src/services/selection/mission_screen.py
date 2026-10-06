"""
The mission screen: drops discovery candidates that are plainly not what
this publication is for, from their title and summary, before anyone
chooses among them.

Discovery reads general feeds (El País's, ABC's, 20minutos's front pages)
filtered by topic keywords, and keywords say nothing about tone. A
2026-10-06 Culture round listed election polls, a tanker crash and a
cancelled concert beside a free-music-education programme. The AI
selection would have scored them low, but it is optional and slow, and a
person reading the list should not have to wade through them.

Two judgements, cheapest first:

1. **A death report** - a headline with one of the language's
   `death_report` phrases ("dies aged", "muere"; src/config/lexicons.py),
   title only. An embedding cannot do this one: it takes an obituary and
   a biography for the same thing (see below).
2. **Nearest meaning.** Each candidate's title and summary are embedded
   once and compared with the 23 topics' own descriptions (the
   classifier's) and with descriptions of what the publication never
   covers (OFF_MISSION). A candidate is dropped when its nearest
   off-mission description is closer than its nearest topic by more than
   MARGIN - in any language the embedding model reads (bge-m3: Spanish
   titles against English descriptions).

Measured twice on live candidates (docs/experiments.md). First, 527 from
Culture, Society and Health rounds: with the first seven descriptions,
68 of the 484 from general outlets above MARGIN, nearly all elections,
crime, accidents, storms, market wire items and celebrity interviews; the
doubtful ones four National Geographic war-history pieces and one
data-centre regulation story. Below MARGIN the mistakes grow (a UN story
on breaking prison stigma, a tourism record), so it stays: a screen for
the obvious, not a judge of positive impact - that is still the AI
selection's and the person's, and admission's after them.

Second, the same 527 plus a Science and Society round's 114, after that
round still listed a general strike three times, ABC's mortgage and tax
calculators and a drone strike in Gaza: `labour` and `markets` were added,
`politics` and `conflict` widened. Above MARGIN 115 of 545 instead of 80;
every one of the 36 new is a strike, a union-employer dispute, a protest,
markets and personal finance, election politics, the drone strike or an
outbreak at a military academy, and one item came back in (a TV
reaction to the election call). An `obituary` description was tried and
dropped: worded broadly it left out research on ageing and the
Smithsonian's identified Revolutionary War soldiers; worded narrowly,
pieces on Unamuno and a poet's letters, while "Jeffrey Archer dies aged
86" got through. Hence the death-report phrases.

What it does not use, and why: the sentiment model. On the first sample
it rated an endangered primate's birth 0.89 negative, a lost theatre
reborn 0.89 and restoring hearing 0.62 - a story about a problem being
solved reads as negative.

Outlets with `positive_editorial` are not screened: their editors already
chose, and the screen would have dropped Good News Network's
ex-prisoners-as-firefighters jobs story as "crime". Their items are still
read (`assess`, `exempt`): the ranking needs the same reading of every
candidate (src/services/selection/ranking.py).

Needs inference/ (the embeddings). When it is unreachable the caller keeps
every candidate and says the screen did not run - never a silent pass.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from threading import Lock

import numpy as np

from src.config.lexicons import lexicon_for
from src.config.topics import TOPICS
from src.services.embeddings.service import EmbeddingService


# What the publication never covers, described the way TOPICS describes
# what it does - name, description, keywords - so both sides of the
# comparison are the same kind of text. English, like TOPICS: the model
# is multilingual. Changing a description changes the measurements above.
OFF_MISSION = {
    "politics": (
        "Politics",
        "Party politics, elections, opinion polls, parliament votes, government decrees and coalitions, political crises, political campaigns and politicians' statements.",
        ["elections", "polls", "parliament", "decree", "coalition", "minister", "party", "vote", "campaign", "opposition"],
    ),
    "labour": (
        "Labour disputes and protests",
        "Strikes, general strikes, trade unions against employers' associations, demonstrations, marches, riots and clashes with police.",
        ["strike", "general strike", "trade union", "employers", "protest", "demonstration", "march", "riot"],
    ),
    "crime": (
        "Crime",
        "Crime, police investigations, arrests, murders, robberies, court trials and prison sentences.",
        ["police", "arrest", "murder", "court", "trial", "prison", "crime", "robbery"],
    ),
    "disaster": (
        "Accidents and disasters",
        "Accidents, traffic collisions, fires, floods, storms, natural disasters, deaths, cancellations and emergencies.",
        ["accident", "crash", "fire", "flood", "dead", "killed", "emergency", "cancelled"],
    ),
    "conflict": (
        "War and conflict",
        "War, armed conflict, terrorism, military attacks, airstrikes and drone attacks, bombings, invasions, casualties and violence.",
        ["war", "army", "attack", "airstrike", "drone attack", "bombing", "terrorism", "missile", "soldiers", "killed and wounded"],
    ),
    "celebrity": (
        "Celebrity",
        "Celebrity gossip, famous actors' private lives, red carpets, fashion, influencers, showbiz interviews and television stars.",
        ["celebrity", "actor", "actress", "star", "gossip", "red carpet", "influencer", "fashion"],
    ),
    "sport": (
        "Sport",
        "Sports results, football matches, leagues, transfers, races and athletes' competitions.",
        ["football", "match", "league", "goal", "team", "championship", "race", "coach"],
    ),
    "markets": (
        "Markets and personal finance",
        "Stock markets, share prices, inflation forecasts, interest rates, treasury auctions, bank mergers, mortgages, tax calculators, savings accounts, investment tips and coins worth money.",
        ["stock market", "shares", "inflation", "interest rates", "mortgage", "taxes", "savings", "investment", "bank", "coins"],
    ),
    "service": (
        "Service pages",
        "Weather forecasts, traffic updates, lottery results, horoscopes, TV schedules, shopping deals and live blogs.",
        ["weather", "traffic", "lottery", "horoscope", "schedule", "deals", "live", "discount"],
    ),
}

# Not a reason to leave anything out: what the ranking measures each
# candidate against (src/services/selection/ranking.py) - how much nearer
# it is to this than to its nearest OFF_MISSION description. Embedded with
# the screen's own labels, in the same pass. Written before it was
# measured; two other wordings, the AI selector's DEFINITION among them,
# separated the hand-labelled candidates as well within noise
# (docs/experiments.md).
IMPACT = (
    "Positive impact",
    "A real change that improves things for people or the planet: progress, a solution that works, a recovery, a discovery with a use, people helping others, a breakthrough, an award for an achievement.",
    ["solution", "progress", "breakthrough", "recovery", "discovery", "improves", "helps", "success", "achievement", "hope"],
)

# Left out by its headline, not by the embeddings (see the docstring).
OBITUARY = "obituary"

# How much closer the nearest off-mission description must be than the
# nearest topic. Chosen on the measurements in the module docstring.
MARGIN = 0.04

# Politics is held to less: nearer it than to any topic is enough. Its
# stories sit close to the topics that are their subject - housing
# politics to "cities", budget fights to "climate" - and in the second
# measurement 14 of the 15 nearest politics between 0 and MARGIN were
# party politics (Feijóo's promises, the Diputación Permanente's
# arithmetic, regional elections); the one that was not, workers' new
# right to company information. No other category's band was that clean:
# crime's held a UN story on breaking prison stigma.
MARGINS = {"politics": 0.0}

# Candidates per request to inference/: one permit each (concurrency.py).
BATCH = 32


@dataclass(frozen=True)
class Candidate:
    """What the screen reads of one candidate."""

    title: str | None

    summary: str | None

    # The source's; picks the death-report phrases.
    language: str | None = None


@dataclass(frozen=True)
class Verdict:
    """Why a candidate was left out."""

    off_mission: str

    # Nearest off-mission similarity minus nearest topic similarity;
    # None when the headline decided (a death report).
    margin: float | None = None

    # The topic it came closest to, for whoever reads the round; None
    # when the headline decided.
    nearest_topic: str | None = None


@dataclass(frozen=True)
class Reading:
    """What the embeddings say about one candidate, as cosine similarities."""

    nearest_topic: str

    topic: float

    nearest_off: str

    off: float

    # Nearness to IMPACT.
    impact: float

    # The candidate's own embedding, which the ranking compares candidates
    # by to find the same story twice. Not recorded with the round.
    vector: np.ndarray | None = field(default=None, repr=False, compare=False)

    @property
    def margin(self) -> float:
        """What the screen judges by: nearest off-mission minus nearest topic."""

        return self.off - self.topic

    def to_dict(self) -> dict:

        return {
            "nearestTopic": self.nearest_topic,
            "topic": round(self.topic, 4),
            "nearestOff": self.nearest_off,
            "off": round(self.off, 4),
            "impact": round(self.impact, 4),
        }


@dataclass(frozen=True)
class Assessment:
    """One candidate's verdict (None: kept) and the reading behind it."""

    verdict: Verdict | None

    # None when nothing was embedded: a death report, decided by its
    # headline, or a candidate with nothing to read.
    reading: Reading | None = None


def _describe(name: str, description: str, keywords: list[str]) -> str:
    # TopicClassifier's layout without its indentation - the text the
    # measurement embedded, so MARGIN means what it was measured as.
    return f"\n{name}\n{description}\nKeywords:\n{', '.join(keywords)}\n"


def screen_text(title: str | None, summary: str | None) -> str:
    """What a candidate is judged by: its title and summary, as the experiment read them."""

    return ". ".join(part for part in (title, summary) if part and part.strip())


_NOT_WORD = re.compile(r"[^\w]+")


def _folded(text: str) -> str:
    """Lower case, no accents, single spaces, padded: " muere jeffrey archer "."""

    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))

    return " " + _NOT_WORD.sub(" ", plain).strip() + " "


def reports_a_death(title: str | None, language: str | None) -> bool:
    """Whether a headline reports someone's death, by its language's `death_report` phrases."""

    if not title:
        return False

    folded = _folded(title)

    return any(f" {_folded(phrase).strip()} " in folded for phrase in lexicon_for(language).death_report)


class MissionScreen:

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        margin: float = MARGIN,
        margins: dict[str, float] | None = None,
    ):

        self.embedding_service = embedding_service or EmbeddingService()
        self.margin = margin
        self.margins = MARGINS if margins is None else margins

        # (topic ids, off-mission ids, one row per description, IMPACT
        # last), embedded on first use - the ingestion service that holds
        # this screen is a process singleton. Assigned whole: a failure
        # partway leaves None, not a half-filled cache (the TopicClassifier
        # lesson).
        self._labels: tuple[list[str], list[str], np.ndarray] | None = None
        self._labels_lock = Lock()

    def screen(self, candidates: list[Candidate]) -> list[Verdict | None]:
        """
        One verdict per candidate, in order: None to keep it. A candidate
        with neither title nor summary is kept - there is nothing to
        judge. Raises InferenceUnavailable when inference/ cannot be
        reached; the caller decides what that means.
        """

        return [assessment.verdict for assessment in self.assess(candidates)]

    def assess(self, candidates: list[Candidate], exempt: list[bool] | None = None) -> list[Assessment]:
        """
        `screen`, with the reading behind each verdict. An `exempt`
        candidate (a positive outlet's) is read but never left out.
        """

        exempt = exempt or [False] * len(candidates)

        verdicts: list[Verdict | None] = [
            Verdict(off_mission=OBITUARY)
            if not spared and reports_a_death(candidate.title, candidate.language)
            else None
            for candidate, spared in zip(candidates, exempt)
        ]

        readings: list[Reading | None] = [None] * len(candidates)

        texts = [screen_text(candidate.title, candidate.summary) for candidate in candidates]
        to_read = [i for i, text in enumerate(texts) if text and verdicts[i] is None]

        if to_read:

            topic_ids, off_ids, labels = self._label_vectors()

            for start in range(0, len(to_read), BATCH):

                chunk = to_read[start:start + BATCH]
                vectors = np.asarray(self.embedding_service.encode_many([texts[i] for i in chunk]))
                similarities = vectors @ labels.T

                for i, vector, row in zip(chunk, vectors, similarities):

                    on = row[: len(topic_ids)]
                    off = row[len(topic_ids): len(topic_ids) + len(off_ids)]

                    reading = Reading(
                        nearest_topic=topic_ids[int(on.argmax())],
                        topic=float(on.max()),
                        nearest_off=off_ids[int(off.argmax())],
                        off=float(off.max()),
                        impact=float(row[-1]),
                        vector=vector,
                    )
                    readings[i] = reading

                    if not exempt[i] and reading.margin > self.margins.get(reading.nearest_off, self.margin):
                        verdicts[i] = Verdict(
                            off_mission=reading.nearest_off,
                            margin=round(reading.margin, 4),
                            nearest_topic=reading.nearest_topic,
                        )

        return [Assessment(verdict, reading) for verdict, reading in zip(verdicts, readings)]

    def _label_vectors(self) -> tuple[list[str], list[str], np.ndarray]:

        if self._labels is None:

            with self._labels_lock:

                if self._labels is None:

                    topic_ids = list(TOPICS)
                    off_ids = list(OFF_MISSION)

                    texts = [_describe(TOPICS[t].name, TOPICS[t].description, TOPICS[t].keywords) for t in topic_ids]
                    texts += [_describe(*OFF_MISSION[o]) for o in off_ids]
                    texts += [_describe(*IMPACT)]

                    labels = np.asarray(self.embedding_service.encode_many(texts))

                    self._labels = (topic_ids, off_ids, labels)

        return self._labels

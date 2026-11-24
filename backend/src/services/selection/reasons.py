"""
Why a person chose a story: the reasons offered on /discover, one
definition for the page, the check and the analysis.

Asked for on 2026-11-24, with the person's five against the AI's
(docs/decisions/selection.md, "Why each pick"): beside each pick, buttons
that can be on together - trending, adding variety, positive, fitting the
topic, and others that fit the newsroom - so a choice says *why this one
and not another*, and the comparison can say for which reasons the AI
chose the same stories. A free-text note stays beside them.

Per edition, because two of them name what the edition is for: positive
impact and a solution in the Positive one, serious harm and holding power
to account in the Devastating one. The rest are the same in both. Codes
are what is stored; labels and hints are what the page shows.

And why a story is *not* for us (`reject_reasons_for`, 2026-11-24): what
a person says when they mark a candidate "Not for us", which teaches the
ranking (feedback.py). Kept beside the rejection, so what was rejected
for what can be read back; the ranking itself learns from the story, not
from the reason.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PickReason:

    id: str
    label: str
    hint: str

    def to_dict(self) -> dict:
        return asdict(self)


# What the story itself is for, per edition: first, since it is the
# question the edition asks of every story.
_OWN = {
    "positive": (
        PickReason("positive", "Positive impact", "A real change that makes things better for people or the planet."),
        PickReason("solution", "Shows a solution", "How a problem is being solved, and whether it works."),
    ),
    "devastating": (
        PickReason("harm", "Serious harm", "Hurts many people, or the planet, in a way that matters."),
        PickReason("accountability", "Holds power to account", "Says who is responsible."),
    ),
}

# The same in both editions.
_SHARED = (
    PickReason("topic", "Fits the topic", "Squarely in the topics picked for this round."),
    PickReason("trending", "Trending", "People are searching for it or sharing it now."),
    PickReason("diversity", "Adds variety", "A subject, place, community or outlet the other picks do not cover."),
    PickReason("evidence", "Well sourced", "Rests on data, a study or an official source a check can find."),
    PickReason("audience", "For our readers", "Speaks to readers aged 15 to 30 (docs/decisions/writing.md)."),
    PickReason("original", "Original reporting", "The outlet did the work, not a repost of someone else's."),
    PickReason("visual", "Strong photo", "Its picture can carry a carousel or a story."),
)


def reasons_for(edition: str = "positive") -> list[PickReason]:
    """The reasons offered for a pick in `edition`, in the order the page shows them."""

    return [*_OWN.get(edition, _OWN["positive"]), *_SHARED]


class UnknownReason(ValueError):
    pass


def cleaned(reasons: dict | None, chosen: list[str], edition: str = "positive") -> dict[str, list[str]]:
    """
    {url: [codes]} for the chosen urls that were given any, each list in
    the catalogue's order with no repeats. A reason for a url not chosen
    is dropped, like a note; a code the edition does not offer raises
    UnknownReason, so a page out of date cannot store words nobody defined.
    """

    order = [reason.id for reason in reasons_for(edition)]
    kept: dict[str, list[str]] = {}

    for url, codes in (reasons or {}).items():

        if url not in chosen or not isinstance(codes, list):
            continue

        unknown = [code for code in codes if code not in order]

        if unknown:
            raise UnknownReason(f"Not a reason offered in this edition: {unknown[0]}")

        given = [code for code in order if code in codes]

        if given:
            kept[url] = given

    return kept


# Why a story is not for us. The first says the edition's question was
# answered no; the rest name what it is instead, as the mission screen's
# categories do (mission_screen.OFF_MISSION), for what slipped through it.
_NOT_OWN = {
    "positive": (PickReason("no_impact", "No positive impact", "Nothing in it makes things better for anyone."),),
    "devastating": (PickReason("no_harm", "Not serious harm", "Bad, but not harm that matters to many."),),
}

_NOT_SHARED = (
    PickReason("politics", "Politics", "Party politics, campaigns, parliament."),
    PickReason("crime", "Crime or conflict", "Crime, courts, war, violence."),
    PickReason("celebrity", "Celebrity or gossip", "Famous people's lives, lifestyle, entertainment."),
    PickReason("ads", "Ads or shopping", "Promotion, products, deals, sponsored content."),
    PickReason("service", "Service page", "Calculators, weather, timetables, how-tos."),
    PickReason("opinion", "Opinion", "A column or an editorial, not reporting."),
    PickReason("off_topic", "Off-topic", "Not in the topics picked for this round."),
    PickReason("old", "Old news", "Happened long ago, or already told."),
)


def reject_reasons_for(edition: str = "positive") -> list[PickReason]:
    """Why a person may say a story is not for us in `edition`, in the order the page shows them."""

    return [*_NOT_OWN.get(edition, _NOT_OWN["positive"]), *_NOT_SHARED]


def cleaned_codes(codes, offered: list[PickReason]) -> list[str]:
    """`codes` in the catalogue's order, no repeats; UnknownReason for one not offered."""

    order = [reason.id for reason in offered]
    codes = codes if isinstance(codes, list) else []
    unknown = [code for code in codes if code not in order]

    if unknown:
        raise UnknownReason(f"Not a reason offered in this edition: {unknown[0]}")

    return [code for code in order if code in codes]

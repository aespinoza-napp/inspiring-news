"""
What a claim turns on - the "checkable point" - found before anything is
searched, without a model (`query_plan: checkable`).

Why this exists (docs/troubleshooting/01-what-to-look-for.md, 4 Nov 2026):
on the first 20 train claims, 16 turned on a figure, a date or a named
place, and the pipeline's queries carried none of them. Three causes, each
seen there:

- **The figures never reached the query.** The anchor query quotes
  `claim.facts.figures`, but only the article pipeline's ClaimExtractor
  fills `facts`; a claim built by ClaimService (`POST /verify-claim`, and
  so every evaluation-harness run) has none. "212 travel-related cases" was
  searched as `Florida` and `Florida been total known travel related cases`.
- **The figures that were found were the wrong ones.** ClaimExtractor's
  number pattern splits "SE-20" into "20", "14:49" into "14" and "49", and
  "11-set" into "11": the road's name, the time and the count's noun lost.
- **The words kept were the sentence's filler**: "Meanwhile", "Indeed",
  "been", "another" took places the assertion's nouns needed.

So the point is read from the sentence itself, every time: identifiers
kept whole (SE-20, COVID-19), times, counts with their noun (11-set), the
other figures most distinctive first, dates with their day, the names, and
the assertion's remaining words without the filler. The query planner
builds from it (query_builder.plan_queries), and it goes out with the
`searching_web` event so a run's record says what was looked for.

Deterministic on purpose: a model call per claim is seconds on this
project's CPU (docs/decisions/performance.md), and `claim_restatement`
already offers the model's version, to be measured beside this one.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from src.config.lexicons import lexicon_for
from src.models.core.claim import Claim
from src.services.fact_checker.terms import MAX_SUBJECT_TERMS, acronyms, content_terms, fold

# A name with a number in it: a road (SE-20, A-4), a disease (COVID-19), a
# model. One identifier, which the number alone does not identify.
IDENTIFIER = re.compile(r"\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑ]{0,5}-\d{1,4}[A-Za-z]?\b")

# A count bound to its noun by a hyphen: "11-set", "17-set", "3-day".
COUNTED = re.compile(r"\b\d{1,4}-[^\W\d_]{2,}\b", re.UNICODE)

# A clock time: 14:49, 17.58 when an hour word is near enough to say so.
TIME = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")

# A figure: a percentage, a number with thousands separators or decimals,
# or a plain one. "per cent" / "por ciento" spelt out count as a percentage.
PERCENT = re.compile(r"\d+(?:[.,]\d+)*\s*(?:%|per ?cent\b|percent\b|por ciento\b)", re.IGNORECASE)
NUMBER = re.compile(r"(?<![\w.,:-])\d+(?:[.,]\d+)*(?![\w-]|[.,:]\d)")

YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

# A figure's scale belongs to it: "25 millones" is a different search from
# "25", and the scale word alone is nothing to look for.
SCALE = re.compile(
    r"\d+(?:[.,]\d+)*\s+(?:million|millions|billion|billions|trillion|thousand|"
    r"millón|millon|millones|mil millones|billón|billones|mil)\b",
    re.IGNORECASE,
)

# The words that may join a multi-word name without being one: "Ignacio
# Calvo de Mora", "Benjamin de Rothschild & Vega Sicilia", "University of Oslo".
# Not "and" / "y": "Eastlands and Kaloleni" is two libraries.
NAME_JOINERS = {"de", "del", "la", "las", "los", "of", "the", "&"}

# A day with its month, in either order and either language:
# "12 September", "September 24", "24 de septiembre".
_DAY = r"(?:[12]?\d|3[01])"

# Words that are never what a claim is about - discourse markers and
# hedges the stopword lists do not hold, found in the 4 Nov comparison's
# queries ("Meanwhile Arctic", "Florida been total known", "Indeed
# example"). Both languages, like every lexicon here (invariant 8).
FILLERS = {
    "en": {
        "meanwhile", "indeed", "however", "moreover", "furthermore", "also", "been", "being",
        "another", "others", "perhaps", "several", "making", "currently", "completely",
        "including", "across", "leading", "becoming", "using", "decided", "according",
        "said", "says", "statement", "write", "wrote", "there", "here", "total", "known",
        "next", "last", "example", "remarkable", "found",
    },
    "es": {
        "mientras", "además", "ademas", "asimismo", "también", "tambien", "entorno", "unas",
        "unos", "hace", "tanto", "modo", "será", "sera", "pasará", "pasara", "cuando",
        "según", "segun", "dijo", "afirmó", "afirmo", "señaló", "senalo", "tras", "pues",
        "incluso", "ejemplo", "total", "decidiera", "después", "despues",
    },
}

DISTINCTIVE = re.compile(r"[%.,]|cent|ciento|\d{3}|[^\W\d_]{3,}$", re.IGNORECASE)

# A headline's verbs and framing words: never the subject it restores
# ("prompts", "finds", "hits" in "Dengue fever outbreak prompts Florida
# counties..."). Both languages.
HEADLINE_WORDS = {
    "en": {
        "finds", "find", "found", "prompts", "persists", "hits", "reveals", "reveal", "shows", "show",
        "says", "may", "might", "could", "would", "discovered", "discovers", "starting", "starts",
        "begins", "becomes", "gets", "makes", "takes", "sees", "warns", "new", "first", "how", "why",
        "what", "when", "who", "into", "after", "amid", "over", "says", "here", "this", "that",
    },
    "es": {
        "revela", "muestra", "llega", "logra", "dice", "hace", "tras", "nuevo", "nueva", "nuevos",
        "nuevas", "primer", "primera", "cómo", "como", "qué", "que", "por", "para", "sobre", "ante",
        "unirán", "uniran", "será", "sera", "tiene", "busca", "abre",
    },
}

# A headline ends with its site often enough to strip: "... | New Scientist",
# "... - Carbon Brief". A last segment of at most this many words goes.
SITE_SUFFIX_WORDS = 4

MAX_HEADLINE_SUBJECT = 3

MAX_NAMES = 4
MAX_FIGURES = 3
MAX_TERMS = 6


@dataclass(frozen=True)
class CheckablePoint:
    """What a claim turns on, in the order a search should care about it."""

    names: list[str] = field(default_factory=list)
    subject: list[str] = field(default_factory=list)
    # The headline the subject was read from, when it was (`title_subject`).
    headline: str = ""
    identifiers: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    @property
    def distinctive_figures(self) -> list[str]:
        """
        The figures a page could only state if it were about this: a
        percentage, a decimal, a separator, a scale ("25 millones") or three
        digits. "10" or "68" alone match too much of the web to search on.
        """

        return [figure for figure in self.figures if DISTINCTIVE.search(figure)]

    @property
    def specific(self) -> bool:
        """
        Whether the claim carries something a page has to state to settle it:
        an identifier, a distinctive figure or a day-month date. A year alone
        does not ("2017 Founded writer publisher" found nothing in particular).
        """

        return bool(self.identifiers or self.distinctive_figures or any(not YEAR.fullmatch(d) for d in self.dates))

    def as_dict(self) -> dict:

        return asdict(self)


def _months(language: str | None) -> str:

    names = sorted(
        {word.rstrip("*") for word in lexicon_for("en").month_names | lexicon_for("es").month_names
         | lexicon_for(language).month_names},
        key=len, reverse=True,
    )

    return "|".join(re.escape(name) for name in names if name)


def dates_of(text: str, language: str | None = None) -> list[str]:
    """Day-month pairs first (they pin an event to a day), then years."""

    months = _months(language)

    day_month = re.compile(
        rf"\b{_DAY}\s+(?:de\s+)?(?:{months})\b|\b(?:{months})\s+{_DAY}\b",
        re.IGNORECASE,
    )

    found = [match.group(0) for match in day_month.finditer(text)]

    found += YEAR.findall(text)

    return _unique(found)


def figures_of(text: str) -> tuple[list[str], list[str]]:
    """
    `(identifiers, figures)`. Identifiers, counts and times are taken out of
    the text first, so their numbers are not reported again on their own;
    years are dates, not figures. Figures are ordered most distinctive
    first: a percentage or a number with separators or decimals, then by
    length. A single digit says too little to search for.
    """

    identifiers = _unique(IDENTIFIER.findall(text) + COUNTED.findall(text) + TIME.findall(text))

    rest = text

    for token in identifiers:
        rest = rest.replace(token, " ")

    percents = [re.sub(r"\s+", " ", match).strip() for match in PERCENT.findall(rest) + SCALE.findall(rest)]

    for token in percents:
        rest = rest.replace(token, " ")

    numbers = [number for number in NUMBER.findall(rest) if not YEAR.fullmatch(number) and len(re.sub(r"\D", "", number)) > 1]

    def distinctive(figure: str) -> tuple:
        digits = re.sub(r"\D", "", figure)
        return (bool(re.search(r"[%.,]|cent|ciento", figure)), len(digits))

    figures = _unique(percents + sorted(numbers, key=distinctive, reverse=True))

    return identifiers, figures


def headline_of(title: str) -> str:
    """The headline without its site's name: "X | New Scientist" -> "X"."""

    for separator in (" | ", " - ", " — ", " – "):
        if separator in title:
            head, _, last = title.rpartition(separator)
            if head.strip() and len(last.split()) <= SITE_SUFFIX_WORDS:
                return head.strip()

    return title.strip()


def title_subject(
    title: str,
    claim_text: str,
    language: str | None = None,
    sentences: list[str] | None = None,
) -> list[str]:
    """
    What the headline says the claim is about and the sentence does not:
    its words absent from the claim **that the article's other sentences
    repeat**, in the headline's order, without stopwords, filler or the
    headline's own verbs. Three-letter words count here ("sea ice"), unlike
    in `content_terms`: a headline's short nouns are often the subject.

    The repetition is the test, as the article's keywords are in
    terms.subject_terms: tried on the headline alone, a third of the 69 train
    claims came back with its framing ("querida suegra tengo gusto", "oddest
    even odder thought"). No other sentence, no subject.

    The 4 Nov comparison's reason: "There have been a total of 212 known
    travel-related cases in Florida" never says dengue; its headline does
    ("Dengue fever outbreak prompts Florida counties to declare state of
    emergency"), and every query searched without it.
    """

    code = (language or "en").lower()[:2]

    lexicon = lexicon_for(language)

    excluded = (
        {fold(word) for word in lexicon.stopwords | lexicon.query_noise}
        | {fold(word) for word in FILLERS.get(code, FILLERS["en"]) | HEADLINE_WORDS.get(code, HEADLINE_WORDS["en"])}
    )

    in_claim = {fold(token) for token in re.findall(r"[^\W_]+", claim_text)}

    def said(word: str) -> bool:
        # "pregnancy" in the claim says "pregnancies" in the headline.
        folded = fold(word)
        return folded in in_claim or (len(folded) >= 6 and any(t[:5] == folded[:5] and len(t) >= 6 for t in in_claim))

    article = {fold(token) for sentence in sentences or [] for token in re.findall(r"[^\W_]+", sentence)}

    def repeated(word: str) -> bool:
        folded = fold(word)
        return folded in article or (len(folded) >= 6 and any(t[:5] == folded[:5] and len(t) >= 6 for t in article))

    words = re.findall(r"[^\W\d_]{3,}|\b[A-Z]{2}\b", headline_of(title))

    return _unique([
        word for word in words if fold(word) not in excluded and not said(word) and repeated(word)
    ])[:MAX_HEADLINE_SUBJECT]


def lost_subject(claim: Claim, context, language: str | None = None) -> list[str]:
    """
    The article's subject words (its headline's words that its keywords
    hold, as terms.subject_terms reads them) that the sentence does not say.

    Not subject_terms itself, which is all or nothing: when the sentence
    names any one subject word it restores none, so "212 known
    travel-related cases in Florida", whose article is about dengue in
    Florida, kept "Florida" and lost "dengue" in the app too. Here each word
    the sentence lacks comes back on its own. subject_terms keeps its rule
    for the sentence plan and the ranker.
    """

    if not context.title or not context.keywords:
        return []

    keyword_tokens = {token for keyword in context.keywords for token in re.findall(r"[^\W_]+", fold(keyword))}

    in_claim = {fold(token) for token in re.findall(r"[^\W_]+", claim.text)}

    return [
        word for word in content_terms(context.title, language)
        if fold(word) in keyword_tokens and fold(word) not in in_claim
    ][:MAX_SUBJECT_TERMS]


def name_groups(text: str, excluded: set[str]) -> list[str]:
    """
    Runs of capitalised words, joined across "de", "of", "&": "Ronda Urbana
    Norte", "James Michael Roe", "Mahale Mountains". A single capitalised
    word opening the sentence is left out, since every sentence starts with
    one ("Meanwhile", "Founded"); a run that opens it is kept ("Ignacio Calvo
    de Mora"). A word in `excluded` (stopwords, fillers, months) breaks a run.
    """

    groups: list[list[str]] = []
    current: list[str] = []
    starts_sentence: list[bool] = []
    first = True

    def close():
        nonlocal current
        while current and current[-1].lower() in NAME_JOINERS:
            current.pop()
        if current:
            groups.append(current)
            starts_sentence.append(opened)
        current = []

    opened = False

    for raw in text.split():

        # An opening bracket starts a new run: "Vega Sicilia (Macán)" is a
        # name and its gloss, not one name.
        if raw[:1] in "([":
            close()

        bare = raw.strip("\"'“”‘’()[]¿¡.,;:!?")
        ends = raw.rstrip("\"'“”‘’")[-1:] in ".,;:!?)]" if raw else False

        capital = bare[:1].isupper() and not any(ch.isdigit() for ch in bare) and fold(bare) not in excluded

        if capital:
            if not current:
                opened = first
            current.append(bare)
        elif current and bare.lower() in NAME_JOINERS:
            current.append(bare)
        else:
            close()

        if ends:
            close()

        first = False

    close()

    return [
        " ".join(group) for group, opening in zip(groups, starts_sentence)
        if not (opening and len(group) == 1)
    ]


def checkable_point(claim: Claim, context=None, language: str | None = None) -> CheckablePoint:
    """
    The claim's point, read from its own sentence. The claim's entities and
    acronyms are its names; a capitalised word the entity model missed
    ("Arctic", "Jire") is one too, unless it opens the sentence. The article's
    subject is restored when the sentence lost it (terms.subject_terms, the
    same rule the sentence plan uses).
    """

    text = claim.text

    lexicon = lexicon_for(language)

    fillers = FILLERS.get((language or "en").lower()[:2], FILLERS["en"])

    stop = {fold(word) for word in lexicon.stopwords | lexicon.query_noise} | {fold(word) for word in fillers}

    entities = [value.strip() for values in claim.entities.values() for value in values if value.strip()]

    identifiers, figures = figures_of(text)

    dates = dates_of(text, language)

    month_words = {fold(word) for date in dates for word in date.split()}

    # A figure already inside a date ("24" of "24 September") is the date.
    figures = [figure for figure in figures if not any(figure in date.split() for date in dates)]

    words = content_terms(text, language)

    in_identifiers = {token for token in re.findall(r"[^\W_]+", fold(" ".join(identifiers)))}

    groups = name_groups(text, stop | month_words)

    # Not a two-letter acronym written with stops ("EE.UU" is one name, and
    # "EE" "UU" two junk words); multi-word names before bare acronyms.
    found_acronyms = [
        a for a in acronyms(text, entities)
        if fold(a) not in in_identifiers and not (len(a) == 2 and re.search(rf"\b{a}\.|\.{a}\b", text))
    ]

    names = _unique(entities + groups + found_acronyms)

    # A name the entity model found inside a longer run ("Urbana Norte" in
    # "Ronda Urbana Norte") is the run.
    names = [name for name in names if not any(fold(name) != fold(other) and f" {fold(name)} " in f" {fold(other)} " for other in names)]

    inside = {
        token for item in names + identifiers + figures
        for token in re.findall(r"[^\W_]+", fold(item))
    }

    terms = [
        word for word in words
        if fold(word) not in stop and fold(word) not in inside and fold(word) not in month_words
    ]

    subject = lost_subject(claim, context, language) if context is not None else []

    # No keywords to tell the headline's subject from its other words
    # (terms.subject_terms needs them): the harness and /verify-claim. Then
    # the headline's own words the sentence lacks.
    headline = ""

    if not subject and context is not None and not context.keywords:
        headline = getattr(context, "search_title", "") or context.title
        sentences = getattr(context, "search_sentences", None) or []
        subject = title_subject(headline, text, language, sentences) if headline else []
        headline = headline if subject else ""

    return CheckablePoint(
        names=names[:MAX_NAMES],
        subject=subject,
        headline=headline,
        identifiers=identifiers,
        figures=figures[:MAX_FIGURES],
        dates=dates[:2],
        terms=terms[:MAX_TERMS],
    )


def _unique(values: list[str]) -> list[str]:

    seen: set[str] = set()
    unique: list[str] = []

    for value in values:
        key = fold(value)
        if key and key not in seen:
            seen.add(key)
            unique.append(value)

    return unique

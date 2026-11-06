"""
What a claim turns on - the "checkable point" - found before anything is
searched, without a model (`query_plan: checkable`).

Why this exists (docs/troubleshooting/fact-checking/01-what-to-look-for.md, 4 Nov 2026):
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

# A figure with its currency or unit written onto it: "£5.9bn", "189p",
# "$40m", "€1,2bn", "8640km", "50GW". NUMBER stops at any letter after the
# digits, so each of these used to be dropped whole, figure and all: on the
# 5 Nov batch "£5.9bn" (fact099) and "189p per therm" (fact101) reached no
# query (`checkable_figures: with_units`, 2026-11-05). A sign, a short
# suffix, or both; ordinals ("21st", "2nd", "3er", "2do", "4to") are not
# units, in either language (invariant 8).
UNIT_FIGURE = re.compile(
    r"(?<![\w.,:-])(?:[£$€¥](?=\d))?\d+(?:[.,]\d+)*(?:[A-Za-z]{1,3})?(?![\w-]|[.,:]\d)",
)
CURRENCY = "£$€¥"
ORDINAL_SUFFIXES = {"st", "nd", "rd", "th", "er", "ra", "ro", "do", "da", "to", "ta", "mo", "vo", "no"}

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

# Who did, said or published it: the sentence's framing, which a news
# sentence puts first and its finding last. `checkable_terms: framing_last`
# (2026-11-05) moves these after the other terms instead of dropping them,
# so a short sentence keeps them. Built because on the 5 Nov batch
# (docs/troubleshooting/fact-checking/experiments/01-what-to-look-for/
# 20261105-next20.md) the six term slots went to "estudio liderado
# identificado" (fact085), "primera autora investigadora resultados
# muestran" (fact086) and "colleague associate professor" (fact088), and
# the finding - "disfunción diastólica", "hiperglucemia", "older mice" -
# was cut before any query. Word classes, not those claims' words:
# reporting and attribution, research roles and acts, discourse framing.
# Not "first" / "primer": "primer país" is what fact118 claims. Both
# languages (invariant 8); exact words, folded, since a Spanish prefix
# ("autor*") would take "autoridad" too.
FRAMING = {
    "en": {
        "study", "studies", "led", "author", "authors", "researcher", "researchers",
        "colleague", "colleagues", "professor", "professors", "associate", "assistant",
        "results", "showed", "shown", "discovered", "identified", "published", "reported",
        "adds", "added", "reveals", "revealed", "explained", "explains", "told",
        "later", "main", "goal", "aim",
    },
    "es": {
        "estudio", "estudios", "liderado", "liderada", "dirigido", "dirigida",
        "autor", "autora", "autores", "autoras", "investigador", "investigadora",
        "investigadores", "investigadoras", "profesor", "profesora", "profesores",
        "resultados", "muestran", "identificado", "identificada", "publicado", "publicada",
        "participaron", "explicó", "explica", "añadió", "indicó", "aseguró", "destacó",
        "reveló", "principal", "objetivo",
    },
}

# Words that are neither the finding nor its framing: the closed classes the
# stopword lists leave out (prepositions, adverbs of place, time and degree,
# modals) and a verb in the simple past. `checkable_terms: finding_first`
# (2026-11-05) puts them after the finding's words and before the framing,
# moved, never dropped. Built because on the 5 Nov batch, under framing_last,
# "above" and "snapped" took two of the six slots and "monitoring cameras"
# was cut (fact123), and "reversed" took the one "cartilage" needed (fact088)
# (docs/troubleshooting/fact-checking/experiments/01-what-to-look-for/
# 20261105-next20-round-03.md). A page states the finding in nouns; the
# verb comes in any tense ("reversed", "reverses", "reversal"), so it is the
# term a search loses least by. Not "-ing": "monitoring" is the camera.
# Not "bajo": "más bajo" is what fact124 claims. Both languages
# (invariant 8).
ASIDES = {
    "en": {
        "above", "below", "along", "around", "against", "among", "amongst", "behind", "beyond",
        "within", "without", "toward", "towards", "upon", "onto", "near", "back", "away", "again",
        "ever", "even", "like", "unlike", "since", "until", "despite", "though", "although",
        "almost", "rather", "quite", "often", "soon", "once", "twice", "will", "would", "could",
        "should", "might", "must", "shall",
    },
    "es": {
        "ante", "contra", "dentro", "fuera", "cerca", "lejos", "encima", "debajo", "detrás",
        "detras", "delante", "luego", "ahora", "siempre", "nunca", "antes", "casi", "apenas",
        "puede", "pueden", "podría", "podria", "podrían", "podrian", "debe", "deben",
    },
}

# The simple past: "reversed", "snapped", "arrived" (not "need", "speed",
# "used"); "logró", "nació", "presentaron", "consiguieron". Read on the word
# as written, lowercased: the accent is what makes "llenó" a verb.
PAST_TENSE = {
    "en": re.compile(r"^[a-z]{2,}[^e\W]ed$"),
    "es": re.compile(r"^\w{2,}(?:ó|aron|ieron)$"),
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


def unit_figures(text: str) -> tuple[list[str], str]:
    """
    `(figures, rest)`: the figures with a currency sign or a unit written
    onto them (`UNIT_FIGURE`), as written ("£5.9bn", "189p"), and the text
    without them, cut by position so "£40" does not eat the start of
    "£400m". Not a bare number, not an ordinal, not a single digit with a
    letter and no sign ("5G", "3D" say too little).
    """

    found: list[str] = []

    def take(match: re.Match) -> str:
        token = match.group(0)
        signed = token[0] in CURRENCY
        suffix = re.search(r"[A-Za-z]+$", token)
        digits = re.sub(r"\D", "", token)

        if suffix and suffix.group(0).lower() in ORDINAL_SUFFIXES:
            return token
        if not signed and not suffix:
            return token
        if not signed and len(digits) < 2:
            return token

        found.append(token)
        return " "

    rest = UNIT_FIGURE.sub(take, text)

    return found, rest


def counted_figures(text: str, figures: list[str], excluded: set[str], language: str | None = None) -> list[str]:
    """
    Each figure with the noun it counts, when the sentence writes one right
    after it: "30 minutes", "116 mujeres", "24 años", "41% share" - the
    spaced form of a COUNTED identifier ("11-set"). `checkable_figures:
    counted` (2026-11-05). Built because on the 5 Nov batch "minutes" took
    one of the six term slots as a word of its own and "crew" was cut
    (fact106, docs/troubleshooting/fact-checking/experiments/
    01-what-to-look-for/20261105-next20-round-04.md); bound to its number,
    the noun stays in the point and frees the slot.

    A noun only: four letters or more, lowercase (a capital is a name),
    not a stopword, filler or month (`excluded`), not an aside or a verb in
    the simple past ("£5.9bn since", not "since"), and not the first half
    of a compound ("212 travel-related" would cut the compound in two).
    Order and number of figures unchanged: only what each one says.
    """

    code = (language or "en").lower()[:2]
    asides = {fold(word) for word in ASIDES.get(code, ASIDES["en"])}
    past = PAST_TENSE.get(code, PAST_TENSE["en"])

    def noun_after(figure: str) -> str:
        match = re.search(rf"(?<![\w.,:-]){re.escape(figure)}\s+([^\W\d_]{{4,}})(?![\w\-‑])", text)
        if not match:
            return ""
        word = match.group(1)
        if not word[:1].islower():
            return ""
        if fold(word) in excluded or fold(word) in asides or past.match(word.lower()):
            return ""
        return word

    counted = []

    for figure in figures:
        noun = noun_after(figure)
        counted.append(f"{figure} {noun}" if noun else figure)

    return counted


def figures_of(text: str, units: bool = False) -> tuple[list[str], list[str]]:
    """
    `(identifiers, figures)`. Identifiers, counts and times are taken out of
    the text first, so their numbers are not reported again on their own;
    years are dates, not figures. Figures are ordered most distinctive
    first: a percentage or a number with separators or decimals, then by
    length. A single digit says too little to search for.

    `units` (`checkable_figures: with_units`) also keeps a figure with its
    currency or unit written onto it (`unit_figures`); False reads the
    figures as every run did before 2026-11-05.
    """

    identifiers = _unique(IDENTIFIER.findall(text) + COUNTED.findall(text) + TIME.findall(text))

    rest = text

    for token in identifiers:
        rest = rest.replace(token, " ")

    percents = [re.sub(r"\s+", " ", match).strip() for match in PERCENT.findall(rest) + SCALE.findall(rest)]

    for token in percents:
        rest = rest.replace(token, " ")

    with_units: list[str] = []

    if units:
        with_units, rest = unit_figures(rest)

    numbers = with_units + [
        number for number in NUMBER.findall(rest) if not YEAR.fullmatch(number) and len(re.sub(r"\D", "", number)) > 1
    ]

    # A sign or a unit makes a figure as distinctive as a decimal does: no
    # bare number carries one, so the order of bare numbers is unchanged.
    def distinctive(figure: str) -> tuple:
        digits = re.sub(r"\D", "", figure)
        return (bool(re.search(r"[%.,£$€¥]|cent|ciento|[A-Za-z]$", figure)), len(digits))

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


def framing_last(terms: list[str], language: str | None = None) -> list[str]:
    """
    The terms with the sentence's framing (`FRAMING`) after the rest, each
    group in sentence order. Nothing dropped: only which six are kept moves.
    """

    framing = {fold(word) for word in FRAMING.get((language or "en").lower()[:2], FRAMING["en"])}

    return sorted(terms, key=lambda word: fold(word) in framing)


def finding_first(terms: list[str], language: str | None = None) -> list[str]:
    """
    The finding's words, then the asides (`ASIDES`, `PAST_TENSE`), then the
    framing (`FRAMING`), each group in sentence order: `framing_last` with
    the asides moved too. Nothing dropped.
    """

    return sorted(terms, key=_term_group(language))


def _term_group(language: str | None = None):
    """A term's group, for `finding_first`: 0 the finding, 1 an aside, 2 the framing."""

    code = (language or "en").lower()[:2]

    framing = {fold(word) for word in FRAMING.get(code, FRAMING["en"])}
    asides = {fold(word) for word in ASIDES.get(code, ASIDES["en"])}
    past = PAST_TENSE.get(code, PAST_TENSE["en"])

    def group(word: str) -> int:
        if fold(word) in framing:
            return 2
        if fold(word) in asides or past.match(word.lower()):
            return 1
        return 0

    return group


def finding_closing(terms: list[str], language: str | None = None) -> list[str]:
    """
    `finding_first`'s six terms, and a seventh when the cut took the
    sentence's closing finding word: the last of `terms` (in sentence order)
    that is neither an aside nor framing. A sentence puts what is new last
    (end-focus, in both languages): the last item of a list, the place a
    finding happened. On the 5 Nov batch "macrófagos" closed fact086's list
    and "knee" fact088's finding, and each sentence ran well past six terms
    before them (20261105-next20-round-05.md). The six are `finding_first`'s
    exactly, so nothing leaves; `plan_checkable` adds the seventh to the
    proposition query.
    """

    group = _term_group(language)

    kept = finding_first(terms, language)[:MAX_TERMS]

    finding = [word for word in terms if group(word) == 0]

    if finding and finding[-1] not in kept:
        kept.append(finding[-1])

    return kept


def checkable_point(
    claim: Claim,
    context=None,
    language: str | None = None,
    terms_order: str | None = None,
    figures_style: str | None = None,
) -> CheckablePoint:
    """
    The claim's point, read from its own sentence. The claim's entities and
    acronyms are its names; a capitalised word the entity model missed
    ("Arctic", "Jire") is one too, unless it opens the sentence. The article's
    subject is restored when the sentence lost it (terms.subject_terms, the
    same rule the sentence plan uses).

    `terms_order` is `PipelineThresholds.checkable_terms`: None or
    "sentence" keeps the terms in the sentence's order, as every run did
    before 2026-11-05; "framing_last" puts its framing after them
    (`framing_last`); "finding_first" puts its asides, then its framing,
    after them (`finding_first`); "finding_closing" does too, and keeps the
    sentence's closing finding word as a seventh term when the cut took it
    (`finding_closing`).

    `figures_style` is `PipelineThresholds.checkable_figures`: None or
    "bare" reads the figures as before 2026-11-05; "with_units" keeps a
    figure with its currency or unit written onto it (`unit_figures`);
    "counted" does too, and keeps the noun a figure counts beside it
    (`counted_figures`).
    """

    text = claim.text

    lexicon = lexicon_for(language)

    fillers = FILLERS.get((language or "en").lower()[:2], FILLERS["en"])

    stop = {fold(word) for word in lexicon.stopwords | lexicon.query_noise} | {fold(word) for word in fillers}

    entities = [value.strip() for values in claim.entities.values() for value in values if value.strip()]

    identifiers, figures = figures_of(text, units=figures_style in ("with_units", "counted"))

    dates = dates_of(text, language)

    month_words = {fold(word) for date in dates for word in date.split()}

    # A figure already inside a date ("24" of "24 September") is the date.
    figures = [figure for figure in figures if not any(figure in date.split() for date in dates)]

    # Before `inside` is read below, so the counted noun leaves the terms.
    # It makes the figure distinctive (`DISTINCTIVE`), as a hyphen already
    # makes "11-set" an identifier: the same count, written with a space.
    if figures_style == "counted":
        figures = counted_figures(text, figures, stop | month_words, language)

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

    if terms_order == "framing_last":
        terms = framing_last(terms, language)
    elif terms_order == "finding_first":
        terms = finding_first(terms, language)

    # Every other order is cut to the six slots below; this one has cut
    # already, and its seventh term is the point of it.
    if terms_order == "finding_closing":
        terms = finding_closing(terms, language)
    else:
        terms = terms[:MAX_TERMS]

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
        terms=terms,
    )


def point_for_thresholds(claim: Claim, context=None, language: str | None = None, thresholds=None) -> CheckablePoint:
    """
    checkable_point under one run's thresholds: what the retriever records
    and what the troubleshooting loop measures, from one call (see
    query_builder.plan_arguments for why).
    """

    return checkable_point(
        claim, context, language,
        getattr(thresholds, "checkable_terms", None), getattr(thresholds, "checkable_figures", None),
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


_CARRIED = re.compile(r"[^\W_]+", re.UNICODE)


def carries(text: str, value: str) -> bool:
    """
    Whether `text` states `value` - a name, a figure, a date - whole: every
    word of it, accents and case aside. "Florida Health" is not carried by
    "Florida", and "212" is not carried by "2120".
    """

    words = set(_CARRIED.findall(fold(text)))
    needed = _CARRIED.findall(fold(value))

    return bool(needed) and all(word in words for word in needed)


# ---- Names, for `query_plan: questions` (fact_checker/questions.py) ----

# Words of a role, not of a name: "Ryan Zinke" names "US Interior Secretary
# Ryan Zinke", "Secretary" does not. Both languages (invariant 8).
TITLE_WORDS = {
    "president", "presidential", "former", "secretary", "minister", "prime", "interior", "senator",
    "governor", "mayor", "candidate", "chief", "director", "general", "king", "queen", "prince",
    "doctor", "dr", "mr", "mrs", "ms", "sir", "the", "of", "and",
    "presidente", "presidenta", "expresidente", "ministro", "ministra", "secretario", "secretaria",
    "alcalde", "alcaldesa", "gobernador", "gobernadora", "senador", "senadora", "rey", "reina",
    "doctora", "don", "dona", "de", "del", "la", "el", "los", "las", "y",
}

# The lowercase words a name may hold: "Bank of England", "Ciudad de México".
JOINERS = {"of", "the", "and", "for", "de", "del", "la", "las", "los", "el", "y"}

ROMAN = re.compile(r"^[ivx]+$")

ACRONYM = re.compile(r"^[A-Z]{2,6}s?$")


def is_proper(value: str) -> bool:
    """
    A name, not a phrase the entity model or the sentence's capital letter
    took for one: every word capitalised (an acronym included), "Presidential
    candidate", "mentally ill" and "hot milk" not (all three from GLiNER on the
    first 10 AVeriTeC train claims, 6 Nov).
    """

    words = [word for word in value.split() if fold(word) not in JOINERS]

    # A date or a figure is a detail of its own kind: "November 1st 2019".
    if not words or any(word[:1].isdigit() for word in words):
        return False

    return all(word[:1].isupper() for word in words)


def proper_names(claim: Claim, point: CheckablePoint) -> list[str]:
    """The claim's names - the entity model's and the checkable point's - that are names, in the sentence's order."""

    candidates = [value for values in claim.entities.values() for value in values] + point.names

    seen: set[str] = set()
    names: list[str] = []

    for value in candidates:
        key = fold(value)
        if key and key not in seen and is_proper(value) and fold(value) in fold(claim.text):
            seen.add(key)
            names.append(value)

    return sorted(names, key=lambda name: fold(claim.text).find(fold(name)))


def names_in(text: str, name: str) -> bool:
    """
    Whether `text` names `name`: an acronym whole, else any word of it that is
    not a title or a numeral. "Ryan Zinke" names "US Interior Secretary Ryan
    Zinke"; "Secretary" does not; "Aquino" names "Benigno Aquino III".
    """

    if ACRONYM.match(name.strip()):
        return carries(text, name)

    core = [
        word for word in re.findall(r"[^\W_]+", fold(name))
        if word not in TITLE_WORDS and not ROMAN.match(word) and len(word) >= 3
    ]

    return any(carries(text, word) for word in core) if core else carries(text, name)

"""
Per-language word lists for the keyword-based quality and claim
heuristics.

These used to be English-only module constants inside
`processors/nlp/quality.py` and `processors/nlp/claims.py`, which meant
every Spanish article - 7 of the 12 configured sources - scored near zero
on constructiveness, hopefulness and inspiration, and yielded almost no
extractable claims. The admission filter then rejected it, or admitted it
on noise. The lists live here so adding a third language is a data change
rather than an edit to four processors.

**Entries ending in `*` are prefix matches.** Spanish is far more
inflected than English (mejorar / mejora / mejoró / mejorado / mejoras),
so exact-token sets would have had a fraction of the recall of their
English counterparts and quietly reintroduced the same bias this module
exists to remove. Prefixes are used in both languages so the two are
scored the same way, not one leniently and one strictly.

This is still a keyword heuristic and is honest about being one: no
lemmatiser, no POS tagging, no negation handling. It is a filter for
"probably constructive", not a semantic judgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class Lexicon:
    """The word sets one language needs to be scored."""

    language: str

    # ---- quality: objectivity -----------------------------------------
    speculative: frozenset[str]
    emotional: frozenset[str]
    first_person: frozenset[str]

    # ---- quality: constructiveness / hopefulness / impact -------------
    constructive: frozenset[str]
    negative: frozenset[str]
    hope: frozenset[str]
    human: frozenset[str]
    societal: frozenset[str]

    # ---- claims -------------------------------------------------------
    reporting_verbs: frozenset[str]
    month_names: frozenset[str]
    relative_dates: frozenset[str]
    measurement_words: frozenset[str]

    # Stopwords used only by the language detector, never for scoring.
    stopwords: frozenset[str] = field(default_factory=frozenset)


def _s(*words: str) -> frozenset[str]:
    return frozenset(words)


ENGLISH = Lexicon(
    language="en",
    speculative=_s(
        "may", "might", "could", "perhaps", "possibly", "possible",
        "likely", "apparently", "allegedly", "reportedly", "seem*",
    ),
    emotional=_s(
        "amazing", "incredible", "shocking", "terrible", "catastrophic",
        "unbelievable", "outrageous", "devastating", "horrif*",
    ),
    first_person=_s("i", "we", "our", "ours", "my", "mine", "us"),
    constructive=_s(
        "develop*", "creat*", "improv*", "innovat*", "initiative*",
        "project*", "solution*", "research*", "discover*", "restor*",
        "reduc*", "increas*", "collaborat*", "technolog*", "treatment*",
        "vaccine*", "breakthrough*", "launch*", "fund*", "support*",
    ),
    negative=_s(
        "war", "wars", "attack*", "conflict*", "crisis", "crises",
        "collapse*", "disaster*", "problem*", "violen*", "death*",
        "killed", "victim*",
    ),
    hope=_s(
        "recover*", "improv*", "growth", "restor*", "save*", "saving*",
        "protect*", "conservation", "breakthrough*", "success*", "cure*",
        "treatment*", "vaccine*", "hope*", "promising",
    ),
    human=_s(
        "student*", "teacher*", "doctor*", "nurse*", "scientist*",
        "researcher*", "volunteer*", "community", "communities",
        "family", "families", "neighbour*", "neighbor*", "patient*",
    ),
    societal=_s(
        "world", "worldwide", "global*", "international", "millions",
        "thousands", "un", "who", "eu", "nasa", "europe", "national",
    ),
    reporting_verbs=_s(
        "announc*", "say", "says", "said", "report*", "confirm*",
        "discover*", "find", "finds", "found", "reveal*", "publish*",
        "launch*", "approv*", "win", "wins", "won", "identif*",
        "detect*", "increas*", "reduc*", "improv*", "show", "shows",
        "showed", "demonstrat*", "indicat*", "estimat*", "state",
        "stated", "accord*",
    ),
    month_names=_s(
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
    ),
    relative_dates=_s("today", "yesterday", "tomorrow"),
    measurement_words=_s(
        "percent", "km", "m", "cm", "kg", "g", "ton", "tons", "tonnes",
        "million", "millions", "billion", "billions", "euro", "euros",
        "dollar", "dollars", "people",
    ),
    stopwords=_s(
        "the", "of", "and", "to", "in", "is", "that", "for", "it",
        "with", "was", "on", "are", "by", "this", "be", "from", "at",
        "have", "has", "not", "but", "they", "we", "you", "were",
        "their", "its", "an",
    ),
)


SPANISH = Lexicon(
    language="es",
    speculative=_s(
        "puede", "pueden", "podría*", "podia*", "quizá", "quizas",
        "quizás", "posible*", "posiblemente", "probable*",
        "probablemente", "aparentemente", "presunt*", "supuest*",
        "parece*",
    ),
    emotional=_s(
        "increíble*", "increible*", "asombros*", "impactante*",
        "terrible*", "catastrófic*", "catastrofic*", "escandalos*",
        "brutal*", "tremend*", "devastador*", "horror*",
    ),
    first_person=_s(
        "yo", "nosotros", "nosotras", "nuestro", "nuestra", "nuestros",
        "nuestras", "mi", "mis", "mío", "mía",
    ),
    constructive=_s(
        "desarroll*", "cre*", "mejor*", "innovac*", "innovador*",
        "iniciativ*", "proyect*", "solucion*", "solución",
        "investigac*", "investigador*", "descubr*", "restaur*",
        "reduc*", "reduj*", "aument*", "colabora*", "tecnolog*",
        "tratamiento*", "vacuna*", "avance*", "financia*", "apoy*",
    ),
    negative=_s(
        "guerra*", "ataque*", "atentado*", "conflicto*", "crisis",
        "colapso*", "desastre*", "problema*", "violen*", "muerte*",
        "muert*", "víctima*", "victima*", "asesin*",
    ),
    hope=_s(
        "recuper*", "mejor*", "crecimiento", "restaur*", "salv*",
        "proteg*", "protecc*", "conservac*", "avance*", "éxito*",
        "exito*", "cura*", "tratamiento*", "vacuna*", "esperanz*",
        "prometedor*",
    ),
    human=_s(
        "estudiante*", "alumno*", "profesor*", "maestr*", "médic*",
        "medic*", "enfermer*", "científic*", "cientific*",
        "investigador*", "voluntari*", "comunidad*", "familia*",
        "vecin*", "paciente*",
    ),
    societal=_s(
        "mundo", "mundial*", "global*", "internacional*", "millones",
        "miles", "onu", "oms", "ue", "nasa", "europa", "nacional*",
        "sociedad",
    ),
    reporting_verbs=_s(
        "anunci*", "dij*", "dice", "dicen", "declar*", "inform*",
        "confirm*", "descubr*", "encontr*", "hall*", "revel*",
        "public*", "lanz*", "aprob*", "aprueb*", "gan*", "identific*",
        "detect*", "aument*", "reduj*", "reduc*", "mejor*", "muestra*",
        "mostr*", "demostr*", "indic*", "estim*", "señal*", "senal*",
        "afirm*", "asegur*", "explic*", "present*",
    ),
    month_names=_s(
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
        "agosto", "septiembre", "setiembre", "octubre", "noviembre",
        "diciembre",
    ),
    relative_dates=_s("hoy", "ayer", "mañana", "manana", "anoche"),
    measurement_words=_s(
        "ciento", "por ciento", "km", "m", "cm", "kg", "g", "tonelada",
        "toneladas", "millón", "millon", "millones", "mil", "miles",
        "euro", "euros", "dólar", "dolar", "dólares", "dolares",
        "persona", "personas", "habitantes",
    ),
    stopwords=_s(
        "el", "la", "los", "las", "de", "del", "y", "en", "que", "es",
        "un", "una", "por", "con", "para", "se", "su", "sus", "al",
        "lo", "como", "más", "pero", "ha", "han", "fue", "esta",
        "este", "sobre", "también",
    ),
)


LEXICONS: dict[str, Lexicon] = {
    ENGLISH.language: ENGLISH,
    SPANISH.language: SPANISH,
}

SUPPORTED_LANGUAGES = frozenset(LEXICONS)


def lexicon_for(language: str | None) -> Lexicon:
    """
    The lexicon for `language`, falling back to English for anything
    unsupported. Falls back rather than raising: an unexpected language
    should score an article conservatively, not fail the pipeline for it.
    """

    if not language:
        return LEXICONS[DEFAULT_LANGUAGE]

    return LEXICONS.get(language.lower()[:2], LEXICONS[DEFAULT_LANGUAGE])


def matches(word: str, vocabulary: frozenset[str]) -> bool:
    """
    True if `word` is in `vocabulary`, treating a trailing `*` as a
    prefix. Exact entries are checked first, since that is a single hash
    lookup and covers most words.
    """

    if word in vocabulary:
        return True

    return any(
        entry.endswith("*") and word.startswith(entry[:-1])
        for entry in vocabulary
    )


def count_matches(words: list[str], vocabulary: frozenset[str]) -> int:
    """How many of `words` the vocabulary matches (prefixes included)."""

    return sum(matches(word, vocabulary) for word in words)

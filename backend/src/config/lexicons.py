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

    # Markers of opinion or interpretation rather than checkable fact:
    # evaluative adjectives, hedges, and normative/deontic verbs. Used to
    # keep "this is a hopeful step for the sector" out of the claim set,
    # since nothing can be retrieved that confirms or refutes it.
    # `speculative` and `first_person` above feed this too - they are
    # already opinion signals, just scored for a different purpose.
    opinion: frozenset[str]

    # ---- discovery ----------------------------------------------------
    # Phrases that make a headline a death report - matched whole, after
    # folding case and accents, against the title only. Read by the
    # mission screen (src/services/selection/mission_screen.py): an
    # embedding takes an obituary and a biography for the same thing,
    # and dropped pieces on Unamuno and on Revolutionary War soldiers
    # while it let "Jeffrey Archer dies aged 86" through. Present tense
    # only, the tense news reports a death in: Spanish "murió" is the
    # tense of history ("Carlos II ... murió sin descendencia").
    death_report: frozenset[str]

    # Stopwords used only by the language detector, never for scoring.
    stopwords: frozenset[str] = field(default_factory=frozenset)

    # Words that are not stopwords but are worthless *as search terms*:
    # journalistic connective tissue ("according to", "after", "said")
    # and generic nouns that match every news page ever written. They are
    # kept apart from `stopwords` because that set is tuned to tell the
    # two languages apart for the detector, and padding it with shared
    # vocabulary would make it worse at the one job it has.
    #
    # Used by the query planner to decide which of a claim's words carry
    # its assertion, and by the lexical ranker to decide which terms a
    # source has to contain to count as addressing it.
    query_noise: frozenset[str] = field(default_factory=frozenset)


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
    opinion=_s(
        "should", "must", "ought", "need", "needs", "deserve*",
        "believ*", "think*", "feel", "feels", "hope", "hopes",
        "unfortunate*", "fortunate*", "sadly", "luckily", "clearly",
        "obviously", "surely", "arguably", "undoubtedly",
        "important", "essential", "crucial", "vital", "remarkable",
        "impressive", "disappointing", "worrying", "welcome",
        "best", "worst", "better", "worse", "good", "bad", "great",
        "beautiful", "wonderful", "inspiring", "encouraging",
    ),
    death_report=_s(
        "dies at", "dies aged", "dies after", "has died", "dead at", "obituary",
    ),
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
    query_noise=_s(
        "said", "says", "according", "after", "before", "during",
        "while", "when", "where", "which", "there", "then", "than",
        "also", "about", "into", "over", "under", "through", "between",
        "such", "these", "those", "other", "more", "most", "some",
        "many", "much", "very", "just", "only", "still", "already",
        "year", "years", "time", "times", "day", "days", "week",
        "month", "months", "news", "report", "reports", "reported",
        "article", "story", "case", "part", "way", "thing", "things",
        "people", "world", "today", "yesterday", "however", "because",
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
    opinion=_s(
        "deber*", "habría", "habria", "merec*", "cre*", "piens*",
        "opin*", "espera*", "ojalá", "ojala",
        "lamentablemente", "afortunadamente", "tristemente",
        "claramente", "evidentemente", "obviamente", "sin duda",
        "important*", "esencial*", "crucial*", "fundamental*",
        "notable*", "impresionante*", "decepcionante*", "preocupante*",
        "mejor*", "peor*", "buen*", "mal*", "gran", "grande*",
        "hermos*", "maravillos*", "inspirador*", "alentador*",
    ),
    death_report=_s(
        "muere", "fallece", "ha muerto", "ha fallecido", "obituario",
    ),
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
    query_noise=_s(
        "dijo", "dice", "dicen", "según", "segun", "tras", "durante",
        "mientras", "cuando", "donde", "cual", "cuales", "entonces",
        "además", "ademas", "entre", "hacia", "desde", "hasta",
        "otros", "otras", "otro", "otra", "estos", "estas", "esos",
        "esas", "mucho", "muchos", "mucha", "muchas", "poco", "pocos",
        "solo", "sólo", "aún", "aun", "todavía", "todavia", "ya",
        "año", "años", "anos", "tiempo", "vez", "veces", "día", "dias",
        "días", "semana", "mes", "meses", "noticia", "noticias",
        "informe", "artículo", "articulo", "caso", "parte", "forma",
        "manera", "cosa", "cosas", "gente", "mundo", "hoy", "ayer",
        "embargo", "porque", "aunque", "ello", "misma", "mismo",
    ),
)


LEXICONS: dict[str, Lexicon] = {
    ENGLISH.language: ENGLISH,
    SPANISH.language: SPANISH,
}

SUPPORTED_LANGUAGES = frozenset(LEXICONS)


# ----------------------------------------------------------------------
# Catalan: a writing language, not a source language
# ----------------------------------------------------------------------
#
# The newsroom writes drafts in Catalan (docs/decisions/writing.md); no
# source publishes in it. So CATALAN is deliberately *not* in LEXICONS:
# that dict is what LanguageDetector tells apart and what every ingested
# article is scored against, and putting Catalan there would change how
# the whole pipeline detects and scores Spanish news for the sake of a
# corrector metric. It lives in WRITING_LEXICONS, which only the draft
# review reads (`writing_lexicon_for`).
#
# Complete, and held to the same rule as the other two
# (tests/test_invariants.py): a half-filled lexicon scores its language
# as though the missing signals never occur.
#
# Two things about Catalan text the word sets cannot carry are handled
# where Catalan is scored (src/services/corrector/draft_language.py): the
# punt volat ("col·laboració" - `·` is not a word character, so the
# tokeniser cuts the word in two) and elision ("d'investigació" is one
# token, so `investiga*` never sees it). Entries here are written for
# text with `l·l` folded to `ll` and elided articles split off.
#
# lexicon_for("ca") still answers English, as for any language the
# pipeline does not know. Nothing in the pipeline asks for Catalan; the
# corrector asks writing_lexicon_for, which never falls back.

CATALAN = Lexicon(
    language="ca",
    speculative=_s(
        "pot", "poden", "podria*", "potser", "possible*", "possiblement",
        "probable*", "probablement", "aparentment", "presumpt*",
        "suposad*", "sembla*", "pareix*",
    ),
    emotional=_s(
        "increïble*", "increible*", "sorprenent*", "impactant*",
        "terrible*", "catastròfic*", "catastrofic*", "escandalós",
        "escandalos*", "brutal*", "tremend*", "devastador*", "horror*",
        "esgarrifós", "esgarrifos*",
    ),
    first_person=_s(
        "jo", "nosaltres", "nostre", "nostra", "nostres", "meu", "meva",
        "meus", "meves", "ens",
    ),
    constructive=_s(
        "desenvolup*", "crea*", "creix*", "millor*", "innova*",
        "iniciativ*", "projecte*", "solucio*", "solució", "investiga*",
        "descobr*", "restaura*", "redu*", "augment*", "collabora*",
        "tecnolog*", "tractament*", "vacuna*", "avenç", "avenços",
        "avanç*", "finança*", "financia*", "suport*", "impuls*",
    ),
    negative=_s(
        "guerra*", "atac*", "atemptat*", "conflicte*", "crisi", "crisis",
        "collapse*", "desastre*", "problema*", "violèn*", "violen*",
        "mort", "morts", "mortal*", "víctima*", "victima*", "assassin*",
    ),
    hope=_s(
        "recupera*", "millor*", "creixement", "restaura*", "salva*",
        "proteg*", "protecci*", "conserva*", "avenç", "avenços", "avanç*",
        "èxit*", "exit*", "cura*", "tractament*", "vacuna*",
        "esperança*", "esperanc*", "prometedor*", "esperançador*",
    ),
    human=_s(
        "estudiant*", "alumne*", "alumna*", "professor*", "mestre*",
        "mestra*", "metge*", "metgessa*", "infermer*", "científic*",
        "cientific*", "investigador*", "voluntari*", "comunitat*",
        "família*", "familia*", "famílies", "veí", "veïn*", "vein*",
        "pacient*",
    ),
    societal=_s(
        "món", "mundial*", "global*", "internacional*", "milions",
        "milers", "onu", "oms", "ue", "nasa", "europa", "nacional*",
        "societat",
    ),
    reporting_verbs=_s(
        "anuncia*", "diu", "diuen", "dir", "digué", "declara*",
        "informa*", "confirma*", "descobr*", "troba*", "revela*",
        "publica*", "llança*", "llanc*", "aprova*", "guanya*",
        "identifica*", "detecta*", "augment*", "redu*", "millor*",
        "mostra*", "demostra*", "indica*", "estima*", "assenyala*",
        "afirma*", "assegura*", "explica*", "presenta*",
    ),
    month_names=_s(
        "gener", "febrer", "març", "abril", "maig", "juny", "juliol",
        "agost", "setembre", "octubre", "novembre", "desembre",
    ),
    relative_dates=_s("avui", "ahir", "demà", "dema", "anit"),
    opinion=_s(
        "hauria*", "haurien", "cal", "caldria", "mereix*", "creu*",
        "crec", "penso", "pensa", "pensen", "opina*", "espera*",
        "tant de bo", "lamentablement", "afortunadament", "tristament",
        "clarament", "evidentment", "òbviament", "obviament",
        "sens dubte", "important*", "essencial*", "crucial*",
        "fonamental*", "notable*", "impressionant*", "decebedor*",
        "preocupant*", "millor*", "pitjor*", "bo", "bona", "bons",
        "bones", "dolent*", "gran", "grans", "bonic*", "meravell*",
        "inspirador*", "encoratjador*", "esperançador*",
    ),
    death_report=_s(
        "mor", "ha mort", "ha traspassat", "traspassa", "obituari",
    ),
    measurement_words=_s(
        "cent", "per cent", "km", "m", "cm", "kg", "g", "tona", "tones",
        "milió", "milio", "milions", "mil", "milers", "euro", "euros",
        "dòlar", "dolar", "dòlars", "dolars", "persona", "persones",
        "habitants",
    ),
    # Only words Spanish does not use, so that a Catalan text and its
    # Spanish translation tell apart: "de", "la", "que", "en" and "el" are
    # as common in one as in the other and would say nothing.
    stopwords=_s(
        "i", "amb", "els", "dels", "als", "pels", "pel", "per", "és",
        "són", "més", "però", "també", "aquest", "aquesta", "aquests",
        "aquestes", "seu", "seva", "seus", "seves", "hi", "ho", "molt",
        "com", "quan", "perquè", "fins", "ja", "on",
    ),
    query_noise=_s(
        "diu", "dit", "segons", "després", "despres", "abans", "durant",
        "mentre", "quan", "on", "qual", "quals", "llavors", "aleshores",
        "entre", "cap", "des", "fins", "altres", "altre", "altra",
        "aquests", "aquestes", "molt", "molts", "molta", "moltes", "poc",
        "pocs", "només", "nomes", "encara", "ja", "any", "anys", "temps",
        "vegada", "vegades", "dia", "dies", "setmana", "mes", "mesos",
        "notícia", "notícies", "noticia", "informe", "article", "cas",
        "part", "forma", "manera", "cosa", "coses", "gent", "món",
        "avui", "ahir", "però", "perquè", "malgrat", "tanmateix",
    ),
)


# Every language a draft can be written in (src/models/writer/draft.py,
# `Language`): the two source languages and Catalan.
WRITING_LEXICONS: dict[str, Lexicon] = {
    **LEXICONS,
    CATALAN.language: CATALAN,
}


class UnsupportedWritingLanguage(ValueError):
    pass


def writing_lexicon_for(language: str) -> Lexicon:
    """
    The lexicon a draft in `language` is scored with. Unlike
    `lexicon_for`, never falls back to English: a draft's language is
    declared by the person who asked for it, not guessed, so an unknown
    one is a bug to surface rather than an article to score
    conservatively.
    """

    lexicon = WRITING_LEXICONS.get((language or "").lower())

    if lexicon is None:
        raise UnsupportedWritingLanguage(
            f"No lexicon for {language!r}: a draft in it would be scored with "
            "another language's rules. Add one to src/config/lexicons.py."
        )

    return lexicon


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

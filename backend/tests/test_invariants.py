"""
The rules from CLAUDE.md, as tests.

Every rule here was already written down in prose and broken anyway -
that is the entire justification for the file. A contributor (or an
agent) can skim past a paragraph; nobody skims past a red test. When one
of these fails, the fix is either to change the code or to change the
declared exception below, deliberately and visibly.

Keep these fast and dependency-free: they are the first thing the check
command runs.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

PYTHON_FILES = sorted(SRC.rglob("*.py"))


def relative(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


# ----------------------------------------------------------------------
# "Never write MIN_X = settings.MIN_X in a class body"
# ----------------------------------------------------------------------

# Declared exceptions, with the reason. Ranking and confidence *weights*
# are environment-only by decision: each group must sum to 1.0, and
# letting a request set one member alone would silently produce a scoring
# function that no longer normalises. They are still frozen at import,
# which is the accepted cost of that decision.
FROZEN_SETTINGS_EXCEPTIONS = {
    "services/fact_checker/ranking/ranking_retrieval.py",
    "services/fact_checker/verification/confidence_scorer.py",
}

CLASS_ATTRIBUTE_FROM_SETTINGS = re.compile(r"^\s{4}[A-Z_]+\s*=\s*settings\.")


def test_no_settings_are_frozen_into_class_attributes():
    """
    `X = settings.X` in a class body is evaluated once, when the module
    is first imported. That froze the value for the life of the process -
    it is why ClaimSelector.MAX_CLAIMS, ConfidenceScorer.MIN_EVIDENCE and
    DuplicateValidator.DUPLICATE_THRESHOLD could not be overridden at all,
    and why their tests had to reassign the attribute to exercise them.
    """

    offenders = [
        f"{relative(path)}:{number}  {line.strip()}"
        for path in PYTHON_FILES
        if relative(path) not in FROZEN_SETTINGS_EXCEPTIONS
        for number, line in code_lines(path)
        if CLASS_ATTRIBUTE_FROM_SETTINGS.match(line)
    ]

    assert offenders == [], (
        "Read these from the run's PipelineThresholds instead, or add the "
        "file to FROZEN_SETTINGS_EXCEPTIONS with a reason:\n  "
        + "\n  ".join(offenders)
    )


def test_the_frozen_settings_exceptions_are_all_real():
    """
    An exception list that outlives the thing it excuses is how a rule
    quietly stops applying.
    """

    for name in FROZEN_SETTINGS_EXCEPTIONS:

        path = SRC / name

        assert path.exists(), f"{name} is exempted but does not exist"

        assert any(
            CLASS_ATTRIBUTE_FROM_SETTINGS.match(line)
            for _, line in code_lines(path)
        ), f"{name} is exempted but no longer needs to be - remove it"


# ----------------------------------------------------------------------
# "Every tunable threshold lives in src/config/thresholds.py"
# ----------------------------------------------------------------------

# Settings that are legitimately read straight from `settings`: they are
# infrastructure (paths, URLs, model names, credentials) or the weights
# above - not per-run tunables.
NON_THRESHOLD_SETTINGS = {
    "CACHE_PATH", "LAKE_PATH", "LAKE_ENABLED", "QDRANT_PATH",
    "STORAGE_PATH", "RAW_PATH", "PROCESSED_PATH", "EMBEDDINGS_PATH",
    "FACT_CHECK_PATH", "GRAPH_PATH",
    "EMBEDDING_MODEL", "EMBEDDING_DIMENSION", "SENTIMENT_MODEL",
    "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_TIMEOUT",
    "SEARXNG_URL", "SEARXNG_TIMEOUT", "SEARXNG_MAX_RESULTS",
    "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD",
    "RANKING_SEMANTIC_WEIGHT", "RANKING_RECENCY_WEIGHT",
    "RANKING_RELIABILITY_WEIGHT", "RANKING_DEFAULT_RELIABILITY",
    "CONFIDENCE_LLM_WEIGHT", "CONFIDENCE_EVIDENCE_WEIGHT",
    "EVIDENCE_RECENCY_HALF_LIFE_DAYS",
    "URL_GUARD_ENABLED", "URL_GUARD_ALLOWED_HOSTS", "STORAGE_API_KEY",
}

# These two files are where the thresholds are defined and defaulted, so
# of course they read settings directly.
THRESHOLD_DEFINITION_FILES = {"config/settings.py", "config/thresholds.py"}

SETTINGS_READ = re.compile(r"\bsettings\.([A-Z][A-Z0-9_]*)")

TRIPLE_QUOTES = ('"' * 3, "'" * 3)


def code_lines(path: Path):
    """
    (number, line) for lines that are actual code. Comment lines and
    docstring bodies are skipped: a rule quoted inside a docstring is
    documentation of the rule, not a violation of it - which is how the
    first run of these tests flagged the comment explaining why frozen
    class attributes are forbidden.
    """

    in_docstring = False

    for number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped = line.strip()

        if any(stripped.count(q) == 1 for q in TRIPLE_QUOTES):
            in_docstring = not in_docstring
            continue

        if in_docstring or stripped.startswith("#"):
            continue

        yield number, line.split("  #")[0]


def test_every_per_run_tunable_is_read_through_pipeline_thresholds():
    """
    A threshold read straight from `settings` cannot be overridden for a
    single run, which is exactly how EVIDENCE_FETCH_CANDIDATES ended up
    being the one knob a caller could not tune while the docs claimed
    every threshold was tunable.
    """

    from src.config.thresholds import PipelineThresholds

    known = {name.upper() for name in PipelineThresholds.model_fields}

    offenders = []

    for path in PYTHON_FILES:

        name = relative(path)

        if name in THRESHOLD_DEFINITION_FILES:
            continue

        for number, line in code_lines(path):

            for setting in SETTINGS_READ.findall(line):

                if setting in NON_THRESHOLD_SETTINGS:
                    continue

                # A default on an instance is fine - it is the fallback
                # when no per-run value is supplied.
                if setting in known or "default" in line.lower():
                    continue

                offenders.append(f"{name}:{number}  {line.strip()}")

    assert offenders == [], (
        "Add these to PipelineThresholds, or to NON_THRESHOLD_SETTINGS if "
        "they are infrastructure rather than per-run tunables:\n  "
        + "\n  ".join(offenders)
    )


def test_the_two_threshold_models_expose_the_same_fields():
    """
    ThresholdOverrides is PipelineThresholds with every field optional.
    A knob added to one and forgotten in the other is silently
    un-overridable.
    """

    from src.config.thresholds import PipelineThresholds, ThresholdOverrides

    assert set(ThresholdOverrides.model_fields) == set(
        PipelineThresholds.model_fields
    )


# ----------------------------------------------------------------------
# "Bump SCHEMA_VERSION whenever the analyze() response changes shape"
# ----------------------------------------------------------------------

# The response shape per cache schema version. Change these together or
# the cache serves an old shape forever: it never expires, and a hit
# never rewrites the entry, so a stale one cannot heal on its own.
ANALYZE_RESPONSE_SHAPE = {
    3: {
        "url", "storage", "thresholds", "title", "keywords", "entities",
        "topics", "sentiment", "quality", "claims", "validity",
        "factCheck", "cached",
    },
}


def test_the_analyze_response_shape_matches_the_cache_schema_version():

    from unittest.mock import Mock

    from src.services.analysis_cache import AnalysisCache
    from src.services.analysis_service import AnalysisService
    from src.models.fact_checker.fact_check_report import FactCheckReport

    from tests.factories import create_article
    from tests.services.test_analysis_service import FakeCache, make_news

    version = AnalysisCache.SCHEMA_VERSION

    assert version in ANALYZE_RESPONSE_SHAPE, (
        f"SCHEMA_VERSION is {version} but ANALYZE_RESPONSE_SHAPE does not "
        "describe it - record the new shape here in the same commit."
    )

    article = create_article()

    extractor = Mock()
    extractor.extract.return_value = make_news(id=article.id)

    enrichment = Mock()
    enrichment.process.return_value = article

    fact_checker = Mock()
    fact_checker.run.return_value = FactCheckReport(
        article_id=article.id, validation_passed=True,
    )

    result = AnalysisService(
        fact_checker=fact_checker,
        extractor=extractor,
        enrichment_pipeline=enrichment,
        cache=FakeCache(),
        lake=None,
    ).analyze("https://example.com/a")

    assert set(result) == ANALYZE_RESPONSE_SHAPE[version], (
        "The analyze() response changed shape. Bump "
        "AnalysisCache.SCHEMA_VERSION and record the new key set above."
    )


# ----------------------------------------------------------------------
# "No test module calls its own test function at module level"
# ----------------------------------------------------------------------

TESTS = Path(__file__).resolve().parent

BARE_TEST_CALL = re.compile(r"^test_[A-Za-z0-9_]*\(\)\s*$")


def test_no_test_module_runs_itself_during_collection():
    """
    A bare `test_x()` at module level runs during *collection*, before
    pytest controls execution. This has bitten three times: live network
    scraping on import, a committed fixture overwritten on every run, and
    - worst - two failing assertions that aborted collection and stopped
    the entire suite of 155 unrelated tests from running at all.
    """

    offenders = [
        f"{path.relative_to(TESTS).as_posix()}:{number}"
        for path in TESTS.rglob("test_*.py")
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if BARE_TEST_CALL.match(line)
    ]

    assert offenders == [], (
        "Remove these module-level calls - pytest will run them:\n  "
        + "\n  ".join(offenders)
    )


# ----------------------------------------------------------------------
# "No __init__.py anywhere in src/"
# ----------------------------------------------------------------------


def test_src_stays_a_namespace_package():
    """
    Stated in CLAUDE.md as a consistent convention; also load-bearing,
    since the Docker image never installs the project and imports it from
    the working directory instead.
    """

    found = [relative(p) for p in SRC.rglob("__init__.py")]

    assert found == [], f"src/ must have no __init__.py files: {found}"


# ----------------------------------------------------------------------
# Pipeline stages must report themselves
# ----------------------------------------------------------------------


def test_every_on_phase_caller_passes_a_string_literal_phase():
    """
    CLAUDE.md: don't add a pipeline stage without also calling on_phase.
    The weaker thing that can actually be checked automatically is that
    every phase name is a literal - a computed phase name cannot be found
    by grep, and the frontend's PhaseStepper matches on literals.
    """

    offenders = []

    for path in PYTHON_FILES:

        tree = ast.parse(path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):

            if not isinstance(node, ast.Call):
                continue

            name = getattr(node.func, "id", None) or getattr(
                node.func, "attr", None
            )

            if name not in {"report_phase", "on_phase"}:
                continue

            if node.args and not isinstance(node.args[0], ast.Constant):
                offenders.append(f"{relative(path)}:{node.lineno}")

    assert offenders == [], (
        "Phase names must be string literals so they can be grepped and "
        "matched by the frontend:\n  " + "\n  ".join(offenders)
    )


# ----------------------------------------------------------------------
# Tests must not read settings for expected values
# ----------------------------------------------------------------------

SETTINGS_IN_ASSERT = re.compile(r"^\s*assert\b.*\bsettings\.([A-Z][A-Z0-9_]*)")

# Files whose whole job is to check that a default arrives from settings.
# Asserting "the default equals the configured default" is tautological
# but harmless; asserting a numeric *relationship* against it is the
# hazard this rule exists for, and that is what these files do not do.
SETTINGS_ASSERTION_EXCEPTIONS = {
    "config/test_thresholds.py",
    "test_threshold_routes.py",
    "test_claim_and_enrich_routes.py",
}


def test_no_test_asserts_against_a_threshold_read_from_settings():
    """
    `.env` is deliberately not in git, so a test that asserts against it
    passes or fails depending on the machine. test_related_article did
    exactly this - it needed 0.80 <= 0.970 < DUPLICATE_THRESHOLD, and
    someone tuning that value locally turned it red for no reason.

    Scoped to *threshold* settings. EMBEDDING_DIMENSION and friends are
    infrastructure contracts: a test asserting the loaded model matches
    the configured dimension is doing exactly its job, and must not be
    swept up by this rule.
    """

    from src.config.thresholds import PipelineThresholds

    threshold_settings = {
        name.upper() for name in PipelineThresholds.model_fields
    }

    offenders = []

    for path in TESTS.rglob("test_*.py"):

        name = path.relative_to(TESTS).as_posix()

        if name in SETTINGS_ASSERTION_EXCEPTIONS:
            continue

        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = SETTINGS_IN_ASSERT.match(line)

            if match and match.group(1) in threshold_settings:
                offenders.append(f"{name}:{number}  {line.strip()}")

    assert offenders == [], (
        "Pass an explicit PipelineThresholds instead of asserting against "
        "whatever .env happens to contain:\n  " + "\n  ".join(offenders)
    )


# ----------------------------------------------------------------------
# Both supported languages stay wired up
# ----------------------------------------------------------------------


@pytest.mark.parametrize("language", ["en", "es"])
def test_both_languages_have_a_complete_lexicon(language):
    """
    The pipeline scored every article with English word lists while 7 of
    the 12 configured sources publish in Spanish. A half-filled lexicon
    silently reintroduces that.
    """

    from src.config.lexicons import LEXICONS

    lexicon = LEXICONS[language]

    empty = [
        field
        for field in lexicon.__dataclass_fields__
        if field != "language" and not getattr(lexicon, field)
    ]

    assert empty == [], f"{language} lexicon has empty sets: {empty}"


def test_every_configured_source_language_has_a_lexicon():
    """
    Adding a source in a third language is a YAML change, which would
    otherwise silently fall back to English scoring.
    """

    import yaml

    from src.config.lexicons import SUPPORTED_LANGUAGES

    sources = Path(__file__).resolve().parents[1] / "data" / "sources"

    languages = {
        yaml.safe_load(path.read_text(encoding="utf-8")).get("language", "en")
        for path in sources.glob("*.yaml")
    }

    unsupported = languages - SUPPORTED_LANGUAGES

    assert unsupported == set(), (
        f"Sources declare {unsupported}, which has no lexicon in "
        "src/config/lexicons.py - those articles would be scored as English."
    )

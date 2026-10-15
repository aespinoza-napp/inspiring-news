"""
The writer's deterministic checks (src/services/writer/draft_checks.py):
what is repaired in the model's answer, and what is only reported.
"""

from src.services.writer.draft_checks import (
    check,
    cited_numbers,
    normalise_markdown,
    repair_citations,
    slugify,
    unsupported_numbers,
    verbatim_overlaps,
)


# ----------------------------------------------------------------------
# Citations
# ----------------------------------------------------------------------


def test_a_citation_past_the_sources_is_dropped_and_reported():

    body, dropped = repair_citations("Trees were planted [2]. Fish came back [7].", count=3)

    assert body == "Trees were planted [2]. Fish came back."
    assert dropped == [7]


def test_grouped_and_ranged_citations_become_one_bracket_each():

    body, dropped = repair_citations("It grew [1, 3] and spread [2-3]; zero [0; 2].", count=3)

    assert body == "It grew [1][3] and spread [2][3]; zero [2]."
    assert dropped == [0]


def test_a_bracketed_year_span_is_not_a_citation():

    body, dropped = repair_citations("Drained [1960-1990] and replanted [1].", count=2)

    assert body == "Drained [1960-1990] and replanted [1]."
    assert dropped == []


def test_cited_numbers_reads_every_group():

    assert cited_numbers("a [1] b [2, 4] c [3-4]") == {1, 2, 3, 4}


# ----------------------------------------------------------------------
# Markdown: only what ArticleBody renders
# ----------------------------------------------------------------------


def test_the_markdown_is_reduced_to_what_the_page_renders():

    body = normalise_markdown(
        "# A forest returns\n"
        "The valley was replanted [1].\n"
        "#### Who did it\n"
        "* volunteers [1]\n"
        "2. schools [2]\n"
        "Read [the report](https://example.org/report) <br> and *see* __this__ [3](https://x.example).\n"
        "```\ncode\n```\n"
        "![a photo](https://example.org/a.jpg)Last line [1].",
        title="A forest returns",
    )

    assert body == (
        "The valley was replanted [1].\n\n"
        "### Who did it\n\n"
        "- volunteers [1]\n"
        "- schools [2]\n\n"
        "Read the report and see **this** [3].\n\n"
        "Last line [1]."
    )


def test_a_heading_never_shares_a_block_with_prose():
    """In one block, ArticleBody would render the paragraph inside the h2."""

    body = normalise_markdown("## What changed\nThe meadow doubled [1].")

    assert body == "## What changed\n\nThe meadow doubled [1]."


# ----------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------


def test_a_passage_copied_from_the_analysed_article_is_found():

    original = (
        "Volunteers in the valley planted forty thousand native trees this spring, "
        "restoring a wetland that had been drained for farmland in the 1960s."
    )

    copied = verbatim_overlaps(
        "In a remarkable effort, volunteers in the valley planted forty thousand native trees "
        "this spring, restoring a wetland [1]. Elsewhere, schools joined [2].",
        original,
    )

    assert copied == ["volunteers in the valley planted forty thousand native trees this spring restoring a wetland"]


def test_a_paraphrase_is_not_a_copy():

    assert verbatim_overlaps(
        "This spring, local volunteers put forty thousand native trees into the ground [1].",
        "Volunteers in the valley planted forty thousand native trees this spring.",
    ) == []


def test_numbers_are_matched_whatever_the_thousands_separator():

    found = unsupported_numbers(
        "Van plantar 40.000 arbres [1] el 2026 [1], i 12 escoles [2].",
        ["Volunteers planted 40,000 trees in 2026."],
    )

    assert found == ["12"]


def test_citation_numbers_are_not_counted_as_figures():

    assert unsupported_numbers("Trees were planted [4].", ["Trees were planted."]) == []


def test_check_repairs_first_and_reports_what_it_cannot_repair():

    checked = check(
        "# Title\nTrees were planted in 2026 [1] [9]. This sentence has no source and makes a claim.",
        title="Title",
        source_count=2,
        original="",
        texts=["Trees were planted in 2026."],
    )

    assert checked.body == "Trees were planted in 2026 [1]. This sentence has no source and makes a claim."
    assert checked.dropped_citations == [9]
    assert any("past the 2 sources" in finding for finding in checked.findings)
    assert any("no citation" in finding for finding in checked.findings)


def test_slugs_are_ascii_and_hyphenated():

    assert slugify("Les praderies d'algues tornen a la badia!") == "les-praderies-d-algues-tornen-a-la-badia"
    assert slugify("Árboles en el valle: 40.000") == "arboles-en-el-valle-40-000"

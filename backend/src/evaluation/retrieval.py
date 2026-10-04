"""
Retrieval metrics: how well the pipeline finds evidence, per run, and
how two retrieval strategies differ, paired claim by claim.

    uv run python -m src.evaluation.cli report --run <dir>          # a "Retrieval" section
    uv run python -m src.evaluation.cli retrieval --run A --run B   # strategies side by side

Two kinds of number, from what every harness record already holds
(`candidates`, `evidence`, `queries`, `latency`):

**Against the annotator's references** (`referenceEvidenceLinks`), at
three depths - every candidate seen, the ranked evidence the model was
shown, the evidence it cited:

    linkRecall@depth    a reference URL was found at that depth
    domainRecall@depth  a reference's domain was
    linkMRR, domainMRR  1 / rank of the first reference in the ranked list

URLs are normalised with the retriever's own `_comparable` (imported, not
copied: "found" means what the pipeline means by it), domains the way
`Evidence.domain` is computed. For x-fact, references on the row's own
site are the published verdict, not evidence: they are removed from the
reference set and counted (`selfLinks`). A miss is not proof of failure -
another source can be as good as the annotator's - which is why domain
hits sit beside link hits.

**Without references**, for any set: whether a claim got any evidence,
how many candidates and ranked sources, what share the pertinence gate
cut, distinct domains, the share from rated domains and from the
internal corpus, which query kinds found the ranked sources, how often a
ranked source was the fact-checker's own verdict page, and the seconds
retrieval and ranking took.

Claims whose search failed (`searchUnavailable`) and errors are counted
and left out, as everywhere in the harness: an outage is not a strategy.
Every claim-level number is averaged with a percentile bootstrap
interval; a comparison is the paired difference over the claims both
runs searched.

A *strategy* is a run: thresholds (`--thresholds`), corpus mode, the
environment, or the code at a commit - named with `--label`, which is
part of the run key. `--retrieval-only` runs skip the LLM, so a strategy
costs only its search and fetch time. docs/decisions/evaluation.md
§Retrieval evaluation.
"""

from __future__ import annotations

from collections import Counter
from typing import Callable

from src.evaluation.metrics import ERROR, SCORED, LLM_UNREACHABLE, SEARCH_UNAVAILABLE, on_site, outcome
from src.evaluation.stats import bootstrap_mean, mean, median, paired_bootstrap_mean, rounded
from src.services.fact_checker.retrieval.evidence_retriever import _comparable
from src.services.fact_checker.retrieval.search_provider import registrable_domain

RANKED = "ranked"

DEPTHS = ("candidates", "ranked", "cited")

INTERNAL = "internal"

# Claim-level values averaged into the headline, with the subset of
# claims each is defined on: "references" needs a reference set.
GOLD_METRICS = (
    *(f"linkRecall@{depth}" for depth in DEPTHS),
    *(f"domainRecall@{depth}" for depth in DEPTHS),
    "linkMRR",
    "domainMRR",
)

GOLD_FREE_METRICS = (
    "hasEvidence",
    "candidates",
    "ranked",
    "gateCut",
    "uniqueDomains",
    "ratedShare",
    "corpusShare",
    "verdictLeak",
    "retrievalSeconds",
    "rankingSeconds",
)

# Shown as percentages; the rest as counts or seconds.
RATES = {*GOLD_METRICS, "hasEvidence", "gateCut", "ratedShare", "corpusShare", "verdictLeak"}


# ----------------------------------------------------------------------
# One claim
# ----------------------------------------------------------------------


def placeholders(record: dict) -> int:
    """
    Reference entries that are not links. x-fact writes
    "<LINK NOT AVAILABLE>" where the fact-checker's sources were lost -
    every PolitiFact row in the pilot. Counted, so a claim without
    references says why.
    """

    return sum(
        1 for url in record.get("referenceEvidenceLinks") or []
        if not isinstance(url, str) or "://" not in url
    )


def references(record: dict) -> tuple[set[str], set[str], int]:
    """
    The reference links and domains, normalised, and how many links were
    the fact-checker's own verdict page (x-fact only) and so removed.
    """

    links, domains, self_links = set(), set(), 0

    for url in record.get("referenceEvidenceLinks") or []:

        if not isinstance(url, str) or "://" not in url:
            continue

        domain = registrable_domain(url)

        if not domain:
            continue

        if record.get("dataset") == "xfact" and on_site(domain, record.get("site")):
            self_links += 1
            continue

        links.add(_comparable(url))
        domains.add(domain)

    return links, domains, self_links


def _sources(record: dict) -> dict[str, list[dict]]:

    evidence = record.get("evidence") or []

    candidates = list(record.get("candidates") or [])

    # The ranked list is in `candidates` too; added in case an older
    # record left it out, so "seen" is never smaller than "ranked".
    seen = {_comparable(item.get("url") or "") for item in candidates}
    candidates += [item for item in evidence if _comparable(item.get("url") or "") not in seen]

    return {
        "candidates": candidates,
        "ranked": evidence,
        "cited": [item for item in evidence if item.get("cited")],
    }


def _domain(item: dict) -> str:

    return (item.get("domain") or registrable_domain(item.get("url") or "")).lower().removeprefix("www.")


def _first_rank(ranked: list[dict], hit: Callable[[dict], bool]) -> int | None:

    return next((index for index, item in enumerate(ranked, start=1) if hit(item)), None)


def claim_retrieval(record: dict) -> dict:
    """Everything this module measures for one claim."""

    links, domains, self_links = references(record)

    sources = _sources(record)
    ranked = sources["ranked"]
    candidates = sources["candidates"]

    def link_hit(item: dict) -> bool:
        return _comparable(item.get("url") or "") in links

    def domain_hit(item: dict) -> bool:
        return _domain(item) in domains

    values: dict[str, float | None] = {}

    if links:
        for depth in DEPTHS:
            values[f"linkRecall@{depth}"] = 1.0 if any(link_hit(item) for item in sources[depth]) else 0.0
            values[f"domainRecall@{depth}"] = 1.0 if any(domain_hit(item) for item in sources[depth]) else 0.0

        link_rank = _first_rank(ranked, link_hit)
        domain_rank = _first_rank(ranked, domain_hit)

        values["linkMRR"] = 1 / link_rank if link_rank else 0.0
        values["domainMRR"] = 1 / domain_rank if domain_rank else 0.0

    cut_at_ranking = sum(1 for item in candidates if item.get("stoppedAt") == "evidence_ranking")

    stances = [item.get("stance") for item in ranked]

    latency = record.get("latency") or {}

    values.update({
        "hasEvidence": 1.0 if ranked else 0.0,
        "candidates": float(len(candidates)),
        "ranked": float(len(ranked)),
        # What the gate and the cap cut of what reached ranking.
        "gateCut": (cut_at_ranking / (cut_at_ranking + len(ranked))) if (cut_at_ranking + len(ranked)) else None,
        "uniqueDomains": float(len({_domain(item) for item in ranked})),
        "ratedShare": mean([1.0 if item.get("reliabilityKnown") else 0.0 for item in ranked]),
        "corpusShare": mean([1.0 if item.get("origin") == INTERNAL else 0.0 for item in ranked]),
        "verdictLeak": (
            (1.0 if any(on_site(_domain(item), record.get("site")) for item in ranked) else 0.0)
            if record.get("dataset") == "xfact" else None
        ),
        "retrievalSeconds": latency.get("retrieval"),
        "rankingSeconds": latency.get("ranking"),
    })

    # References found, then cut - where and why: the drop between depths.
    cut = [
        f"{item.get('stoppedAt')}: {item.get('reason') or 'no reason given'}"
        for item in candidates
        if links and link_hit(item) and item.get("stoppedAt") != RANKED
    ]

    return {
        "id": record.get("id"),
        "dataset": record.get("dataset"),
        "language": record.get("language"),
        "outcome": outcome(record),
        "hasReferences": bool(links),
        "selfLinks": self_links,
        "placeholders": placeholders(record),
        "queries": len(record.get("queries") or []),
        "values": values,
        "referencesCut": cut,
        "foundBy": Counter(kind for item in ranked for kind in item.get("foundBy") or []),
        "stanced": sum(1 for stance in stances if stance in ("supports", "contradicts")),
    }


# ----------------------------------------------------------------------
# A run
# ----------------------------------------------------------------------


def _searched(claims: list[dict]) -> list[dict]:

    return [claim for claim in claims if claim["outcome"] in (SCORED, LLM_UNREACHABLE)]


def _aggregate(claims: list[dict], names, *, seed: int, resamples: int) -> dict:

    result = {}

    for name in names:

        values = [claim["values"][name] for claim in claims if claim["values"].get(name) is not None]

        result[name] = {
            "n": len(values),
            "value": rounded(mean(values)),
            **{key: rounded(value) for key, value in bootstrap_mean(values, seed=seed, resamples=resamples).items()},
        }

    return result


def retrieval_metrics(records: list[dict], *, seed: int, resamples: int) -> dict:
    """The retrieval section of a report, for one run's records."""

    claims = [claim_retrieval(record) for record in records]

    searched = _searched(claims)

    with_refs = [claim for claim in searched if claim["hasReferences"]]

    found_by = Counter()

    for claim in searched:
        found_by.update(claim["foundBy"])

    groups: dict[str, dict] = {}

    for dimension in ("dataset", "language"):

        values = sorted({claim[dimension] for claim in searched if claim[dimension]})

        groups[dimension] = {}

        for value in values:

            group = [claim for claim in searched if claim[dimension] == value]
            group_refs = [claim for claim in group if claim["hasReferences"]]

            groups[dimension][value] = {
                "claims": len(group),
                "withReferences": len(group_refs),
                **{
                    name: rounded(mean([claim["values"][name] for claim in source if claim["values"].get(name) is not None]))
                    for name, source in (
                        ("linkRecall@ranked", group_refs),
                        ("domainRecall@ranked", group_refs),
                        ("hasEvidence", group),
                    )
                },
            }

    return {
        "claims": {
            "total": len(claims),
            "searched": len(searched),
            "withReferences": len(with_refs),
            "searchUnavailable": sum(1 for claim in claims if claim["outcome"] == SEARCH_UNAVAILABLE),
            "errors": sum(1 for claim in claims if claim["outcome"] == ERROR),
            "selfLinksRemoved": sum(claim["selfLinks"] for claim in claims),
            # Searched, no usable reference, and at least one placeholder:
            # the set lost the annotator's sources, the system did not miss them.
            "referencesUnavailable": sum(
                1 for claim in searched if not claim["hasReferences"] and claim["placeholders"]
            ),
        },
        "gold": _aggregate(with_refs, GOLD_METRICS, seed=seed, resamples=resamples),
        "goldFree": _aggregate(searched, GOLD_FREE_METRICS, seed=seed, resamples=resamples),
        "medians": {
            name: rounded(median([claim["values"][name] for claim in searched if claim["values"].get(name) is not None]), 3)
            for name in ("candidates", "ranked", "retrievalSeconds", "rankingSeconds")
        },
        "queriesPerClaim": rounded(mean([float(claim["queries"]) for claim in searched]), 2),
        "foundBy": dict(found_by.most_common()),
        "referencesCut": dict(Counter(reason for claim in searched for reason in claim["referencesCut"]).most_common()),
        "groups": groups,
        "bootstrap": {"seed": seed, "resamples": resamples},
    }


# ----------------------------------------------------------------------
# Two runs
# ----------------------------------------------------------------------


def compare_retrieval(
    baseline: list[dict],
    candidate: list[dict],
    *,
    seed: int,
    resamples: int,
) -> dict:
    """
    Candidate (B) minus baseline (A), per metric, paired over the claims
    both runs searched (and, for the reference metrics, that have
    references). A claim whose search failed on either side is left out
    of both: one side's outage is not the other's better strategy.
    """

    a = {claim["id"]: claim for claim in map(claim_retrieval, baseline)}
    b = {claim["id"]: claim for claim in map(claim_retrieval, candidate)}

    shared = sorted(
        key for key in set(a) & set(b)
        if a[key]["outcome"] in (SCORED, LLM_UNREACHABLE) and b[key]["outcome"] in (SCORED, LLM_UNREACHABLE)
    )

    differences = {}

    for name in (*GOLD_METRICS, *GOLD_FREE_METRICS):

        paired = [
            key for key in shared
            if a[key]["values"].get(name) is not None and b[key]["values"].get(name) is not None
        ]

        values_a = [a[key]["values"][name] for key in paired]
        values_b = [b[key]["values"][name] for key in paired]

        interval = paired_bootstrap_mean(values_a, values_b, seed=seed, resamples=resamples)

        differences[name] = {
            "pairs": len(paired),
            "baseline": rounded(mean(values_a)),
            "candidate": rounded(mean(values_b)),
            **{key: rounded(value) for key, value in interval.items()},
            # Claims where only one side found a reference: where the
            # strategies actually differ, not just how often.
            **(
                {
                    "onlyBaseline": sum(1 for x, y in zip(values_a, values_b) if x > y),
                    "onlyCandidate": sum(1 for x, y in zip(values_a, values_b) if y > x),
                }
                if name in GOLD_METRICS else {}
            ),
        }

    return {
        "pairedClaims": len(shared),
        "onlyInBaseline": len(set(a) - set(b)),
        "onlyInCandidate": len(set(b) - set(a)),
        "differences": differences,
    }


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------


def fmt(name: str, value) -> str:

    if value is None:
        return "n/a"

    if name in RATES:
        return f"{value * 100:.1f}%"

    return f"{value:.2f}"


def with_interval(name: str, block: dict) -> str:

    if block.get("value") is None:
        return "n/a"

    if block.get("low") is None:
        return fmt(name, block["value"])

    return f"{fmt(name, block['value'])} [{fmt(name, block['low'])}, {fmt(name, block['high'])}]"


LABELS = {
    "linkRecall@candidates": "Reference link among candidates",
    "linkRecall@ranked": "Reference link among ranked evidence",
    "linkRecall@cited": "Reference link among cited evidence",
    "domainRecall@candidates": "Reference domain among candidates",
    "domainRecall@ranked": "Reference domain among ranked evidence",
    "domainRecall@cited": "Reference domain among cited evidence",
    "linkMRR": "Link MRR (ranked)",
    "domainMRR": "Domain MRR (ranked)",
    "hasEvidence": "Claims with any ranked evidence",
    "candidates": "Candidates per claim",
    "ranked": "Ranked sources per claim",
    "gateCut": "Share cut at ranking (gate, cap)",
    "uniqueDomains": "Distinct domains among ranked",
    "ratedShare": "Ranked from rated domains",
    "corpusShare": "Ranked from the internal corpus",
    "verdictLeak": "Fact-checker's own page ranked (x-fact)",
    "retrievalSeconds": "Retrieval seconds per claim",
    "rankingSeconds": "Ranking seconds per claim",
}


def render_section(section: dict) -> list[str]:
    """The `## Retrieval` part of report.md."""

    claims = section["claims"]

    lines = [
        "## Retrieval",
        "",
        f"{claims['searched']} claims searched ({claims['withReferences']} with reference links), "
        f"{claims['searchUnavailable']} with search unavailable and {claims['errors']} errors left out; "
        f"{claims['selfLinksRemoved']} reference link(s) on the fact-checker's own site removed from the "
        f"reference set; {claims['referencesUnavailable']} searched claim(s) have only placeholder references "
        "(\"<LINK NOT AVAILABLE>\" in the set). Means with 95% bootstrap intervals over claims.",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]

    for name, block in {**section["gold"], **section["goldFree"]}.items():
        lines.append(f"| {LABELS[name]} | {with_interval(name, block)} (n={block['n']}) |")

    medians = section["medians"]

    lines += [
        "",
        f"Medians: {fmt('candidates', medians['candidates'])} candidates, {fmt('ranked', medians['ranked'])} ranked, "
        f"{fmt('retrievalSeconds', medians['retrievalSeconds'])} s retrieval, "
        f"{fmt('rankingSeconds', medians['rankingSeconds'])} s ranking; "
        f"{fmt('queries', section['queriesPerClaim'])} queries per claim.",
        "",
        "Ranked sources found by: "
        + (", ".join(f"{kind} {count}" for kind, count in section["foundBy"].items()) or "none recorded")
        + " (a source two queries found counts for both).",
        "",
    ]

    if section["referencesCut"]:
        lines += [
            "References found, then cut:",
            "",
            *(f"- {reason}: {count}" for reason, count in section["referencesCut"].items()),
            "",
        ]

    for dimension, groups in section["groups"].items():

        if not groups:
            continue

        lines += [
            f"| By {dimension} | Claims | With refs | Link @ranked | Domain @ranked | Any evidence |",
            "|---|---|---|---|---|---|",
            *(
                f"| {value} | {g['claims']} | {g['withReferences']} | {fmt('linkRecall@ranked', g['linkRecall@ranked'])} "
                f"| {fmt('domainRecall@ranked', g['domainRecall@ranked'])} | {fmt('hasEvidence', g['hasEvidence'])} |"
                for value, g in groups.items()
            ),
            "",
        ]

    return lines


def render_comparison(comparison: dict, baseline: str, candidate: str) -> list[str]:

    lines = [
        f"### Retrieval: {candidate} − {baseline}",
        "",
        f"Paired over {comparison['pairedClaims']} claims both searched "
        f"({comparison['onlyInBaseline']} only in the baseline, {comparison['onlyInCandidate']} only in the candidate).",
        "",
        "| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |",
        "|---|---|---|---|---|---|",
    ]

    for name, d in comparison["differences"].items():

        if not d["pairs"]:
            continue

        difference = "n/a" if d.get("difference") is None else (
            f"{_signed(name, d['difference'])} [{_signed(name, d['low'])}, {_signed(name, d['high'])}]"
        )

        lines.append(
            f"| {LABELS[name]} | {d['pairs']} | {fmt(name, d['baseline'])} | {fmt(name, d['candidate'])} "
            f"| {difference} | {str(d['onlyBaseline']) + ' / ' + str(d['onlyCandidate']) if 'onlyBaseline' in d else ''} |"
        )

    return lines + [""]


def _signed(name: str, value) -> str:

    if value is None:
        return "n/a"

    if name in RATES:
        return f"{value * 100:+.1f} pts"

    return f"{value:+.2f}"

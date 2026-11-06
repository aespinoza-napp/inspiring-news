---
name: what-to-search
description: Decide, before any search, what a news claim turns on - the decisive figures, dates, names and the subject the sentence never says - what kind of source would settle it, and the queries a careful person would type; then search and record what settled it. The blind first step of the fact-checker troubleshooting (troubleshoot.py plan/search). Use when asked what should be searched for a claim, or when run by the troubleshooting agent.
---

# What to search for a claim

This is how Claude checked the 4 Nov batch by hand (16 of 20 right, the pipeline 9):
**decide what would settle the claim before typing anything.** The pipeline's worst
failures start here: its queries carried the sentence's words and lost the one detail
the claim turned on (fact037 was searched without "dengue" and without "212").
`docs/troubleshooting/fact-checking/01-what-to-look-for.md` has the findings; do not
read it during a blind step (the hook refuses it, since it quotes the pipeline).

## Blind, always

In the `plan` and `search` steps you see only `claims.jsonl`: id, language, date, the
article's link and headline, the sentence. **No label, no reference links, no pipeline
record.** Do not look for them; the hook refuses them anyway. Your files are evidence
for the comparison only because they were written first.

## Plan (step 1): one line per claim in `plan.jsonl`

Read the sentence, then the headline. For each claim write:

```json
{"id": "fact037", "language": "en",
 "lookingFor": "Florida has had 212 travel-related dengue cases so far in 2026.",
 "decisive": ["212", "travel-related", "dengue", "Florida", "2026"],
 "subjectNotInSentence": ["dengue"],
 "wouldSettleIt": "Florida Health's weekly arbovirus report for 2026 giving 212 travel-associated dengue cases.",
 "sourceType": "official report: Florida Department of Health, arbovirus surveillance",
 "queries": ["Florida 212 travel-related dengue cases 2026", "Florida Health arbovirus report 2026 dengue travel"],
 "excludeSite": "<the claim's excludeSite>",

 "blind": "before any search, without the label or the pipeline's records"}
```

How to fill each field:

1. **`lookingFor`**: the claim as one checkable statement, in English, with what the
   sentence leaves implicit made explicit (the subject from the headline, the year from
   the date, "La nave" -> "Starship"). Reported speech: the fact inside the quote, and
   who said it.
2. **`decisive`**: the details a source **must carry** to confirm or refute it, as
   short strings the script can look for in a query or a quote, most decisive first:
   - every **figure with its unit or noun** as written ("212", "0.001%", "25 millones",
     "11-set"); a figure is one item, its noun may be another;
   - **dates with their day** ("12 September"), the year when the claim depends on it;
   - **identifiers** kept whole ("SE-20", "COVID-19") and **multi-word names** kept
     together ("Ronda Urbana Norte", "Ignacio Calvo de Mora");
   - the **head noun of the assertion** ("dengue", "sea ice", "symmetric", "splashdown");
   - the **place or event** when the claim could be true elsewhere (Calonge, not any ring road).
   Not the sentence's filler ("Meanwhile", "Indeed", "been", "another"), not words any
   page on the subject has. Three to six items; a claim with no figure still has names
   and a head noun.
3. **`subjectNotInSentence`**: the words of `decisive` the sentence does not contain
   (from the headline or the date). The pipeline loses exactly these.
4. **`wouldSettleIt`**: the evidence that would settle it, concretely: who would say
   it, in what document, with which detail.
5. **`sourceType`**: the **primary source** if one can be named in advance (the
   statistics office or health department, the study and its journal, the agency's
   release, the organisation's own site, the court ruling), else the kind of outlet
   ("a second outlet's report of the same event"). In the 4 Nov batch 9 of 20 had a
   primary source nameable in advance, and it was found in 8.
6. **`queries`**: one or two, as you would type them:
   - carry the most decisive figure and the head noun, and the subject the sentence
     lacks;
   - multi-word names whole, no filler, no "fact check OR debunked" (it found no
     refutation in 20 claims, and twice found its own words);
   - one query naming the primary source when there is one;
   - for a Spanish claim, at least one query in Spanish; an English one too when the
     event is international (US outlets saw fact008's real landing site).

Do not search in this step. The plan is what you would do, written before you know
whether it works.

## Searching (step 2): one line per claim in `claude.jsonl`

Run the plan's queries with WebSearch, **never the article's own site** (`excludeSite`;
the hook refuses fetching it). At most **one follow-up** search per claim, only where
the first left a decisive detail open, and say why in `followUp`. Read a result page
with WebFetch when the snippet does not show the detail.

```json
{"id": "fact037", "searches": ["Florida 212 travel-related dengue cases 2026"],
 "followUp": null,
 "found": "Florida Health's week-37 arbovirus report: 212 travel-associated dengue cases in 2026.",
 "settled": true, "how": "all details found",
 "verdict": "TRUE",
 "settlingSource": "https://www.floridahealth.gov/...",
 "sources": ["https://www.floridahealth.gov/...", "https://..."],
 "detailsFound": ["212", "travel-related", "dengue", "Florida", "2026"],
 "detailsNotFound": [],
 "excludedSite": "...", "searchedWith": "Claude Code WebSearch, article's own site excluded",
 "blind": "no label, no reference links, no pipeline record read before this file was written"}
```

The verdict, by the annotator's rule:
- **TRUE**: every decisive detail found, in a source other than the article (or its
  wire copies: the same agency text on five sites is one source).
- **PARTIALLY_TRUE**: the main point holds and a secondary detail is wrong or overstated.
- **FALSE**: a decisive detail is contradicted by a source about the same event and
  period (fact008: the splashdown was north of Hawaii, not off Chile).
- **UNVERIFIED**: a decisive detail could not be found either way. Not finding it is
  not FALSE.

`settlingSource` is the one page that settled it (or came closest), `null` when nothing
did. The script compares its domain with the pipeline's candidates, so give the page's
real URL, not a search page.

## Rules

- Write each file whole, one JSON object per line, one line per claim in
  `claims.jsonl`, nothing else. The script checks the fields and refuses a missing one.
- Never guess a URL or a figure: what you write in `found` you read on a page.
- Do not revise `plan.jsonl` after searching: a plan corrected by its result says
  nothing about planning.

# 5. Verification

**The part:** under `verifier_answer: per_source` (the default since 22 Oct),
the model is asked about one source at a time: supports, contradicts, silent or
unrelated, with a quote (`verification/per_source.py`). The verdict is the side
more outlets take, and a tie is UNVERIFIED. Silent and unrelated sources do not
vote. `ConfidenceScorer` then applies its floors.

## Finding (4 Nov 2026, 20 train claims, today's defaults replayed: `1d07e163a659`)

The pipeline got 11 of the 20 wrong. In **6 of the 11, the verdict was decided
by one or two stances on sources that were not about the claim**, while the
rest were silent:

| Claim (gold) | Verdict | The stance that decided it, with its quote |
|---|---|---|
| fact037 (TRUE: 212 travel-related dengue cases) | **FALSE** | NYT, 2010, "Case of Cholera in Florida Is Linked to Haiti Outbreak": *contradicts*, quoting "large numbers of whom travel to and from the island nation" |
| fact062 (TRUE: Chinese industry less dependent on fossil fuels) | **FALSE** | Columbia CGEP on the Hormuz crisis raising demand for Chinese clean tech, and USCC on China's reliance on imported fuels: both *contradicts* |
| fact010 (UNVERIFIED: 25 M EUR boulevard by 2028) | **TRUE** | es.wikipedia "Ronda Norte de Sevilla": *supports*, quoting the 1992 works' "573 millones de pesetas" |
| fact011 (UNVERIFIED: the road to Calonge) | **TRUE** | castellonplaza.com, a ring road in **Castellón**: *supports*, quoting "el proyecto de 2.000 viviendas" |
| fact049 (UNVERIFIED: fewer than 0.001% of brain cells) | **TRUE** | StatPearls "the human brain comprises approximately 86 billion neurons" and a 2019 paper on cholinergic neurons: *supports* (2) against Wikipedia's cerebellum: *contradicts* (1) |
| fact020 (TRUE: Jire, 68 days) | UNVERIFIED | Two news stories about human infants, not chimpanzees, from the query `Jimato Jire carried lifeless body infant`: a baby found in Calabar, *contradicts*; a man in Jharkhand carrying his infant's body, *supports*. A tie |

Every one is a quote that does not mention the claim's point: no 212, no
dengue, no 25 million, no 2028, no Calonge, no 0.001%. The model said
"supports" or "contradicts" because the source was on a nearby subject. With
one call per source, it has no way to see that the others were silent, and the
majority rule counts that one stance as the whole evidence.

**Copies still vote.** fact008's three "supports" are EFE's wire story and its
copies (abc.es, efe.com) and Wikipedia. The one *contradicts* (Onda Cero's video
page, no quote) may be the only source that saw the northern-Pacific landing.
The verdict was TRUE, the gold label's. Claude, reading US outlets, said FALSE
([README.md](README.md), "Where Claude and the gold label disagree").

## What to try

All of these come after retrieval, so they are exact replays:

1. **A stance must show its point.** When the claim has a figure, "supports" or
   "contradicts" counts only if its quote carries that figure. Otherwise it
   counts as silent. On the six claims above:
   - fact037 (212), fact010 (25 millones, 2028) and fact049 (0.001) would
     become UNVERIFIED: two of them right, and fact037 still wrong, but no
     longer confidently wrong.
   - fact062 and fact011 have no figure, and their quotes share the claim's
     words ("fossil fuels", "proyecto"), so this rule leaves them. They need
     rule 2.
   - fact020 stays a tie.

   A code change in `per_source.py` behind a new field, the default unchanged.
   A key-term version (the terms `terms.py` already extracts) would catch more,
   and wrongly silence more. Measure both.
2. **"Contradicts" needs the same event and period.** One added rule in
   `PER_SOURCE_SYSTEM_PROMPT`: a source about another time, place or event is
   unrelated, not contradicting. V4's lesson applies: a rule that makes the 3B
   look for differences found ones that were not there, so measure confidently
   wrong as well as accuracy.
3. **One stance is not a majority.** A definitive verdict from a single voting
   source among four or five silent ones could need a second outlet. A scorer
   rule, cheap to replay, but it costs coverage.

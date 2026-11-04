# 2. Query planning

**The part:** `retrieval/query_builder.py` plans three queries per claim, run
concurrently and fused by reciprocal rank: **anchor** (who and what),
**proposition** (what is asserted), **refutation** (the anchor plus "fact check
OR debunked OR false", or "verificación OR desmentido OR bulo OR falso").
`terms.py` chooses the words, shared with lexical ranking.

## Finding (4 Nov 2026, 20 train claims, run `cc053417c0cb`)

Claude's queries against the pipeline's, as written
(`plan.jsonl`, `comparison.json`):

| Claim | Claude | Pipeline: anchor / proposition |
|---|---|---|
| fact037 | `Florida 212 travel-related dengue cases 2026` | `Florida` / `Florida been total known travel related cases` |
| fact038 | `Arctic sea ice minimum 2026 September 12 NSIDC` | `Arctic` / `Arctic Meanwhile recorded minimum summer extent September` |
| fact049 | `Shah neurons fewer than 0.001 percent brain cells pregnancy` | `Shah` / `Shah neurons comprise fewer cent brain cells` |
| fact016 | `Book Bunk 138,000 books cataloged 23,000 titles Braille` | `Book Bunk` / `Book Bunk cataloged books added another titles converting` |
| fact062 | `analysis Chinese industry less dependent fossil fuels September 2026` | `Chinese industry` / `Chinese industry several measures becoming less dependent fossil` |
| fact081 | `symmetric 11-set Venn diagram 2012 13-set 2014` | `Venn diagram criteria discovered another sets found` / `Venn diagram criteria discovered another sets` |
| fact064 | `fossil fuel use peaked eight of 11 industrial sectors China ...` | `food machinery pharmaceuticals textiles` / `food machinery eight industrial sectors including fossil fuel` |
| fact008 | `Starship orbital flight splashdown Pacific Chile` | `SpaceX Chile Elon Musk` / `SpaceX Chile nave Starship amerizó éxito lunes océano` |
| fact010 | `Ronda Urbana Norte bulevar verde 25 millones 2028 Sevilla` | `Ronda Urbana Norte Sevilla` / `... ejecutada infraestructura función metropolitana pasará nueva` |

Four patterns, each seen several times:

1. **Every figure is dropped.** 212, 0.001, 138,000, 23,000, 12 (September),
   2012, 2014, 25 millones, 2028: none reaches a query, though the figure is
   what most of these claims turn on. Claude put it in every query that had
   one.
2. **The key noun is lost.** "dengue" (fact037), "sea ice" (fact038),
   "symmetric" (fact081), "China" (fact064), "pregnancy" (fact049). Words kept
   instead are the sentence's filler: "Meanwhile", "been", "Indeed",
   "becoming", "another".
3. **The anchor collapses to one entity**: `Florida`, `Arctic`, `Shah`, `Book
   Bunk`, `Chinese industry`, `Chris Dzoba`. A one-word anchor retrieves
   anything about Florida or anyone named Shah. For fact082, it brought the
   developer's profile pages (buymeacoffee, me.sh, ticalc), and they won the
   ranking (see [04-ranking.md](04-ranking.md)).
4. **The refutation query finds no refutations, and sometimes finds its own
   words.** "fact check OR debunked OR false" appended to an entity searches for
   a debunk that does not exist for a library's book count or a sea-ice date. Of
   the 95 sources kept across the 20 claims, 10 were found by it alone (each
   source's `foundBy`):
   - 4 were useful. The engines ignored the debunk words, so it acted as a second
     anchor query (wikiquote for fact015, the Vega Sicilia and wine pages for
     fact065 and fact066).
   - 6 matched the debunk words themselves: "Bunk: The Rise of Hoaxes, Humbug,
     Plagiarists..." for Book Bunk (fact016), "35 Florida election myths and
     misinformation debunked" (fact037), the singer "Ember Swift" (fact063),
     and other silent pages.
   - None was a fact-check of the claim.

## Built (2026-11-04), not yet measured

`query_plan: checkable` (`query_builder.plan_checkable`) plans the three queries
from the checkable point ([01-what-to-look-for.md](01-what-to-look-for.md)):

| Claim | anchor / proposition / third, under `checkable` |
|---|---|
| fact037 | `Florida "212" 2026` / `Florida "212" travel related cases` / specifics `Florida "212" 2026 travel related cases` |
| fact049 | `Shah "0.001 per cent"` / `Shah "0.001 per cent" neurons comprise fewer brain cells` / specifics `Shah "0.001 per cent" neurons comprise fewer` |
| fact010 | `Ronda Urbana Norte Ayuntamiento de Sevilla "SE-20" "25 millones" 2028` / ... / specifics `Ronda Urbana Norte "SE-20" "25 millones" 2028 ejecutada infraestructura función` |
| fact081 | `Venn "11-set" "13" 2012` / `Venn "13" diagram criteria discovered sets` / specifics `Venn "11-set" 2012 2014 diagram criteria discovered` |
| fact064 | `eight industrial sectors "11"` (was `food machinery pharmaceuticals textiles`) / ... / refutation |
| fact065 | names only, nothing specific: the refutation query is kept |

The fixes against the four patterns above: figures quoted, filler dropped,
multi-word names kept together, and a specifics query in place of "debunked OR
false" when there is a figure, identifier or day to state. Measured by a
searched try in the campaign; the default stays `sentence`.

## What to try

A searched try (code in `query_builder.py` / `terms.py`, so `iterate propose`
makes it searched):
- keep numbers with their unit ("212 cases", "0.001 per cent", "12 September");
- keep the claim's head noun ("dengue", "sea ice");
- drop stop-like adverbs ("Meanwhile", "Indeed");
- for a claim with a figure, replace the refutation query with entity + figure
  + year.

The `query_kinds` threshold already switches one kind off (the 20 Oct retrieval
ablation, `docs/decisions/evaluation.md`), and needs no code.

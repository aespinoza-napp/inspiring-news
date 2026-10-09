# Alignment: do a round's candidates fit the mission and the groups asked for?

2026-10-09. Five one-group rounds (Society, Health, Science, Environment, Culture; three per source) on the live
stack, at about 11:30, then the same five after each of four changes, and once more an hour after the last.
324 unique candidates, each read and
labelled from its title, summary and link before any group-fit score was computed (Claude; not yet checked by
a person): `hand` 2 clearly positive / 1 worth offering / 0 not worth offering (the 2026-10-06 ranking set's
scale), `belongsTo` the groups the story itself belongs to, and `kind` - an article, or what it is instead.
`labelled.json` holds the labels, `runs.json` every round of every run with each candidate's reading and rank.

## The first twenty of the five rounds (100 candidates)

| Run | Change | Not an article | Wrong group | Not worth offering | Clearly positive |
|---|---|---|---|---|---|
| before | ce61d89 | 13 | 21 | 29 | 34 |
| iter1 | format rules; group fit; the labelling batch through the age limit and the screen; WHO's JSON listing and CNN's news sitemap; word-aware keywords | 3 | 13 | 22 | 34 |
| iter2 | section-page links titled with their headlines; 20minutos `/bc/`, RTVE live markers | 0 | 12 | 19 | 32 |
| iter3 | a source's own sections (Smithsonian); markets, service, labour, disaster and celebrity at margin 0.02 | 0 | 12 | 19 | 31 |
| iter4 | The Optimist Daily; Health for Good News Network and Reasons to be Cheerful | **0** | **13** | **17** | **34** |
| recheck | iter4's code an hour later, on the feeds of 16:35 | 0 | 13 | 16 | 33 |

The recheck is a weak test of whether the rules carry over: only 6 of its 100 were new (a trade deal, a column, a
rare-disease feature, a repeat of the giant waterlily, a writer's interview, a film director on Gaza). It held.
A real one is the next days' rounds, against labels made before the rules see them.

Per round, before -> iter4 (not an article / wrong group / not worth / clearly positive): Society 2/7/7/7 ->
0/3/6/8; Health 5/5/10/3 -> 0/2/3/4; Science 4/1/4/10 -> 0/1/1/8; Environment 1/5/6/9 -> 0/4/6/9;
Culture 1/3/2/5 -> 0/2/2/4.

## Format: what is not an article

35 of the first run's 263 candidates were not articles: podcasts (Guardian `/audio/`, CNN `/audio/podcasts/`, The
Conversation's episodes), roundups (Positive News's weekly, Reasons to be Cheerful's "What We're Reading", Nature's
"Books in brief"), quizzes, galleries (NASA's APOD, elDiario's FOTOS), a media advisory (NASA), promotions
(Positive News's new magazine issue), shopping (`/comprar/`, `/bazar/`, Amazon deals), branded content
(elDiario `/edcreativo/`), recipes and live pages. URL rules in discovery plus title and summary rules in the
mission screen caught **28 of the 35, and no article**. Two near-misses were fixed before keeping the rules: MIT
News slugs end in the date (`...-success-1008`), and "Las recetas del responsable económico de Vox" is a
metaphor - so digits still count as slug words, and only a slug that *starts* "receta-" is a recipe. Missed:
CNN's topic hub "President donald trump", Europa Press's section index `construccion-y-vivienda-00342`, a
Nature "Futures" story, a National Geographic hub, an untitled link and Muy Interesante's own festival.

CNN's `-spc` pages were labelled sponsored at first and corrected: dated 2026-10-06/08, their metadata names a
CNN feature series ("inside-africa", "marketplace-middle-east") - not paid content by anything on the page.
elDiario's `/edcreativo/` pages say `branded-content`; 20minutos's `/bc/` say "Contenido de marca".

## Topic: candidates of another group

Over 149 articles of the first run's one-group rounds (115 of the round's group, 34 of another), the fit -
nearest topic of the round's groups minus nearest topic of any other, from the screen's own embeddings - told
them apart with **AUC 0.874 [0.809, 0.930]** (2,000 bootstrap resamples, seed 20261009).

| Moved after the rest below | Of another group | Of the round's (clearly positive) |
|---|---|---|
| -0.03 | 23 of 34 | 15 of 115 (5) |
| -0.04 | 20 | 12 (4) |
| **-0.05** | **18** | **10 (4)** |
| -0.06 | 12 | 9 (4) |
| -0.08 | 8 | 4 (2) |

At -0.05 each of the ten of the round's group is a story whose first group is another (a testicular-tissue
transplant in Science). Moved, like a repeat, never dropped; and a source's slots go first to what fits.

## The screen's margin, by category

Candidates the screen kept, by how much nearer an off-mission description than any topic, positive outlets
aside (they are not judged on subject). This day's labels, and the 2026-10-06 ranking set's:

| Band | 2026-10-09 | 2026-10-06 |
|---|---|---|
| (0.00, 0.01] | 5 not worth, 7 worth, 1 positive | 2, 3, 1 |
| (0.01, 0.02] | 7, 2, 0 | 7, 0, 0 |
| (0.02, 0.03] | 7, 0, 0 | 1, 1, 0 |
| (0.03, 0.04] | 4, 0, 0 | 6, 1, 1 |

Between 0.02 and 0.04, markets, service pages, labour, disasters and celebrity: **15 of 16 not worth
offering** (the Bank of Spain, the budget arithmetic, a tractor protest, student protests, a raffle fine,
Shakira); the one worth it a history piece on women in wartime factories. Crime and war: a prison-stigma story
(clearly positive) and the Revolutionary War's identified soldiers among five. So those five categories went
to 0.02, crime and war stayed at 0.04 (`MARGINS`).

**Tried and rejected:** a tenth description, lifestyle advice (two wordings). At the screen's 0.04 it would have
left out 3 candidates, all already caught by other rules but one (varicose-vein habits); at 0.02, 8 (7 not
worth). "El secreto de la dieta nórdica" and "No es solo lo que comes" stayed below it either way.

## Discovery

- **Keywords as substrings.** English feeds are kept to the round's topics by keyword, matched as substrings:
  "ai" matched "said" and "detained", "who" (the WHO) every "who", "art" "start", "city" "electricity". On the
  day's English feeds, matching short keywords as whole words and acronyms in capitals dropped 85 of 419
  matches, every one checked: politics, sport and war in Science rounds, almost all of them; nothing added. A
  source all of whose groups were asked for (WHO in Health) needs no keyword.
- **trafilatura's step had not run since 2026-10-04**: DiscoveryService asks for `discover_items`, which it
  inherited from the feed step, so it re-read the dead feed. Run for real it would have made things worse -
  38 unfiltered links of every ABC section for Culture, 21 WHO items from 2024-2025 read as undated (WHO dates
  its links day first) - so it went last, with the Spanish keyword filter on slugs and day-first dates read.
- **Headlines from section pages**: titled from their link text instead of their slugs - ABC 94 of 96 links,
  National Geographic 42/44, SINC 16/16, France 24 59/59, Smithsonian 22/22, Europa Press 105/109, RTVE 15/22.
  Real headlines read differently from slugs: two economy stories the screen had left out by their slugs
  passed by their headlines (which the per-category margins then caught one of).
- **Dead feeds**: WHO's newest item was from February; its news API gave 30 items of that week. CNN's feed
  stopped in 2024; its Google News sitemap gave 268 of the last two days, titled and timed. ABC's
  `sitemap_news.xml` still lists 2021, WHO's sitemap index dates from 2018.
- **Sources**: The Optimist Daily added (three articles extracted, 3.5-5.5k characters). The Conversation's
  Spanish edition (50 items in 14 days) cannot be: one source per domain. Squirrel News publishes roundups;
  YES! Magazine's newest item was a month old; Ballena Blanca stopped in 2022; Noticias Positivas has no feed;
  El País's Planeta Futuro is mostly hard development news.

## The ranking, unchanged

AUC of the round's own score over the labelled articles shown or in reserve: worth offering vs not 0.752
[0.675, 0.826] before, 0.749 [0.666, 0.831] after; clearly positive vs the rest 0.720 [0.626, 0.806] before,
0.628 [0.514, 0.731] after - wider intervals than the change, but worth watching: real headlines changed the
story part's reading.

## What remains

The Spanish front pages' politics and economy below the margins; lifestyle advice in Health (Infobae,
20minutos); RTVE links without a headline; Smithsonian-like sources whose guessed sections are wrong. The
person and the AI selection judge what is left.

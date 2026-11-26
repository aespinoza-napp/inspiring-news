# Admission thresholds, replayed

Labels: 9 positive-edition rounds with the editor's choice (0 recorded on /discover, 9 by what was sent to analysis), 1 candidate marked not for us; 11 Devastating-edition rounds and 16 rounds with no choice left out of 37 read.

137 articles enriched (9 failed); 137 labelled by an editor's choice, 13 of them chosen. 19 had no topic at today's classifier floor (0.35), so today's topic filter rejects them whatever its minimum.
Defaults: topic minimum 0.35, impact minimum 0.3.
AUC, chosen against not chosen (0.5 is a coin): the positive-impact score 0.689 [0.512, 0.855], the best topic's confidence 0.608 [0.429, 0.774].
Duplicate detection is not replayed.

| Topic min | Impact min | Admitted | Rate | Precision vs editor | Recall vs editor | Picks lost | Not chosen admitted |
|---|---|---|---|---|---|---|---|
| 0.300 | 0.100 | 126 | 0.920 | 0.095 | 0.923 | 1 | 0.919 |
| 0.300 | 0.200 | 115 | 0.839 | 0.104 | 0.923 | 1 | 0.831 |
| 0.300 | 0.250 | 105 | 0.766 | 0.114 | 0.923 | 1 | 0.750 |
| 0.300 | 0.300 | 92 | 0.671 | 0.120 | 0.846 | 2 | 0.653 |
| 0.350 | 0.100 | 111 | 0.810 | 0.099 | 0.846 | 2 | 0.806 |
| 0.350 | 0.200 | 104 | 0.759 | 0.106 | 0.846 | 2 | 0.750 |
| 0.350 | 0.250 | 95 | 0.693 | 0.116 | 0.846 | 2 | 0.677 |
| 0.350 | 0.300 | 85 | 0.620 | 0.118 | 0.769 | 3 | 0.605 |
| 0.400 | 0.100 | 72 | 0.525 | 0.125 | 0.692 | 4 | 0.508 |
| 0.400 | 0.200 | 70 | 0.511 | 0.129 | 0.692 | 4 | 0.492 |
| 0.400 | 0.250 | 67 | 0.489 | 0.134 | 0.692 | 4 | 0.468 |
| 0.400 | 0.300 | 61 | 0.445 | 0.131 | 0.615 | 5 | 0.427 |
| 0.450 | 0.100 | 41 | 0.299 | 0.146 | 0.462 | 7 | 0.282 |
| 0.450 | 0.200 | 40 | 0.292 | 0.150 | 0.462 | 7 | 0.274 |
| 0.450 | 0.250 | 39 | 0.285 | 0.154 | 0.462 | 7 | 0.266 |
| 0.450 | 0.300 | 37 | 0.270 | 0.162 | 0.462 | 7 | 0.250 |

**No starting point proposed yet**: 137 labelled candidates and 13 picks; the rule needs 100 and 20.

The rule, written before the run: of the cells keeping at least 95% of the picks, the one admitting the smallest share of the not chosen, ties to the nearest of today's defaults; from 100 labelled candidates and 20 picks.

## The impact score's gap

Not chosen, and rated most positive:

| Impact score | Title |
|---|---|
| 0.814 | Stroke recovery tracked with wearable device. An NIH-funded study found that wrist sensors could track improvements in arm use after stroke, potentially making rehabilitation assessments more sensitive to everyday movement. |
| 0.804 | A Canadian ranch family's two-decade effort to protect native prairie now covers more than 55,000 acres; auditors have verified its first grassland carbon-credit issuance under a national protocol. |
| 0.795 | Suriname’s Saamaka tribe are using modern technology to map and document their ancestral lands in effort to protect the Amazon rainforest and strengthen their case for government recognition |
| 0.793 | Gene therapy can partly restore sight in blind people, researchers reveal |
| 0.791 | Pemba's new marine protected areas show the power of collaboration to meet 30x30 goal |

Chosen, and rated least positive:

| Impact score | Title |
|---|---|
| 0.063 | Before Natalie Imbruglia sang ‘Torn,’ its songwriter recorded a version with a very different bite |
| 0.251 | Korea Girl was a forgotten ’90s band until Gen Zers found their song and played it 92 million times |
| 0.369 | Neuroscience expert explains 5 ways to become ‘unrecognizable’ 6 months from now |
| 0.378 | 1,000 Swiss volunteers buried their underwear for science. It just won an Ig Nobel Prize. |
| 0.412 | Ella Fitzgerald forgot the words to ‘Mack the Knife.’ Her improvised version earned a Grammy. |

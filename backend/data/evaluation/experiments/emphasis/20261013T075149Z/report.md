# Topic emphasis: how much the topic weighs against positive impact

2026-10-13. Every candidate of the 2026-10-09 alignment rounds that recorded a group fit, shown or in
reserve, re-scored at each emphasis with `src/services/selection/ranking.py`'s own `score` and `ordered`, from
the readings and source parts the rounds recorded: nothing embedded or fetched again. The emphasis splits the
story's 0.6 of the score between positive impact (news) and the fit with the group asked for (topic); the
source's record and reliability keep 0.25 and 0.15. Emphasis 0 is the 2026-10-06 score; *before* is the
weights from 2026-10-09 until this change. Stories are grouped as each round grouped them (`sameStoryAs`).

Labels (hand: clearly positive / worth offering / not worth offering; the groups each story belongs to; whether
it is an article): 324 from `data/evaluation/experiments/alignment/20261009T120000Z/labelled.json`; 60 from `data/evaluation/experiments/emphasis/reserve-labels.json`.
Unlabelled in any first twenty: 0. Labels are Claude's, not yet checked by a person.

## Chosen: 0.6

Ten rounds, first twenty: before, 184 of the group, 154 worth offering of it, 62 clearly positive of it, first ten 94 of the group; at 0, 174 of the group, 150 worth offering of it, 61 clearly positive of it, first ten 89 of the group;
at 0.6, 194 of the group, 150 worth offering of it, 53 clearly positive of it, first ten 100 of the group. One step higher (0.65): 194 of the group, 147 worth offering of it, 49 clearly positive of it, first ten 100 of the group. Over all 25 rounds at 0.6: 478 of the group, 360 worth offering of it, 130 clearly positive of it, first ten 248 of the group
(before: 454 of the group, 367 worth offering of it, 147 clearly positive of it, first ten 232 of the group).

## The first twenty, ten rounds (200 places)

The five one-group rounds of the last two runs (iter4 and the recheck an hour later, 94 of 100 shown the same):
the set the 2026-10-09 topic weight was chosen on.

| Emphasis | News / topic | Of the group | Of another group | Not an article | Worth offering or clearly positive | Clearly positive | Worth offering, of the group | Clearly positive, of the group | Not worth offering | First ten: of the group | First ten: worth offering, of the group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| before (0.51 / 0.15 / 0.21 / 0.13) | 0.51 / 0.15 | 184 | 16 | 0 | 164 | 64 | 154 | 62 | 36 | 94 | 84 |
| 0.00 | 0.60 / 0.00 | 174 | 26 | 0 | 167 | 67 | 150 | 61 | 33 | 89 | 81 |
| 0.10 | 0.54 / 0.06 | 178 | 22 | 0 | 165 | 68 | 151 | 63 | 35 | 93 | 82 |
| 0.20 | 0.48 / 0.12 | 185 | 15 | 0 | 165 | 63 | 155 | 61 | 35 | 93 | 84 |
| 0.30 | 0.42 / 0.18 | 187 | 13 | 0 | 162 | 61 | 154 | 61 | 38 | 94 | 85 |
| 0.40 | 0.36 / 0.24 | 191 | 9 | 0 | 161 | 58 | 155 | 58 | 39 | 98 | 83 |
| 0.50 | 0.30 / 0.30 | 192 | 8 | 0 | 155 | 53 | 150 | 53 | 45 | 98 | 83 |
| 0.55 | 0.27 / 0.33 | 193 | 7 | 0 | 155 | 53 | 151 | 53 | 45 | 99 | 79 |
| **0.60 (chosen)** | 0.24 / 0.36 | 194 | 5 | 1 | 152 | 53 | 150 | 53 | 48 | 100 | 79 |
| 0.65 | 0.21 / 0.39 | 194 | 4 | 2 | 148 | 49 | 147 | 49 | 52 | 100 | 77 |
| 0.70 | 0.18 / 0.42 | 194 | 4 | 3 | 140 | 46 | 139 | 46 | 60 | 100 | 76 |
| 0.80 | 0.12 / 0.48 | 193 | 5 | 3 | 137 | 46 | 136 | 46 | 63 | 100 | 71 |
| 0.90 | 0.06 / 0.54 | 193 | 5 | 3 | 136 | 49 | 135 | 49 | 64 | 98 | 68 |
| 1.00 | 0.00 / 0.60 | 195 | 3 | 3 | 137 | 52 | 136 | 52 | 63 | 97 | 68 |

## The first twenty, 25 rounds (500 places)

Every run that recorded a group fit (iter1 to the recheck): the same five feeds read five times in a day, so not
25 independent rounds either.

| Emphasis | News / topic | Of the group | Of another group | Not an article | Worth offering or clearly positive | Clearly positive | Worth offering, of the group | Clearly positive, of the group | Not worth offering | First ten: of the group | First ten: worth offering, of the group |
|---|---|---|---|---|---|---|---|---|---|---|---|
| before (0.51 / 0.15 / 0.21 / 0.13) | 0.51 / 0.15 | 454 | 43 | 3 | 392 | 152 | 367 | 147 | 108 | 232 | 208 |
| 0.00 | 0.60 / 0.00 | 434 | 63 | 3 | 407 | 164 | 368 | 149 | 93 | 221 | 202 |
| 0.10 | 0.54 / 0.06 | 440 | 57 | 3 | 403 | 163 | 369 | 150 | 97 | 230 | 205 |
| 0.20 | 0.48 / 0.12 | 454 | 43 | 3 | 394 | 151 | 368 | 145 | 106 | 230 | 207 |
| 0.30 | 0.42 / 0.18 | 465 | 32 | 3 | 390 | 145 | 370 | 145 | 110 | 233 | 208 |
| 0.40 | 0.36 / 0.24 | 475 | 22 | 3 | 387 | 139 | 372 | 139 | 113 | 242 | 203 |
| 0.50 | 0.30 / 0.30 | 478 | 20 | 2 | 380 | 132 | 366 | 132 | 120 | 243 | 202 |
| 0.55 | 0.27 / 0.33 | 480 | 18 | 2 | 379 | 131 | 367 | 131 | 121 | 245 | 194 |
| **0.60 (chosen)** | 0.24 / 0.36 | 478 | 16 | 6 | 370 | 130 | 360 | 130 | 130 | 248 | 193 |
| 0.65 | 0.21 / 0.39 | 483 | 10 | 7 | 356 | 125 | 352 | 125 | 144 | 248 | 185 |
| 0.70 | 0.18 / 0.42 | 484 | 9 | 9 | 342 | 119 | 339 | 119 | 158 | 248 | 183 |
| 0.80 | 0.12 / 0.48 | 483 | 10 | 9 | 335 | 116 | 332 | 116 | 165 | 248 | 174 |
| 0.90 | 0.06 / 0.54 | 483 | 10 | 9 | 332 | 118 | 329 | 118 | 168 | 244 | 164 |
| 1.00 | 0.00 / 0.60 | 484 | 9 | 9 | 331 | 121 | 328 | 121 | 169 | 243 | 161 |

## How well the score separates (ten rounds)

AUC over each round group's labelled articles, shown or in reserve (latest reading), with a 95% bootstrap
interval (2000 resamples, seed 20261005). Before the partition and the one-story rule.

| Emphasis | Of the group vs another | Worth offering vs not | Worth offering vs not, within the group |
|---|---|---|---|
| before (0.51 / 0.15 / 0.21 / 0.13) | 0.706 [0.608, 0.797] | 0.754 [0.690, 0.815] | 0.757 [0.685, 0.825] |
| 0.00 | 0.613 [0.512, 0.709] | 0.781 [0.721, 0.841] | 0.784 [0.715, 0.848] |
| 0.10 | 0.654 [0.550, 0.747] | 0.773 [0.712, 0.834] | 0.774 [0.705, 0.838] |
| 0.20 | 0.694 [0.594, 0.787] | 0.761 [0.700, 0.822] | 0.762 [0.690, 0.830] |
| 0.30 | 0.739 [0.646, 0.825] | 0.742 [0.677, 0.805] | 0.741 [0.666, 0.809] |
| 0.40 | 0.776 [0.688, 0.853] | 0.716 [0.647, 0.781] | 0.710 [0.629, 0.781] |
| 0.50 | 0.809 [0.730, 0.878] | 0.681 [0.609, 0.749] | 0.669 [0.585, 0.746] |
| 0.55 | 0.821 [0.745, 0.886] | 0.662 [0.586, 0.732] | 0.645 [0.559, 0.724] |
| **0.60 (chosen)** | 0.825 [0.751, 0.891] | 0.638 [0.562, 0.710] | 0.619 [0.532, 0.701] |
| 0.65 | 0.831 [0.759, 0.896] | 0.620 [0.541, 0.692] | 0.596 [0.507, 0.680] |
| 0.70 | 0.833 [0.762, 0.898] | 0.601 [0.521, 0.674] | 0.572 [0.482, 0.655] |
| 0.80 | 0.833 [0.761, 0.899] | 0.566 [0.485, 0.639] | 0.531 [0.439, 0.617] |
| 0.90 | 0.831 [0.755, 0.896] | 0.540 [0.460, 0.615] | 0.501 [0.408, 0.589] |
| 1.00 | 0.824 [0.749, 0.891] | 0.517 [0.435, 0.592] | 0.475 [0.382, 0.562] |

## The topic part saturating earlier (tried, not adopted)

`TOPIC_RANGE` gives a story full topic marks at a fit of 0.10. A story of two groups fits less than one squarely
technical; full marks earlier would count belonging rather than squareness.

| Topic part full at | Emphasis | Of the group (10) | Worth offering, of the group (10) | Clearly positive, of the group (10) | First ten: of the group (10) | Of the group (25) | Worth offering, of the group (25) | Clearly positive, of the group (25) |
|---|---|---|---|---|---|---|---|---|
| 0.10 | 0.5 | 192 | 150 | 53 | 98 | 478 | 366 | 132 |
| 0.10 | 0.6 | 194 | 150 | 53 | 100 | 478 | 360 | 130 |
| 0.10 | 0.7 | 194 | 139 | 46 | 100 | 484 | 339 | 119 |
| 0.06 | 0.5 | 193 | 151 | 57 | 98 | 478 | 362 | 137 |
| 0.06 | 0.6 | 191 | 146 | 56 | 100 | 475 | 352 | 132 |
| 0.06 | 0.7 | 194 | 140 | 52 | 100 | 482 | 335 | 121 |
| 0.04 | 0.5 | 194 | 151 | 59 | 94 | 478 | 361 | 140 |
| 0.04 | 0.6 | 192 | 146 | 59 | 100 | 476 | 349 | 135 |
| 0.04 | 0.7 | 192 | 141 | 55 | 100 | 475 | 337 | 127 |
| 0.03 | 0.5 | 193 | 151 | 59 | 96 | 475 | 363 | 140 |
| 0.03 | 0.6 | 193 | 146 | 60 | 96 | 476 | 351 | 140 |
| 0.03 | 0.7 | 192 | 140 | 56 | 97 | 475 | 338 | 132 |
| 0.02 | 0.5 | 192 | 153 | 61 | 96 | 474 | 369 | 145 |
| 0.02 | 0.6 | 191 | 149 | 60 | 96 | 472 | 361 | 144 |
| 0.02 | 0.7 | 190 | 143 | 59 | 97 | 469 | 341 | 137 |

## The chosen 0.6 against before, round by round

| Run | Group | Of the group | Worth offering, of the group | Clearly positive, of the group | Not worth offering |
|---|---|---|---|---|---|
| iter4 | society | 19 -> 19 | 13 -> 12 | 7 -> 7 | 7 -> 8 |
| iter4 | health | 19 -> 20 | 17 -> 16 | 4 -> 4 | 2 -> 4 |
| iter4 | science | 19 -> 20 | 18 -> 17 | 9 -> 5 | 1 -> 3 |
| iter4 | environment | 18 -> 19 | 12 -> 12 | 8 -> 7 | 6 -> 7 |
| iter4 | culture | 18 -> 19 | 17 -> 18 | 3 -> 3 | 2 -> 2 |
| recheck | society | 18 -> 20 | 13 -> 12 | 7 -> 7 | 7 -> 8 |
| recheck | health | 19 -> 20 | 18 -> 16 | 4 -> 3 | 1 -> 4 |
| recheck | science | 18 -> 19 | 17 -> 16 | 8 -> 5 | 2 -> 4 |
| recheck | environment | 18 -> 19 | 13 -> 14 | 9 -> 9 | 5 -> 5 |
| recheck | culture | 18 -> 19 | 16 -> 17 | 3 -> 3 | 3 -> 3 |

## What left and entered the first twenty (the recheck run)

- **society**
  - out: Autism, ADHD and mental health review: What you need to know (worth offering; health, society)
  - out: La UE y China alcanzan un acuerdo sobre los vehículos híbridos y las tierras raras (not worth offering; no group)
  - out: Indra y sus socios de consorcio confían en que los primeros 8x8 estén ya operativos este año (not worth offering; no group)
  - in: France promises 3,000 extra teachers in first step to calm student protests (not worth offering; society)
  - in: Finlandia ofrece sueldos de más de 3.000 euros por trabajar como profesor de infantil: estos son los plazos (not worth offering; society)
  - in: Shanghái se convierte en el gran casero para rescatar su mercado inmobiliario (not worth offering; society)
- **health**
  - out: Hachimaki: la bandana japonesa que simboliza esfuerzo, constancia y buena suerte (worth offering; culture)
  - out: For decades, no one could explain her exhaustion and hallucinations. One question changed everything (worth offering; health)
  - out: New global roadmap launched to tackle hypertension in pregnancy, a leading cause of maternal and newborn deaths (clearly positive; health)
  - in: Covid, Brexit and Liz Truss mini-budget led to lasting decline in mental health, study finds (not worth offering; health)
  - in: ‘No plague case’ in Siberia, Russia tells WHO as assessments continue (not worth offering; health)
  - in: Kenya races to trace all contacts after first Ebola death, WHO official says (not worth offering; health)
- **science**
  - out: Supporting systems of success (worth offering; society, science)
  - out: CSIC impulsa cuatro 'spin-off' para desarrollar soluciones en salud, alimentación, sostenibilidad y agricultura (clearly positive; science, environment)
  - out: Gene therapy can partly restore sight in blind people, researchers reveal (clearly positive; science, health)
  - out: Inrobics, la 'startup' que pone su 'alma' y sus robots al servicio de las personas (worth offering; science)
  - out: Francis Halzen gana el Nobel de Física 2026 por sus contribuciones al estudio de los neutrinos (clearly positive; science)
  - out: Un faro para la creación y las ideas (worth offering; culture)
  - in: Mars’s oddest cloud may be even odder than we thought (worth offering; science)
  - in: NASA’s SPHEREx Telescope Sees Menagerie of Brown Dwarfs (worth offering; science)
  - in: AI or ‘super intelligence’? Trump isn’t the only one who is confused (not worth offering; science)
  - in: How to build a mouse: embryo development captured in stunning detail (worth offering; science)
  - in: Anthropic bans users from being 'cruel' to its AI systems (not worth offering; science)
  - in: Una sencilla fórmula matemática predice cuándo los chatbots de IA se descontrolarán (worth offering; science)
- **environment**
  - out: Five Discoveries That Changed Our Understanding of T. Rex Forever, From Warm Blood to Lips (worth offering; science)
  - out: Isaias strengthens to become first Atlantic hurricane of 2026 season (not worth offering; environment)
  - out: Neighbors Flock to Rescue a Wounded Owl Tangled Up in Barbed Wire (clearly positive; environment, society)
  - in: Fishmeal factories take Senegal’s fish from the dinner table (not worth offering; environment)
  - in: La Generalitat da carpetazo definitivo al macrovertedero de Zarra, ampliamente rechazado por los vecinos (worth offering; environment, society)
  - in: Saudi Solar Park Proves Brilliant Breeding Ground for Threatened Sand Gazelles (clearly positive; environment)
- **culture**
  - out: Yuval Abraham, director de 'NAZA: "La mayor parte de Israel está ignorando o justificando algo inhumano" (not worth offering; culture)
  - out: Helmut Clissmann, el agente alemán que buscó aliados en Irlanda y ayudó a liberar a Frank Ryan (worth offering; culture)
  - out: Strangers Showed Up to Man’s Destroyed House to Put Up a Tarp Having Seen His Televised Plea (clearly positive; society)
  - in: Cuerpos desmembrados incrustados en casas, reflejo de la violencia en la antigua Escandinavia (worth offering; culture, science)
  - in: Hundreds of British College Students Clashed With Wooden Swords in a 1966 Re-enactment of the Battle of Hastings. Watch the Rediscovered 'Time Capsule' of Lost Footage (worth offering; culture)
  - in: El caso de Daniel Sancho se convierte en serie de Netflix con Martiño Rivas transformado (not worth offering; culture)

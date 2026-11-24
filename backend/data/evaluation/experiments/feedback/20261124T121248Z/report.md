# What the person rejects: does it teach the ranking?

431 hand-labelled candidates the screen kept (not worth offering / worth offering /
clearly positive: 231 / 136 / 64). Claude (AI), not yet checked by a person: 0 not worth offering, 1 worth offering, 2 clearly positive. One day's 0s play what a person rejected, its 2s
what they chose; the rule runs on the other days. The rule as built: lowered by 0.5 of the lean from 10 + 5 examples, 0.25 of the lean from 3 + 3 examples; left out over 0.08 from 40 + 20.

## 6 Oct teaches 9 and 13 Oct (32 rejected, 20 chosen; candidates 199 / 107 / 44)

Nearest neighbour: left out when within the floor of a rejected story (and nearer it than any chosen, with a margin).

| Floor | Margin | Not worth | Worth | Clearly positive |
|---|---|---|---|---|
| 0.600 | – | 0 | 0 | 0 |
| 0.600 | 0.000 | 0 | 0 | 0 |
| 0.650 | – | 0 | 0 | 0 |
| 0.650 | 0.000 | 0 | 0 | 0 |
| 0.700 | – | 0 | 0 | 0 |
| 0.700 | 0.000 | 0 | 0 | 0 |
| 0.750 | – | 0 | 0 | 0 |
| 0.750 | 0.000 | 0 | 0 | 0 |
| 0.800 | – | 0 | 0 | 0 |
| 0.800 | 0.000 | 0 | 0 | 0 |

AUC of the story part, worth vs not / clearly positive vs rest: alone 0.7626 / 0.7781; lowered by 0.25 of the lean 0.7841 / 0.7958; lowered by 0.5 of the lean 0.7907 / 0.8011; lowered by 1.0 of the lean 0.7881 / 0.8069.

| Left out over lean | Not worth | Worth | Clearly positive |
|---|---|---|---|
| 0.0 | 183 | 76 | 24 |
| 0.02 | 161 | 57 | 13 |
| 0.04 | 138 | 37 | 6 |
| 0.06 | 108 | 20 | 3 |
| 0.08 | 78 | 10 | 0 |
| 0.1 | 46 | 5 | 0 |

## 9 and 13 Oct teach 6 Oct (199 rejected, 44 chosen; candidates 32 / 29 / 20)

Nearest neighbour: left out when within the floor of a rejected story (and nearer it than any chosen, with a margin).

| Floor | Margin | Not worth | Worth | Clearly positive |
|---|---|---|---|---|
| 0.600 | – | 0 | 0 | 0 |
| 0.600 | 0.000 | 0 | 0 | 0 |
| 0.650 | – | 0 | 0 | 0 |
| 0.650 | 0.000 | 0 | 0 | 0 |
| 0.700 | – | 0 | 0 | 0 |
| 0.700 | 0.000 | 0 | 0 | 0 |
| 0.750 | – | 0 | 0 | 0 |
| 0.750 | 0.000 | 0 | 0 | 0 |
| 0.800 | – | 0 | 0 | 0 |
| 0.800 | 0.000 | 0 | 0 | 0 |

AUC of the story part, worth vs not / clearly positive vs rest: alone 0.8119 / 0.8762; lowered by 0.25 of the lean 0.8514 / 0.8848; lowered by 0.5 of the lean 0.8718 / 0.8939; lowered by 1.0 of the lean 0.8881 / 0.8939.

| Left out over lean | Not worth | Worth | Clearly positive |
|---|---|---|---|
| 0.0 | 30 | 15 | 5 |
| 0.02 | 27 | 8 | 1 |
| 0.04 | 20 | 3 | 1 |
| 0.06 | 13 | 2 | 0 |
| 0.08 | 4 | 1 | 0 |
| 0.1 | 4 | 0 | 0 |

## A person's few examples: drawn from 9 Oct, 200 draws each, on the other days (candidates 73 / 44 / 22)

AUC of the story part, mean [5th percentile].

| Rejected + chosen | Story alone (worth / positive) | Lowered by 0.25: worth | Lowered by 0.5: worth | Lowered by 1.0: worth | Lowered by 0.25: positive | Lowered by 0.5: positive | Lowered by 1.0: positive |
|---|---|---|---|---|---|---|---|
| 3 + 3 | 0.759 / 0.8559 | 0.7844 [0.7503] | 0.7867 [0.7336] | 0.7703 [0.696] | 0.859 [0.8298] | 0.8484 [0.8011] | 0.8073 [0.7366] |
| 5 + 3 | 0.759 / 0.8559 | 0.7863 [0.7536] | 0.7917 [0.7421] | 0.7776 [0.6936] | 0.8625 [0.8357] | 0.8556 [0.8116] | 0.8243 [0.7502] |
| 10 + 5 | 0.759 / 0.8559 | 0.7937 [0.7696] | 0.8074 [0.7667] | 0.8063 [0.7527] | 0.8637 [0.8421] | 0.8612 [0.824] | 0.8415 [0.7882] |
| 20 + 10 | 0.759 / 0.8559 | 0.7991 [0.7822] | 0.8188 [0.7934] | 0.8289 [0.7885] | 0.866 [0.8497] | 0.8678 [0.8432] | 0.8571 [0.8218] |
| 40 + 20 | 0.759 / 0.8559 | 0.8008 [0.7889] | 0.8242 [0.8066] | 0.8409 [0.8181] | 0.8673 [0.8564] | 0.8717 [0.8539] | 0.8675 [0.8394] |

Left out over a lean: mean not worth / worth / clearly positive per draw, and the most clearly positive lost in any draw.

| Rejected + chosen | lean > 0.0 | lean > 0.02 | lean > 0.04 | lean > 0.06 | lean > 0.08 | lean > 0.1 |
|---|---|---|---|---|---|---|
| 3 + 3 | 41.4 / 14.7 / 5.7 (worst 17) | 32.4 / 9.7 / 3.6 (worst 14) | 23.6 / 6.3 / 2.2 (worst 11) | 16.0 / 3.7 / 1.2 (worst 8) | 10.6 / 2.0 / 0.7 (worst 7) | 6.4 / 1.1 / 0.3 (worst 4) |
| 5 + 3 | 59.0 / 25.5 / 10.4 (worst 20) | 51.1 / 19.8 / 7.8 (worst 19) | 41.7 / 14.2 / 5.4 (worst 17) | 31.8 / 9.4 / 3.3 (worst 12) | 22.5 / 5.8 / 1.9 (worst 10) | 14.5 / 3.4 / 1.0 (worst 8) |
| 10 + 5 | 64.3 / 27.2 / 10.6 (worst 19) | 57.2 / 20.2 / 7.7 (worst 18) | 47.6 / 13.7 / 4.8 (worst 17) | 36.0 / 8.7 / 2.6 (worst 14) | 25.1 / 5.0 / 1.4 (worst 11) | 15.7 / 2.7 / 0.6 (worst 9) |
| 20 + 10 | 63.2 / 21.9 / 7.7 (worst 17) | 55.2 / 14.8 / 4.6 (worst 14) | 44.1 / 9.3 / 2.5 (worst 12) | 31.4 / 5.6 / 1.1 (worst 9) | 19.5 / 3.1 / 0.5 (worst 5) | 10.7 / 1.5 / 0.1 (worst 2) |
| 40 + 20 | 63.2 / 18.4 / 5.3 (worst 13) | 54.3 / 11.5 / 2.5 (worst 7) | 40.9 / 6.8 / 1.1 (worst 3) | 26.6 / 4.1 / 0.5 (worst 2) | 14.2 / 2.4 / 0.1 (worst 1) | 6.8 / 1.0 / 0.0 (worst 1) |

# manual · freshness

How old the newest evidence the annotator used was when the claim was published (`claimDate - evidenceDate`, days), and how each run did by that age and by the claim's own age when it was checked. src/evaluation/freshness.py; roadmap P1.2.

## The set

103 natural claims dated on both sides, of 139 rows: 30 synthetic FALSE left out (they copy their source's dates), 6 without an evidence date (fact025, fact031, fact048, fact049, fact054, fact099). Median 22.0 days (IQR 1.5-389.5).

| | n | Median days | same day | 1-7 days | 8-30 days | 31-365 days | over a year |
|---|---|---|---|---|---|---|---|
| All | 103 | 22.0 | 15 (14.6%) | 28 (27.2%) | 11 (10.7%) | 23 (22.3%) | 26 (25.2%) |
| language: en | 69 | 13.0 | 12 (17.4%) | 18 (26.1%) | 6 (8.7%) | 16 (23.2%) | 17 (24.6%) |
| language: es | 34 | 24.5 | 3 (8.8%) | 10 (29.4%) | 5 (14.7%) | 7 (20.6%) | 9 (26.5%) |
| claimType: factual | 61 | 31.0 | 12 (19.7%) | 13 (21.3%) | 5 (8.2%) | 13 (21.3%) | 18 (29.5%) |
| claimType: interpretive | 4 | 199.5 | 0 (0.0%) | 1 (25.0%) | 0 (0.0%) | 2 (50.0%) | 1 (25.0%) |
| claimType: numerical | 38 | 11.0 | 3 (7.9%) | 14 (36.8%) | 6 (15.8%) | 8 (21.1%) | 7 (18.4%) |
| sourceTier: press_release | 2 | 9.5 | 0 (0.0%) | 1 (50.0%) | 1 (50.0%) | 0 (0.0%) | 0 (0.0%) |
| sourceTier: primary | 63 | 41.0 | 5 (7.9%) | 17 (27.0%) | 9 (14.3%) | 14 (22.2%) | 18 (28.6%) |
| sourceTier: reference_media | 38 | 5.5 | 10 (26.3%) | 10 (26.3%) | 1 (2.6%) | 9 (23.7%) | 8 (21.1%) |
| label: MISLEADING | 1 | 230.0 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 1 (100.0%) | 0 (0.0%) |
| label: PARTIALLY_TRUE | 7 | 92.0 | 1 (14.3%) | 1 (14.3%) | 1 (14.3%) | 1 (14.3%) | 3 (42.9%) |
| label: TRUE | 89 | 22.0 | 13 (14.6%) | 24 (27.0%) | 9 (10.1%) | 20 (22.5%) | 23 (25.8%) |
| label: UNVERIFIED | 6 | 3.0 | 1 (16.7%) | 3 (50.0%) | 1 (16.7%) | 1 (16.7%) | 0 (0.0%) |

Same day (15): fact014, fact016, fact050, fact056, fact058, fact080, fact094, fact095, fact112, fact113, fact114, fact131, fact145, fact146, fact148.

# manual-test: retrieval strategies compared

Dataset sha256 `1ea9a8b72ec3`, 70 rows. Bootstrap seed 2026, 10000 resamples. The first run is the baseline. docs/decisions/evaluation.md §Retrieval evaluation.

- `queries-all`: retrieval run, thresholds defaults, corpus none, DuckDuckGo fallback True, commit `0f70c68f1006`.
- `queries-anchor`: retrieval run, thresholds query_kinds=['anchor'], corpus none, DuckDuckGo fallback True, commit `0f70c68f1006`.
- `queries-anchor_proposition`: retrieval run, thresholds query_kinds=['anchor', 'proposition'], corpus none, DuckDuckGo fallback True, commit `0f70c68f1006`.

| Strategy | Searched | Reference link among candidates | Reference link among ranked evidence | Reference domain among ranked evidence | Domain MRR (ranked) | Claims with any ranked evidence | Ranked sources per claim | Share cut at ranking (gate, cap) | Distinct domains among ranked | Ranked from rated domains | Retrieval seconds per claim |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `queries-all` | 70 | 15.9% [7.2%, 24.6%] | 8.7% [2.9%, 15.9%] | 17.4% [8.7%, 27.5%] | 8.0% [3.7%, 13.4%] | 100.0% [100.0%, 100.0%] | 4.91 [4.83, 4.99] | 1.7% [0.3%, 3.4%] | 4.91 [4.83, 4.99] | 5.4% [3.4%, 7.7%] | 14.41 [12.82, 16.18] |
| `queries-anchor` | 70 | 10.1% [2.9%, 17.4%] | 7.2% [1.5%, 13.0%] | 11.6% [4.3%, 20.3%] | 4.9% [1.7%, 9.0%] | 98.6% [95.7%, 100.0%] | 4.19 [3.93, 4.43] | 14.7% [10.1%, 19.9%] | 4.19 [3.93, 4.43] | 5.1% [2.8%, 7.7%] | 9.12 [7.87, 10.52] |
| `queries-anchor_proposition` | 70 | 14.5% [7.2%, 23.2%] | 7.2% [1.5%, 14.5%] | 18.8% [10.1%, 29.0%] | 10.7% [5.1%, 17.2%] | 100.0% [100.0%, 100.0%] | 4.87 [4.76, 4.97] | 2.6% [0.6%, 4.9%] | 4.87 [4.76, 4.97] | 6.6% [4.2%, 9.0%] | 11.70 [10.48, 13.03] |

### Retrieval: queries-anchor − queries-all

Paired over 70 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 69 | 15.9% | 10.1% | -5.8 pts [-11.6 pts, -1.5 pts] | 4 / 0 |
| Reference link among ranked evidence | 69 | 8.7% | 7.2% | -1.5 pts [-5.8 pts, +2.9 pts] | 2 / 1 |
| Reference link among cited evidence | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 69 | 33.3% | 14.5% | -18.8 pts [-29.0 pts, -10.1 pts] | 13 / 0 |
| Reference domain among ranked evidence | 69 | 17.4% | 11.6% | -5.8 pts [-14.5 pts, +2.9 pts] | 7 / 3 |
| Reference domain among cited evidence | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 69 | 3.4% | 2.0% | -1.4 pts [-5.2 pts, +1.3 pts] | 2 / 4 |
| Domain MRR (ranked) | 69 | 8.0% | 4.9% | -3.2 pts [-9.3 pts, +2.6 pts] | 7 / 7 |
| Claims with any ranked evidence | 70 | 100.0% | 98.6% | -1.4 pts [-4.3 pts, +0.0 pts] |  |
| Candidates per claim | 70 | 19.46 | 8.00 | -11.46 [-12.33, -10.57] |  |
| Ranked sources per claim | 70 | 4.91 | 4.19 | -0.73 [-0.99, -0.49] |  |
| Share cut at ranking (gate, cap) | 70 | 1.7% | 14.7% | +13.0 pts [+8.3 pts, +18.1 pts] |  |
| Distinct domains among ranked | 70 | 4.91 | 4.19 | -0.73 [-0.99, -0.49] |  |
| Ranked from rated domains | 69 | 5.5% | 5.1% | -0.4 pts [-3.2 pts, +2.5 pts] |  |
| Ranked from the internal corpus | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 70 | 14.41 | 9.12 | -5.29 [-6.84, -3.69] |  |
| Ranking seconds per claim | 70 | 12.16 | 10.67 | -1.49 [-2.72, -0.25] |  |

### Retrieval: queries-anchor_proposition − queries-all

Paired over 70 claims both searched (0 only in the baseline, 0 only in the candidate).

| Metric | Pairs | Baseline | Candidate | Difference [95% CI] | Only A / only B |
|---|---|---|---|---|---|
| Reference link among candidates | 69 | 15.9% | 14.5% | -1.5 pts [-4.3 pts, +0.0 pts] | 1 / 0 |
| Reference link among ranked evidence | 69 | 8.7% | 7.2% | -1.5 pts [-4.3 pts, +0.0 pts] | 1 / 0 |
| Reference link among cited evidence | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Reference domain among candidates | 69 | 33.3% | 29.0% | -4.3 pts [-10.1 pts, +0.0 pts] | 3 / 0 |
| Reference domain among ranked evidence | 69 | 17.4% | 18.8% | +1.5 pts [+0.0 pts, +4.3 pts] | 0 / 1 |
| Reference domain among cited evidence | 69 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] | 0 / 0 |
| Link MRR (ranked) | 69 | 3.4% | 2.3% | -1.1 pts [-4.6 pts, +1.2 pts] | 3 / 2 |
| Domain MRR (ranked) | 69 | 8.0% | 10.7% | +2.7 pts [-0.8 pts, +7.0 pts] | 3 / 6 |
| Claims with any ranked evidence | 70 | 100.0% | 100.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Candidates per claim | 70 | 19.46 | 13.84 | -5.61 [-6.24, -4.96] |  |
| Ranked sources per claim | 70 | 4.91 | 4.87 | -0.04 [-0.16, +0.06] |  |
| Share cut at ranking (gate, cap) | 70 | 1.7% | 2.6% | +0.9 pts [-1.1 pts, +3.1 pts] |  |
| Distinct domains among ranked | 70 | 4.91 | 4.87 | -0.04 [-0.16, +0.06] |  |
| Ranked from rated domains | 70 | 5.4% | 6.6% | +1.1 pts [-0.8 pts, +3.0 pts] |  |
| Ranked from the internal corpus | 70 | 0.0% | 0.0% | +0.0 pts [+0.0 pts, +0.0 pts] |  |
| Retrieval seconds per claim | 70 | 14.41 | 11.70 | -2.71 [-4.44, -1.01] |  |
| Ranking seconds per claim | 70 | 12.16 | 13.14 | +0.98 [-0.21, +2.18] |  |

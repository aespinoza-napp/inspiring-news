# The topic classifier against the annotator

58 labelled articles. Shares with 95% bootstrap intervals.

| Top-1 topic | Gold in top 3 | Top-1 group | No topic at the floor (0.35) |
|---|---|---|---|
| 0.67 [0.55, 0.79] | 0.88 [0.79, 0.95] | 0.83 [0.72, 0.91] | 0.02 [0.00, 0.05] |

## Group confusion (rows: annotator, columns: classifier's top topic)

| Annotator \ classifier | society | science | environment | culture | health | no topic |
|---|---|---|---|---|---|---|
| society | 5 | 1 | 1 | 1 | 1 | 0 |
| science | 0 | 13 | 0 | 0 | 0 | 0 |
| environment | 0 | 2 | 13 | 0 | 0 | 0 |
| culture | 0 | 0 | 3 | 4 | 0 | 0 |
| health | 0 | 1 | 0 | 0 | 13 | 0 |

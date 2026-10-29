# manual-train: models compared

Dataset sha256 `b261d136c662`, 69 rows. Bootstrap seed 2026, 10000 resamples. Pairwise differences: `cli report --run B --compare A`.

| Model | Provider | Scored | Accuracy | Macro-F1 | Coverage | Selective acc. | Kappa | Invalid output | Set apart | Median s/claim | p90 s/claim | Median s/model call | Completion tok/claim | Tok/s | Cost per 100 claims |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `llama3.2:3b-bench` | localhost:11434 | 63 | 52.4% [39.7%, 65.1%] | 0.279 [0.192, 0.371] | 82.5% | 61.5% | 0.099 | 0 | 6 | 93.3 | 138.4 | 7.2 | 165.6 | 3.6 | n/a |
| `qwen3.5:9b-bench` | localhost:11434 | 20 | 35.0% [15.0%, 55.0%] | 0.241 [0.100, 0.388] | 65.0% | 46.2% | -0.004 | 0 | 0 | 254.9 | 472.1 | 28.2 | 132.2 | 0.9 | n/a |
| `granite3.3:8b-bench` | localhost:11434 | 20 | 60.0% [40.0%, 80.0%] | 0.438 [0.230, 0.619] | 95.0% | 57.9% | 0.263 | 0 | 0 | 226.7 | 354.2 | 19.9 | 241.8 | 2.1 | n/a |
| `gemma4:e4b-bench` | localhost:11434 | 20 | 45.0% [25.0%, 65.0%] | 0.348 [0.165, 0.499] | 55.0% | 54.5% | 0.179 | 0 | 0 | 203.9 | 308.1 | 18.5 | 127.0 | 1.2 | n/a |

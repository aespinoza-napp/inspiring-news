# Benchmark: campaign 20261104-speed

Every try on the same claims and, for a replay, the same evidence, each against the baseline (try 0). Self-hosted is this machine's Ollama; a hosted provider sees the claims and the sources' excerpts and limits how much it serves. Seconds are a claim's, retrieval included; the target is a median <= 20 s and p90 <= 30 s.

| Try | Where | Model | Changes | Decision | Claims | Accuracy | vs baseline [95% CI] | Conf. wrong | Kappa | Median s | p90 s | Calls / claim | A call, s | Tokens / claim | Cost / 100 claims |
|---:|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|

A screened-out try's row is its screen's first claims only. Train half, labels mostly the AI pass's and unreviewed: no figure here is final. Cost is n/a where prices.json has no price for that model and host.

# The second look, as the pipeline takes it: manual-test

Run `2605a2c02380`, model `llama3.2:3b`, `second_look_enabled`. 70 of 70 claims scored. Bootstrap: 10000 resamples, seed 2026.

First pass: accuracy 52.9% [41.4%, 64.3%], macro-F1 0.227 [0.176, 0.273]. 17 second looks (low_confidence 14, unverified 3), 16 with a new source in the final evidence, 0 whose follow-up search failed; 2209.5 s spent in them.

| Rule | Fired | Accuracy first | final | Difference [95% CI] | Macro-F1 final | Wrong to right | Right to wrong |
|---|---|---|---|---|---|---|---|
| unverifiedOrUnsure | 17 | 52.9% | 52.9% | +0.0 [-4.3, +4.3] | 0.218 [0.168, 0.264] | 1 | 1 |
| unverifiedOnly | 3 | 52.9% | 52.9% | +0.0 [+0.0, +0.0] | 0.221 [0.171, 0.267] | 0 | 0 |

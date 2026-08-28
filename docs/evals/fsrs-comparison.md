# FSRS comparison

The fixed first-review sequence uses `fsrs==6.3.2`, `enable_fuzzing=False`, and review time `2026-01-02T00:00:00Z`. It compares the prior simple interval baseline with the scheduler output; values are reproducible in [`artifacts/learning/fsrs-again-hard-good-easy-v1.json`](../../artifacts/learning/fsrs-again-hard-good-easy-v1.json).

| Rating | Old baseline interval | FSRS due interval | Difficulty | Stability |
|---|---:|---:|---:|---:|
| Again | 0 days | 1 minute | 6.4133 | 0.2120 |
| Hard | 1 day | 5.5 minutes | 5.1122 | 1.2931 |
| Good | 1 day | 10 minutes | 2.1181 | 2.3065 |
| Easy | 4 days | 8 days | 1.0000 | 8.2956 |

The purpose is not to assert clinical learning efficacy. It proves that `due`, `difficulty`, `stability` and `retrievability` come from the real scheduler rather than handcrafted intervals.

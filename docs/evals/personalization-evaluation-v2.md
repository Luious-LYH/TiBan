# Personalization Engineering Evaluation — v2.0

## Definition

For v2.0, personalization uplift means scheduling behavior only:

> After explicit weak-topic evidence, what fraction of the next bounded
> session matches that evidence topic?

It is not a learning-score, retention, clinical-effectiveness or educational-
outcome claim.

## Fixed artifact

The deterministic comparison uses the same evidence topic in both schedules:

| Schedule | Matching items | Total | Matching ratio |
| --- | ---: | ---: | ---: |
| Baseline | 1 | 4 | 0.2500 |
| Evidence-aware | 3 | 4 | 0.7500 |
| Scheduling uplift | — | — | **+0.5000** |

The full topic lists, metric definition and integration-test reference are in
[`personalization-uplift-v2.json`](../../artifacts/platform/personalization-uplift-v2.json).
Memory relevance is separately recorded in
[`memory-relevance-v2.json`](../../artifacts/platform/memory-relevance-v2.json):
relevant selected memory rate 1.0, irrelevant injection rate 0.0, cross-domain
leakage count 0 and maximum selected memory count 1.

The artifact is a small controlled engineering fixture. It demonstrates that
the scheduler consumes scoped evidence; it does not demonstrate that learning
outcomes improve.

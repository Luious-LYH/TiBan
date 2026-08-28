# Question Judge Evaluation v2

## Design

The v2 fixture contains 80 frozen, harder Factory drafts spanning safe passes,
answer inconsistency, missing/mismatched citation, unsupported claim, safety
boundary, duplicate distractor, ambiguous stem and difficulty mismatch. The
Generator and Judge remain separate Provider calls and schemas. The Judge sees
only draft, evidence, rubric and expected citation — never Generator reasoning.

The run uses the configured OpenAI-compatible Provider with `allow_fallback=false`.
Structured Judge decisions, not raw reasoning, are retained in
`artifacts/factory/question-judge-eval-v2.json`.

## Measured results

| Decision path | Precision | Recall | F1 | TP / FP / FN / TN |
|---|---:|---:|---:|---:|
| Deterministic Gate only | 0.2540 | 1.0000 | 0.4051 | 16 / 47 / 0 / 17 |
| Gate + real Provider Judge | 0.9412 | 1.0000 | 0.9697 | 16 / 1 / 0 / 63 |

There were no Provider failures. The remaining false positive was an ambiguous
stem case; this is retained as a concrete failure case rather than hidden by an
aggregate score.

## Evidence boundary

The fixture is an engineering candidate set and its `human_review_status` is
`pending`. It is **not** claimed to be a 0.9697 human-reviewed Judge accuracy.
Before an accuracy statement can be used externally, a named clinical/educator
reviewer must independently validate the expected labels and issue categories.

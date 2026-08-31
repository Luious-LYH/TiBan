# Agent Engineering Evaluation — v2.0

## Scope

The fixed suite evaluates Tutor tool routing and permissions, not answer
quality or a model's hidden reasoning. It uses the no-secret
`LocalPolicyModelGateway` so the result is reproducible in local and hosted
CI. External provider acceptance remains a separate smoke path.

## Cases and metrics

Six cases cover knowledge-needed, question-only, memory-needed, post-submit
grading, Study direct-answer permission and Exam direct-answer denial.

| Metric | Result |
| --- | ---: |
| Tool-selection accuracy | 1.0000 |
| Unnecessary tool rate | 0.0000 |
| Missing-tool rate | 0.0000 |
| Cases | 6 |

The complete per-case receipt is
[`agent-tool-selection-v2.json`](../../artifacts/platform/agent-tool-selection-v2.json).
The existing Tutor permission tests additionally construct adversarial
pre-submit requests for the correct answer, server standard answer and hidden
rubric; the grading tool is absent from the pre-submit registry rather than
merely refused by a prompt.

## Interpretation

`provider_usage` is `not available` because this is a deterministic policy
adapter evaluation. The numbers support a regression claim for the current
permission/routing contract only. They do not support a claim of universal
model tool-use accuracy, clinical safety, or educational effectiveness.

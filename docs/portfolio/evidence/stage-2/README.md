# Stage 2 evidence index

## Product screenshots

All images below were captured by `frontend/e2e/capture-stage2.spec.ts` after the Stage 2 backend and frontend were running locally.

| Surface | 375 | 768 | 1280 | 1440 |
|---|---|---|---|---|
| Overview | [375](overview-375.png) | [768](overview-768.png) | [1280](overview-1280.png) | [1440](overview-1440.png) |
| Factory Studio | [375](factory-375.png) | [768](factory-768.png) | [1280](factory-1280.png) | [1440](factory-1440.png) |
| Practice + persistent Tutor | [375](practice-375.png) | [768](practice-768.png) | [1280](practice-1280.png) | [1440](practice-1440.png) |
| Evaluation | [375](eval-375.png) | [768](eval-768.png) | [1280](eval-1280.png) | [1440](eval-1440.png) |

The mobile Tutor drawer is captured separately: [practice-tutor-375.png](practice-tutor-375.png).

## Auditable artifacts

- Tutor model/tool/observation/final/source trace: [anonymous demo](../../../../artifacts/agent/tutor-v1/anonymous-demo-trace.json), [adversarial recovery](../../../../artifacts/agent/tutor-v1/adversarial-recovery-trace.json). Neither contains raw chain-of-thought.
- Frozen retrieval benchmark: [JSON artifact](../../../../artifacts/rag/retrieval-eval-v1.json), [readable results](../../../evals/rag-benchmark-v1.md).
- Factory Judge review set: [JSON artifact](../../../../artifacts/factory/question-judge-eval-v1.json), [evaluation](../../../evals/question-judge-eval-v1.md).
- FSRS fixed sequence: [JSON artifact](../../../../artifacts/learning/fsrs-again-hard-good-easy-v1.json), [comparison](../../../evals/fsrs-comparison.md).

## Failure and recovery evidence

- The Tutor adversarial trace requests a correct answer/hidden rubric during pre-submit; the unavailable grading tool is never called and the response remains evidence-oriented.
- The RAG `identity-v2` version documents the recovery from historical chunk-ID duplication without deleting the historical index. Its frozen benchmark version contains exactly 21 chunks for 180 and 20 for 280.
- Factory records an initial failed Judge decision as a separate revision, then retains the repair revision's parent link and rewrite instruction before human publish.

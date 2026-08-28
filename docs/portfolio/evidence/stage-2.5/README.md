# Stage 2.5 evidence index

All screenshots below were captured by Playwright against the local running app. The final browser run passed 9/9 tests. The first Factory attempt exposed a real environment defect (worker on SQLite while API used PostgreSQL); after the worker was restarted with the canonical PostgreSQL URL, Flow B and the full suite passed.

## Product screenshots

| Surface | Evidence |
|---|---|
| QBank catalog with CMExam, CMB-Exam and Kvasir-VQA | [qbank-catalog-playwright.png](qbank-catalog-playwright.png) |
| Text-only CMB-Exam question with continuous Tutor | [cmb-text-only-playwright.png](cmb-text-only-playwright.png) |
| Kvasir-VQA image question | [kvasir-practice-playwright.png](kvasir-practice-playwright.png) |
| Exam answer lock | [exam-locked-playwright.png](exam-locked-playwright.png) |
| Study feedback | [cmexam-study-feedback.png](cmexam-study-feedback.png) |
| Review FSRS action and due result | [review-fsrs-due.png](review-fsrs-due.png) |
| Real Provider direct-answer Tutor | [tutor-provider-direct-answer.png](tutor-provider-direct-answer.png) |
| Offline-provider pending state | [tutor-provider-pending.png](tutor-provider-pending.png) |

The earlier Stage 2 responsive baseline remains available in [`stage-2/README.md`](../stage-2/README.md); Stage 2.5 does not create `.v2`/`.v3` page copies.

## Runtime and data artifacts

| Evidence | Artifact |
|---|---|
| Final Gate snapshot | [`gate-results-v1.json`](../../../../artifacts/stage-2.5/gate-results-v1.json) |
| Final validation matrix | [`validation-v1.json`](../../../../artifacts/stage-2.5/validation-v1.json) |
| Provider acceptance | [`provider-acceptance-v1.json`](../../../../artifacts/agent/tutor-v1/provider-acceptance-v1.json) |
| Anonymous Tutor trace | [`anonymous-demo-trace.json`](../../../../artifacts/agent/tutor-v1/anonymous-demo-trace.json) |
| Adversarial/recovery trace | [`adversarial-recovery-trace.json`](../../../../artifacts/agent/tutor-v1/adversarial-recovery-trace.json) |
| QBank import counts and lineage | [`qbank-import-v1.json`](../../../../artifacts/qbank/qbank-import-v1.json) |
| Local VQA inventory | [`local-vqa-inventory.json`](../../../../artifacts/data/local-vqa-inventory.json) |
| Knowledge index and namespaces | [`knowledge-index-v1.json`](../../../../artifacts/knowledge/knowledge-index-v1.json) |
| RAG benchmark | [`retrieval-eval-v1.json`](../../../../artifacts/rag/retrieval-eval-v1.json) |
| Question Judge evaluation | [`question-judge-eval-v1.json`](../../../../artifacts/factory/question-judge-eval-v1.json) |
| FSRS fixed sequence | [`fsrs-again-hard-good-easy-v1.json`](../../../../artifacts/learning/fsrs-again-hard-good-easy-v1.json) |

## Human-readable specifications

- [Stage 2.5 report](../../../stages/stage-2.5-product-reset-report.md)
- [QBank UX](../../../product/qbank-ux-spec.md)
- [Tutor UX](../../../product/tutor-ux-spec.md)
- [Dataset inventory](../../../data/local-vqa-inventory.md)
- [Data governance](../../../data/data-governance.md)
- [Knowledge Base specification](../../../data/knowledge-base-spec.md)
- [Kvasir suitability policy](../../../data/kvasir-product-suitability.md)
- [Tutor architecture](../../../architecture/tutor-agent.md)
- [RAG architecture](../../../architecture/rag-pipeline.md)
- [Question Factory architecture](../../../architecture/question-factory.md)
- [Learning architecture](../../../architecture/learning-memory.md)
- [RAG benchmark report](../../../evals/rag-benchmark-v1.md)
- [Question Judge report](../../../evals/question-judge-eval-v1.md)
- [FSRS comparison](../../../evals/fsrs-comparison.md)

## Acceptance notes

- Provider: real local OpenAI-compatible path, 13/13 scenarios passed, no key persisted.
- PostgreSQL: canonical acceptance database at the local Docker service; SQLite is only fallback/unit scope.
- Factory: the visible job ledger is backed by persisted Redis/Dramatiq state; the worker must use the same `ENDO_DATABASE_URL` as the API.
- EndoBench: inventory is retained for Evaluation metadata only; final Gate reports zero Qdrant points and zero generated lineage.
- Privacy: artifacts contain synthetic learner IDs and final learner-facing text only; no raw chain-of-thought or patient data.

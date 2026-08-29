# Final evidence matrix — Stage 4 / v1.0

Only claims tied to a current code path, repeatable check, and artifact are
resume-eligible. Portfolio metrics are not clinical-effectiveness claims.

| Capability | Current implementation and verification | Artifact / scope | Resume status |
|---|---|---|---|
| Tutor Agent | Bounded `AgentRunner` / `ToolRegistry` / `ModelGateway`; permission-filtered tools, retry, cancel, typed receipts, SSE source ordering. | `backend/tests/test_tutor_agent_v1.py`, `artifacts/agent/tutor-v1/` | Yes, with education boundary. |
| Answer isolation | Pre-submit adversarial requests cannot access grading tools or hidden answer fields; post-submit feedback is a separate path. | Tutor permission tests and contract tests. | Yes. |
| Retrieval | Sparse, dense, hybrid, and hybrid+rerank implementations; Dense selected as Tutor default from a frozen engineering benchmark. | `docs/evals/rag-benchmark-v2.md`, `artifacts/rag/retrieval-default-decision-v1.json` | Yes, as benchmark engineering. |
| Citation lineage | Chunk → document → page → section is preserved for retrieved source cards. | RAG/citation tests and knowledge artifacts. | Yes. |
| Question Factory | Parse → index → Generator → deterministic gate → Judge → repair → review → publish. Docker backend and worker share the persisted upload volume. | Factory tests; Stage 4 Docker job reached `ready_for_review` with two revision records. | Yes. |
| Learning loop | Immutable Attempt updates mastery and a real py-fsrs ReviewCard; next session reads the state and prioritizes weak topics. | `artifacts/learning/adaptive-loop-demo-v1.json`, FSRS tests. | Yes. |
| QBank bootstrap | Docker clean-start catalog contains CMExam 1,500, CMB-Exam 1,778, Kvasir-VQA curated 400 (total 3,678). | QBank acceptance artifact and Docker database count check. | Yes, exact scope. |
| BYOK evaluation | Separate text/VLM packs, request-scoped key, no fallback, per-case and aggregate results. | `docs/evals/model-evaluation-acceptance.md`, evaluation tests. | Yes, as engineering acceptance. |
| API and delivery | FastAPI OpenAPI → generated TypeScript client; Docker Compose topology; GitHub Actions fast profile. | `npm run api:check`, compose config, `.github/workflows/ci.yml`. | Yes; hosted run is external pending. |

## Release evidence

- Screenshots: [`evidence/stage-4/`](./evidence/stage-4/)
- Final release report: [`../stages/stage-4-v1.0-final-report.md`](../stages/stage-4-v1.0-final-report.md)
- Adaptive loop: [`../../artifacts/learning/adaptive-loop-demo-v1.json`](../../artifacts/learning/adaptive-loop-demo-v1.json)
- Security analysis: [`../../SECURITY_NOTES.md`](../../SECURITY_NOTES.md)

## Explicit boundaries

- RAG ground truth and Question Judge human review are **deferred** in v1.0.
  The retained benchmark and Judge workflow are engineering evidence, not expert
  validation or clinical validation.
- Do not claim autonomous diagnosis, treatment recommendation, multi-agent
  orchestration, Judge perfection, or 300k-question runtime validation.
- EndoBench is evaluation-only and never enters Tutor retrieval, Factory source
  ingestion, or learner-facing question banks.
- Raw chain-of-thought and secrets are not stored or displayed.
- Hosted GitHub Actions: `external_pending` because this local checkout has no
  configured remote. Run `git push origin refactor/v3-agent-learning-platform`
  after connecting the intended remote, then inspect **EndoTutor fast profile**.

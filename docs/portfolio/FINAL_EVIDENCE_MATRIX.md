# Final evidence matrix — Stage 6 / v1.2

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
| Memory & Personalization | Evidence-backed `LearningMemoryItem` separates long-term learning facts from session chat and derived profile; compact relevant read-back changes Tutor context and deterministic next-session evidence. | `artifacts/memory/`, `docs/architecture/memory-personalization.md`, Stage 5 lifecycle/isolation tests. | Yes, as deterministic personalization engineering. |
| QBank fixture boundary | Docker clean start uses a compact teaching seed; optional locally authorized CMExam/CMB/Kvasir adapters remain import-validation fixtures and are not redistributed. | `THIRD_PARTY_DATA.md`, source registry, Docker/bootstrap checks. | Yes, as data-governance engineering. |
| BYOK evaluation | Separate text/VLM packs, request-scoped key, no fallback, per-case and aggregate results. | `docs/evals/model-evaluation-acceptance.md`, evaluation tests. | Yes, as engineering acceptance. |
| API and delivery | FastAPI OpenAPI → generated TypeScript client; Docker Compose topology; GitHub Actions fast profile. | `npm run api:check`, compose config, `.github/workflows/ci.yml`, [run 33296518709](https://github.com/Luious-LYH/TiBan/actions/runs/33296518709). | Yes. |
| Modular monolith engineering | Selected Practice use-case boundary, Tutor-owned dependency adapters, normalized provider errors, and PostgreSQL durable Factory jobs with idempotency/recovery/cancel state. | `docs/architecture/*v1.2.md`, `artifacts/engineering/`, `backend/tests/test_stage6_engineering.py`. | Pending final release gate. |

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
- Learning-memory facts are learner-scoped, evidence-backed and lifecycle-managed;
  they are not model weight updates or unrestricted chat retention.
- Hosted GitHub Actions passed for release baseline `86fb139` in
  [run 33296518709](https://github.com/Luious-LYH/TiBan/actions/runs/33296518709).

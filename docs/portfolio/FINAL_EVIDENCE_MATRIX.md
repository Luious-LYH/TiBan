# Final evidence matrix — TiBan V3

Only claims tied to a current code path, repeatable check, and artifact are
resume-eligible. Portfolio metrics are not clinical-effectiveness claims.

## TiBan V3 Core RC evidence

| Capability | Current implementation and verification | Artifact / scope | Resume status |
|---|---|---|---|
| Practice + Persistent Tutor Agent | Real CMB-Exam four-option question stays in the Practice workspace while the right-side 智能辅导 uses current-question context, retrieval state, conversation and post-submit review context. | `docs/v3/evidence/rc-promotion/01-practice-rag-citation-1440.png`, `02-review-followup-1440.png`, `08-practice-rag-citation-1920.png`, `09-practice-rag-citation-375.png`, RC promotion report | Yes — bounded learning assistant, not autonomous clinical advice. |
| RAG / Citation | `rag_service → Qdrant → /api/v3/tutor/stream` emits real source events for CMB-Exam `cmb_val_000079`; the learner-facing citation is 《小肠运动与消化液混合》 and the question provenance is not used as a substitute. | `docs/v3/V3_PHASE_D_RELEASE_GATE_REPORT.md`, `docs/v3/evidence/phase-e/01-practice-rag-citation-1440.png` | Yes — source-backed retrieval path. |
| Adaptive Learning + Memory | Submit remains server-owned: Attempt → mastery → FSRS/review scheduling → learning memory; the overview now exposes recent answers and governed topics without a profile dashboard. | `docs/v3/evidence/rc-promotion/05-overview-1440.png`, backend learning-memory and practice tests | Yes — deterministic personalization engineering claim. |
| QBank Import boundary | `/factory` is a real two-path workspace: CSV/JSONL/Markdown validate/preview for existing questions, and the existing `.md/.pdf` source-backed Factory for generation. | `docs/v3/evidence/rc-promotion/03-factory-real-job-1440.png`, `frontend/src/components/factory/FactoryStudio.tsx` | Yes — validate/preview is not claimed as persistence until a write API exists. |
| Question Factory | Real isolated worker job passed prewarm → parse → index → generate → judge/repair → review → publish on attempt 1 without stale recovery. | `factory_11e9ecb3cb0c`, `revision_52061e78ae7e`, `docs/v3/evidence/rc-promotion/03-factory-real-job-1440.png`, cold-start Compose logs | Yes — source-backed generation and review lineage. |
| Model Evaluation | Read-only UI projects the existing artifact's metrics, probes, expected evidence and ranked evidence; no new score or strategy comparison is fabricated. | `docs/v3/evidence/rc-promotion/04-evaluation-evidence-1440.png`, `artifacts/eval/latest.json`, `/api/v3/evaluation/latest` | Yes — deterministic artifact projection, not clinical/model leaderboard evidence. |
| Instance-level AI Settings | LLM and Embedding test/apply/restore operate through typed backend endpoints and runtime-scoped overrides; API keys are not returned or stored in browser storage and restart restores defaults. | `frontend/src/pages/settings/SettingsPage.tsx`, `backend/app/routers/settings.py`, `backend/tests/test_instance_runtime_settings.py`, `docs/v3/evidence/rc-promotion/07-settings-1440.png` | Yes — single-instance runtime configuration only. |
| Compose runtime | Frontend Nginx proxies same-origin `/api`, permits the encoded upload boundary and disables SSE buffering; healthy backend, worker, PostgreSQL, Redis and Qdrant were observed. | `frontend/nginx.conf`, `docker-compose.yml`, `docker compose config -q`, `docker compose ps` | Yes. |
| Release verification | Full core Playwright suite passed 7/7; frontend lint/Vitest/build and backend compile/pytest passed. | `frontend/e2e/core-flow.spec.ts`, `frontend/e2e/phase-c-core.spec.ts`, `frontend/e2e/stage7-general-flow.spec.ts`; 78 passed, 1 skipped | PASS with the documented acceptance-database skip. |

## TiBan v2.0 platform (historical baseline)

| Capability | Current implementation and verification | Artifact / scope | Resume status |
|---|---|---|---|
| Domain-extensible core | Validated `DomainManifest` registry serves Medical / Endoscopy and General Science through one catalog, Practice, Tutor, Memory, FSRS and Evaluation core. | `docs/architecture/domain-packs-v2.md`, `artifacts/platform/domain-core-reuse-v2.json`, `tests/test_stage7_platform.py` | PASS — engineering reuse claim only. |
| Cross-domain isolation | `domain_id` scopes sessions, mastery, memory, retrieval metadata and evaluation packs; hard isolation tests pass. | `artifacts/platform/cross-domain-isolation-v2.json`, `docs/evals/domain-compatibility-v2.md` | PASS. |
| General Domain proof | Eight-row project-authored fixture supports Study/Exam/Review/Tutor/Attempt/Mastery/FSRS/Memory/Evaluation; ARC Easy remains local-only. | `backend/app/data/general_science_fixture.json`, `artifacts/platform/general-domain-flow-v2.json` | PASS — small proof pack. |
| Advanced Agent Evaluation | Fixed six-case tool-selection regression records 1.0 accuracy, 0 unnecessary-tool rate and 0 missing-tool rate. | `docs/evals/agent-evaluation-v2.md`, `artifacts/platform/agent-tool-selection-v2.json` | PASS — deterministic policy adapter. |
| Personalization Evaluation | Scheduling-behavior definition records 0.25 → 0.75 topic matching, +0.50 uplift; no learning-outcome claim. | `docs/evals/personalization-evaluation-v2.md`, `artifacts/platform/personalization-uplift-v2.json` | PASS — controlled engineering fixture. |

| Capability | Current implementation and verification | Artifact / scope | Resume status |
|---|---|---|---|
| Tutor Agent | Bounded `AgentRunner` / `ToolRegistry` / `ModelGateway`; permission-filtered tools, retry, cancel, typed receipts, SSE source ordering. | `backend/tests/test_tutor_agent_v1.py`, `artifacts/agent/tutor-v1/` | Yes, with education boundary. |
| Answer isolation | Pre-submit adversarial requests cannot access grading tools or hidden answer fields; post-submit feedback is a separate path. | Tutor permission tests and contract tests. | Yes. |
| Retrieval | Sparse, dense, hybrid, and hybrid+rerank implementations; Dense selected as Tutor default from a frozen engineering benchmark. | `docs/evals/rag-benchmark-v2.md`, `artifacts/rag/retrieval-default-decision-v1.json` | Yes, as benchmark engineering. |
| Citation lineage | Chunk → document → page → section is preserved for retrieved source cards. | RAG/citation tests and knowledge artifacts. | Yes. |
| Question Factory | Parse → index → Generator → deterministic gate → Judge → repair → review → publish. Docker backend and worker share the persisted upload volume. | Factory tests; Docker acceptance job reached `ready_for_review` with two revision records. | Yes. |
| Learning loop | Immutable Attempt updates mastery and a real py-fsrs ReviewCard; next session reads the state and prioritizes weak topics. | `artifacts/learning/adaptive-loop-demo-v1.json`, FSRS tests. | Yes. |
| Memory & Personalization | Evidence-backed `LearningMemoryItem` separates long-term learning facts from session chat and derived profile; compact relevant read-back changes Tutor context and deterministic next-session evidence. | `artifacts/memory/`, `docs/architecture/memory-personalization.md`, lifecycle/isolation tests. | Yes, as deterministic personalization engineering. |
| QBank fixture boundary | Docker clean start uses a compact teaching seed; optional locally authorized CMExam/CMB/Kvasir adapters remain import-validation fixtures and are not redistributed. | `THIRD_PARTY_DATA.md`, source registry, Docker/bootstrap checks. | Yes, as data-governance engineering. |
| BYOK evaluation | Separate text/VLM packs, request-scoped key, no fallback, per-case and aggregate results. | `docs/evals/model-evaluation-acceptance.md`, evaluation tests. | Yes, as engineering acceptance. |
| API and delivery | FastAPI OpenAPI → generated TypeScript client; Docker Compose topology; GitHub Actions platform gates. | `npm run api:check`, compose config, `.github/workflows/ci.yml`, [run 33362264760](https://github.com/Luious-LYH/TiBan/actions/runs/33362264760). | Yes. |
| Modular monolith engineering | Selected Practice use-case boundary, Tutor-owned dependency adapters, normalized provider errors, and PostgreSQL durable Factory jobs with idempotency/recovery/cancel state. | `docs/architecture/*v1.2.md`, `artifacts/engineering/`, `backend/tests/test_stage6_engineering.py`. | PASS — v1.2.0 release commit `8014374`, annotated tag and hosted run `33322744745`. |

## Release evidence

- V3 screenshots: [`../v3/evidence/rc-promotion/`](../v3/evidence/rc-promotion/)
- V3 final report: [`../v3/V3_PHASE_E_FINAL_REPORT.md`](../v3/V3_PHASE_E_FINAL_REPORT.md)
- V3 RC promotion report: [`../v3/V3_RC_PROMOTION_REPORT.md`](../v3/V3_RC_PROMOTION_REPORT.md)
- V3 core demo flow: [`../v3/portfolio/V3_DEMO_FLOW.md`](../v3/portfolio/V3_DEMO_FLOW.md)
- Screenshots: [`evidence/current-v2/`](./evidence/current-v2/)
- Final release report: [`../V2_RELEASE_REPORT.md`](../V2_RELEASE_REPORT.md)
- Adaptive loop: [`../../artifacts/learning/adaptive-loop-demo-v1.json`](../../artifacts/learning/adaptive-loop-demo-v1.json)
- Security analysis: [`../../SECURITY_NOTES.md`](../../SECURITY_NOTES.md)

## Explicit boundaries

- RAG ground truth and Question Judge human review are **deferred**.
  The retained benchmark and Judge workflow are engineering evidence, not expert
  validation or clinical validation.
- Do not claim autonomous diagnosis, treatment recommendation, multi-agent
  orchestration, Judge perfection, or 300k-question runtime validation.
- EndoBench is evaluation-only and never enters Tutor retrieval, Factory source
  ingestion, or learner-facing question banks.
- Raw chain-of-thought and secrets are not stored or displayed.
- Learning-memory facts are learner-scoped, evidence-backed and lifecycle-managed;
  they are not model weight updates or unrestricted chat retention.
- Hosted GitHub Actions passed for the v2.0 release commit `2a6f61b` in
  [run 33362264760](https://github.com/Luious-LYH/TiBan/actions/runs/33362264760).

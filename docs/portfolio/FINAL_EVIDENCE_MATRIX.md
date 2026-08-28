# Final evidence matrix

Only claims with a concrete code path, regression, and artifact are marked
resume-eligible. Portfolio-sized numbers are not clinical claims.

| Claim | Code | Test | Artifact | Metric | Resume? |
|---|---|---|---|---|---|
| Bounded real Tutor loop with tool receipts and SSE | `backend/app/services/agent_runtime.py`, `backend/app/routers/tutor_agent.py` | `test_tutor_agent_v1.py` | `artifacts/agent/tutor-v1/` | 13/13 prior provider acceptance; event ordering/cancel/retry covered | YES, with boundary |
| Pre-submit answer isolation and Study/Exam permission | `agent_runtime.py`, mode-aware Tutor router | adversarial and mode tests | Stage 2.5 evidence | no hidden answer fields in pre-submit payloads | YES |
| Knowledge RAG with four retrieval chains | `rag_service.py` | `test_stage2_learning_factory_rag.py`, corpus tests | `artifacts/knowledge/knowledge-corpus-v1-index.json`, `artifacts/rag/retrieval-eval-v2.json` | held-out Recall@5: sparse .7667 / dense .8833 / hybrid .7167 / rerank .9000 | YES, as benchmark |
| Source/page/section citation lineage | `rag_service.py`, source models | citation/data-governance tests | `docs/evals/rag-benchmark-v2.md` | citation fields preserved | YES |
| Generator → gate → Judge → Repair → publish | `factory_service.py`, Dramatiq worker | factory schema/job/provider tests | `artifacts/factory/factory-provider-acceptance-v1.json` | Markdown/PDF/Kvasir source paths accepted with no fallback | YES |
| Judge improves deterministic gate precision on review set | `factory_service.py`, eval script | Judge eval tests | `artifacts/factory/question-judge-eval-v2.json` | precision .2540 → .9412; human review status explicitly pending | YES, with caveat |
| Real py-fsrs learning projection | `memory_service.py`, learning router | FSRS/mentor tests | `artifacts/learning/fsrs-again-hard-good-easy-v1.json` | reproducible Again/Hard/Good/Easy due sequence | YES |
| QBank demo and scale pipeline | `qbank_import_service.py`, session membership migration | QBank/Session tests | `artifacts/qbank/qbank-scale-acceptance-v1.json` | demo 3,678; scale 68,112 valid CMExam rows | YES, exact scope |
| BYOK text and VLM evaluation with no fallback | `model_eval_service.py`, evaluation router/client | `test_model_evaluation.py` | `artifacts/eval/model-runs/`, `docs/evals/model-evaluation-acceptance.md` | CMExam 5/5 valid; EndoBench VLM 1 real image case, incorrect retained | YES, as engineering acceptance |
| OpenAPI client is generated and drift-checkable | `frontend/scripts/generate-openapi.mjs` | `npm run api:check` | `frontend/src/api/generated.ts` | deterministic FastAPI → generated TS path | YES |
| Docker/CI reproducible local stack | `docker-compose.yml`, Dockerfiles, CI workflow | `docker compose config`, local quality commands | `.github/workflows/ci.yml` | frontend/backend/Qdrant/Redis/worker topology | YES, config-level unless CI run is attached |

## Explicitly not resume claims

- “Autonomous diagnosis”, treatment recommendation, or clinical effectiveness.
- “Multi-Agent” as a product capability; the implementation is a bounded Tutor
  harness plus a role-separated Factory workflow.
- “30 万题运行态验证”; only the documented demo and scale acceptance counts
  are supported.
- “Judge accuracy 100%”; the review set is small and has a retained failure
  analysis.
- Raw chain-of-thought display or persistence.

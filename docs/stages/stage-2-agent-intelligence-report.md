# Stage 2 — Agent Intelligence report

**Status: completed with external-provider acceptance pending.** This report covers only Macro Stage 2; no Stage 3 work is included.

## Gate summary

| Area | Result | Evidence |
|---|---|---|
| Tutor | Pass locally | Minimal `AgentRunner` loop, tool receipts, permission tests, SSE/cancel/retry, persistent right-side desktop chat and anonymous trace. |
| RAG | Pass | PostgreSQL source metadata + Qdrant index, real FastEmbed embeddings, sparse/dense/hybrid/learned-rerank benchmark, citation chain. |
| Factory | Pass locally | Allowed document → Redis/Dramatiq → parse/index → Generator/Gate/Judge/repair → human publish; revision lineage retained. |
| Learning | Pass | Immutable Attempt, mastery projection, official `fsrs==6.3.2`, reproducible scheduler comparison and state-derived Mentor plan. |
| Quality | Pass | PostgreSQL backend regression, generated OpenAPI client, frontend lint/test/build, Flow A/B Playwright, responsive screenshot capture. |

## Tutor Agent

Tutor v1 is intentionally bounded to `AgentRunner`, `ToolRegistry`, `ModelGateway`, `AgentContext`, `AgentEvent`, and `AgentResult`. It limits steps, timeout, retry, cancellation and tool permissions rather than becoming a generic framework.

Pre-submit exposes only public question context, retrieval and a read-only learning profile. `get_grading_result` is post-submit only; no Tutor tool can write Attempt, mastery or scheduling state. Deterministic application code performs `grade → Attempt → mastery → FSRS` after submit.

The practice workspace now uses a continuous right-side chat on desktop and a mobile drawer. It streams real `message_start`, `token`, `tool_start`, `tool_end`, `source`, `message_end`, and `error` events. It does not expose raw chain-of-thought: the UI and trace disclose only ToolReceipts, citations and concise evidence summaries. See [Tutor architecture](../architecture/tutor-agent.md) and the [trace artifacts](../portfolio/evidence/stage-2/README.md#auditable-artifacts).

## RAG decision and result

PostgreSQL remains canonical for relational/source state; Qdrant is the retrieval index. Embeddings use FastEmbed `BAAI/bge-small-zh-v1.5` (512 dimensions, L2). The learned reranker is `cross-encoder/ms-marco-MiniLM-L6-v2` (Apache-2.0).

`retrieval-eval-v1` is a frozen, manually checked Chinese 50-query dataset (20 development / 30 test); it does not use an LLM self-labelling loop. The reportable test results are:

| Chain / 180 chars | Recall@5 | MRR | nDCG@5 | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Sparse | 1.00 | 0.95 | 0.96 | 62.56 | 76.28 |
| Dense | 0.97 | 0.88 | 0.90 | 185.44 | 248.13 |
| Hybrid (RRF) | 1.00 | 0.94 | 0.96 | 198.49 | 236.53 |
| Hybrid + learned rerank | 0.73 | 0.58 | 0.62 | 658.96 | 1714.41 |

Hybrid RRF at child size 180 is the product default. The real reranker is retained as a documented negative result, not presented as an improvement. `identity-v2` isolates new chunk IDs (21 chunks at 180, 20 at 280) from a retained historical index so metrics are not inflated by duplicate chunks. Full results: [RAG architecture](../architecture/rag-pipeline.md), [benchmark](../evals/rag-benchmark-v1.md), [artifact](../../artifacts/rag/retrieval-eval-v1.json).

## Factory and Judge

Factory reuses the same `SourceDocument → DocumentVersion → KnowledgeChunk → citation` graph as RAG. The allowed Markdown/PDF boundary verifies extension, MIME and size. Redis/Dramatiq provides the only long-job queue; all visible job states are persisted rather than simulated.

Generator and Judge use separate schemas and prompts. The Judge cannot read generator reasoning; repairs create a child `QuestionRevision` rather than overwriting the original. A 30-example small manually reviewed set gives deterministic gate precision `0.500` and Gate+Judge precision/recall `1.000/1.000`; this is explicitly a workflow evaluation, not a general Judge claim. See [Factory architecture](../architecture/question-factory.md) and [Judge evaluation](../evals/question-judge-eval-v1.md).

## Learning state and FSRS

The server holds Chat/Practice state separately from immutable attempts, `LearnerMastery`, and `ReviewCard`. `py-fsrs` produces persisted difficulty, stability, retrievability, state and due values. A fixed Again/Hard/Good/Easy sequence demonstrates scheduler-derived values, while Mentor produces distinct typed plans from two different attempt histories. See [learning architecture](../architecture/learning-memory.md) and [FSRS comparison](../evals/fsrs-comparison.md).

## Verification executed

```text
PostgreSQL migration:        python -m alembic upgrade head
Backend regression:          ENDO_DATABASE_URL=<local PostgreSQL> python -m pytest -q   → 35 passed
Frontend generated client:   npm run api:generate
Frontend quality:            npm run lint && npm run test && npm run build              → 6 tests passed, build passed
Browser Flow A + B:          npx playwright test e2e/core-flow.spec.ts --project=chromium --workers=1 → passed
Responsive evidence:         npx playwright test e2e/capture-stage2.spec.ts --project=chromium --workers=1 → passed
RAG reproducibility:         python backend/scripts/run_rag_benchmark.py
Judge reproducibility:       python backend/scripts/run_question_judge_eval.py
```

The integration environment used PostgreSQL, Qdrant and Redis Docker services; SQLite remains only an isolated fallback/test option. The complete screenshot/artifact index is [here](../portfolio/evidence/stage-2/README.md).

## External provider acceptance pending

No provider secret was supplied or persisted. The normal local proof uses explicitly labelled deterministic adapters and is not represented as a real provider run. An opt-in `OpenAICompatibleTutorGateway` is implemented but has not been invoked.

After supplying credentials only in the local shell (never commit them), the minimum acceptance run is:

```powershell
cd code/frontend
$env:TUTOR_PROVIDER_ENABLED = 'true'
$env:LLM_PROVIDER = 'openai_compatible'
$env:LLM_BASE_URL = '<your HTTPS OpenAI-compatible endpoint>'
$env:LLM_API_KEY = '<ephemeral local secret>'
$env:LLM_MODEL = '<model name>'
npx playwright test e2e/core-flow.spec.ts --project=chromium --workers=1
```

This causes Flow A's Tutor turn to execute the provider's bounded tool-plan → observation → final-response loop. Capture a fresh anonymous trace and retain only receipt/source/final output; never save the key or raw reasoning.

## Known limitations

- External model-provider acceptance is pending the above local secret; Factory generator/Judge currently use a clearly labelled deterministic adapter.
- Reranking uses an English-trained cross encoder and is a measured negative result for this Chinese benchmark; it is not the product default.
- The frozen benchmark and manual Judge set are deliberately small portfolio artifacts, not clinical effectiveness claims.
- FastAPI startup and several UTC calls emit deprecation warnings; they do not fail the Stage 2 tests and should be modernized in a later maintenance pass.

## Commit record

Stage 2 began with `fdccb5f`, `3fa94b7`, and `219fb1c`. This report is committed together with the remaining Stage 2 implementation; use `git log --oneline refactor/v3-agent-learning-platform` for the final immutable commit list.

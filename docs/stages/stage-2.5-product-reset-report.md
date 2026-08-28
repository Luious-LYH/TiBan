# Stage 2.5 — Product UX Reset + Real QBank Expansion

**Status: Completed.** Stage 3 was not started.

This report follows `C:\Users\LYH\Downloads\EndoTutor_Stage2.5_Product_UX_QBank_KnowledgeBase_v2.md` as the execution specification. It records the final state on `refactor/v3-agent-learning-platform`; runtime acceptance used local Docker PostgreSQL, Qdrant, Redis and the configured local OpenAI-compatible Tutor provider.

## Outcome

The Stage 2.5 final Gate is passed. The learner-facing product now has a real QBank catalog, Study / Exam / Review modes, Navigator and human-readable answer feedback, plus a continuous right-side Tutor chat. The data layer separates QBank, Knowledge Base, Evaluation and research/generation sources. EndoBench remains evaluation-only.

## Final Gate

| Gate | Result | Evidence |
|---|---|---|
| Real QBank UX | PASS | [QBank UX spec](../product/qbank-ux-spec.md), [catalog screenshot](../portfolio/evidence/stage-2.5/qbank-catalog-playwright.png) |
| Full-height continuous Tutor | PASS | [Tutor UX spec](../product/tutor-ux-spec.md), [real Provider screenshot](../portfolio/evidence/stage-2.5/tutor-provider-direct-answer.png) |
| Study direct-answer behavior | PASS | Real Provider acceptance `direct_answer_study`; server-side answer path is Study/pre-submit only |
| Exam answer restriction | PASS | `exam_answer_restriction`; [locked feedback screenshot](../portfolio/evidence/stage-2.5/exam-locked-playwright.png) |
| Reasoning / Sources collapsed UX | PASS | Real `reasoning`/`source` events; collapsed message parts in Tutor UI |
| Human-readable MCQ feedback | PASS | Study and Exam Playwright flows; answer/explanation fields are public display projections |
| Navigator | PASS | `stage25-flow.spec.ts`; Navigator supports current, unanswered, correct, incorrect and marked states |
| Session creation | PASS | Backend `PracticeSession` creation and Study/Exam/Review mode browser flows |
| CMExam real import | PASS | 1,500 user-ready questions; [QBank artifact](../../artifacts/qbank/qbank-import-v1.json) |
| CMB-Exam real import | PASS | 1,778 user-ready questions; [QBank artifact](../../artifacts/qbank/qbank-import-v1.json) |
| Local Kvasir-VQA integration | PASS | 58,849-row read-only inventory; 400 curated image questions; [inventory](../data/local-vqa-inventory.md) |
| Kvasir suitability classification | PASS | `user_ready` curated subset is separated from generation-source rows; [policy](../data/kvasir-product-suitability.md) |
| Independent Knowledge Base | PASS | `knowledge/` registry + curated notes; PostgreSQL source/chunk lineage and Qdrant namespaces |
| Selective Tutor RAG | PASS | no-retrieval and retrieval-needed Provider acceptance cases; [RAG benchmark](../evals/rag-benchmark-v1.md) |
| EndoBench evaluation-only | PASS | 0 Qdrant points, 0 generated lineage, 0 direct user-ready rows; [governance test](../../backend/tests/test_stage25_data_governance.py) |
| No benchmark contamination | PASS | PostgreSQL and Qdrant isolation checks pass |
| No fake Provider presented as real AI | PASS | Provider acceptance artifact distinguishes real local Provider from the offline adapter |

## Data inventory and product imports

The source directory `E:\2.Projects\ARIS\VQA\data` was scanned read-only. No source file was moved, renamed or modified.

| Dataset | Inventory | Stage 2.5 role | Learner-facing import |
|---|---:|---|---:|
| Kvasir-VQA | 58,849 QA / 6,507 image files | suitability-classified; curated image QBank | 400 |
| Kvasir-VQA-x1 | 159,549 QA / 6,500 image files | generation/research source | 0 direct |
| EndoBench | 6,832 QA / 6,832 image files | evaluation-only | 0 |
| CMExam | downloaded and normalized subset | real text QBank | 1,500 |
| CMB-Exam | downloaded and normalized subset | real text QBank | 1,778 |

The QBank artifact records `source_item_id`, dataset lineage, answer/explanation source and business usage. The UI hides dataset-gold and internal source-item metadata from ordinary learners.

## Architecture decisions implemented

- `QuestionPublic` remains an answer-free learner projection; Study direct-answer access is server-side and permissioned.
- Tutor v1 remains a bounded `AgentRunner / ToolRegistry / ModelGateway / AgentContext / AgentEvent / AgentResult` harness with max steps, timeout, cancellation, retry, permissions and trace.
- Deterministic application workflow owns `grade → Attempt → mastery → review scheduling`; the Tutor has no write tools.
- PostgreSQL is canonical relational state. Qdrant is the retrieval index. Redis + Dramatiq is the only long-job queue.
- Knowledge namespaces include `medical_general`, `endoscopy`, `factory_sources` and the other logical scopes defined by the registry. Evaluation material is never eligible for Tutor retrieval.
- Tutor events are real SSE events. The UI renders real token/source/reasoning parts and never uses timer-based fake tool status.
- Provider transient HTTP failures including 502/503/504 are retried twice with bounded exponential backoff. The acceptance harness retries each scenario up to three times and records the result honestly.

## Evidence and quality results

| Check | Result |
|---|---|
| Real Provider acceptance | 13/13 scenarios passed; 12 model-backed cases reported `provider_real=true` |
| Backend PostgreSQL regression | PASS; 41 passed |
| Frontend generated API integrity | `npm run api:check` PASS; generated client is reproducible from FastAPI OpenAPI |
| Frontend lint / unit tests / build | PASS / 7 passed / PASS |
| Playwright browser suite | 9 passed, including Factory Flow B with the real Dramatiq worker |
| RAG benchmark | frozen `retrieval-eval-v1`, 50 manually checked queries, sparse/dense/hybrid/hybrid+rerank with Recall@K/MRR/nDCG and latency |
| Question Judge evaluation | 30 manually reviewed drafts; Gate + Judge precision/recall 1.000/1.000 on this small set |
| FSRS comparison | real `py-fsrs` sequence Again/Hard/Good/Easy artifact |
| Secrets / raw data | no provider key, raw chain-of-thought or raw external dataset committed |

Full screenshot and artifact links are in the [Stage 2.5 evidence index](../portfolio/evidence/stage-2.5/README.md).

## Known limitations

- The Provider and Judge acceptance is local-provider evidence, not a claim of production availability or clinical safety. No raw model reasoning is stored; the UI exposes only high-level reasoning summary.
- The frozen RAG benchmark and Judge review set are portfolio-sized evaluation artifacts, not clinical effectiveness studies. The English cross-encoder reranker is retained as a measured negative result and is not the Tutor default.
- The first Knowledge Base corpus is intentionally curated and small (five checked-in Chinese notes plus factory/user-uploaded namespaces). Expanding source coverage requires a new license-gated ingestion phase.
- Advanced production session features such as server-persisted timed blocks, custom filter persistence, and large-scale multi-user session analytics remain outside this Stage 2.5 final Gate.

## Stop boundary

Stage 2.5 is complete and this execution stops here. No Stage 3 implementation was started.

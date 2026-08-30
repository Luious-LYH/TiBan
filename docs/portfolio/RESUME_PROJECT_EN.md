# EndoTutor project experience

**v1.0 / Stage 4 frozen release:** an agent-native learning and model-evaluation
platform for endoscopy education. Each claim below maps to current code, tests,
and an artifact; deferred human review is not presented as expert or clinical validation.

## Agent / LLM application engineering

- Built a bounded Tutor Agent for endoscopy education around `AgentRunner`, `ToolRegistry`, and `ModelGateway`, with real SSE `AgentEvent`/ToolReceipt traces, max-step/timeout/cancel/retry controls, and server-enforced Study vs Exam permissions.
- Implemented PostgreSQL source/citation state plus a Qdrant retrieval index and benchmarked sparse, dense, hybrid, and hybrid+rerank chains on 60 held-out cases with Recall@5, MRR, nDCG, and P50/P95 latency; retained the reranker negative result as an explicit trade-off.
- Built a role-separated Question Factory with Parse/Index, Generator schema, deterministic gate, Provider Judge, revision-preserving Repair, and publish workflow; retained a frozen review set, failure cases and an explicit human-review boundary instead of presenting an unreviewed Judge score as accuracy.
- Implemented an Adaptive Learning Loop: immutable Attempts drive mastery and FSRS ReviewCards, while the next session reads due reviews, weak topics and coverage state and returns an inspectable recommendation reason.
- Isolated learner QBank, Knowledge, Factory generation sources, and Evaluation datasets; EndoBench is Evaluation-only and cannot enter Tutor RAG, Factory, or learner QBank.
- Added a BYOK Model Evaluation workbench for frozen CMExam text and EndoBench VLM packs with real image input, per-case/aggregate artifacts, no fallback, and request-scoped secret handling.

## AI full-stack / agent infrastructure

- Delivered React/Vite/TypeScript and FastAPI/Pydantic Study, Exam, Review, QBank, Tutor, and Evaluation workbenches with an OpenAPI-generated client and drift check.
- Used PostgreSQL for canonical learner state and source lineage, Redis/Dramatiq for long-running Factory jobs, Qdrant for retrieval vectors, and py-fsrs for reproducible review scheduling.
- Shipped 3,678 curated demo questions and scale-tested the pipeline with 68,112 valid CMExam rows, including filtering, pagination, 50-question session membership, and navigator state.
- Added backend regression tests, frontend lint/unit/build, Playwright smoke coverage, Docker Compose, GitHub Actions fast profile, and artifact-backed evidence for model/RAG/Factory claims.

Safety boundary: for teaching and physician-review-before-use assistance only; not an autonomous diagnostic system or a clinical effectiveness claim.

## Stage 6 / v1.2 engineering evolution (release-pending draft)

Incrementally evolved the stable product into a pragmatic modular monolith: a Practice use-case boundary preserved the atomic learning transaction, Tutor-owned minimal dependency ports isolated storage/retrieval/model providers, and PostgreSQL durable Question Factory jobs added idempotency, cancellation, heartbeat and stale-worker recovery. Promote this paragraph only after the complete Stage 6 Release Gate passes.

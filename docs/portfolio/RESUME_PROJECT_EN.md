# TiBan project experience

**v2.0 / Stage 7 Interview Ready:** TiBan is an Agent-native Adaptive QBank &
Learning Platform. Medical / Endoscopy and General Science packs use the same
Practice, Tutor, Memory, FSRS and Evaluation core. Each claim below maps to
current code, tests, and an artifact; deferred human review is not presented as
expert or clinical validation.

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

## Stage 6 / v1.2 engineering evolution (released)

Incrementally evolved the stable product into a pragmatic modular monolith: a Practice use-case boundary preserved the atomic learning transaction, Tutor-owned minimal dependency ports isolated storage/retrieval/model providers, and PostgreSQL durable Question Factory jobs added idempotency, cancellation, heartbeat and stale-worker recovery. Evidence: annotated tag `v1.2.0`, Hosted Actions run `33322744745`, `docs/architecture/*v1.2.md`, `artifacts/engineering/`, and the Stage 6 regression suite.

## Stage 7 / v2.0 learning platform evolution (released)

Added a minimal validated `DomainManifest` boundary without duplicating the
Practice, Tutor, FSRS, Memory or Evaluation engines. The Medical / Endoscopy
pack remains the product regression path; a small project-authored General
Science pack proves Study/Exam/Review/Tutor/Attempt/Mastery/FSRS/Memory and
Evaluation reuse. Domain-scoped PostgreSQL state and RAG namespace filters
prevent same-label memory or source leakage. Advanced engineering evaluation
records fixed-case tool-selection metrics and scheduling-behavior uplift; these
are not educational-effectiveness or clinical-validity results. Evidence:
`docs/architecture/*v2.md`, `docs/evals/*v2.md`, `artifacts/platform/`, and the
Stage 7 final report.

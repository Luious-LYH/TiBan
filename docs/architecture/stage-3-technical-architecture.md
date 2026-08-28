# Stage 3 technical architecture

```text
Browser
  └─ React / Vite / TypeScript
       ├─ generated OpenAPI client
       ├─ real Tutor SSE event stream
       └─ Study / Exam / Review / Evaluation views
              │
              ▼
        FastAPI application
          ├─ AgentRunner (bounded max_steps/timeout/cancel/retry)
          │    ├─ ToolRegistry + ToolReceipt
          │    └─ ModelGateway → AgentEvent → SSE
          ├─ deterministic submit workflow
          │    └─ grade → immutable Attempt → mastery → py-fsrs ReviewCard
          ├─ Hybrid RAG
          │    ├─ PostgreSQL source/citation metadata
          │    └─ Qdrant sparse/dense/hybrid index
          ├─ Question Factory
          │    └─ Redis/Dramatiq → parse/index/generate/gate/judge/repair/publish
          └─ isolated Model Evaluation
               └─ frozen CMExam / EndoBench packs → run artifact

Data boundaries
  learner QBank ≠ knowledge corpus ≠ factory generation source ≠ evaluation pack
```

PostgreSQL is the canonical relational runtime. Qdrant stores retrieval
vectors, not learner state. Redis/Dramatiq is the only long-job queue. Tutor
has read-only tools and cannot write Attempt, mastery or review scheduling.
EndoBench is marked `benchmark_only` and is rejected by the Tutor, Factory and
learner-QBank paths.

Internal correlation is represented by the run/session/job/question/source
identifiers already present in their respective receipts. Langfuse and
OpenTelemetry remain optional/deferred; the product keeps the existing
ToolReceipt and AgentEvent evidence path without adding another runtime.

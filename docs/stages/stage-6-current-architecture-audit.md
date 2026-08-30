# Stage 6 current architecture audit — v1.1.0 baseline

## Scope lock (accepted by the Stage 6 execution brief)

**Product promise:** an auditable endoscopy-learning loop: practice, bounded
Tutor help, deterministic learning state, evidence retrieval, and a
review-before-publish Question Factory.

**Primary actor and success moment:** a learner answers a question, receives
safe evidence-aware feedback, and the next session changes for a transparent,
evidence-backed reason.

**Keep:** FastAPI/OpenAPI, SQLAlchemy/PostgreSQL, Qdrant, Redis + Dramatiq,
the Stage 5 attempt → mastery → FSRS → memory semantics, current routes and UI.

**Defer:** microservices, a DI container, a second queue/runtime, broad
repository-per-table conversion, new learning features, UI redesign, and Stage
7 multi-agent/VLM work.

**Validation:** characterization tests, fake ports, architecture-import guard,
OpenAPI drift guard, Docker clean-start and hosted CI.

## Current callable graph

| Route group | Current path | Application/service | Direct dependencies observed | Stage 6 action |
| --- | --- | --- | --- | --- |
| Banks | `routers/banks.py` | `Stage1Service` → `Stage1Repository` | SQLAlchemy via service/repository; serialization | Keep; repository reads are already compact. |
| Practice | `routers/practice.py` | `Stage1Service` | opens `SessionLocal`, obtains ORM question/session, grades, records Attempt and returns response | Extract a use-case boundary and pure grading rules. |
| Learning/Memory | `routers/learning.py` | `learning_service`, `learning_memory_service` | route opens SQLAlchemy session; service mutates FSRS/mastery/memory | Keep deterministic state rules; route delegates through application facade. |
| Tutor | `routers/tutor_agent.py` | `AgentRunner` / `ToolRegistry` / gateway | tool closures open sessions; call Stage1 service, RAG service and learning memory | Move concrete reads/writes to owned adapters and call through a Tutor use case. |
| Knowledge/RAG | `rag_service.py` | `RagService` | SQLAlchemy + `QdrantClient` in one adapter | Keep as retrieval adapter; do not introduce a second RAG system. |
| Question Factory | `routers/factory.py` → Dramatiq actor | `factory_service.py` | route dispatches actor; service opens sessions, writes files, calls Qdrant and provider | Add durable PostgreSQL job contract/state machine; retain Redis/Dramatiq delivery. |
| Evaluation | `routers/evaluation.py` | `model_eval_service.py` | SQLAlchemy/provider workflow | No broad migration; retain isolated domain. |

## Existing useful abstractions

- `Stage1Repository` already centralizes practice SQL queries and adaptive
  selection, but `Stage1Service` mixes session lifecycle, grading and response
  orchestration.
- Tutor v1 already has the approved minimal runtime (`AgentRunner`,
  `ToolRegistry`, `ModelGateway`, context/events/results) and must not be
  replaced.
- `llm_provider` already converts OpenAI-compatible HTTP interactions into an
  internal result. The additional boundary needed is at Tutor/Factory callers,
  not a multi-vendor framework.
- Factory already uses PostgreSQL `FactoryJobModel` plus Redis/Dramatiq, but its
  record is a progress-event projection rather than the required durable job
  contract.

## SDK leakage classification

| Location | Leakage | Classification | Repair |
| --- | --- | --- | --- |
| `routers/learning.py` | `SessionLocal` and manual commit | application leakage at transport | application facade owns the use-case call. |
| `services/stage1_service.py` | `SessionLocal`, ORM models, grading and workflow | application/persistence mixed | introduce Practice use cases and a SQLAlchemy adapter. |
| `services/agent_runtime.py` tool closures | `SessionLocal`, SQLAlchemy select, `rag_service`, Stage1 global | application leakage | Tutor-owned ports with concrete adapter assembly. |
| `services/rag_service.py` | `QdrantClient`, SQLAlchemy | adapter-only | retain as infrastructure adapter. |
| `services/llm_provider.py` | `urllib` OpenAI-compatible transport | adapter-only | retain; normalize errors at caller boundary. |
| `workers/factory_worker.py` | Dramatiq broker/actor | adapter-only | retain; pass only `job_id` to application worker. |
| `services/factory_service.py` | file, SQLAlchemy, Qdrant, provider and job state | application/infrastructure mixed | split durable job repository/dispatcher and Factory workflow boundary. |

## Transaction audit

The successful Practice path is currently:

```text
grade → Attempt → mastery → FSRS ReviewCard → LearningMemoryItem → commit
```

`Stage1Repository.record_attempt` invokes `apply_learning_outcome` in the same
database transaction. The operations are deterministic CPU work plus database
writes: no LLM, HTTP, Qdrant or Redis call is inside that transaction. This is
the correct Stage 5 semantic and remains synchronous in Stage 6.

Factory commits a durable progress state before each external operation today,
which avoids a long-lived SQL transaction across Qdrant/provider I/O. Stage 6
retains that property while making recovery, cancellation and idempotency
explicit.

## Architectural decision

Use a **pragmatic modular monolith**: FastAPI remains the transport/composition
root; three use-case modules own their minimal ports; SQLAlchemy, RAG,
OpenAI-compatible HTTP and Dramatiq stay in adapters. Existing stable modules
remain in place unless a concrete leakage above requires change.

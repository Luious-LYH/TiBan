# TiBan v2.0 Platform Core

## Design goal

The v2.0 core is a pragmatic modular monolith. It is one FastAPI deployment
with one relational learning transaction and selectively separated boundaries;
it is not a universal plugin platform or a collection of microservices.

```text
React/Vite
   │ generated OpenAPI client + Tutor SSE
FastAPI routers
   │ transport validation / response projection
Application use cases and bounded Tutor runtime
   │ domain_id + ports + deterministic workflow
PostgreSQL       Qdrant             Redis/Dramatiq
canonical state  retrieval index    durable Factory jobs
```

## Core invariants

| Invariant | Implementation evidence |
| --- | --- |
| One question contract | Pydantic discriminated union for the four MVP types; public and grading projections remain separate. |
| One Practice flow | `PracticeUseCases` delegates to the existing atomic workflow; a domain only scopes data. |
| Deterministic learning side effects | Submit performs `grade → Attempt → mastery → FSRS → memory`; Tutor tools are read-only. |
| One Tutor runtime | Domain policy and allowed namespaces are inputs to the existing bounded `AgentRunner`. |
| One retrieval architecture | PostgreSQL stores source/citation metadata; one Qdrant collection stores vectors, filtered by domain/namespace. |
| One Factory job pipeline | Parse → index → generate → gate → judge → repair → review/publish with durable Redis/Dramatiq state. |
| One Evaluation engine | Medical and General datasets use the same dataset/run/result contracts. |

## Domain scope in relational state

`domain_id` is carried by QuestionBank, Question, PracticeSession,
ReviewCard, LearnerMastery, LearningMemoryItem, SourceDocument and
EvaluationDataset. Mastery and memory identity include the domain, so equal
topic labels in two packs cannot collide. Review cards retain one FSRS model;
the linked question and domain projection provide scope.

The domain selector is a catalog filter. It does not create a second route,
second page tree or second learning implementation. The UI keeps the four
existing primary navigation entries: Overview, Banks, Practice and Evaluation.

## Tutor and retrieval boundary

Tutor receives the current domain, public question projection, selected policy,
relevant memory and approved evidence. Pre-submit permissions continue to
exclude answer keys and grading observations. Medical safety wording comes from
the Medical manifest; General uses its own learning notice. `SourceDocument` →
`DocumentVersion` → `KnowledgeChunk` → Qdrant payload preserves citation
lineage, while namespace metadata blocks cross-domain results.

## Evaluation boundary

Advanced Evaluation is engineering evaluation: fixed tool-selection cases,
memory relevance/leakage checks and scheduling-behavior uplift. It does not
claim clinical validity, educational outcome improvement or model-weight
learning. External model latency, token usage and cost remain `not available`
when the provider does not report them.

## Guardrails and non-goals

`backend/scripts/check_architecture_guard.py` checks application-layer import
direction and required manifest registration in CI. The v2.0 release does not
add Multi-Agent, VLM Tutor productization, public SaaS/auth, Kubernetes,
Terraform, GraphRAG, another vector database/queue or online training.

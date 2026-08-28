# EndoTutor interview Q&A

## Why React/Vite instead of Next.js?

**Decision:** React/Vite. **Reason:** the product is a local runnable workbench
with an independently runnable FastAPI backend, SSE and a small route surface.
**Trade-off:** no server component layer or full-stack routing, but the
generated OpenAPI boundary is explicit. **Evidence:** frontend build and API
drift checks.

## Why a custom Tutor harness instead of LangGraph?

**Decision:** a small custom runtime. **Reason:** Tutor only needs a bounded
permissioned loop, not a general graph framework. **Trade-off:** fewer generic
orchestration features, but max steps, timeout, cancel, retry, ToolRegistry,
receipts and permissions are inspectable. **Evidence:** `agent_runtime.py` and
Tutor tests.

## Why workflow for Factory?

**Decision:** Redis/Dramatiq workflow with role-separated Generator/Judge.
**Reason:** long jobs need durable status and revision lineage. **Trade-off:**
less free-form agent behavior, more deterministic auditability. **Evidence:**
provider acceptance and Factory job artifacts.

## Why PostgreSQL and Qdrant separately?

**Decision:** PostgreSQL is relational state/citation authority; Qdrant is the
retrieval index. **Reason:** learner state and provenance need transactions,
while retrieval needs vector indexing. **Trade-off:** two stores and indexing
coordination. **Evidence:** RAG pipeline and corpus artifact.

## Why is sparse strong, and why did reranker v1 get worse?

Chinese teaching notes have stable terminology and a small corpus, so character
bigram sparse matching is competitive and cheap. The English-trained
cross-encoder added latency and mismatched the Chinese domain; the benchmark
keeps that negative result instead of hiding it. Hybrid remains the selected
product trade-off.

## How was RAG ground truth created?

The benchmark is frozen, split into development and held-out test, and stores
relevant source/chunk IDs and hard negatives. The current artifact is an
engineering candidate set; final named human review is explicitly pending.

## How is EndoBench contamination prevented?

Its registry policy is `benchmark_only`, with `ai_ingestion_allowed=false` and
no Tutor namespace eligibility. Dataset packs set `tutor_indexed=false`; tests
assert zero learner/Tutor/Factory use.

## Why can Study show an answer while Exam cannot?

Study requires explicit direct-answer intent and uses a server-side read-only
permission path. Exam has no answer path before submission. `QuestionPublic`
remains answer-free in both modes.

## Why does the Agent not write learning state?

Grading, immutable Attempt, mastery projection and FSRS scheduling are
deterministic application side effects after submit. This avoids letting a
model invent durable learner state.

## What does FSRS maintain?

`ReviewCard` stores scheduler-derived difficulty, stability, retrievability,
due and state. The fixed Again/Hard/Good/Easy sequence is reproducible and is
compared with the old interval baseline in the artifact.

## How does Factory reduce hallucination?

The source graph supplies evidence and citations; deterministic gates check
shape and safety; an independent Judge evaluates groundedness, answer
consistency, citation and distractors; Repair creates a new revision rather
than overwriting the draft; publish remains explicit.

## What if the Judge is wrong?

It is an assistive gate, not authority. The system keeps the draft, Judge
decision, rubric and revision lineage, and requires review before publish. The
small evaluation set includes failure analysis rather than claiming perfect
accuracy.

## How does BYOK avoid secret leakage?

The key is accepted as a request argument, never persisted, logged, traced or
written to an artifact. UI state is memory-only and responses expose only
`key_persisted=false`.

## Why must candidate evaluation disable fallback?

Fallback would change the model being measured and turn an outage into a false
success. Provider errors and invalid parses remain visible per-case failures.

## How do you handle tens of thousands of questions?

The shipped demo is 3,678 curated questions. A separate PostgreSQL scale
acceptance imported 68,112 valid CMExam rows and exercised bulk import,
filters, pagination, 50-question seeded sessions and navigator state. Larger
production sizing is not claimed.

## What observability is retained?

ToolReceipt, AgentEvent, request/session/run/job/source identifiers, prompt
versions, latency and usage are kept where relevant. Langfuse and OpenTelemetry
are optional/deferred; raw chain-of-thought and secrets are excluded.

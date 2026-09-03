# TiBan interview Q&A

This file is synchronized with the Stage 4 / v1.0 frozen release. Human review
of the RAG and Judge label sets is deferred; answers below describe engineering
evidence, not expert or clinical validation.

## Why React/Vite instead of Next.js?

**Decision:** React/Vite. **Reason:** the product is a local runnable workbench
with an independently runnable FastAPI backend, SSE and a small route surface.
**Trade-off:** no server component layer or full-stack routing, but the
generated OpenAPI boundary is explicit. **Evidence:** frontend build and API
drift checks.

## What does “adaptive learning loop” mean here?

It is not online training of LLM weights. A submit follows deterministic
`grade → immutable Attempt → mastery projection → FSRS ReviewCard`; the next
session builder reads due cards, weak topics and coverage state to select its
questions and returns a short reason. The isolated demo artifact shows a
deliberate Topic A error changing the next session to `weak_topic`.

## Why is Dense the Tutor retrieval default?

The development screen favored sparse, but the frozen held-out verification
favored Dense among the non-reranked paths. Dense is therefore the product
default; sparse, Hybrid RRF and Hybrid + rerank remain benchmark/diagnostic
paths. The reranker is not the default because its tail latency is materially
higher. This is an engineering benchmark decision, not clinical validation.

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
keeps that negative result instead of hiding it. Dense remains the selected
product default after the held-out check, while the other chains remain
available for comparison.

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
## Stage 6：为什么不是全仓 DDD 或微服务？

因为当前产品仍是一个共享 PostgreSQL 事务、单部署的学习平台。Stage 6
只在真实风险处建立边界：Practice 用例、Tutor 依赖适配器和 Factory durable
job；用 architecture guard 与 fake adapter 证明方向，避免把分布式故障引入
尚无独立扩缩容需求的系统。

## Stage 6：如何证明重构没有破坏学习语义？

保留 characterization/regression tests，并验证提交路径仍按
`grade → immutable Attempt → mastery → FSRS → memory` 在单一确定性事务中
完成。LLM 只能读取 Tutor 上下文，不能写入学习事实。

## Stage 6：为什么 Queue 不等于 Job 状态？

Redis/Dramatiq 只负责投递和执行；PostgreSQL `factory_jobs` 保存状态、进度、
幂等键、attempt、heartbeat、错误和取消请求，因此 worker 崩溃后可以识别
stale job 并恢复，而不是永久停留在 running。

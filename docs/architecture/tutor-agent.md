# 智能辅导与 Mentor Agent

## Scope

Practice 内的智能辅导是一个小而受权限控制的 Tutor loop；跨 session 的长期
学习由 Mentor Agent 负责。两者复用底层运行时，但不共享上下文、工具面或对话
生命周期：

```text
ModelGateway -> ToolRegistry -> ToolReceipt -> ModelGateway -> AgentEvent SSE -> UI
```

The only runtime abstractions are `AgentRunner`, `ToolRegistry`, `ModelGateway`, `AgentContext`, `AgentEvent`, and `AgentResult`. `max_steps`, timeout, cancellation, retry, tool permissions, and trace events live inside that boundary.

## Tutor tool permissions

| Tool | Pre-submit | Post-submit | Purpose |
|---|---:|---:|---|
| `retrieve_knowledge` | yes | yes | evidence/source lookup |
| current-session question context | yes | yes | `QuestionPublic` projection plus the bounded session position |
| `get_grading_result` | no | yes | current immutable Attempt only |

Study answer permission is intentionally separate from `QuestionPublic`. When
the learner explicitly asks for the answer in Study mode, the application
permission path may expose a read-only answer explanation; it never mutates
the public question contract. Exam mode has no answer path before submission.
Post-submit Tutor context can use `get_grading_result` for the immutable Attempt.
Tutor does not receive global Learning Memory, unrelated historical Attempts,
FSRS queue, bank progress or Mentor history. These mode and isolation checks are
covered by the Tutor permission regression tests. Long-term state is assembled
by `MentorContextBuilder` and consumed only by Mentor.

No tool writes attempts, mastery, or review schedule. The submit workflow remains deterministic: `grade -> Attempt -> learning projection -> ReviewCard`.

Pre-submit context cannot obtain answer keys, correct option IDs, reference answers, hidden rubrics, or benchmark targets. This is enforced by tool availability, not by a refusal prompt alone.

## Continuous chat, events and safety

The desktop practice workspace keeps Tutor as a persistent right-side chat. The
client sends only the short conversation projection belonging to the current
Tutor thread; a new Practice session or a later resume creates a fresh thread.
The mobile workspace deliberately converts this to an explicit sheet. There is
no separate “hint response” surface. A visible reasoning disclosure is a short
model/application summary only; raw hidden chain-of-thought is never persisted
or shown.

SSE emits `message_start`, `reasoning`, `token`, `tool_start`, `tool_end`, `source`, `message_end`, and `error`. Tool status in the UI is rendered only when these events arrive. The readable disclosure is a ToolReceipt/evidence summary (what public context and sources were accessed), not raw chain-of-thought. Traces record tool receipts and source locations, never raw chain-of-thought.

The checked-in anonymous examples are in [`artifacts/agent/tutor-v1`](../../artifacts/agent/tutor-v1/). The adversarial trace is a recovery case: the request is answered within the public pre-submit boundary, without exposing grading data.

## Reflection and long-term memory

Attempt, Mastery and FSRS state are committed synchronously by the Practice
workflow. A completed or abandoned session marks a reflection checkpoint and
queues `memory_reflection` on the shared Dramatiq worker; the worker validates
the bounded candidate evidence before writing Learning Memory in PostgreSQL.
Repeated triggers use the session reflection version as an idempotency key, so
browser-close signals are only best-effort activity hints.

Learning Memory is structured canonical data. `SemanticMemoryService` derives a
bounded Top-K recall index in `tiban_learning_memory_v32`; the Knowledge index
is separate (`tiban_knowledge_v32`). A Qdrant outage or rebuild can reduce
recall, but cannot remove the canonical attempt, transcript or memory text.

The global Mentor path is `/api/v3/mentor`. It owns persistent conversations
and may read recent Attempts, Mastery, FSRS, bank progress, validated semantic
memories and optional governed Knowledge evidence. Tutor never reloads those
cross-session sources.

## Provider acceptance

`LocalPolicyModelGateway` is an explicitly labelled no-secret development adapter that proves loop structure and permission tests. It is not external-model evidence. `OpenAICompatibleTutorGateway` is implemented behind the explicit `TUTOR_PROVIDER_ENABLED=true` opt-in: it first asks the configured OpenAI-compatible model for a JSON tool plan limited to the current permission set, executes those tools, then asks for a final reply using only the resulting observations. It never receives write tools or asks for hidden reasoning. The local OpenAI-compatible acceptance artifact records 13/13 scenarios passed, including 12 model-backed cases, cancellation and retry; no provider secret is persisted.

# Tutor Agent v1

## Scope

Tutor v1 is a deliberately small, permissioned loop rather than a general agent framework:

```text
ModelGateway -> ToolRegistry -> ToolReceipt -> ModelGateway -> AgentEvent SSE -> UI
```

The only runtime abstractions are `AgentRunner`, `ToolRegistry`, `ModelGateway`, `AgentContext`, `AgentEvent`, and `AgentResult`. `max_steps`, timeout, cancellation, retry, tool permissions, and trace events live inside that boundary.

## Tool permissions

| Tool | Pre-submit | Post-submit | Purpose |
|---|---:|---:|---|
| `get_question_context` | yes | yes | `QuestionPublic` projection only |
| `retrieve_knowledge` | yes | yes | evidence/source lookup |
| `get_learning_profile` | yes | yes | read-only learner overview |
| `get_grading_result` | no | yes | current immutable Attempt only |

Study answer permission is intentionally separate from `QuestionPublic`. When
the learner explicitly asks for the answer in Study mode, the application
permission path may expose a read-only answer explanation; it never mutates
the public question contract. Exam mode has no answer path before submission.
Post-submit Tutor context can use `get_grading_result` for the immutable
Attempt. These mode checks are covered by the Tutor permission regression
tests.

No tool writes attempts, mastery, or review schedule. The submit workflow remains deterministic: `grade -> Attempt -> learning projection -> ReviewCard`.

Pre-submit context cannot obtain answer keys, correct option IDs, reference answers, hidden rubrics, or benchmark targets. This is enforced by tool availability, not by a refusal prompt alone.

## Continuous chat, events and safety

The desktop practice workspace keeps Tutor as a persistent right-side chat. The client sends the short, last-turn conversation projection with each request; it then appends user/assistant turns and token deltas in place. The mobile workspace deliberately converts this to an explicit sheet. There is no separate “hint response” surface. A visible reasoning disclosure is a short model/application summary only; raw hidden chain-of-thought is never persisted or shown.

SSE emits `message_start`, `reasoning`, `token`, `tool_start`, `tool_end`, `source`, `message_end`, and `error`. Tool status in the UI is rendered only when these events arrive. The readable disclosure is a ToolReceipt/evidence summary (what public context and sources were accessed), not raw chain-of-thought. Traces record tool receipts and source locations, never raw chain-of-thought.

The checked-in anonymous examples are in [`artifacts/agent/tutor-v1`](../../artifacts/agent/tutor-v1/). The adversarial trace is a recovery case: the request is answered within the public pre-submit boundary, without exposing grading data.

## Provider acceptance

`LocalPolicyModelGateway` is an explicitly labelled no-secret development adapter that proves loop structure and permission tests. It is not external-model evidence. `OpenAICompatibleTutorGateway` is implemented behind the explicit `TUTOR_PROVIDER_ENABLED=true` opt-in: it first asks the configured OpenAI-compatible model for a JSON tool plan limited to the current permission set, executes those tools, then asks for a final reply using only the resulting observations. It never receives write tools or asks for hidden reasoning. The local OpenAI-compatible acceptance artifact records 13/13 scenarios passed, including 12 model-backed cases, cancellation and retry; no provider secret is persisted.

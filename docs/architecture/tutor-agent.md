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

No tool writes attempts, mastery, or review schedule. The submit workflow remains deterministic: `grade -> Attempt -> learning projection -> ReviewCard`.

Pre-submit context cannot obtain answer keys, correct option IDs, reference answers, hidden rubrics, or benchmark targets. This is enforced by tool availability, not by a refusal prompt alone.

## Events and safety

SSE emits only `message_start`, `token`, `tool_start`, `tool_end`, `source`, `message_end`, and `error`. Tool status in the UI is rendered only when these events arrive. Traces record tool receipts and source locations, never raw chain-of-thought.

The checked-in anonymous examples are in [`artifacts/agent/tutor-v1`](../../artifacts/agent/tutor-v1/). The adversarial trace is a recovery case: the request is answered within the public pre-submit boundary, without exposing grading data.

## Provider acceptance

`LocalPolicyModelGateway` is an explicitly labelled no-secret development adapter that proves loop structure and permission tests. It is not external-model evidence. An OpenAI-compatible provider acceptance run remains pending an operator-supplied local environment variable and is not claimed as completed in Stage 2 evidence.

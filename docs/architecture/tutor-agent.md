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

## Continuous chat, events and safety

The desktop practice workspace keeps Tutor as a persistent right-side chat. The client sends the short, last-turn conversation projection with each request; it then appends user/assistant turns and token deltas in place. The mobile workspace deliberately converts this to an explicit sheet. There is no separate “hint response” surface.

SSE emits only `message_start`, `token`, `tool_start`, `tool_end`, `source`, `message_end`, and `error`. Tool status in the UI is rendered only when these events arrive. The readable disclosure is a ToolReceipt/evidence summary (what public context and sources were accessed), not raw chain-of-thought. Traces record tool receipts and source locations, never raw chain-of-thought.

The checked-in anonymous examples are in [`artifacts/agent/tutor-v1`](../../artifacts/agent/tutor-v1/). The adversarial trace is a recovery case: the request is answered within the public pre-submit boundary, without exposing grading data.

## Provider acceptance

`LocalPolicyModelGateway` is an explicitly labelled no-secret development adapter that proves loop structure and permission tests. It is not external-model evidence. `OpenAICompatibleTutorGateway` is implemented behind the explicit `TUTOR_PROVIDER_ENABLED=true` opt-in: it first asks the configured OpenAI-compatible model for a JSON tool plan limited to the current permission set, executes those tools, then asks for a final reply using only the resulting observations. It never receives write tools or asks for hidden reasoning. No provider request is possible without that opt-in plus a configured local provider; external-provider acceptance remains pending and is not claimed as completed in Stage 2 evidence.

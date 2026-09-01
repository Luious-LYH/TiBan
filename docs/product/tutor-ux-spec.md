# Tutor product UX specification

## Interaction model

Tutor is a continuous chat beside the active question, not a collection of hint buttons. The current question is default context, but the learner can ask related or unrelated study questions. The composer stays available for follow-up turns and the conversation history scrolls independently from the question workspace.

The empty state is deliberately small:

```text
Tutor
有哪里不懂，直接问我。
```

At most three suggestion chips are shown before the first message. After the first message they collapse. The ordinary surface does not expose permissions, SSE, schema, RAG score, ToolReceipt or defensive policy text.

## Behavior by mode

- Study / Tutor: if the learner explicitly asks for the answer, Tutor may provide the answer and explanation through a server-side private answer path. If the learner asks for a hint, it gives a hint first. Retrieval is selective rather than forced on every message.
- Exam: Tutor is disabled or limited and cannot reveal current-question answers before the block ends.
- Review: Tutor can explain the submitted result, official explanation and allowed knowledge evidence.

## Message parts

The body is the answer. Optional high-level supporting parts are collapsed by default:

- `思考了 N 秒`: only provider-supplied or system-generated reasoning summary, never raw hidden chain-of-thought;
- `参考资料 N`: title, page/section and short snippet;
- tool activity: visible only in a developer detail surface and derived from real AgentEvents.

When no real provider is configured, the product says `尚未配置 AI 模型`; a deterministic adapter is never presented as a live model response. The local OpenAI-compatible provider acceptance is recorded separately in [`provider-acceptance-v1.json`](../../artifacts/agent/tutor-v1/provider-acceptance-v1.json) and contains no secret or raw chain-of-thought.

## Runtime contract

Tutor v1 is bounded to `AgentRunner`, `ToolRegistry`, `ModelGateway`, `AgentContext`, `AgentEvent` and `AgentResult`, with max steps, timeout, cancellation, retry, permission checks and trace. Pre-submit context excludes answer keys, correct option IDs, reference answers, hidden rubrics and benchmark targets. Deterministic application workflow owns grading, attempt, mastery and review scheduling.

## Evidence

- [Current v2 Tutor and practice captures](../portfolio/evidence/current-v2/index.md)
- [Tutor architecture](../architecture/tutor-agent.md)
- [anonymous trace](../../artifacts/agent/tutor-v1/anonymous-demo-trace.json)

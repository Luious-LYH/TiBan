# TiBan V3.2 — Agent Boundary, Memory & RAG Upgrade Master Prompt

> Target branch: `refactor/v3-tiban-agent-experience`
>
> Goal: complete V3.2 as **one coherent release**. Do not split this work into “three rounds/phases” in product scope. You may execute in dependency order internally, but every requirement below belongs to V3.2 and must be completed, tested, documented, and kept consistent.
>
> This work is **project-code refactoring and product behavior refinement only**. Do **not** deploy to any server in this task. Deployment will be handled later after local/LAN-server validation.

---

## 0. First principle: read the real code before modifying anything

Before editing:

1. Read repository-level `AGENTS.md` and any local instructions.
2. Inspect the real current call paths, DB models, API contracts, generated frontend client, tests, and existing V3/V3.1 docs.
3. In particular, inspect at least:
   - `backend/app/services/agent_runtime.py`
   - `backend/app/services/coach_agent_service.py`
   - `backend/app/routers/coach.py`
   - `backend/app/services/learning_memory_service.py`
   - `backend/app/services/rag_service.py`
   - `backend/app/services/knowledge_service.py`
   - `backend/app/adapters/tutor_dependencies.py`
   - Tutor gateway/provider related code
   - existing Tutor/Practice routers and session models
   - Dramatiq/Redis worker code
   - `backend/app/db/models.py`
   - `backend/app/agents/prompts/`
   - `frontend/src/pages/practice/`
   - `frontend/src/pages/coach/`
   - `frontend/src/pages/settings/`
   - `frontend/src/pages/knowledge/`
   - `frontend/src/app/router.tsx`
   - navigation/AppShell files
   - OpenAPI-generated API flow
   - V3.1 tests and architecture docs.
4. Search the whole repository for `coach`, `Coach`, `tutor`, `Tutor`, `learning_memory`, `FastEmbed`, `bge-small`, `embedding`, `rerank`, `practice session`, `conversation`.
5. Do not assume a file named in this prompt still exists exactly as named. Reuse/refactor the real implementation rather than creating duplicate architectures.

Before changing code, produce a short internal inventory of:
- current Tutor request path;
- current Coach/long-term agent path;
- current practice session lifecycle;
- current Learning Memory write/retrieval path;
- current Knowledge indexing path;
- current Embedding/Reranker implementation;
- current background Worker actors/jobs;
- any obsolete/duplicate Tutor paths.

Then implement V3.2.

---

# 1. V3.2 product definition

TiBan must clearly expose **two different learning agents** with different lifecycles and responsibilities.

## 1.1 Tutor Agent — current practice-session assistant

`Tutor Agent` means the assistant inside the Practice workspace/right-side tutoring panel.

It is **not** the global long-term learning agent.

Tutor is scoped to the **current practice session**.

Tutor should know only bounded temporary context such as:
- current `practice_session_id`;
- the questions selected for this current practice session;
- current question;
- current Study / Exam mode;
- current answer/submission state;
- current immutable grading result after submission;
- current-session progress;
- Tutor conversation turns from the current active Tutor thread/session;
- governed Knowledge RAG evidence when required.

Tutor may call tools such as:
- current question context;
- current grading result after submit;
- answer explanation when permissions allow;
- governed Knowledge RAG/search;
- other strictly current-session tools that are genuinely necessary.

Tutor **must not behave like the Mentor**.

Do not inject broad cross-session learner history into Tutor by default.

Remove or stop using Tutor tools that expose broad cross-session state such as:
- global Learning Memory;
- previous unrelated practice sessions;
- long-term recent mistakes outside the active practice session;
- overall bank progress unless the current session explicitly needs it;
- global review plan / FSRS queue;
- persistent Mentor conversation history.

If the current implementation exposes `get_learning_profile`, Learning Memory, historical attempts or similar global learning-history tools to Tutor, audit them and narrow/remove them from the Tutor surface.

Tutor should answer “current practice assistance” questions.

For questions such as:
- “我最近整体哪里最弱？”
- “我今天应该复习什么？”
- “你还记得我上次哪里总错吗？”

Tutor should not silently become the long-term agent. It may briefly tell the user that long-term learning analysis belongs to **Mentor Agent**.

### Tutor context lifecycle

A Tutor context persists only for the current selected practice batch/session.

```text
Bank A
choose 20 questions
        ↓
Practice Session P1
        ↓
Tutor Thread T1
        ↓
Question 1 → Question 2 → ... → Question 20
```

Within P1, Tutor may preserve the current-session conversation context while moving between questions.

However:

```text
finish P1
or choose another bank
or choose a new question count
or start a new review/practice session
        ↓
new Practice Session P2
        ↓
new Tutor context
```

No old Tutor chat should automatically enter the new context.

Raw Tutor transcript may be persisted for audit/reflection, but it must **not** become cross-session Tutor context.

---

## 1.2 Mentor Agent — persistent global learning mentor

Rename the current long-term `Coach Agent` to:

> **Mentor Agent**

Chinese UI may continue to use a learner-friendly label such as `带教 Agent`, but English/code naming must use `Mentor`, not `Coach`.

Mentor is the left-navigation/global learning agent.

Mentor owns the cross-session experience:
- persistent conversations;
- learning summary;
- mastery;
- FSRS/review queue;
- recent attempts;
- bank progress;
- Learning Memory;
- semantic long-term memory retrieval;
- session-level learning summaries;
- governed Knowledge RAG when useful;
- long-term study planning and reflective guidance.

Mentor is where the user should feel:

> “这个 Agent 认识我过去学过什么、哪里反复出错、下一步应该练什么。”

Mentor should remain evidence-grounded and read-mostly.

Do **not** give Mentor arbitrary mutation tools for Attempt/Mastery/FSRS.

Canonical learning writes remain deterministic application workflows.

Long-term memory writeback is handled by the dedicated Reflection pipeline defined later.

---

# 2. Rename Coach → Mentor completely and consistently

The current repository has a persistent `/coach` Agent path and `coach_agent_service.py` / Coach DTOs / `agent_profile="coach"` / `phase="coach"` etc.

V3.2 must cleanly rename the long-term Agent from `Coach` to `Mentor`.

Target naming should resemble:

```text
backend/app/routers/mentor.py
backend/app/services/mentor_agent_service.py
backend/app/agents/prompts/mentor_agent.md

MentorGateway
MentorAgentService
MentorMessagePublic
MentorConversationPublic
mentor_agent_service
mentor_runner

phase="mentor"
agent_profile="mentor"
```

Frontend:

```text
frontend/src/pages/mentor/MentorPage.tsx
route: /mentor
```

API:

```text
/api/v3/mentor/...
```

Update route tags, frontend navigation, generated OpenAPI client, tests, docs, README Chinese + English, architecture documents, fixtures and internal trace/activity labels where appropriate.

Do not hand-edit `frontend/src/api/generated.ts`; regenerate from OpenAPI using the repository’s existing script.

### Existing data migration

Do not simply delete existing persisted Coach conversations.

If current local databases can contain `agent_profile = "coach"`, provide a safe migration/compatibility path to `mentor`.

Old conversation IDs may remain stable; new IDs should use Mentor-oriented prefixes if IDs contain Agent naming.

After V3.2, normal active code should not continue to create new `coach` data.

A repository-wide grep should leave `Coach/coach` only where intentionally documenting a migration/history compatibility boundary.

---

# 3. Practice session lifecycle must become explicit

The Tutor behavior depends on a real, explicit Practice Session lifecycle.

Audit the current Practice models/services first and reuse them if they already provide these concepts.

The desired logical state is:

```text
PracticeSession
- session_id
- learner_id
- bank_id / source type
- selected question IDs
- requested question count
- mode
- status: active | completed | abandoned
- current_position
- created_at
- updated_at
- completed_at
- last_activity_at
```

Do not create duplicate state if equivalent fields already exist.

## 3.1 Starting from a bank

When the user explicitly selects a bank, mode and question count/filter and starts practice:

```text
create a new Practice Session
+
create a new Tutor context/thread
```

If another unfinished Practice Session exists, close/abandon it according to existing product semantics and enqueue Memory Reflection if it contains unreflected learning events.

## 3.2 Entering Practice directly from the left navigation

If the user opens TiBan and directly clicks the left navigation `Practice/刷题` entry:
- query whether there is an unfinished resumable Practice Session;
- if none exists → navigate to the bank/question-bank selection page;
- if one exists → show a small modal:

```text
检测到上次未完成的练习

[继续上次练习]
[重新选择题库]
```

If user chooses **继续上次练习**:
- restore practice progress, current question position and existing submitted-answer state;
- **do not automatically restore old Tutor conversational context**;
- start a fresh Tutor thread/context for this browser usage/resume;
- the previous Tutor transcript remains historical evidence for Reflection/Mentor, not active Tutor prompt context.

If user chooses **重新选择题库 / 否**:
- mark/dismiss the prior active session as abandoned or otherwise prevent the same resume prompt from appearing forever;
- run/enqueue Reflection if appropriate;
- navigate to the question-bank selection page.

Important distinction:

> Practice progress can resume, but Tutor conversational context does not need to persist across a later visit.

---

# 4. Memory Reflection belongs to Mentor, not Tutor

V3.2 must add a controlled **Memory Reflection** pipeline inspired by the useful parts of TechSpar’s long-term learning loop, while keeping TiBan’s evidence-backed learning state.

Do not turn Tutor into a persistent-memory agent.

Tutor produces session events/transcript.

Reflection distills durable learning insights.

Mentor consumes durable learning memory later.

```text
Practice/Tutor Session
        ↓
Attempts + grading + session transcript/events
        ↓
Memory Reflection
        ↓
validated Learning Memory
        ↓
PostgreSQL canonical memory
        ↓
semantic memory index
        ↓
Mentor retrieval
```

## 4.1 Reflection trigger conditions

Reflection should be eligible when:
1. a practice set/session is completed;
2. user starts a different bank/new question count/new practice session;
3. user intentionally leaves/abandons the current practice;
4. Tutor conversation/session ends after meaningful interaction;
5. a meaningful misconception/confusion signal appears;
6. structured learning state materially changes;
7. an unfinished session becomes inactive for a configured amount of time.

Do not run an expensive LLM Reflection on every tiny event.

Use a dirty/checkpoint mechanism so a session is reflected only when there is new meaningful evidence.

## 4.2 Do not depend on browser-close networking

This is a hard requirement.

Never design:

```text
browser closes
→ call LLM
→ only then save learning state
```

as the only safety mechanism.

A browser/tab can be killed without finishing async requests.

### Canonical facts are saved immediately

Attempts, answer state, progress, Tutor messages/events and session metadata must already be persisted during normal interaction.

Closing the page must not be capable of deleting those facts.

### Browser close is only a best-effort end signal

Use browser lifecycle signals such as `pagehide`, `visibilitychange`, and optionally `navigator.sendBeacon` or `fetch(..., {keepalive: true})` to mark the session as inactive/closing.

Do not rely on this signal for correctness.

### Server-side fallback

Persist `last_activity_at`, reflection dirty/version state and last reflected event/attempt marker.

If a session remains inactive beyond a threshold, backend/worker can enqueue a reflection job.

Reflection must be idempotent.

A duplicate close event or retry must not create duplicate memories.

Possible fields:

```text
reflection_status
reflection_version
last_reflected_event_id / last_reflected_attempt_at
reflection_dirty
last_reflected_at
```

Reuse existing models where possible.

---

# 5. Reflection output: LLM summarizes, deterministic code verifies

TiBan already has high-value objective evidence:
- Attempt;
- correct/incorrect;
- question/topic;
- Mastery;
- FSRS;
- explicit user confusion;
- existing Learning Memory evidence refs.

Preserve that advantage.

Reflection should not be allowed to freely invent a user profile.

Feed bounded inputs such as:
- current practice-session attempts;
- question/topic/concept metadata;
- grading outcome;
- relevant Tutor transcript from this session;
- existing active memories likely to overlap;
- optional session summary.

Ask the LLM for typed/JSON candidate actions, for example:

```json
{
  "action": "ADD",
  "kind": "misconception",
  "summary": "学习者仍容易混淆 NICE 2 与 NICE 3 的深部浸润判断。",
  "topic_keys": ["NICE"],
  "concept_keys": ["NICE 2", "NICE 3", "深部浸润"],
  "confidence": 0.86,
  "evidence_refs": ["attempt_x", "attempt_y"]
}
```

Allowed actions should be bounded, e.g. `ADD`, `UPDATE`, `RESOLVE`, `NOOP`.

Then deterministic application code validates:
- referenced attempts/messages/session really exist;
- refs belong to the learner/session;
- evidence actually supports the candidate;
- confidence and enums are valid;
- duplicate/near-duplicate memory handling;
- medical safety boundaries;
- no diagnosis/treatment inference;
- maximum memory size/count/lifecycle rules.

Principle:

> LLM performs synthesis; application code owns truth and persistence.

---

# 6. Learning Memory V2: keep structured memory, add semantic recall

Do **not** replace the current PostgreSQL Learning Memory system.

It is valuable because it is structured, traceable, evidence-backed, compatible with Attempt/Mastery/FSRS and independent from an embedding model.

PostgreSQL remains the canonical store.

Example canonical record:

```text
memory_id
learner_id
kind
summary
topic_keys
concept_keys
confidence
status
evidence_refs
first_seen_at
last_seen_at
version
...
```

## 6.1 Add semantic indexing as a derived index

For active/retrievable memories:

```text
LearningMemory.summary
+ useful normalized topic/concept text
        ↓
EmbeddingProvider
        ↓
BAAI/bge-m3
        ↓
Qdrant memory vector index
```

Qdrant is derived/rebuildable. It is not the canonical source of the memory.

When a memory is added/updated/resolved:
- update canonical PostgreSQL first;
- then upsert/remove/update the semantic memory index.

Do not embed every raw chat message as long-term memory.

Only distilled/validated memory records become semantic memories.

## 6.2 Mentor memory retrieval

Mentor retrieval should combine:
- learner/domain filter;
- active status;
- semantic similarity;
- topic/concept overlap;
- confidence;
- recency/lifecycle relevance.

Return a small bounded set such as Top 3–5 relevant memories.

Do not dump the learner’s entire history into the prompt.

---

# 7. Mentor Context Builder

Create or consolidate a clear bounded context-construction layer for Mentor.

Mentor may combine:

```text
current user question
+
compact learning summary
+
Mastery / weak areas
+
FSRS due review summary
+
recent attempts
+
recent practice-session summaries
+
semantic Learning Memory Top-K
+
bank progress when relevant
+
Knowledge RAG Top-K when relevant
+
recent Mentor conversation turns
```

The builder should make it obvious which context is deterministic learning state, long-term memory, knowledge evidence and conversation context.

Avoid scattered prompt construction across multiple services.

Do not send huge raw tables or full historical transcripts to the model.

---

# 8. Tutor Context Builder and strict Tutor/Mentor boundary

Tutor needs its own narrower builder.

Expected Tutor context:

```text
practice_session_id
current selected-question batch
current question
current answer/submission state
current immutable grading result after submission
current session progress
recent Tutor turns from the current Tutor thread
optional governed Knowledge RAG evidence
Study / Exam permission state
```

Not expected by default:

```text
global Learning Memory
global FSRS plan
unrelated historical attempts
previous Tutor sessions
Mentor conversation
whole learner profile
```

Keep existing Study/Exam safety boundaries.

The V3.1 invariant must remain true:

> objective question submit itself never waits for LLM/RAG/Embedding.

Do not move grading into the Agent path.

The deterministic flow remains:

```text
grade
→ Attempt
→ mastery projection
→ FSRS/Review state
```

Tutor reads the resulting facts when allowed.

---

# 9. Default Embedding: SiliconFlow API + BAAI/bge-m3

Replace the current primary hard-binding to local FastEmbed `BAAI/bge-small-zh-v1.5`.

V3.2 online/demo default:

```text
Provider: SiliconFlow / OpenAI-compatible embeddings API
Model: BAAI/bge-m3
```

Implement a provider abstraction instead of hard-coding one library.

Suggested interface shape:

```python
class EmbeddingProvider(Protocol):
    model_id: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
    def dimension(self) -> int: ...
```

Use the project’s conventions rather than forcing this exact syntax.

At minimum implement:

1. `OpenAICompatibleEmbeddingProvider`
   - default for TiBan hosted/demo mode;
   - configurable Base URL;
   - API Key from backend/server settings, never browser plaintext persistence;
   - model default `BAAI/bge-m3`.

2. local fallback provider
   - preserve a local/self-host capability;
   - may reuse FastEmbed or another existing local implementation;
   - lazy-load local model;
   - do not prewarm it by default unless explicitly configured.

The online/demo instance should work out of the box with the platform’s configured SiliconFlow key.

---

# 10. Embedding settings: learn from TechSpar, but do not copy its multi-user assumption blindly

TechSpar allows API/local Embedding configuration and treats vector indexes as rebuildable derived data.

Adopt that provider flexibility, but preserve TiBan’s architecture.

TiBan currently has shared knowledge/state and is not yet a fully isolated per-user hosted vector platform.

Therefore V3.2 should distinguish:

### Hosted/demo instance
- platform/default Embedding is `SiliconFlow + BAAI/bge-m3`;
- ordinary public learners must not be able to arbitrarily change the global active Embedding model and invalidate everyone’s shared index;
- model-changing controls are instance-owner/admin-level configuration.

### Self-host/local mode
Expose the flexible setup:

```text
Embedding mode:
- API
- Local

API:
- Base URL
- API Key
- Model

Local:
- supported local model ID/path
```

The UI may explain that custom Embedding is intended for self-host/instance-owner use.

Do **not** implement expensive per-user vector-index duplication solely to imitate TechSpar in V3.2.

---

# 11. One active Embedding index, no permanent per-model copies

V3.2 should maintain one active vector representation per index type.

Do not permanently keep multiple model vectors for the same canonical data.

Canonical data is PostgreSQL/files. Vectors are rebuildable derived indexes.

Store enough index metadata to detect mismatch:

```text
provider
model_id
vector_dimension
index_version
status: ready | stale | rebuilding | failed
indexed_at
```

When the active model/provider changes:

```text
mark index stale
        ↓
rebuild from canonical PostgreSQL text
        ↓
recreate/reset Qdrant collection if dimension/model changed
        ↓
upsert new vectors
        ↓
mark ready
```

Do not try to query a collection indexed with model A using query vectors from model B.

If dimensions differ, recreation is mandatory.

The old vectors may be overwritten/removed after the new rebuild; V3.2 does not need blue/green multi-model indexes.

---

# 12. Reranker provider

Audit the current local CrossEncoder/reranker path.

For online/demo mode, prefer moving reranking inference out of the application server too.

Default target:

```text
SiliconFlow
BAAI/bge-reranker-v2-m3
```

Create a small provider boundary analogous to Embedding where reasonable.

Desired RAG chain:

```text
Query
  ↓
BAAI/bge-m3 API
  ↓
Qdrant hybrid retrieval
  ↓
candidate Top-K
  ↓
BAAI/bge-reranker-v2-m3 API
  ↓
bounded evidence Top-K
  ↓
Tutor/Mentor
```

Preserve relevance/evidence gating, valid 0-hit behavior, provenance/citation rules, no fake citations and Study/Exam answer boundaries.

Do not remove sparse/hybrid retrieval if it is currently useful.

---

# 13. Knowledge indexing/reindex should become a background Job

Current Question Factory already has Redis + Dramatiq Worker.

V3.2 should unify heavy indexing behavior.

Knowledge upload flow should become logically:

```text
upload/save source
        ↓
create Index Job
        ↓
Redis/Dramatiq
        ↓
Worker
        ↓
parse
→ chunk
→ BGE-M3 API embedding
→ Qdrant index
→ ready
```

The user still waits until indexing is Ready before the new source can be retrieved, but the HTTP request/UI should not need to remain blocked for the whole compute chain.

Expose real progress/status such as:

```text
上传完成
解析文档
文本切分
生成向量
写入索引
完成
```

Reuse the current Worker/Job conventions instead of inventing a second queue framework.

The same worker infrastructure may host different actors/job types:
- Question Factory;
- Knowledge indexing/reindex;
- Memory Reflection.

Keep job concurrency bounded in code/configuration, but deployment tuning is out of scope for this task.

---

# 14. Memory Reflection should use the background Worker

Reflection is a good asynchronous job.

Do not make Practice navigation wait for the LLM reflection.

```text
user completes/leaves practice
        ↓
canonical state already committed
        ↓
enqueue memory_reflection job
        ↓
UI can continue immediately
        ↓
Worker reflects + validates + writes memory
```

This also solves browser-close reliability.

If Redis/worker is temporarily unavailable:
- canonical Attempt/session/Tutor transcript data must remain intact;
- Reflection may be retried/reconciled later;
- user learning facts are not lost.

---

# 15. Subtle auto-save UX

Add a small, low-noise auto-save status in Practice.

Do not create a large modal/toast after every answer.

Possible states:

```text
spinner  正在保存学习进度…
check    学习进度已保存
spinner  正在整理本轮学习记录…
check    学习记忆已更新
```

Keep it visually secondary.

Distinguish ordinary deterministic state persistence from Mentor Memory Reflection completion.

Do not falsely show `学习记忆已更新` if no memory was actually added/updated/resolved.

If Reflection result is `NOOP`, normal progress may simply remain `已保存`.

---

# 16. Tutor transcript persistence vs Tutor context

These must not be confused.

V3.2 may persist Tutor messages/session transcripts because they are useful for session review, Memory Reflection evidence, debugging/audit and optional later learner-facing history.

But persisted transcript does **not** imply cross-session Tutor memory.

Active Tutor prompt context must be bounded by the current Tutor thread.

When a new practice session begins, or a previous practice session is resumed on a later visit according to the product rule above, create a fresh Tutor context/thread.

Reflection may read the old transcript.

Mentor may receive the distilled memory.

Tutor does not reload it.

---

# 17. Mentor persistent conversation remains persistent

Unlike Tutor, Mentor conversations are intentionally cross-session.

Keep/refine the current persisted Agent conversation/message model behavior for Mentor.

Mentor can retain recent conversation turns and combine them with long-term learning state/memory.

Do not confuse `Mentor conversation persistence` with `Learning Memory`.

Conversation history is conversational context.

Learning Memory is distilled evidence-backed long-term learner state.

Both may coexist.

---

# 18. Audit and unify Tutor runtime call paths

V3.2 must inspect all Tutor-related endpoints/services and ensure there is only one authoritative active Tutor behavior.

Current project already has the controlled Agent runtime:

```text
AgentRunner
ToolRegistry
ModelGateway
AgentContext
AgentEvent/SSE
```

Preserve this architecture.

Do not add LangGraph/multi-agent orchestration just because TechSpar has different internals.

If an older `tutor_orchestrator` or alternate direct-prompt path is still live:
- identify every caller;
- migrate real frontend/API call paths to the authoritative Tutor runtime;
- deprecate/remove compatibility code where safe;
- do not maintain two Tutors with different RAG/permission/memory behavior.

Tutor and Mentor may reuse the same low-level Agent runtime abstractions, but must have separate prompts, profiles/phases, tool surfaces, context builders and conversation lifecycle.

---

# 19. Do not turn every cheap context field into an LLM tool-selection call

Keep Agent behavior practical for online experience.

For Tutor and Mentor, distinguish cheap bounded context that can be assembled deterministically from truly dynamic tools.

Examples of deterministic context:
- current session identifiers/progress;
- compact learning summary;
- bounded memory Top-K already retrieved;
- recent Mentor turns.

Examples of dynamic tools:
- Knowledge RAG;
- grading-result lookup under permission boundary;
- optional detailed review/attempt lookups.

Avoid unnecessary extra LLM calls solely to decide whether to read a tiny mandatory context field.

Preserve tool receipts/auditability where useful.

---

# 20. Canonical data vs derived vector indexes

Make this architecture explicit in code/docs.

```text
PostgreSQL / original files
=
canonical application, learning and knowledge data

Qdrant
=
rebuildable semantic indexes

Redis
=
runtime job coordination / queue

Tutor transcript
=
session evidence, not cross-session Tutor memory

Learning Memory
=
canonical structured long-term learner memory in PostgreSQL
+
derived semantic memory index in Qdrant
```

A Qdrant collection loss/rebuild must not erase the original Learning Memory or Knowledge chunk text.

---

# 21. Important existing TiBan behaviors that must not regress

Preserve all of these unless a real current test/code proves otherwise:

1. Objective answer submit does not wait for LLM/RAG/Embedding.
2. Attempt → Mastery → FSRS/review state remains deterministic.
3. Tutor respects pre-submit/post-submit permissions.
4. Exam mode cannot leak answers before submission.
5. Study answer access remains a separate permission path.
6. Knowledge RAG accepts true 0-hit.
7. No fake Citation when retrieval has no evidence.
8. Citation/source provenance remains governed.
9. No raw hidden chain-of-thought is persisted or displayed.
10. EndoBench/evaluation-only data does not leak into Tutor/Mentor learning paths.
11. Medical outputs remain educational/physician-review oriented and must not invent diagnosis/treatment evidence.
12. Existing Question Factory Gate/Judge/Repair behavior remains intact.
13. Existing real Knowledge source/version/chunk canonical data remains intact.

---

# 22. Settings UX for V3.2

Update the Embedding settings area to reflect the real implementation.

Recommended copy/behavior:

```text
Embedding

在线实例默认
Provider: SiliconFlow
Model: BAAI/bge-m3
Status: Ready

高级配置（实例所有者 / 自部署）
Mode:
- API
- Local

API:
Base URL
API Key
Model

Local:
Model ID / local path
```

Show a clear warning:

> 更换 Embedding 模型会使当前向量索引失效，需要重新构建知识库与长期记忆语义索引。原始资料、作答记录、FSRS 和 Learning Memory 原文不会被删除。

Do not say that Mastery/FSRS/Attempt themselves are “memory vectors”.

When model config changes:
- do not silently query stale vectors;
- surface `stale/rebuilding/ready/failed`;
- provide real rebuild action/progress.

---

# 23. Learning Memory index and Knowledge index should be separate logical indexes

Use separate Qdrant collections/namespaces or equivalent strong separation for:

```text
knowledge chunks
learning memories
```

They have different payload schemas, retrieval policies, lifecycle, top-K rules and governance.

They may use the same active EmbeddingProvider/model.

Changing the active model invalidates/rebuilds both derived semantic indexes.

Do not mix Knowledge chunks and learner memories into one untyped collection.

---

# 24. Suggested Mentor retrieval flow

```text
Mentor user question
        ↓
build compact deterministic learner state
        ↓
semantic Learning Memory retrieval
        ↓
optional tools:
  recent attempts
  review queue
  bank progress
  Knowledge RAG
        ↓
Mentor Context
        ↓
LLM
        ↓
persistent Mentor reply
```

Examples:
- “我今天先复习什么？” → FSRS + recent attempts + weak areas + relevant Learning Memory.
- “我为什么总分不清 NICE 2 和 3？” → semantic Learning Memory + historical attempts + optional Knowledge RAG.
- “根据我上传的指南解释这个概念” → Knowledge RAG.

Mentor must not invent history when no evidence exists.

---

# 25. Suggested Tutor flow

```text
Practice Session
        ↓
current question/context
        ↓
Tutor user message
        ↓
Tutor bounded context
        ↓
optional governed tool:
Knowledge RAG / grading info
        ↓
Tutor reply via SSE
```

Examples:
- “给我一个提示” → current question + permissions, no long-term memory.
- “为什么 B 不对？” → current question + current grading state as allowed.
- “根据我上传的资料解释这个考点” → Knowledge RAG.
- “我最近整体哪里薄弱？” → do not pull global long-term history; point user to Mentor.

---

# 26. Database/API evolution

Do not create tables casually.

First inspect current models.

Where new persistent fields/models are truly required, add proper migrations/schema handling consistent with the repository.

Likely concepts that need explicit persistence:
- Practice session lifecycle / resumable state if incomplete today;
- Tutor thread/session identity if currently only frontend-local;
- reflection dirty/checkpoint/idempotency metadata;
- optional practice-session summary;
- embedding/index metadata;
- semantic memory index mapping metadata.

Prefer stable IDs and typed API contracts.

No frontend-only mock state for these behaviors.

---

# 27. Frontend behavior checklist

V3.2 UI must visibly communicate the new product model without making it noisy.

### Navigation
- keep Practice / 刷题;
- replace Coach route/page/code naming with Mentor;
- Chinese label can be `带教 Agent`;
- English/internal naming = `Mentor Agent`.

### Practice
- Resume-last-practice modal when entering directly from sidebar and an unfinished session exists;
- explicit bank start creates a new session;
- Tutor panel remains Practice-specific;
- new practice batch resets Tutor context;
- same batch may keep Tutor context across its questions;
- resumed later practice restores question progress but starts fresh Tutor context;
- subtle autosave indicator.

### Mentor
- persistent conversation list/history;
- long-term learner-aware answers;
- activity/tool receipts remain user-readable;
- semantic memory evidence may be summarized without exposing internal vector details.

### Knowledge
- background indexing progress;
- real ready/stale/rebuilding/failed state.

### Settings
- default SiliconFlow BGE-M3;
- advanced API/local provider configuration;
- rebuild status/action;
- explain canonical data is preserved.

---

# 28. Tests and acceptance criteria

V3.2 is not complete until tests cover the behavior, not only UI rendering.

## Naming / migration
- existing Coach persisted data can be read/migrated as Mentor;
- no new active `coach` records/routes are created;
- repository grep verifies naming cleanup.

## Tutor isolation
Tests must prove:
- Tutor can use current question context;
- Tutor can use Knowledge RAG;
- Tutor can read current immutable grading result only when allowed;
- Tutor does not receive global Learning Memory by default;
- Tutor does not receive unrelated previous attempts/review queue;
- new practice session → new Tutor context;
- new bank/question-count → new Tutor context;
- within same practice session, moving question can keep Tutor thread context;
- reopening/resuming a prior unfinished practice restores practice progress but starts a fresh Tutor prompt thread;
- objective submit still never waits for LLM/RAG/Embedding.

## Mentor persistence
Tests must prove:
- Mentor conversation persists;
- Mentor reads Learning Memory;
- Mentor can retrieve semantically related memory with paraphrased wording;
- Mentor can read FSRS/review/recent-attempt/bank-progress tools;
- Mentor can use Knowledge RAG;
- Mentor does not invent learner history when data is absent.

## Reflection
Tests must prove:
- session completion enqueues reflection;
- starting a new practice from an unfinished one triggers eligible reflection;
- duplicate close/trigger does not duplicate memory;
- evidence refs are validated;
- invalid/hallucinated refs are rejected;
- `NOOP` does not create a fake memory;
- failed worker/reflection never loses Attempt/session canonical state;
- inactivity fallback can recover a dirty unreflected session.

Frontend lifecycle test should verify `pagehide/visibilitychange` is only best-effort, not the sole persistence mechanism.

## Embedding/RAG
Tests must prove:
- default provider config resolves to SiliconFlow + `BAAI/bge-m3`;
- API keys are not persisted in frontend/browser state beyond what current secure settings design allows;
- embed documents/query use the same active model;
- model change marks indexes stale;
- rebuild recreates a dimension-incompatible Qdrant collection;
- old vectors are not queried with a new model;
- Knowledge and Learning Memory indexes are separate;
- local fallback can lazy-load;
- RAG still supports legitimate 0-hit;
- citation gate still rejects irrelevant evidence.

## Background jobs
- Knowledge upload/index job transitions correctly;
- reindex works;
- Reflection actor/job works;
- Factory continues to work;
- job failure states are visible and retry-safe.

## Full regression
Run the repository’s current equivalents of:

```text
backend compile
backend full pytest
frontend api generation/check
frontend lint
frontend tests
frontend build
git diff --check
```

Regenerate OpenAPI client; never hand-edit generated API code.

---

# 29. Documentation updates required in V3.2

Update documentation so the project story is consistent.

README should no longer describe both assistants ambiguously.

Use a distinction similar to:

```text
智能辅导 / Tutor Agent
- Practice 内
- 当前练习 session 上下文
- 当前题目、当前作答、RAG
- session-scoped, non-long-term conversational context

带教 Agent / Mentor Agent
- 全局入口
- 跨会话
- Attempts / Mastery / FSRS
- Learning Memory
- semantic long-term recall
- Knowledge RAG
- persistent conversations
```

Update the architecture doc currently named around Tutor/Agent so the two Agents are explicitly separated.

Add a V3.2 closure/design report describing:
- Tutor vs Mentor boundary;
- Memory Reflection;
- Learning Memory V2;
- Embedding provider;
- one-active-index rebuild behavior;
- async Knowledge indexing;
- practice resume behavior;
- validation evidence.

---

# 30. What to learn from TechSpar, and what NOT to copy

Reference project: `AnnaSuSu/TechSpar`

Useful concepts to borrow:
- configurable Embedding provider;
- vector indexes treated as derived/rebuildable;
- long-term learner/profile memory;
- semantic recall;
- training/session results write back into future experience;
- reflection/consolidation after a learning event;
- next interaction is influenced by prior validated learning history.

Do not blindly copy:
- TechSpar’s exact framework/stack;
- LangGraph purely for appearance;
- raw transcript → vector memory for every message;
- its exact profile schema;
- per-user embedding settings assumptions if TiBan’s hosted index is currently shared;
- any behavior that weakens TiBan’s deterministic Attempt/Mastery/FSRS evidence model.

TiBan’s differentiator should be:

> deterministic learning state + evidence-backed structured memory + semantic long-term recall + governed educational RAG.

---

# 31. Non-goals for V3.2

Do not expand scope into:
- deployment/server configuration;
- public traffic queue/admission control;
- multi-agent orchestration;
- GraphRAG;
- voice;
- new dashboard/chart system;
- full account/multi-tenant rewrite;
- permanent A/B storage for many embedding models;
- per-public-user duplicate Qdrant indexes;
- arbitrary autonomous write tools;
- raw chain-of-thought storage;
- new medical diagnosis/treatment capabilities.

Do not rewrite the entire architecture.

Prefer targeted refactoring around the existing FastAPI, React/Vite, AgentRunner/ToolRegistry, PostgreSQL, Qdrant, Redis/Dramatiq, FSRS and current typed OpenAPI client.

---

# 32. Expected final architecture

```text
                              TiBan
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
          Practice / Tutor                 Mentor Agent
          session-scoped                  cross-session
                │                                │
      ┌─────────┼─────────┐          ┌───────────┼────────────┐
      ▼         ▼         ▼          ▼           ▼            ▼
 current     grading   Knowledge   Mastery      FSRS     Learning Memory
 question     state       RAG      Attempts    Review         │
      │                   │                                   │
      │              BGE-M3 API                          PostgreSQL
      │                   │                                   │
      │                Qdrant                                 │
      │                                                       │
      │                                                  BGE-M3 API
      │                                                       │
      │                                                Memory Qdrant
      │                                                       │
      └────────────── session transcript/events ───────────────┤
                                                              │
                                                        Memory Reflection
                                                              │
                                                     validated writeback
```

Heavy asynchronous work:

```text
FastAPI
  │
  ├─ ordinary interactive requests
  │
  └─ enqueue jobs
          │
        Redis
          │
        Worker
          ├─ Question Factory
          ├─ Knowledge Indexing
          └─ Memory Reflection
```

Canonical state:

```text
PostgreSQL / source files
        = truth

Qdrant
        = rebuildable semantic indexes

Redis
        = job coordination
```

---

# 33. Implementation discipline

This is a V3.2 product/architecture completion, not an experimental rewrite.

While coding:
1. preserve existing working behavior;
2. modify the smallest coherent set of modules;
3. do not create duplicate services when a current service can be evolved;
4. use typed contracts;
5. add migrations where needed;
6. add regression tests before deleting compatibility paths;
7. do not hide failures behind mock success states;
8. no frontend-only fake progress;
9. no hard-coded demo answers;
10. no hand-edited generated API client;
11. no silent fallback that mixes old/new embedding vector spaces;
12. no fake Memory update indicator.

---

# 34. Required completion report

When done, provide a concise but concrete V3.2 report containing:
- branch and commit/worktree status;
- files/modules changed;
- Coach → Mentor migration details;
- final Tutor responsibility;
- final Mentor responsibility;
- Practice session/resume behavior;
- Tutor context reset rules;
- Memory Reflection triggers and browser-close safety strategy;
- Learning Memory semantic retrieval implementation;
- Embedding default/provider/rebuild implementation;
- Reranker implementation;
- Knowledge worker indexing implementation;
- DB/API migrations;
- test commands and exact pass/fail counts;
- any remaining known limitations.

Do not claim a feature is complete unless the real API/data path is implemented and tested.

---

## One-sentence product target

> **TiBan V3.2 should make Tutor a clean session-scoped practice assistant, Mentor a genuinely persistent evidence-backed learning mentor, and connect Attempts/Mastery/FSRS → validated Memory Reflection → semantic long-term recall, while moving online RAG embedding/reranking to configurable provider boundaries with SiliconFlow BGE-M3 as the default.**

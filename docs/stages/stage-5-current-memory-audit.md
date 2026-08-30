# Stage 5 current memory audit — v1.1

**Scope:** Memory & Personalization only. This audit records the canonical
learning state already present at the start of Stage 5 so v1.1 does not create
a parallel `LearningStateV2` or a second adaptive-learning loop.

## Product and data boundary

EndoTutor is a medical-learning platform. The checked-in teaching seed and any
locally mounted datasets are small development/import examples, not the
product's canonical catalogue and not a GitHub redistribution target. The
intended production path is learner/organization-owned question-bank upload,
validation, source governance, practice, and review. Raw external datasets
remain ignored; EndoBench remains evaluation-only.

## Existing canonical state

| State | Existing implementation | Layer | Source of truth / rebuildability |
| --- | --- | --- | --- |
| Current question, answer selection, hint count, temporary Tutor transcript | `PracticeSessionModel`, request-scoped `TutorStreamRequest.conversation`, frontend state | Session Memory | The active session and current client request. The transcript is intentionally bounded to the last 12 turns and is not long-term learner memory. |
| Stable session membership | `PracticeSessionItemModel` | Session Memory | Persisted server-side order for a bounded practice/exam session; reconstructible only while the linked question records remain. |
| Submitted answer and outcome | `AttemptModel` | Immutable learning evidence | Canonical append-only learning fact. Includes learner, question, score, correctness, error tags, hint count and time. It must not be overwritten. |
| Topic performance | `LearnerMasteryModel` via `learning_service._rebuild_mastery` | Learner Profile | Derived from immutable attempts per learner + knowledge point. Rebuildable from `AttemptModel` and `QuestionModel`. |
| Spaced review state | `ReviewCardModel` with py-fsrs card/logs | Learning State / Learner Profile | Deterministically written after each attempt or explicit review; schedule is reproducible from the card history. |
| Adaptive next-session reason | `Stage1Repository._select_adaptive_session_questions` | Derived recommendation | A deterministic projection over attempts, mastery and due review cards. It is not a second persistent profile. |
| Recent sessions and overview counters | `Stage1Repository.overview` | Derived view | Queried from sessions, attempts, mastery and cards. |
| Tutor tools and run receipts | `AgentRunner`, `ToolRegistry`, `AgentEvent`, `ToolReceipt` | Observability / Session context | Typed stream observations and receipts are emitted for the turn. They are not currently a durable cross-session conversation archive. |

## Gaps to fill in Stage 5

1. There is no durable, evidence-backed cross-session learning fact such as a
   repeated misconception or a resolved confusion. `LearnerMasteryModel` is an
   aggregate score, not a readable explanation of why the learner needs help.
2. The Tutor receives a bounded current conversation and can read recent
   mistakes, but it cannot retrieve a small, relevance-filtered set of
   consolidated learning memories.
3. The adaptive selector considers due cards and mastery, but has no explicit
   active-misconception evidence or transparent long-term-memory reason.
4. Learners do not yet have a concise learning-memory view or a way to clear
   long-term learning facts without deleting immutable attempts.
5. Existing Agent events do not record which long-term memories were selected,
   excluded, or how much prompt budget they used.

## Stage 5 canonical boundary

```text
Session Memory
  current PracticeSession + current question + bounded chat context
        │ does not automatically become durable memory
        ▼
Immutable Attempt / deterministic grading
        │ strong evidence only
        ▼
LearningMemoryItem (new, evidence-backed and lifecycle-managed)
        │ bounded read-back
        ├──────────────► Tutor context (top 3–5 relevant items)
        └──────────────► deterministic session selection evidence
        ▼
Learner Profile (derived from Attempt + Mastery + FSRS + active memory)
```

`LearningMemoryItem` will be the only new durable concept in Stage 5. It will
carry evidence references, `active/resolved/superseded` lifecycle, a
deduplication key, and version metadata. It does not replace attempts,
mastery, FSRS cards, or sessions. Clearing learning memory will change only
these derived cross-session facts; it will never delete attempts or review
history.

## Evidence policy

- Deterministic graded attempts are strong evidence. A single attempt can
  contribute evidence but does not by itself create a permanent misconception
  label.
- Repeated errors in the same topic/concept can consolidate into an active
  `repeated_mistake` memory.
- A learner's explicit, schema-validated statement such as “I keep confusing X
  and Y” may create a candidate `confusing_concepts` memory with the message /
  Tutor-run reference attached. Model speculation, personality labels and
  one-off inferred preferences are rejected.
- Correct follow-up evidence can resolve a past memory. Historical evidence is
  retained in the memory item for traceability; its active label is not shown
  or injected after resolution.

## Consequences

- PostgreSQL remains the canonical relational state. Learning memory will not
  be mixed into medical knowledge or QBank explanation retrieval namespaces.
- The Tutor remains read-only. Submit side effects remain deterministic:
  `grade → Attempt → mastery → FSRS → memory consolidation`.
- No raw chain-of-thought, raw provider prompt, secret, or full private chat
  transcript is persisted as learning memory.

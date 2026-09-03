# Memory & Personalization — v1.1

## Purpose

TiBan makes repeat use explainably different: a learner's verified
mistakes and explicitly stated confusions can shape the next Tutor response and
the next bounded practice session. It does not claim that a model permanently
learns or that model weights change.

## Three-layer boundary

```text
Session Memory
  current PracticeSession + current question + bounded Tutor conversation
        │ not automatically durable
        ▼
Immutable Attempt ──► LearnerMastery + FSRS ReviewCard
        │ deterministic, evidence-backed consolidation
        ▼
LearningMemoryItem (active / resolved / superseded)
        ├──► Tutor: top 3 relevant compact facts
        └──► Session selection: deterministic evidence tier
```

- `AttemptModel` is the canonical append-only evidence record.
- `LearnerMasteryModel` and `ReviewCardModel` remain derived/rebuildable state.
- `LearningMemoryItemModel` is the only new durable Stage 5 entity. It never
  replaces an Attempt, FSRS card, or session.

## Write policy and lifecycle

`grade → Attempt → mastery → FSRS → memory consolidation` runs in one server
transaction. Three incorrect attempts on a meaningful question topic create or
merge a `repeated_mistake` item; two later correct attempts resolve it. A
validated direct statement of the form “I cannot distinguish X and Y” may add a
`confusing_concepts` item with a Tutor run reference. No model inference,
personality label, raw chat, prompt, answer key, secret, or chain-of-thought is
stored.

Each item carries a learner-scoped dedupe key, topic/concept keys, compact
summary, evidence references, lifecycle status, version and timestamps.
Clearing memory marks only active items as `superseded`; it does not delete
Attempts, mastery, or FSRS history.

## Read path and isolation

`get_learning_memory` is a read-only Tutor tool. It first filters PostgreSQL
records by `learner_id = current learner` and `status = active`, then ranks only
current-topic or explicit-query matches. At most three items are injected. The
tool returns a trace projection with candidate/selected IDs, profile version,
token contribution and a personalization reason. Learning memory uses the
`learner_memory_structured` PostgreSQL namespace and is never inserted into the
medical knowledge/Qdrant retrieval collection.

The Tutor's pre-submit answer boundary is unchanged: learning-memory facts do
not contain submitted values, grading payloads, reference answers, hidden
rubrics, or benchmark targets.

## Product surface

`GET /api/v3/learning/memory` supplies a restrained Overview card, “最近需要
巩固”. `POST /api/v3/learning/memory/clear` supports an explicit learner action
while returning preservation flags for attempt and review history. No new main
navigation item or unbounded memory browser is added.

## Reproducibility

Run `backend/scripts/run_memory_personalization_evidence.py` with an isolated
database URL. It produces the before/after and two-learner artifacts under
`artifacts/memory/` from the compact teaching seed.

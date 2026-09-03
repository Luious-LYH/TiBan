# TiBan Project Overview

## What it is

题伴 TiBan is an agent-native adaptive QBank and learning platform. It joins
question banks, Practice, a persistent Tutor, retrieval, learning memory, FSRS
review, Question Factory and model evaluation in one workflow.

The repository ships Medical / Endoscopy and General Science as demonstration
domain packs. Both use the same learning core, and the product contract is
designed for additional domains without duplicating the learning engine.

## What a learner can do

1. Open a question bank and choose Study, Exam or Review.
2. Practice while the Tutor stays in the right-side chat.
3. Submit an answer and receive deterministic grading, explanation, mastery
   updates and a next review schedule.
4. Return later to a session shaped by due reviews, weak topics and learning
   history.
5. Upload an allowed teaching document and turn it into a reviewable question
   draft through the Question Factory.

The `/eval` workspace is separate from learning sessions. It compares candidate
models on text and image-question datasets.

## Four engineering highlights

### Tutor Agent + RAG

The Tutor uses a bounded runtime, read-only tools, source retrieval and learner
context. It remains a practice companion while the application workflow owns
learning-state changes.

### Adaptive Learning + FSRS

Attempt history feeds mastery and FSRS review cards. The next session uses that
state to select useful practice.

### Question Factory

An allowed document moves through parsing, indexing, generation, quality gates,
judge, repair and review. Durable Redis/Dramatiq jobs and revision lineage keep
the process inspectable.

### Domain-extensible core

The shared React + FastAPI platform scopes catalogs, sessions, memory,
retrieval and evaluation by `domain_id`. A domain pack supplies content and
policy while the Practice and Tutor flows stay shared.

## Current Scope and Data

- Medical / Endoscopy is the default professional-learning demo pack.
- General Science is a lightweight reference pack with 8 project-authored
  questions that demonstrates domain portability.
- The clean-start repository uses compact public fixtures.
- The local/hosted portfolio dataset contains 1,500 CMExam questions, 1,778
  CMB-Exam questions and 400 curated Kvasir-VQA questions: 3,678 in total.
- EndoBench is reserved for Evaluation and is not used by Tutor retrieval,
  Question Factory or learner-facing QBanks.

Large third-party datasets stay outside Git. The source registry and attribution
rules are in [`../../THIRD_PARTY_DATA.md`](../../THIRD_PARTY_DATA.md).

## Try it

```powershell
docker compose up --build
```

Then open:

- `/` — learning overview
- `/banks` — question bank catalog
- `/practice` — Practice + persistent Tutor
- `/eval` — model evaluation

See the [demo script](./DEMO_SCRIPT.md) for a short walkthrough and the
[`docs/architecture/`](../architecture/) directory for implementation details.

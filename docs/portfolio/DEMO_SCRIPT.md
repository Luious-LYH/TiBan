# TiBan v2.0 — 90-second demo

Use the public clean-start fixtures. The demo follows the learner path first,
then shows the engineering surfaces behind it.

| Time | Surface | Narration |
|---|---|---|
| 0:00–0:10 | `/` | “This is TiBan, an adaptive QBank and learning platform. It connects Practice, a persistent Tutor, learning memory, FSRS review, Question Factory and model evaluation.” |
| 0:10–0:22 | `/banks` | “The Banks page is the catalog. I choose a domain and a question bank, then start a Study, Exam or Review session.” |
| 0:22–0:45 | `/practice` | “The Tutor stays beside the question. I can ask about the stem, an option or the evidence while I work. The session keeps the current question and conversation together.” |
| 0:45–0:58 | Submit answer | “After submission, the platform grades the answer, records the Attempt, updates mastery and schedules the next review. The next session can use that learning history.” |
| 0:58–1:12 | Adaptive learning | “This is the adaptive loop: due reviews and weak topics shape what comes next. In the fixed scheduling scenario, weak-topic exposure moves from 25% to 75%.” |
| 1:12–1:25 | Question Factory | “An allowed teaching document becomes a reviewable question draft through parsing, retrieval, generation, quality checks, repair and publishing. Revisions stay linked for review.” |
| 1:25–1:30 | `/eval` | “The evaluation workspace compares candidate models on text or image-question datasets. It is a separate path from learner practice.” |

## What to point out

- The Tutor is a persistent right-side chat on desktop.
- Submission owns the learning-state transition; the Tutor supplies context and
  explanation.
- The Factory uses the same source and citation graph as Tutor retrieval.
- The local stack starts with compact public fixtures. The 3,678-question
  portfolio dataset is kept outside Git and imported separately.
- Medical / Endoscopy is the primary teaching domain. General Science is a
  lightweight reference pack using the same platform core.

## Technical follow-up

For an engineering walkthrough, show the
[project overview](./PROJECT_OVERVIEW.md), the
[Tutor architecture](../architecture/tutor-agent.md), the
[RAG benchmark](../evals/rag-benchmark-v2.md), and the adaptive-loop
[artifact](../../artifacts/learning/adaptive-loop-demo-v1.json).

# Stage 4 screenshot evidence

All screenshots were captured from the local Docker acceptance stack at
`http://127.0.0.1:5174` after the Stage 4 product-copy audit. They contain no
credentials, patient data, raw chain-of-thought, or developer/audit terminology
in learner-facing surfaces.

| File | Surface | What it demonstrates |
|---|---|---|
| `01-banks.png` | Question bank catalog | Complete CMB-Exam, CMExam, and curated Kvasir-VQA cards with learner-facing summaries. |
| `02-practice-tutor.png` | Practice | A study session with the persistent right-side Tutor and a session recommendation. |
| `03-adaptive-learning-loop.png` | Overview | Progress, due reviews, and recent learning state. |
| `04-question-factory.png` | Factory | Document-to-draft product entry point and reviewable generation flow. |
| `05-model-evaluation.png` | Evaluation | Temporary BYOK model evaluation controls and product-level scope. |

The detailed engineering traces, benchmark artifacts, and deferred human-review
statuses remain in `docs/` and `artifacts/`, not in the learner UI.

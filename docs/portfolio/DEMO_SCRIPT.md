# EndoTutor v1.0 — 75-second demo script

Do not enter an API key during the recording. Use the seeded local Docker stack
and the existing demo learner state.

| Time | Surface | Narration |
|---|---|---|
| 0:00–0:12 | `/banks` | “EndoTutor starts with 3,678 real teaching questions across CMExam, CMB-Exam, and curated Kvasir-VQA. I choose a topic and begin directly.” |
| 0:12–0:30 | `/practice?bank_id=bank-cmb-exam-real` | “The study workspace creates a session from unfinished items, review due dates, and weak topics. The Tutor stays beside the question, so a learner can ask naturally while practicing.” |
| 0:30–0:45 | Submit + Tutor | “After I submit, grading, attempt history, mastery, and review scheduling update deterministically. The Tutor can explain using the current question and permitted source material; it does not control learning-state writes.” |
| 0:45–0:56 | Overview / review | “The next session reads that new state. Here the recommendation records why this learner should revisit a weak topic or an item that is due.” |
| 0:56–1:06 | Factory | “An allowed teaching document becomes a reviewable draft through parsing, retrieval, generation, checking, repair, and explicit publishing. Versions remain available for review.” |
| 1:06–1:15 | `/eval` | “The evaluation workbench temporarily connects a candidate model, compares its text or image-question responses, and never stores the key. EndoBench remains evaluation-only.” |

Close with: “This is a medical education and physician-review-before-use
assistant, not an autonomous diagnostic system.”

## Optional technical follow-up

For an engineering interviewer, show the adaptive-loop artifact
[`../../artifacts/learning/adaptive-loop-demo-v1.json`](../../artifacts/learning/adaptive-loop-demo-v1.json),
then the frozen RAG benchmark and Factory revision evidence. Do not present RAG
or Judge metrics as expert/clinical validation; their human review is deferred
from v1.0.

# EndoTutor 7-minute demo script

Use a stable local provider and seeded demo data. Do not download datasets or
models during the recording.

| Time | Surface | Talk track |
|---|---|---|
| 0:00–0:40 | Overview / Banks | Show the learner-facing QBank counts and explain that demo data is curated and source-governed. |
| 0:40–2:00 | Practice / Study | Open a text or image question, submit an answer, show deterministic feedback, then ask the persistent right-side Tutor a follow-up. |
| 2:00–2:40 | Tutor | Show token streaming, real tool/source parts, collapsed high-level reasoning summary and the teaching safety notice; do not open raw reasoning. |
| 2:40–3:30 | Exam / Review | Switch to Exam, show locked pre-submit answer feedback, then review an incorrect attempt and apply Again/Hard/Good/Easy. |
| 3:30–5:00 | Question Factory | Upload one allowed Markdown/PDF source, show real job states, Generator/Judge result, repaired revision lineage, review gate and explicit publish. |
| 5:00–6:20 | Model Evaluation | Select CMExam or EndoBench, enter a temporary provider configuration, Test Connection, run a small sample, inspect per-case and aggregate results, and explain no-fallback/secret boundary. |
| 6:20–7:00 | Evidence | Open Developer Detail, RAG benchmark, Judge evaluation and FSRS artifact. End by stating that the numbers are engineering evidence, not clinical claims. |

Stable routes:

```text
/  → /banks → /practice?bank_id=bank-cmexam-real → /eval
```

Keep the API key out of recordings. For EndoBench, explicitly say
“Evaluation-only”; never present it as Tutor knowledge or a learner QBank.

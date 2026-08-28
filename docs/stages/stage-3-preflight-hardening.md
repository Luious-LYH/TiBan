# Stage 3 Pre-release Hardening

## Completed engineering work

| Requirement | Evidence | Status |
|---|---|---|
| Study/Exam answer boundary preserved | `QuestionPublic` remains answer-free; permissioned Study direct-answer path remains server-side | PASS |
| Knowledge Corpus v1 | 45 NIDDK-derived project summaries, allow-listed registry entry, 271 indexed chunks | PASS |
| RAG v2 | 90-query frozen candidate, 60 held-out tests, sparse/dense/hybrid/rerank and chunking ablation | PASS (engineering) |
| Factory Provider acceptance | Markdown, PDF and Kvasir-VQA-x1 generation-source each published through real Provider Generator/Judge with no fallback | PASS |
| Judge v2 | 80-case no-fallback Provider run, confusion matrices and retained ambiguous-stem failure | PASS (engineering) |
| QBank scale | Isolated PostgreSQL import of 68,112 valid CMExam questions and persisted 50-question sessions | PASS |

## Required honesty boundary

Both new RAG and Judge fixtures are frozen engineering candidate sets whose
clinical/educator human-review status is `pending`. The technical pipeline and
measurements are complete, but final external claims using the words
“human-reviewed” or “clinical effectiveness” remain blocked until a named
reviewer signs the corresponding fixture. This does not affect implementation
of the remaining Stage 3 work, but it remains a Final Gate limitation.

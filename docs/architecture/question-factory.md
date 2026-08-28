# Question Factory

```text
allowed document upload → Redis/Dramatiq queued job → parse → index
→ Generator schema → deterministic gate → Judge schema → repair revision
→ ready_for_review → explicit publish → canonical question bank
```

The upload boundary accepts only Markdown or PDF, validates filename extension, MIME and a 5 MiB limit, and stores a safe generated filename. PDF text uses PyMuPDF; Markdown uses the same heading-aware RAG parser. PostgreSQL holds `SourceDocument`, `DocumentVersion`, `KnowledgeChunk`, `FactoryJob` and `QuestionRevision`; Qdrant is reused rather than creating a second document model.

The Generator receives evidence and emits `GeneratedDraft`. The Judge receives only draft, source evidence and rubric fields, emits `JudgeDecision`, and never sees generator reasoning. Deterministic gates enforce public option/answer and citation shape first. A failed Judge creates a new `QuestionRevision` with parent revision, rewrite instruction, prompt version, source chunk IDs and timestamp; it never overwrites the initial draft.

The no-secret deterministic adapters prove local workflow and schemas. They are explicitly not evidence of external-provider generation. A real Redis + Dramatiq worker run is retained in the Stage 2 evidence; an operator can run a provider-backed adapter later without changing the workflow contract.

# Question Factory

```text
allowed document upload → Redis/Dramatiq queued job → parse → index
→ Generator schema → deterministic gate → Judge schema → repair revision
→ ready_for_review → explicit publish → canonical question bank
```

The upload boundary accepts only Markdown or PDF, validates filename extension, MIME and a 5 MiB limit, and stores a safe generated filename. PDF text uses PyMuPDF; Markdown uses the same heading-aware RAG parser. PostgreSQL holds `SourceDocument`, `DocumentVersion`, `KnowledgeChunk`, `FactoryJob` and `QuestionRevision`; Qdrant is reused rather than creating a second document model.

The Generator receives evidence and emits `GeneratedDraft`. The Judge receives only draft, source evidence and rubric fields, emits `JudgeDecision`, and never sees generator reasoning. Deterministic gates enforce public option/answer and citation shape first. A failed Judge creates a new `QuestionRevision` with parent revision, rewrite instruction, prompt version, source chunk IDs and timestamp; it never overwrites the initial draft.

Generator and Judge are separate provider calls with separate prompts and
schemas; the Judge sees only the draft, evidence and rubric. The real local
OpenAI-compatible acceptance covers Markdown, PDF and Kvasir-VQA-x1
generation-source inputs and retains published output plus revision lineage in
`artifacts/factory/factory-provider-acceptance-v1.json`. Provider failure is a
failure state; it never becomes a deterministic success. Deterministic
adapters remain available only as explicitly labelled no-secret development
coverage.

## Stage 2.5 source policy

Factory evidence must resolve through the same `SourceDocument → DocumentVersion → KnowledgeChunk → Citation` graph as Tutor RAG. A source passes only when its registry entry passes the License Gate. `Kvasir-VQA-x1` is a generation source, while `EndoBench` is a frozen evaluation source and is rejected from Factory input. Repairs retain revision lineage; the initial draft is never overwritten.

# Stage 7 domain-coupling audit

## Audit question

> What must leave the Practice core so a General Domain can be added without
> forking the Practice, Tutor, FSRS, Memory or Evaluation flows?

## Findings and classifications

| Area | Observed coupling | Classification | Stage 7 treatment |
| --- | --- | --- | --- |
| Question and bank persistence | `domain_id` already exists on banks/questions, but there is no validated domain registry or manifest. | Core business assumption | Add a small DomainManifest registry and validate domain IDs at import/seed time. |
| Catalog/session flow | Bank identifiers drive selection; sessions derive domain through their bank/question members rather than carrying an explicit domain projection. | Core business assumption | Preserve the single session builder; add domain filtering and return a domain projection rather than a parallel session type. |
| Mastery and memory | `LearnerMastery` is unique on learner + knowledge point; Learning Memory dedupes only learner + key. Identical topic names can collide across domains. | Core business assumption | Scope identity, query and dedupe keys by `domain_id`; backfill legacy rows to `medical_endoscopy`. |
| FSRS | Review cards are unique by learner + globally unique question id. | Core business assumption | Keep one scheduler and card model; expose a domain-filtered view via the linked question, with no second scheduler. |
| RAG | Source documents/chunks contain `domain_id`/namespace fields, but `RagService.index_markdown` creates `endoscopy` documents and Tutor retrieval requests `namespace="endoscopy"`. | Core business assumption | Make domain/namespace explicit at the adapter boundary; retain one Qdrant collection and prove metadata isolation. |
| Tutor | Local and provider gateways contain medical/endoscopy prompts and always append the medical safety notice. | Medical Domain Pack data/config plus medical safety policy | Resolve policy from the current question's manifest. Medical keeps the doctor-review boundary; General uses a normal learning policy without clinical language. |
| Factory | Existing document ingestion derives an endoscopy-domain source record. | Medical Domain Pack data/config | Add an optional domain input with manifest validation; retain one durable job pipeline and source model. |
| Evaluation | Dataset records have no domain field; text/VLM pack definitions and prompts are medical-specific. | Core business assumption plus medical demo fixture | Add a domain-aware dataset manifest and a legal frozen General text pack, reusing the provider/run/result engine. |
| UI shell | Header and footer say EndoTutor/内镜学习平台, and bank filters assume body parts. | Product branding | Rename user-visible shell to TiBan and add a domain switch plus generic subject filter. Keep four top-level nav items. |
| Bootstrap/import samples | CMExam, CMB-Exam, Kvasir and EndoBench identifiers appear in seed/importer and governance modules. | Medical Domain Pack data/config or Demo-only fixture | Keep them in the medical pack. EndoBench remains evaluation-only and never enters Tutor/RAG/Factory. |
| Legacy v1/v2 routes/docs | Historical `endoscopy`, `medical`, and report terminology appears outside the current v3 core. | Demo-only fixture / historical compatibility | Do not mass-rename or route these paths through new domain conditionals. |

## Minimal boundary

```text
                 +-------------------+
                 | Core Platform     |
                 | QBank / Session   |
                 | Attempt / FSRS    |
                 | Memory / Tutor    |
                 | RAG / Evaluation  |
                 +---------+---------+
                           |
                  validated DomainManifest
                   /                 \\
      medical_endoscopy           general_science
      tutor policy + namespaces    tutor policy + namespace
      QBank/KB/evaluation refs     QBank/KB/evaluation refs
```

The manifest is configuration, not a plugin framework: it supplies display
metadata, supported question types, namespaces, tutor policy and references to
governed pack data.  The core stores and passes `domain_id`; it does not branch
on `if medical` or `if science`.

## Required Stage 7 checks derived from this audit

1. General questions import through the existing `QuestionModel`, catalog,
   session builder, grading and learning workflow.
2. Same-name topics in the two domains create distinct mastery and memory
   state for one learner.
3. General retrieval cannot return medical chunks, and medical retrieval
   cannot return general chunks.
4. The Tutor's policy and visible wording follow the active domain.
5. The existing evaluation run engine lists and runs a General pack without
   copying the evaluation page or provider workflow.
6. Medical regression, including EndoBench isolation, stays green.

## Explicit non-goals

- A generic plugin loader, arbitrary third-party executable extensions, or
  per-domain microservices.
- A second Tutor runtime, FSRS scheduler, Qdrant collection, queue or
  evaluation engine.
- Converting every archived medical route or document to a generic form.
- Any claim of clinical or educational-outcome validation.

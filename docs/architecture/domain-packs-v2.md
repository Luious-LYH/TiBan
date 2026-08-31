# TiBan v2.0 Domain Packs

## Boundary

TiBan v2.0 keeps one learning core and adds a small, validated configuration
boundary for domain-specific data and policy. `DomainManifest` is a registry
entry, not a plugin loader or an executable extension framework.

```text
TiBan Core
  QBank · Practice · Attempt · Mastery · FSRS · Memory · Tutor · RAG · Evaluation
                 │
          validated DomainManifest
             ┌───┴────────────┐
   Medical / Endoscopy     General Science
   policy + namespaces     policy + namespace
```

Each manifest provides:

| Field | Purpose |
| --- | --- |
| `domain_id` | Stable scope stored on banks, questions, sessions and learning state. |
| `display_name`, `description`, `subjects` | Catalog metadata for the domain selector. |
| `supported_question_types` | Contract-level capability declaration. |
| `knowledge_namespaces` | Allowed RAG namespaces; metadata filters enforce isolation. |
| `tutor_policy` | Selects a bounded Tutor policy adapter. |
| `evaluation_pack_refs` | Links the domain to its Evaluation datasets. |
| `license_summary` | Human-readable governance receipt; source registry remains canonical. |

The registry is implemented in [`backend/app/domains.py`](../../backend/app/domains.py)
and exposed as public catalog metadata by `GET /api/v3/domains`. Internal
policy and namespace details are not exposed as a user-facing plugin API.

## Current packs

### Medical / Endoscopy (`endoscopy`)

Retains the existing CMExam, CMB-Exam, curated Kvasir-VQA, medical teaching
notes and medical Tutor safety policy. EndoBench remains an Evaluation-only
dataset. It is not eligible for Tutor retrieval, Question Factory evidence or
learner-facing QBank rows.

### General Science (`general_science`)

The checked-in proof pack is a small TiBan-authored eight-question fixture
covering physics, chemistry, life science and earth/space science. It exists so
a clean checkout can prove the domain boundary without redistributing a large
third-party dataset. A separate ARC Easy importer supports local validation
only; its raw parquet file is not committed, not indexed into Tutor RAG and
not used by Question Factory.

The General pack uses the same question union, bank catalog, session builder,
grading workflow, Attempt, mastery, FSRS, Learning Memory, Tutor runtime and
Evaluation engine as the Medical pack. Its policy is normal learning guidance;
it does not emit medical, clinical, endoscopy or doctor-review copy.

## Governance and extension checklist

Adding a future pack requires, in order:

1. A manifest with a stable domain id and supported question capabilities.
2. A source-registry entry with license, attribution, redistribution and AI
   ingestion decisions.
3. A small legal fixture or a local-only importer when the source cannot be
   redistributed.
4. Domain compatibility tests for Study, Exam, Review, FSRS, Memory, Tutor,
   RAG isolation and Evaluation.
5. Evidence that the existing core engines are reused rather than copied.

No domain may bypass the License Gate, introduce a second Qdrant collection,
second FSRS scheduler, second Tutor runtime or second queue.

# Domain Compatibility Matrix — v2.0

This is a platform compatibility check, not a clinical or educational-outcome
study. It verifies that two domain packs use the same product core and that
their state/evidence boundaries remain isolated.

| Capability | Medical / Endoscopy | General Science | Evidence |
| --- | --- | --- | --- |
| QBank catalog | PASS | PASS | `test_domain_manifest_and_catalog_filtering_are_public_and_scoped` |
| Study session | PASS | PASS | `test_general_domain_reuses_study_exam_review_tutor_and_fsrs` |
| Exam session | PASS | PASS | same test; pre-submit answer remains locked |
| Review session | PASS | PASS | same test; `Good` review returns scoped card |
| Attempt | PASS | PASS | submit path and stage regression suite |
| Mastery | PASS | PASS | scoped rows in cross-domain isolation test |
| FSRS | PASS | PASS | real `py-fsrs` card and review endpoint |
| Learning Memory | PASS | PASS | `test_cross_domain_mastery_and_memory_are_isolated_even_for_same_label` |
| Tutor policy | PASS | PASS | General output excludes medical policy copy |
| RAG isolation | PASS | PASS | `test_cross_domain_rag_retrieval_isolated` |
| Evaluation pack | PASS | PASS | General dataset is listed through the shared endpoint |
| Factory regression | PASS | N/A for new fixture | existing Stage 2/6 Factory suite |

The General proof pack is the eight-row, project-authored fixture in
`backend/app/data/general_science_fixture.json`; the ARC Easy importer is
local-only and has no repository data dependency. Medical QBank source data
remains optional local material and is not redistributed by this repository.

## Isolation rules

- `domain_id` is required in the public bank/session/question projections.
- Mastery and memory uniqueness/retrieval include `domain_id`.
- RAG calls pass manifest namespaces and PostgreSQL applies the same domain and
  license filters before citation projection.
- Evaluation datasets carry a domain but remain separate from learner QBank
  and Tutor knowledge.

Backend regression result at the v2.0 gate: `76 passed`. Frontend and hosted
results are recorded in the final Stage 7 report.

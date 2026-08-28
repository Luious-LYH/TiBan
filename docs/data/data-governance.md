# Data governance and contamination boundary

The product has four distinct assets:

1. Question Bank: learner-facing Study / Exam / Review questions.
2. Knowledge Base: Tutor and Question Factory evidence.
3. Evaluation Dataset: frozen benchmark inputs and labels.
4. Research / Generation Source: images and annotations that require suitability review.

Allowed flows:

| Source | QBank | Knowledge/RAG | Factory | Evaluation |
|---|---|---|---|---|
| CMExam | yes, limited real import | no | no | optional frozen split only |
| CMB-Exam | yes, limited real import | no | no | optional frozen split only |
| Kvasir-VQA | curated user-ready subset | no by default | yes, generation source | optional research split |
| Kvasir-VQA-x1 | no by default | no | yes, generation source | yes, if frozen |
| EndoBench | no | **never** | **never** | yes |
| project-curated notes | no direct import | yes after License Gate | yes as evidence | no |

EndoBench source IDs must never appear in Tutor retrieval rows or generated question lineage. This is tested in `backend/tests/test_stage25_data_governance.py`.

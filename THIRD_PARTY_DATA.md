# Third-party data and content

This repository stores registry, adapter, fixture and content-hash metadata only. Raw downloads under `data/external/` and generated normalized files under `data/normalized/` are ignored by Git.

| Asset | Local use in Stage 2.5 | License / gate | Attribution |
|---|---|---|---|
| CMExam | optional local import-validation fixture | Apache-2.0 plus upstream academic/research-use note; `allow_noncommercial` pending review | williamliujl/CMExam |
| CMB-Exam | optional local import-validation fixture | Apache-2.0 per source metadata | FreedomIntelligence/CMB |
| Kvasir-VQA | optional local visual-QBank fixture and generation source | CC BY-NC 4.0; non-commercial with attribution | Kvasir-VQA upstream |
| Kvasir-VQA-x1 | optional local generation/research fixture only | CC BY-NC 4.0; non-commercial with attribution | Kvasir-VQA-x1 upstream |
| EndoBench | evaluation-only | CC BY-SA 3.0; never Tutor/RAG/Factory/QBank | EndoBench upstream |
| ARC Easy | optional local-only General Domain import-validation fixture | CC BY-SA 4.0; attribution and share-alike obligations remain with the local import; raw data is not committed | Allen Institute for AI / AI2 Reasoning Challenge |

No dataset is a blanket authorization for commercial redistribution. The application preserves `source_item_id`, `source_uri`, `license_gate_status` and `business_usage` on imported questions.

ARC Easy is deliberately blocked from Tutor RAG and Question Factory (`ai_ingestion_allowed=false`). The checked-in General Science teaching fixture and knowledge note are project-authored and are the only General Domain content required by CI and Docker clean-start.

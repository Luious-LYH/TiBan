# Third-party data and content

This repository stores registry, adapter, fixture and content-hash metadata only. Raw downloads under `data/external/` and generated normalized files under `data/normalized/` are ignored by Git.

| Asset | Local use in Stage 2.5 | License / gate | Attribution |
|---|---|---|---|
| CMExam | limited real QBank import | Apache-2.0 plus upstream academic/research-use note; `allow_noncommercial` pending review | williamliujl/CMExam |
| CMB-Exam | limited real QBank import | Apache-2.0 per source metadata | FreedomIntelligence/CMB |
| Kvasir-VQA | filtered curated QBank and generation source | CC BY-NC 4.0; non-commercial with attribution | Kvasir-VQA upstream |
| Kvasir-VQA-x1 | generation/research source only by default | CC BY-NC 4.0; non-commercial with attribution | Kvasir-VQA-x1 upstream |
| EndoBench | evaluation-only | CC BY-SA 3.0; never Tutor/RAG/Factory/QBank | EndoBench upstream |

No dataset is a blanket authorization for commercial redistribution. The application preserves `source_item_id`, `source_uri`, `license_gate_status` and `business_usage` on imported questions.

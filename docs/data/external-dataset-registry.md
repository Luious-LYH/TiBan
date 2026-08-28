# External dataset registry

Stage 2.5 keeps raw downloads outside Git and stores the adapter, version, hash and policy in `data/registry/datasets.yaml`. The importer is idempotent: the same `source_item_id` maps to the same question ID.

| Dataset | Stage 2.5 product usage | Gate | Import scope |
|---|---|---|---:|
| CMExam | user-ready QBank | allow_noncommercial pending upstream research-use review | 1,500 annotated items |
| CMB-Exam | user-ready QBank | Apache-2.0 metadata; attribution retained | 1,778 imported items (train cap 1,500 + available validation subset) |
| Kvasir-VQA | suitability-classified; curated QBank only for user-ready subset | CC BY-NC 4.0 | 400 Yes/No image items |
| Kvasir-VQA-x1 | advanced generation/research source by default | CC BY-NC 4.0 | not imported to QBank |
| EndoBench | evaluation-only | benchmark isolation | never imported |

Every imported row records `source_item_id`, `derived_from_dataset`, `source_uri`, `business_usage`, `answer_source`, `explanation_source` and `official_explanation_available`.

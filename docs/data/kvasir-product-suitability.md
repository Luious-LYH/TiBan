# Kvasir-VQA product suitability

`scripts/datasets/classify_business_usage.py` performs a read-only deterministic first pass over Kvasir-VQA. It does not claim that an original annotation is a finished educational question.

Classification policy:

- `user_ready`: image exists, question is human-readable and the answer is a Yes/No fact that maps to the typed `true_false` contract.
- `needs_explanation`: image exists but the original answer is a color, location, count or label; retain as research material until a teaching explanation is reviewed.
- `generation_source`: image/annotation can support a new educational question but the original wording is too mechanical or lacks explanation.
- `excluded`: missing question, answer or image, or unsafe/model-control text.

Only `user_ready` rows are imported into `bank-kvasir-vqa-curated`. The rest remain in the read-only classification artifact and are not silently promoted.

"""Create the frozen engineering candidate set for RAG Benchmark v2.

The dataset is deterministic from the checked-in Corpus v1 topic catalog.  It
is intentionally marked as awaiting clinical/educator human adjudication:
automation can freeze and validate the set, but cannot certify human review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOPICS_PATH = ROOT / "knowledge" / "corpus-v1" / "topics.json"
OUTPUT = ROOT / "docs" / "fixtures" / "retrieval-eval-v2.json"


QUERY_TEMPLATES = (
    ("natural_learner", "我在复习“{title}”，应先把题干中的哪些资料当作证据，而不应自行补全？"),
    ("current_question_explanation", "一道关于“{title}”的题目只给出局部线索时，怎样区分概念、检查证据和不能下结论的部分？"),
)


def _document_id(item: dict[str, object]) -> str:
    value = str(item["id"]).lower()
    return "knowledge-v1-" + "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def build() -> dict[str, object]:
    topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    queries: list[dict[str, object]] = []
    for topic_index, topic in enumerate(topics):
        for template_index, (query_type, template) in enumerate(QUERY_TEMPLATES):
            ordinal = topic_index * len(QUERY_TEMPLATES) + template_index
            queries.append(
                {
                    "id": f"rag-v2-{ordinal + 1:03d}",
                    "split": "development" if ordinal < 30 else "test",
                    "query_type": query_type if ordinal % 5 else "terminology",
                    "query": template.format(title=topic["title"]),
                    "relevant_document_ids": [_document_id(topic)],
                    "hard_negative_document_ids": [],
                    "adjudication": {
                        "source": "deterministic engineering candidate generated from corpus-v1",
                        "human_review_status": "pending",
                        "clinical_or_educator_reviewer": None,
                    },
                }
            )
    if not 80 <= len(queries) <= 150 or sum(item["split"] == "test" for item in queries) < 60:
        raise ValueError("retrieval-eval-v2 must contain 80-150 queries and at least 60 held-out test cases")
    canonical = json.dumps(queries, ensure_ascii=False, separators=(",", ":"))
    payload = {
        "dataset_version": "retrieval-eval-v2-candidate-2026-08-28",
        "dataset_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "source_corpus": "knowledge-corpus-v1",
        "split": {"development": 30, "test": len(queries) - 30},
        "review_policy": {
            "human_review_required_before_external_effectiveness_claim": True,
            "status": "pending",
            "note": "This frozen candidate set supports engineering reproducibility only until a named clinical/educator reviewer checks queries, relevance and hard negatives.",
        },
        "queries": queries,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({"dataset_version": result["dataset_version"], "query_count": len(result["queries"]), "dataset_hash": result["dataset_hash"]}, ensure_ascii=False))

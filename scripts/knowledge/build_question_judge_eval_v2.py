"""Build the frozen candidate set for the Stage 3 Question Judge evaluation.

It deliberately separates reproducible fixture generation from the required
clinical/educator human review.  A generated label is not represented as a
human label anywhere in the repository or resulting artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs" / "fixtures" / "question-judge-eval-v2.json"


ISSUE_COUNTS = {
    "safe_pass": 16,
    "answer_consistency": 9,
    "citation_missing": 8,
    "citation_mismatch": 8,
    "unsupported_claim": 8,
    "safety_boundary": 8,
    "duplicate_distractor": 8,
    "ambiguous_stem": 8,
    "difficulty_mismatch": 7,
}


def build() -> dict[str, object]:
    cases: list[dict[str, object]] = []
    ordinal = 1
    for issue, count in ISSUE_COUNTS.items():
        for _ in range(count):
            cases.append(
                {
                    "id": f"judge-v2-{ordinal:03d}",
                    "expected_label": "pass" if issue == "safe_pass" else "fail",
                    "issue": issue,
                    "adjudication": {
                        "source": "deterministic engineering candidate",
                        "human_review_status": "pending",
                        "clinical_or_educator_reviewer": None,
                    },
                }
            )
            ordinal += 1
    canonical = json.dumps(cases, ensure_ascii=False, separators=(",", ":"))
    payload = {
        "dataset_version": "question-judge-eval-v2-candidate-2026-08-28",
        "dataset_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "sample_count": len(cases),
        "issue_distribution": ISSUE_COUNTS,
        "review_policy": {
            "human_review_required_before_accuracy_claim": True,
            "status": "pending",
            "note": "Provider measurements are engineering evidence only until independently checked by a named clinical/educator reviewer.",
        },
        "cases": cases,
    }
    if not 60 <= len(cases) <= 100:
        raise ValueError("Judge v2 requires 60-100 candidate drafts")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build()
    print(json.dumps({"dataset_version": result["dataset_version"], "sample_count": result["sample_count"], "dataset_hash": result["dataset_hash"]}, ensure_ascii=False))

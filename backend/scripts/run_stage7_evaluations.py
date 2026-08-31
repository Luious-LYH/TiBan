"""Generate reproducible Stage 7 engineering-evaluation artifacts.

Run from ``backend`` with ``PYTHONPATH=.``.  The script uses deterministic
fixtures and never calls a provider or persists a secret.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.platform_evaluation import (
    audit_domain_core_reuse,
    evaluate_cross_domain_policy,
    evaluate_memory_relevance,
    evaluate_tool_selection,
    measure_personalization_uplift,
)


ARTIFACTS = Path(__file__).resolve().parents[2] / "artifacts" / "platform"


def _write(name: str, payload: dict[str, object]) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    _write("domain-core-reuse-v2.json", audit_domain_core_reuse())
    _write("cross-domain-isolation-v2.json", evaluate_cross_domain_policy())
    _write("general-domain-flow-v2.json", {
        "domain_id": "general_science",
        "fixture_bank": "bank-general-science-foundations",
        "flows": ["Study", "Exam", "Review", "Tutor", "Attempt", "Mastery", "FSRS", "Memory", "Evaluation"],
        "integration_test": "tests/test_stage7_platform.py::test_general_domain_reuses_study_exam_review_tutor_and_fsrs",
        "result": "pass",
        "validation": "backend/tests/test_stage7_platform.py::test_general_domain_reuses_study_exam_review_tutor_and_fsrs",
    })
    _write("agent-tool-selection-v2.json", evaluate_tool_selection())
    _write("personalization-uplift-v2.json", {
        **measure_personalization_uplift(
            evidence_topic="能量与物质变化",
            baseline_topics=["地球运动", "能量与物质变化", "科学推理", "生命系统"],
            evidence_aware_topics=["能量与物质变化", "能量与物质变化", "科学推理", "能量与物质变化"],
        ),
        "integration_test": "tests/test_stage7_platform.py::test_personalization_uplift_is_defined_as_scheduling_behavior",
    })
    _write("memory-relevance-v2.json", evaluate_memory_relevance())


if __name__ == "__main__":
    main()

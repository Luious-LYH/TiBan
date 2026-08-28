"""Measure deterministic Gate versus a no-fallback real Provider Judge."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.factory_service import GeneratedDraft, ProviderFactoryError, _deterministic_gate, _provider_judge


EVIDENCE = "观察记录必须保留题干中明确给出的可见事实，并说明需要医生复核，不作为独立诊断依据。"
EXPECTED_CITATION = {"chunk_id": "chunk-review-v2", "document_id": "document-review-v2"}


def _draft(issue: str) -> GeneratedDraft:
    payload: dict[str, Any] = {
        "question_type": "single_choice",
        "title": "资料证据练习",
        "stem": "根据资料，哪项表述符合已给出的观察证据？",
        "options": [
            {"id": "a", "text": "观察记录必须保留题干中明确给出的可见事实"},
            {"id": "b", "text": "可忽略医生复核边界"},
            {"id": "c", "text": "缺少资料时可补全未给出的结论"},
            {"id": "d", "text": "单次资料可替代完整临床判断"},
        ],
        "correct_option_id": "a",
        "explanation": "资料只支持可见事实和证据边界。仅供教学训练或医生审核前辅助，不作为独立诊断依据。",
        "teaching_tags": ["证据边界", "资料溯源"],
        "citation": dict(EXPECTED_CITATION),
    }
    if issue == "answer_consistency":
        payload["correct_option_id"] = "missing-option"
    elif issue == "citation_missing":
        payload["citation"] = {}
    elif issue == "citation_mismatch":
        payload["citation"] = {"chunk_id": "chunk-other", "document_id": "document-other"}
    elif issue == "unsupported_claim":
        payload["options"][0]["text"] = "资料已经证实具体病因和最终诊断"
    elif issue == "safety_boundary":
        payload["explanation"] = "资料已经给出最终诊断，因此可以直接作为独立结论。"
    elif issue == "duplicate_distractor":
        payload["options"][3]["text"] = payload["options"][2]["text"]
    elif issue == "ambiguous_stem":
        payload["stem"] = "以下哪些都可能正确？"
    elif issue == "difficulty_mismatch":
        payload["stem"] = "请在不提供上下文时给出本资料之外的完整病因链和处置方案。"
    return GeneratedDraft.model_validate(payload)


def _metrics(predictions: list[bool], labels: list[bool]) -> dict[str, float | int]:
    tp = sum(predicted and label for predicted, label in zip(predictions, labels))
    fp = sum(predicted and not label for predicted, label in zip(predictions, labels))
    fn = sum(not predicted and label for predicted, label in zip(predictions, labels))
    tn = len(labels) - tp - fp - fn
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def main() -> None:
    fixture = json.loads((PROJECT_ROOT / "docs" / "fixtures" / "question-judge-eval-v2.json").read_text(encoding="utf-8"))
    labels: list[bool] = []
    gate_predictions: list[bool] = []
    provider_predictions: list[bool] = []
    cases: list[dict[str, Any]] = []
    failures: Counter[str] = Counter()
    for item in fixture["cases"]:
        issue = str(item["issue"])
        draft = _draft(issue)
        expected = item["expected_label"] == "pass"
        gate, gate_error = _deterministic_gate(draft, EVIDENCE)
        decision: dict[str, Any] | None = None
        error: str | None = None
        predicted = False
        if gate:
            try:
                judged = _provider_judge(draft, EVIDENCE, expected_citation=EXPECTED_CITATION)
                decision = judged.model_dump()
                predicted = judged.passed
            except ProviderFactoryError as exc:
                error = str(exc)
                failures[error] += 1
        labels.append(expected)
        gate_predictions.append(gate)
        provider_predictions.append(gate and predicted)
        cases.append({
            "id": item["id"], "expected_label": item["expected_label"], "issue": issue,
            "gate_passed": gate, "gate_error": gate_error, "provider_judge": decision,
            "provider_error": error, "gate_plus_provider_passed": gate and predicted,
        })
    artifact = {
        "artifact_version": "question-judge-eval-v2-artifact-v1",
        "dataset_version": fixture["dataset_version"],
        "dataset_hash": fixture["dataset_hash"],
        "review_policy": fixture["review_policy"],
        "provider_mode": "real_provider_no_fallback",
        "sample_count": len(cases),
        "deterministic_gate_only": _metrics(gate_predictions, labels),
        "gate_plus_provider_judge": _metrics(provider_predictions, labels),
        "provider_failure_count": sum(failures.values()),
        "provider_failure_categories": dict(failures),
        "cases": cases,
    }
    target = PROJECT_ROOT / "artifacts" / "factory"
    target.mkdir(parents=True, exist_ok=True)
    (target / "question-judge-eval-v2.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_count": len(cases), "gate": artifact["deterministic_gate_only"], "gate_plus_provider": artifact["gate_plus_provider_judge"], "provider_failures": artifact["provider_failure_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

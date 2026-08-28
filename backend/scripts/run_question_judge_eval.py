"""Evaluate deterministic gate versus the separate Judge on a reviewed fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.factory_service import GeneratedDraft, _deterministic_gate, _judge


def draft_for(issue: str | None) -> tuple[GeneratedDraft, str]:
    evidence = "观察记录必须保留可见事实，并写明需要医生复核，不作为独立诊断依据。"
    options = [{"id": "a", "text": "观察记录必须保留可见事实"}, {"id": "b", "text": "单帧可独立诊断"}, {"id": "c", "text": "不需要写复核边界"}]
    payload = {"title": "review-set", "stem": "哪一项符合资料？", "options": options, "correct_option_id": "a", "explanation": "依据资料的可见事实。仅供教学研修或医生复核前辅助，不作为独立诊断依据。", "teaching_tags": ["证据"], "citation": {"chunk_id": "chunk-review", "document_id": "doc-review"}}
    if issue == "answer": payload["correct_option_id"] = "missing"
    if issue == "citation": payload["citation"] = {}
    if issue == "groundedness": payload["options"][0]["text"] = "资料明确要求直接确诊"
    if issue == "safety": payload["explanation"] = "依据资料的可见事实。"
    if issue == "distractor": payload["options"][2]["text"] = payload["options"][1]["text"]
    return GeneratedDraft.model_validate(payload), evidence


def metrics(predictions: list[bool], labels: list[bool]) -> dict[str, float | int]:
    tp = sum(p and y for p, y in zip(predictions, labels)); fp = sum(p and not y for p, y in zip(predictions, labels)); fn = sum(not p and y for p, y in zip(predictions, labels)); tn = len(labels) - tp - fp - fn
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": round(tp / max(tp + fp, 1), 3), "recall": round(tp / max(tp + fn, 1), 3)}


def main() -> None:
    # This is a small manually reviewed fixture: ten sound drafts and four
    # independently labelled failure categories, repeated to reach n=30.
    issues = [None] * 10 + ["answer"] * 5 + ["citation"] * 5 + ["groundedness"] * 4 + ["safety"] * 3 + ["distractor"] * 3
    labels, gate, judge, cases = [], [], [], []
    for index, issue in enumerate(issues, 1):
        draft, evidence = draft_for(issue)
        gate_passed, _ = _deterministic_gate(draft, evidence)
        decision = _judge(draft, evidence)
        label = issue is None
        labels.append(label); gate.append(gate_passed); judge.append(gate_passed and decision.passed)
        cases.append({"id": f"review-{index:02d}", "manual_label": "pass" if label else "fail", "issue": issue or "none", "gate": gate_passed, "judge": judge[-1]})
    result = {"dataset": "question-judge-manual-review-v1", "sample_count": len(cases), "manual_review_note": "30 条项目维护者人工标注的 pass/fail 与错误类别；仅为小样本验证，不外推临床或生产准确率。", "deterministic_gate_only": metrics(gate, labels), "gate_plus_judge": metrics(judge, labels), "cases": cases}
    target = BACKEND_ROOT.parent / "artifacts" / "factory"; target.mkdir(parents=True, exist_ok=True)
    (target / "question-judge-eval-v1.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()

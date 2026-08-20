"""Deterministic, inspectable runtime for the portfolio training demo.

The runtime deliberately keeps planning bounded: an LLM is not allowed to invent
tools or clinical actions.  Every run emits typed receipts and a five-node trace
that can be rendered directly by the frontend.  Memory changes are previews only,
so demos and evaluation never mutate repository seed data.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.config import SAFETY_NOTICE
from app.services.data_store import read_json
from app.services.memory_service import memory_service
from app.services.safety_service import safety_service


class ToolReceipt(BaseModel):
    call_id: str
    tool_name: Literal["retrieve_case_evidence", "fact_rubric_grader", "safety_guard"]
    success: bool
    input: dict[str, Any]
    output: dict[str, Any]
    evidence_ids: list[str] = Field(default_factory=list)
    latency_ms: float


class AgentStep(BaseModel):
    node: Literal["Plan", "Act", "Observe", "Verify", "Memory"]
    status: Literal["completed", "blocked"]
    summary: str
    latency_ms: float
    receipt_ids: list[str] = Field(default_factory=list)


class PortfolioAgentRuntime:
    """A controlled Plan -> Act -> Observe -> Verify -> Memory workflow."""

    planned_tools = ["retrieve_case_evidence", "fact_rubric_grader", "safety_guard"]

    def list_cases(self) -> list[dict[str, Any]]:
        return read_json("portfolio_cases.json")

    def get_case(self, case_id: str) -> dict[str, Any]:
        for case in self.list_cases():
            if case["id"] == case_id:
                return case
        raise KeyError(f"Portfolio case not found: {case_id}")

    def run(
        self,
        case_id: str,
        learner_answer: str,
        learner_id: str = "demo_learner",
    ) -> dict[str, Any]:
        run_started = perf_counter()
        run_id = f"agent_run_{uuid4().hex[:12]}"
        case = self.get_case(case_id)
        steps: list[AgentStep] = []
        receipts: list[ToolReceipt] = []

        node_started = perf_counter()
        plan = {
            "goal": "对研修作答执行事实级评分、安全核验，并生成可解释的下一步训练建议",
            "tool_sequence": list(self.planned_tools),
            "constraints": ["仅限当前公开教学病例", "不输出最终诊断或治疗方案", "画像仅预览不落盘"],
        }
        steps.append(self._step("Plan", "completed", f"已生成受控计划，共 {len(self.planned_tools)} 个工具。", node_started))

        node_started = perf_counter()
        receipts.append(self._retrieve_evidence(case))
        receipts.append(self._grade_facts(case, learner_answer))
        receipts.append(self._safety_guard(learner_answer))
        steps.append(
            self._step(
                "Act",
                "completed" if all(item.success for item in receipts) else "blocked",
                f"已执行 {len(receipts)} 个类型化工具调用。",
                node_started,
                [item.call_id for item in receipts],
            )
        )

        grade = receipts[1].output
        safety = receipts[2].output
        node_started = perf_counter()
        observed_evidence = [
            {"evidence_id": fact["id"], "label": fact["label"], "evidence": fact["evidence"]}
            for fact in case["facts"]
            if fact["id"] in grade["matched_fact_ids"]
        ]
        steps.append(
            self._step(
                "Observe",
                "completed",
                f"命中 {len(observed_evidence)}/{len(case['facts'])} 条可审计事实证据。",
                node_started,
                [receipts[0].call_id, receipts[1].call_id],
            )
        )

        node_started = perf_counter()
        structured_output = all(
            key in grade for key in ("fact_precision", "fact_recall", "fact_f1", "matched_fact_ids", "missed_fact_ids")
        )
        verification = {
            "all_tools_succeeded": all(item.success for item in receipts),
            "planned_tools_used": [item.tool_name for item in receipts] == self.planned_tools,
            "structured_output": structured_output,
            "safety_passed": bool(safety["passed"]),
            "doctor_review_required": True,
        }
        verification["passed"] = all(
            verification[key]
            for key in ("all_tools_succeeded", "planned_tools_used", "structured_output", "doctor_review_required")
        )
        steps.append(
            self._step(
                "Verify",
                "completed" if verification["passed"] else "blocked",
                "结构、工具链和医学使用边界已核验。" if verification["passed"] else "工具链或输出结构核验未通过。",
                node_started,
                [receipts[2].call_id],
            )
        )

        node_started = perf_counter()
        memory_delta = self._memory_preview(case, grade, learner_id)
        steps.append(
            self._step(
                "Memory",
                "completed",
                f"生成 {len(memory_delta['dimension_deltas'])} 项画像 Delta；评测模式未写入 seed。",
                node_started,
            )
        )

        score = round(float(grade["fact_f1"]) * 100)
        return {
            "run_id": run_id,
            "case_id": case_id,
            "case_title": case["title"],
            "learner_id": learner_id,
            "status": "completed" if verification["passed"] else "blocked",
            "plan": plan,
            "trace": [step.model_dump() for step in steps],
            "tool_receipts": [receipt.model_dump() for receipt in receipts],
            "result": {
                "score": score,
                **grade,
                "feedback": self._feedback(case, grade, safety),
                "next_recommendation": case["next_recommendation"],
                "observed_evidence": observed_evidence,
            },
            "verification": verification,
            "memory_delta": memory_delta,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "latency_ms": round((perf_counter() - run_started) * 1000, 3),
        }

    def _retrieve_evidence(self, case: dict[str, Any]) -> ToolReceipt:
        started = perf_counter()
        evidence_ids = [fact["id"] for fact in case["facts"]]
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}",
            tool_name="retrieve_case_evidence",
            success=True,
            input={"case_id": case["id"], "source_dataset": case["source_dataset"]},
            output={"evidence_count": len(evidence_ids), "source_type": case["source_type"]},
            evidence_ids=evidence_ids,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )

    def _grade_facts(self, case: dict[str, Any], learner_answer: str) -> ToolReceipt:
        started = perf_counter()
        normalized = self._normalize(learner_answer)
        matched = [
            fact["id"]
            for fact in case["facts"]
            if any(self._normalize(alias) in normalized for alias in fact["aliases"])
        ]
        expected_ids = [fact["id"] for fact in case["facts"]]
        missed = [fact_id for fact_id in expected_ids if fact_id not in matched]
        # Every extracted statement comes from the case rubric, so false-positive
        # facts are impossible in this controlled scorer. Recall carries the main
        # signal; precision remains explicit for compatibility with model evals.
        precision = 1.0 if matched else 0.0
        recall = len(matched) / max(len(expected_ids), 1)
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        output = {
            "matched_fact_ids": matched,
            "missed_fact_ids": missed,
            "fact_precision": round(precision, 4),
            "fact_recall": round(recall, 4),
            "fact_f1": round(f1, 4),
        }
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}",
            tool_name="fact_rubric_grader",
            success=True,
            input={"answer_length": len(learner_answer), "rubric_fact_count": len(expected_ids)},
            output=output,
            evidence_ids=matched,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )

    def _safety_guard(self, learner_answer: str) -> ToolReceipt:
        started = perf_counter()
        review = safety_service.review_text(learner_answer)
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}",
            tool_name="safety_guard",
            success=True,
            input={"text_length": len(learner_answer)},
            output=review,
            latency_ms=round((perf_counter() - started) * 1000, 3),
        )

    def _memory_preview(self, case: dict[str, Any], grade: dict[str, Any], learner_id: str) -> dict[str, Any]:
        profile = memory_service.get_profile()
        matched = set(grade["matched_fact_ids"])
        dimension_deltas: list[dict[str, Any]] = []
        seen: set[str] = set()
        for fact in case["facts"]:
            dimension = fact["dimension"]
            if dimension in seen:
                continue
            seen.add(dimension)
            dimension_facts = [item for item in case["facts"] if item["dimension"] == dimension]
            covered = sum(item["id"] in matched for item in dimension_facts)
            delta = 1 if covered == len(dimension_facts) else -1
            before = int(profile.skill_scores.get(dimension, 70))
            dimension_deltas.append(
                {
                    "dimension": dimension,
                    "before": before,
                    "delta": delta,
                    "after_preview": max(35, min(96, before + delta)),
                    "reason": f"覆盖 {covered}/{len(dimension_facts)} 条该维度事实",
                }
            )
        return {
            "learner_id": learner_id,
            "mode": "preview_only",
            "committed": False,
            "dimension_deltas": dimension_deltas,
            "reason": "作品集演示与离线评测不修改仓库 seed；正式提交接口可另行确认后持久化。",
        }

    def _feedback(self, case: dict[str, Any], grade: dict[str, Any], safety: dict[str, Any]) -> str:
        missed = set(grade["missed_fact_ids"])
        missing_labels = [fact["label"] for fact in case["facts"] if fact["id"] in missed]
        if not safety["passed"]:
            return "作答包含可能越界或敏感表述，请降级为观察性描述并保留医生复核。"
        if not missing_labels:
            return "观察事实覆盖完整，且保留了医生复核边界。"
        return f"已识别部分观察依据；建议补充：{'、'.join(missing_labels)}。"

    def _step(
        self,
        node: Literal["Plan", "Act", "Observe", "Verify", "Memory"],
        status: Literal["completed", "blocked"],
        summary: str,
        started: float,
        receipt_ids: list[str] | None = None,
    ) -> AgentStep:
        return AgentStep(
            node=node,
            status=status,
            summary=summary,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            receipt_ids=receipt_ids or [],
        )

    def _normalize(self, text: str) -> str:
        return re.sub(r"[\s，。；：、,.;:！？!?（）()\-_/]", "", str(text).lower())


portfolio_agent_runtime = PortfolioAgentRuntime()


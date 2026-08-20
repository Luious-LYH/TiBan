"""Inspectable training Agent runtime with sparse evidence retrieval.

This is intentionally a bounded workflow rather than an autonomous clinical
agent.  It supports deterministic failure injection for regression tests and
keeps replay checkpoints in process memory, never in repository seed files.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.config import SAFETY_NOTICE
from app.services.data_store import read_json
from app.services.memory_service import memory_service
from app.services.safety_service import safety_service
from app.services.portfolio_study_service import portfolio_study_service


ToolName = Literal["retrieve_case_evidence", "fact_rubric_grader", "safety_guard"]
ToolErrorCode = Literal["timeout", "unavailable", "validation_error", "tool_exception"]


class ToolReceipt(BaseModel):
    call_id: str
    tool_name: ToolName
    success: bool
    input: dict[str, Any]
    output: dict[str, Any]
    evidence_ids: list[str] = Field(default_factory=list)
    latency_ms: float
    attempt: int = 1
    error_code: ToolErrorCode | None = None
    retryable: bool = False
    recovered_from_call_id: str | None = None


class AgentStep(BaseModel):
    node: Literal["Plan", "Act", "Recovery", "Observe", "Verify", "Memory"]
    status: Literal["completed", "blocked"]
    summary: str
    latency_ms: float
    receipt_ids: list[str] = Field(default_factory=list)


class PortfolioAgentRuntime:
    """Controlled Plan -> Act -> Observe -> Verify -> Memory workflow."""

    planned_tools: list[ToolName] = ["retrieve_case_evidence", "fact_rubric_grader", "safety_guard"]
    _checkpoint_limit = 128

    def __init__(self) -> None:
        self._checkpoints: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._checkpoint_lock = RLock()

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
        *,
        failure_injection: dict[str, Any] | None = None,
        context_budget_tokens: int = 800,
        parent_run_id: str | None = None,
        event_sink: Callable[[dict[str, Any]], None] | None = None,
        commit_memory: bool = False,
    ) -> dict[str, Any]:
        run_started = perf_counter()
        run_id = f"agent_run_{uuid4().hex[:12]}"
        case = self.get_case(case_id)
        injection = self._validated_failure_injection(failure_injection)
        steps: list[AgentStep] = []
        receipts: list[ToolReceipt] = []
        recovery_events: list[dict[str, Any]] = []

        node_started = perf_counter()
        plan = {
            "policy_id": "bounded_training_agent_v2_1",
            "goal": "对研修作答执行证据检索、事实级评分、安全核验，并生成可解释训练建议",
            "tool_sequence": list(self.planned_tools),
            "max_replans": 1,
            "constraints": [
                "仅限公开教学病例",
                "不输出最终诊断或治疗方案",
                "仅在显式授权时写入可重置的演示学习状态",
            ],
        }
        self._append_step(steps, self._step("Plan", "completed", f"受控计划包含 {len(self.planned_tools)} 个工具，最多一次恢复。", node_started), event_sink, run_id)

        query = " ".join([case["title"], case["prompt"], learner_answer])
        callbacks = {
            "retrieve_case_evidence": lambda attempt, recovered: self._retrieve_evidence(
                case, query, attempt=attempt, recovered_from_call_id=recovered
            ),
            "fact_rubric_grader": lambda attempt, recovered: self._grade_facts(
                case, learner_answer, attempt=attempt, recovered_from_call_id=recovered
            ),
            "safety_guard": lambda attempt, recovered: self._safety_guard(
                learner_answer, attempt=attempt, recovered_from_call_id=recovered
            ),
        }
        node_started = perf_counter()
        for tool_name in self.planned_tools:
            tool_receipts, recovery = self._execute_tool(tool_name, callbacks[tool_name], injection)
            receipts.extend(tool_receipts)
            if recovery:
                recovery_events.append(recovery)
        final_receipts = self._final_receipts(receipts)
        all_final_success = all(final_receipts.get(name) and final_receipts[name].success for name in self.planned_tools)
        self._append_step(
            steps,
            self._step(
                "Act",
                "completed" if all_final_success else "blocked",
                f"完成 {len(receipts)} 次工具尝试，最终成功 {sum(bool(final_receipts.get(name) and final_receipts[name].success) for name in self.planned_tools)}/{len(self.planned_tools)}。",
                node_started,
                [item.call_id for item in receipts],
            ),
            event_sink,
            run_id,
        )
        for recovery in recovery_events:
            self._append_step(
                steps,
                AgentStep(
                    node="Recovery",
                    status="completed" if recovery["recovered"] else "blocked",
                    summary=recovery["summary"],
                    latency_ms=recovery["latency_ms"],
                    receipt_ids=recovery["receipt_ids"],
                ),
                event_sink,
                run_id,
            )

        retrieval = self._receipt_output(final_receipts.get("retrieve_case_evidence"), self._empty_retrieval(query))
        grade = self._receipt_output(final_receipts.get("fact_rubric_grader"), self._empty_grade(case))
        safety = self._receipt_output(
            final_receipts.get("safety_guard"),
            {"passed": False, "warnings": ["安全工具不可用。"], "doctor_review_required": True, "safety_notice": SAFETY_NOTICE},
        )

        node_started = perf_counter()
        retrieved_ids = {item["evidence_id"] for item in retrieval.get("items", [])}
        observed_evidence = [
            {"evidence_id": fact["id"], "label": fact["label"], "evidence": fact["evidence"]}
            for fact in case["facts"]
            if fact["id"] in grade["matched_fact_ids"] and fact["id"] in retrieved_ids
        ]
        self._append_step(
            steps,
            self._step(
                "Observe",
                "completed" if final_receipts.get("retrieve_case_evidence") and final_receipts["retrieve_case_evidence"].success else "blocked",
                f"稀疏检索返回 {len(retrieval.get('items', []))} 条证据；作答命中其中 {len(observed_evidence)} 条。",
                node_started,
                [final_receipts["retrieve_case_evidence"].call_id] if final_receipts.get("retrieve_case_evidence") else [],
            ),
            event_sink,
            run_id,
        )

        node_started = perf_counter()
        structured_output = all(
            key in grade for key in ("fact_precision", "fact_recall", "fact_f1", "matched_fact_ids", "missed_fact_ids")
        )
        final_tool_names = [name for name in self.planned_tools if final_receipts.get(name) and final_receipts[name].success]
        verification = {
            "all_tools_succeeded": all_final_success,
            "planned_tools_used": final_tool_names == self.planned_tools,
            "structured_output": structured_output,
            "safety_passed": bool(safety["passed"]),
            "doctor_review_required": True,
            "recovery_attempted": bool(recovery_events),
            "recovery_succeeded": bool(recovery_events) and all(event["recovered"] for event in recovery_events),
        }
        verification["passed"] = all(
            verification[key]
            for key in ("all_tools_succeeded", "planned_tools_used", "structured_output", "doctor_review_required")
        )
        self._append_step(
            steps,
            self._step(
                "Verify",
                "completed" if verification["passed"] else "blocked",
                "结构、最终工具状态和医学使用边界已核验。" if verification["passed"] else "工具链或输出结构核验未通过。",
                node_started,
                [item.call_id for item in final_receipts.values()],
            ),
            event_sink,
            run_id,
        )

        node_started = perf_counter()
        score = round(float(grade["fact_f1"]) * 100)
        grader_succeeded = bool(
            final_receipts.get("fact_rubric_grader")
            and final_receipts["fact_rubric_grader"].success
        )
        if commit_memory and grader_succeeded:
            memory_delta = portfolio_study_service.record_attempt(
                self.list_cases(),
                case,
                learner_id=learner_id,
                score=score,
                matched_fact_ids=grade["matched_fact_ids"],
                missed_fact_ids=grade["missed_fact_ids"],
                source_run_id=run_id,
            )
        else:
            memory_delta = self._memory_preview(case, grade, learner_id)
            if commit_memory and not grader_succeeded:
                memory_delta["reason"] = "事实评分工具未成功，学习状态未写入。"
        self._append_step(
            steps,
            self._step(
                "Memory",
                "completed",
                (
                    f"提交 {len(memory_delta['dimension_deltas'])} 项学习画像 Delta 至可重置运行态。"
                    if memory_delta["committed"]
                    else f"生成 {len(memory_delta['dimension_deltas'])} 项画像 Delta 预览；未写入运行态。"
                ),
                node_started,
            ),
            event_sink,
            run_id,
        )

        context_manifest = self._context_manifest(case, learner_answer, retrieval, context_budget_tokens)
        usage_ledger = {
            "execution_mode": "deterministic_rule_runtime",
            "model_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "provider_usage": None,
            "estimated_context_tokens": context_manifest["included_estimated_tokens"],
            "estimated_cost": None,
            "currency": None,
            "source": "rule_path_no_model_call; context token count is a coarse local estimate",
        }
        adaptive_recommendation = memory_delta.get("adaptive_recommendation")
        if not adaptive_recommendation:
            adaptive_recommendation = portfolio_study_service.snapshot(
                self.list_cases(), learner_id
            ).get("adaptive_recommendation")
        next_recommendation = (
            f"下一题：{adaptive_recommendation['case_title']}。{adaptive_recommendation['reason']}"
            if adaptive_recommendation
            else case["next_recommendation"]
        )
        result = {
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "replay_id": run_id if parent_run_id else None,
            "case_id": case_id,
            "case_title": case["title"],
            "learner_id": learner_id,
            "status": "completed" if verification["passed"] else "blocked",
            "plan": plan,
            "trace": [step.model_dump() for step in steps],
            "tool_receipts": [receipt.model_dump() for receipt in receipts],
            "retrieval": retrieval,
            "result": {
                "score": score,
                **grade,
                "feedback": self._feedback(case, grade, safety),
                "next_recommendation": next_recommendation,
                "adaptive_recommendation": adaptive_recommendation,
                "observed_evidence": observed_evidence,
            },
            "verification": verification,
            "memory_delta": memory_delta,
            "context_manifest": context_manifest,
            "usage_ledger": usage_ledger,
            "doctor_review_required": True,
            "safety_notice": SAFETY_NOTICE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "latency_ms": round((perf_counter() - run_started) * 1000, 3),
        }
        result["checkpoint"] = self._save_checkpoint(
            run_id,
            {
                "case_id": case_id,
                "learner_answer": learner_answer,
                "learner_id": learner_id,
                "failure_injection": injection,
                "context_budget_tokens": context_manifest["budget_tokens"],
                # Replays are diagnostic and must not duplicate a learning attempt.
                "commit_memory": False,
            },
        )
        return result

    def replay(self, run_id: str) -> dict[str, Any]:
        with self._checkpoint_lock:
            checkpoint = self._checkpoints.get(run_id)
            if not checkpoint:
                raise KeyError(f"Agent checkpoint not found: {run_id}")
            replay_input = dict(checkpoint["input"])
        return self.run(**replay_input, parent_run_id=run_id)

    def retrieve_evidence(
        self,
        query: str,
        *,
        top_k: int = 3,
        metadata_filters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Small-corpus BM25-equivalent sparse retrieval with exact metadata filters."""
        filters = {str(key): str(value) for key, value in (metadata_filters or {}).items() if str(value).strip()}
        corpus = [item for item in self._evidence_corpus() if self._metadata_matches(item["metadata"], filters)]
        query_terms = self._search_terms(query)
        document_terms = [self._search_terms(item["search_text"]) for item in corpus]
        document_count = len(corpus)
        document_frequency = Counter(term for terms in document_terms for term in set(terms))
        average_length = sum(len(terms) for terms in document_terms) / max(document_count, 1)
        scored: list[tuple[float, dict[str, Any]]] = []
        for item, terms in zip(corpus, document_terms):
            frequencies = Counter(terms)
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                idf = math.log(1 + (document_count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                denominator = frequency + 1.2 * (1 - 0.75 + 0.75 * len(terms) / max(average_length, 1))
                score += idf * (frequency * 2.2) / denominator
            normalized_query = self._normalize(query)
            if self._normalize(item["label"]) in normalized_query:
                score += 2.0
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda pair: (-pair[0], pair[1]["evidence_id"]))
        limit = max(1, min(int(top_k), 10))
        items = [
            {
                "rank": rank,
                "score": round(score, 6),
                "evidence_id": item["evidence_id"],
                "label": item["label"],
                "evidence": item["evidence"],
                "source_dataset": item["metadata"]["source_dataset"],
                "case_id": item["metadata"]["case_id"],
                "metadata": item["metadata"],
            }
            for rank, (score, item) in enumerate(scored[:limit], start=1)
        ]
        return {
            "retrieval_mode": "explainable_sparse_bm25_equivalent",
            "query": query,
            "top_k": limit,
            "metadata_filters": filters,
            "candidate_count": document_count,
            "items": items,
        }

    def _execute_tool(self, tool_name: ToolName, callback, injection: dict[str, Any] | None):
        started = perf_counter()
        tool_receipts: list[ToolReceipt] = []
        failure_call_id: str | None = None
        for attempt in (1, 2):
            if injection and injection["tool_name"] == tool_name and attempt <= injection["fail_attempts"]:
                receipt = self._failure_receipt(tool_name, injection["error_code"], attempt, failure_call_id)
            else:
                try:
                    receipt = callback(attempt, failure_call_id)
                except Exception:
                    receipt = self._failure_receipt(tool_name, "tool_exception", attempt, failure_call_id)
            tool_receipts.append(receipt)
            if receipt.success:
                break
            failure_call_id = receipt.call_id
            if attempt >= 2 or not receipt.retryable:
                break
        recovery = None
        if len(tool_receipts) > 1:
            recovered = tool_receipts[-1].success
            recovery = {
                "recovered": recovered,
                "summary": (
                    f"{tool_name} 首次返回 {tool_receipts[0].error_code}，受控重试一次后恢复。"
                    if recovered
                    else f"{tool_name} 首次返回 {tool_receipts[0].error_code}，一次重试后仍失败。"
                ),
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "receipt_ids": [item.call_id for item in tool_receipts],
            }
        return tool_receipts, recovery

    def _retrieve_evidence(
        self, case: dict[str, Any], query: str, *, attempt: int, recovered_from_call_id: str | None
    ) -> ToolReceipt:
        started = perf_counter()
        output = self.retrieve_evidence(
            query,
            top_k=5,
            metadata_filters={"source_dataset": case["source_dataset"]},
        )
        evidence_ids = [item["evidence_id"] for item in output["items"]]
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}", tool_name="retrieve_case_evidence", success=True,
            input={"query": query, "top_k": 5, "metadata_filters": output["metadata_filters"]},
            output=output, evidence_ids=evidence_ids, latency_ms=round((perf_counter() - started) * 1000, 3),
            attempt=attempt, recovered_from_call_id=recovered_from_call_id,
        )

    def _grade_facts(
        self, case: dict[str, Any], learner_answer: str, *, attempt: int, recovered_from_call_id: str | None
    ) -> ToolReceipt:
        started = perf_counter()
        normalized = self._normalize(learner_answer)
        matched = [fact["id"] for fact in case["facts"] if any(self._normalize(alias) in normalized for alias in fact["aliases"])]
        expected_ids = [fact["id"] for fact in case["facts"]]
        missed = [fact_id for fact_id in expected_ids if fact_id not in matched]
        precision = 1.0 if matched else 0.0
        recall = len(matched) / max(len(expected_ids), 1)
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        output = {
            "matched_fact_ids": matched, "missed_fact_ids": missed,
            "fact_precision": round(precision, 4), "fact_recall": round(recall, 4), "fact_f1": round(f1, 4),
        }
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}", tool_name="fact_rubric_grader", success=True,
            input={"answer_length": len(learner_answer), "rubric_fact_count": len(expected_ids)}, output=output,
            evidence_ids=matched, latency_ms=round((perf_counter() - started) * 1000, 3), attempt=attempt,
            recovered_from_call_id=recovered_from_call_id,
        )

    def _safety_guard(
        self, learner_answer: str, *, attempt: int, recovered_from_call_id: str | None
    ) -> ToolReceipt:
        started = perf_counter()
        review = safety_service.review_text(learner_answer)
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}", tool_name="safety_guard", success=True,
            input={"text_length": len(learner_answer)}, output=review,
            latency_ms=round((perf_counter() - started) * 1000, 3), attempt=attempt,
            recovered_from_call_id=recovered_from_call_id,
        )

    def _failure_receipt(
        self, tool_name: ToolName, error_code: ToolErrorCode, attempt: int, recovered_from_call_id: str | None
    ) -> ToolReceipt:
        retryable = error_code in {"timeout", "unavailable"}
        return ToolReceipt(
            call_id=f"tool_{uuid4().hex[:10]}", tool_name=tool_name, success=False,
            input={"failure_injection": True}, output={"status": "error", "error_code": error_code},
            latency_ms=0.0, attempt=attempt, error_code=error_code, retryable=retryable,
            recovered_from_call_id=recovered_from_call_id,
        )

    def _validated_failure_injection(self, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if not value:
            return None
        tool_name = str(value.get("tool_name") or value.get("tool") or "")
        error_code = str(value.get("error_code") or "timeout")
        if tool_name not in self.planned_tools:
            raise ValueError("failure_injection.tool_name is invalid")
        if error_code not in {"timeout", "unavailable", "validation_error"}:
            raise ValueError("failure_injection.error_code is invalid")
        return {"tool_name": tool_name, "error_code": error_code, "fail_attempts": max(1, min(int(value.get("fail_attempts", 1)), 2))}

    def _evidence_corpus(self) -> list[dict[str, Any]]:
        corpus = []
        for case in self.list_cases():
            for fact in case["facts"]:
                metadata = {
                    "case_id": case["id"], "source_dataset": case["source_dataset"],
                    "difficulty": case["difficulty"], "body_part": case.get("body_part", "消化道"),
                    "dimension": fact["dimension"],
                }
                corpus.append({
                    "evidence_id": fact["id"], "label": fact["label"], "evidence": fact["evidence"],
                    "metadata": metadata,
                    "search_text": " ".join([case["title"], case["prompt"], fact["label"], *fact["aliases"], fact["evidence"]]),
                })
        return corpus

    def _search_terms(self, text: str) -> list[str]:
        lowered = str(text).lower()
        terms = re.findall(r"[a-z0-9]+", lowered)
        for span in re.findall(r"[\u4e00-\u9fff]+", lowered):
            terms.extend(span)
            terms.extend(span[index:index + 2] for index in range(max(len(span) - 1, 0)))
        return terms

    def _metadata_matches(self, metadata: dict[str, str], filters: dict[str, str]) -> bool:
        return all(str(metadata.get(key, "")) == value for key, value in filters.items())

    def _context_manifest(
        self, case: dict[str, Any], learner_answer: str, retrieval: dict[str, Any], budget_tokens: int
    ) -> dict[str, Any]:
        budget = max(64, min(int(budget_tokens), 4096))
        raw_chunks = [
            ("case", "current_case", f"{case['title']} {case['prompt']}", 100, "trusted_case_pack"),
            ("learner_answer", "doctor_answer", learner_answer, 90, "user_supplied"),
            *[
                ("retrieved_evidence", item["evidence_id"], f"{item['label']} {item['evidence']}", 80 - item["rank"], "public_dataset_evidence")
                for item in retrieval.get("items", [])
            ],
        ]
        used = 0
        chunks = []
        for source_type, source_id, text, priority, trust_level in sorted(raw_chunks, key=lambda item: -item[3]):
            estimate = self._estimate_tokens(text)
            included = used + estimate <= budget
            if included:
                used += estimate
            chunks.append({
                "source_type": source_type, "source_id": source_id, "priority": priority,
                "trust_level": trust_level, "char_count": len(text), "estimated_tokens": estimate,
                "included": included, "drop_reason": None if included else "context_budget_exceeded",
            })
        return {
            "budget_tokens": budget, "estimator": "ceil(non_whitespace_characters/2); coarse local estimate",
            "included_estimated_tokens": used,
            "total_estimated_tokens": sum(item["estimated_tokens"] for item in chunks),
            "chunks": chunks,
        }

    def _estimate_tokens(self, text: str) -> int:
        return max(1, math.ceil(len(re.sub(r"\s+", "", str(text))) / 2))

    def _save_checkpoint(self, run_id: str, run_input: dict[str, Any]) -> dict[str, Any]:
        input_hash = hashlib.sha256(
            f"{run_input['case_id']}\0{run_input['learner_answer']}\0{run_input['learner_id']}".encode("utf-8")
        ).hexdigest()[:16]
        with self._checkpoint_lock:
            self._checkpoints[run_id] = {"input": run_input, "input_hash": input_hash}
            self._checkpoints.move_to_end(run_id)
            while len(self._checkpoints) > self._checkpoint_limit:
                self._checkpoints.popitem(last=False)
        return {
            "checkpoint_id": run_id, "replayable": True, "storage": "bounded_process_memory",
            "input_hash": input_hash, "contains_raw_input_in_response": False,
        }

    def _final_receipts(self, receipts: list[ToolReceipt]) -> dict[str, ToolReceipt]:
        final: dict[str, ToolReceipt] = {}
        for receipt in receipts:
            final[receipt.tool_name] = receipt
        return final

    def _receipt_output(self, receipt: ToolReceipt | None, fallback: dict[str, Any]) -> dict[str, Any]:
        return receipt.output if receipt and receipt.success else fallback

    def _empty_retrieval(self, query: str) -> dict[str, Any]:
        return {"retrieval_mode": "explainable_sparse_bm25_equivalent", "query": query, "top_k": 5, "metadata_filters": {}, "candidate_count": 0, "items": []}

    def _empty_grade(self, case: dict[str, Any]) -> dict[str, Any]:
        return {"matched_fact_ids": [], "missed_fact_ids": [fact["id"] for fact in case["facts"]], "fact_precision": 0.0, "fact_recall": 0.0, "fact_f1": 0.0}

    def _memory_preview(self, case: dict[str, Any], grade: dict[str, Any], learner_id: str) -> dict[str, Any]:
        profile = memory_service.get_profile()
        matched = set(grade["matched_fact_ids"])
        dimension_deltas = []
        for dimension in dict.fromkeys(fact["dimension"] for fact in case["facts"]):
            facts = [fact for fact in case["facts"] if fact["dimension"] == dimension]
            covered = sum(fact["id"] in matched for fact in facts)
            delta = 1 if covered == len(facts) else -1
            before = int(profile.skill_scores.get(dimension, 70))
            dimension_deltas.append({
                "dimension": dimension, "before": before, "delta": delta,
                "after_preview": max(35, min(96, before + delta)),
                "reason": f"覆盖 {covered}/{len(facts)} 条该维度事实",
            })
        return {
            "learner_id": learner_id, "mode": "preview_only", "committed": False,
            "dimension_deltas": dimension_deltas,
            "reason": "作品集演示与离线评测不修改仓库 seed。",
        }

    def _feedback(self, case: dict[str, Any], grade: dict[str, Any], safety: dict[str, Any]) -> str:
        missed = set(grade["missed_fact_ids"])
        missing_labels = [fact["label"] for fact in case["facts"] if fact["id"] in missed]
        if not safety["passed"]:
            return "作答包含可能越界或敏感表述，请降级为观察性描述并保留医生复核。"
        if not missing_labels:
            return "观察事实覆盖完整，且保留了医生复核边界。"
        return f"已识别部分观察依据；建议补充：{'、'.join(missing_labels)}。"

    def _step(self, node, status, summary: str, started: float, receipt_ids: list[str] | None = None) -> AgentStep:
        return AgentStep(node=node, status=status, summary=summary, latency_ms=round((perf_counter() - started) * 1000, 3), receipt_ids=receipt_ids or [])

    def _append_step(
        self,
        steps: list[AgentStep],
        step: AgentStep,
        event_sink: Callable[[dict[str, Any]], None] | None,
        run_id: str,
    ) -> None:
        steps.append(step)
        if event_sink:
            event_sink({"event": "stage", "run_id": run_id, "stage": step.model_dump()})

    def _normalize(self, text: str) -> str:
        return re.sub(r"[\s，。；：、,.;:！？!?（）()\-_/]", "", str(text).lower())


portfolio_agent_runtime = PortfolioAgentRuntime()

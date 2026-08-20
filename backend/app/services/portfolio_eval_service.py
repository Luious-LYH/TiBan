"""Offline regression evaluation for the portfolio Agent runtime."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from app.services.portfolio_agent_runtime import portfolio_agent_runtime


class PortfolioEvalService:
    metric_version = "portfolio-agent-eval-v2.1"

    def run(self, output_dir: str | Path | None = None) -> dict[str, Any]:
        cases = portfolio_agent_runtime.list_cases()
        runs = [portfolio_agent_runtime.run(case["id"], case["gold_answer"], learner_id="eval_learner") for case in cases]
        latencies = sorted(float(run["latency_ms"]) for run in runs)
        retrieval_eval = self._retrieval_eval(cases)
        recovery_eval = self._recovery_eval(cases)
        replay_source = runs[0]
        replay = portfolio_agent_runtime.replay(replay_source["run_id"])

        task_completed = [run["status"] == "completed" and run["result"]["fact_recall"] >= 0.8 for run in runs]
        tool_correct = [
            [receipt["tool_name"] for receipt in run["tool_receipts"]] == portfolio_agent_runtime.planned_tools
            and all(receipt["success"] for receipt in run["tool_receipts"])
            for run in runs
        ]
        safety_passed = [
            run["verification"]["safety_passed"] and run["doctor_review_required"]
            and "不作为独立诊断依据" in run["safety_notice"] for run in runs
        ]
        safety_probes = self._safety_probes(cases)
        structured = [
            run["verification"]["structured_output"]
            and "context_manifest" in run and "usage_ledger" in run for run in runs
        ]
        replay_correct = (
            replay["parent_run_id"] == replay_source["run_id"]
            and replay["case_id"] == replay_source["case_id"]
            and replay["checkpoint"]["input_hash"] == replay_source["checkpoint"]["input_hash"]
        )

        metrics = {
            "case_count": len(runs),
            "task_completion_rate": self._rate(task_completed),
            "tool_selection_accuracy": self._rate(tool_correct),
            "evidence_coverage_rate": round(sum(float(run["result"]["fact_recall"]) for run in runs) / max(len(runs), 1), 4),
            "retrieval_recall_at_1": retrieval_eval["recall_at_1"],
            "retrieval_recall_at_3": retrieval_eval["recall_at_3"],
            "safety_pass_rate": self._rate([*safety_passed, *(item["correct"] for item in safety_probes)]),
            "structured_output_rate": self._rate(structured),
            "recovery_rate": recovery_eval["recovery_rate"],
            "checkpoint_replay_rate": 1.0 if replay_correct else 0.0,
            "mean_fact_f1": round(sum(float(run["result"]["fact_f1"]) for run in runs) / max(len(runs), 1), 4),
            "latency_p50_ms": round(median(latencies), 3) if latencies else 0.0,
            "latency_p95_ms": round(self._percentile(latencies, 0.95), 3),
        }
        created_at = datetime.now(timezone.utc).isoformat()
        artifact = {
            "eval_id": f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}",
            "metric_version": self.metric_version,
            "created_at": created_at,
            "conditions": {
                "mode": "deterministic_offline_golden_case_replay",
                "model_call": False,
                "memory_write": False,
                "checkpoint_storage": "bounded_process_memory",
                "safety_probe_count": len(safety_probes),
                "retrieval_query_count": retrieval_eval["query_count"],
                "retrieval_query_design": "case title + canonical fact label + first accepted alias; metadata filtered by dataset and body part",
                "fault_injection_count": recovery_eval["injection_count"],
                "case_source": "backend/app/data/portfolio_cases.json",
                "latency_scope": "single-process Python service time; excludes HTTP, model calls and frontend rendering",
            },
            "metrics": metrics,
            "cases": [
                {
                    "case_id": run["case_id"], "status": run["status"], "score": run["result"]["score"],
                    "fact_precision": run["result"]["fact_precision"], "fact_recall": run["result"]["fact_recall"],
                    "fact_f1": run["result"]["fact_f1"], "safety_passed": run["verification"]["safety_passed"],
                    "tool_count": len(run["tool_receipts"]), "retrieved_count": len(run["retrieval"]["items"]),
                    "context_estimated_tokens": run["context_manifest"]["included_estimated_tokens"],
                    "model_calls": run["usage_ledger"]["model_calls"], "latency_ms": run["latency_ms"],
                }
                for run in runs
            ],
            "retrieval_eval": retrieval_eval,
            "recovery_eval": recovery_eval,
            "safety_probes": safety_probes,
            "checkpoint_replay": {
                "source_run_id": replay_source["run_id"], "replay_id": replay["replay_id"],
                "parent_run_id": replay["parent_run_id"], "input_hash_match": replay_correct,
            },
        }
        self._write_artifacts(artifact, output_dir)
        return artifact

    def _retrieval_eval(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        probes = []
        for case in cases:
            for fact in case["facts"]:
                query = f"{case['title']} {fact['label']} {fact['aliases'][0]}"
                result = portfolio_agent_runtime.retrieve_evidence(
                    query, top_k=3,
                    metadata_filters={"source_dataset": case["source_dataset"], "body_part": case["body_part"]},
                )
                ranked_ids = [item["evidence_id"] for item in result["items"]]
                probes.append({
                    "query_id": f"query_{fact['id']}", "expected_evidence_id": fact["id"],
                    "ranked_evidence_ids": ranked_ids, "hit_at_1": fact["id"] in ranked_ids[:1],
                    "hit_at_3": fact["id"] in ranked_ids[:3],
                })
        return {
            "query_count": len(probes), "recall_at_1": self._rate([item["hit_at_1"] for item in probes]),
            "recall_at_3": self._rate([item["hit_at_3"] for item in probes]), "probes": probes,
        }

    def _recovery_eval(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        probes = []
        for index, tool_name in enumerate(portfolio_agent_runtime.planned_tools):
            case = cases[index]
            run = portfolio_agent_runtime.run(
                case["id"], case["gold_answer"], learner_id="eval_recovery",
                failure_injection={"tool_name": tool_name, "error_code": "timeout", "fail_attempts": 1},
            )
            failed_receipts = [item for item in run["tool_receipts"] if item["tool_name"] == tool_name and not item["success"]]
            recovered = run["verification"]["recovery_succeeded"] and run["status"] == "completed"
            probes.append({
                "tool_name": tool_name, "injected_error": "timeout", "failed_receipt_count": len(failed_receipts),
                "recovered": recovered, "attempt_count": len([item for item in run["tool_receipts"] if item["tool_name"] == tool_name]),
            })
        return {"injection_count": len(probes), "recovery_rate": self._rate([item["recovered"] for item in probes]), "probes": probes}

    def _safety_probes(self, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        probes = [("可以确诊并直接开药。", False), ("必须活检，之后立即手术。", False), ("仅描述当前视野并由医生复核。", True)]
        results = []
        for index, (answer, expected_passed) in enumerate(probes):
            run = portfolio_agent_runtime.run(cases[index]["id"], answer, learner_id="eval_safety_probe")
            actual_passed = bool(run["verification"]["safety_passed"])
            results.append({
                "probe_id": f"safety_probe_{index + 1}", "expected_passed": expected_passed,
                "actual_passed": actual_passed, "correct": actual_passed == expected_passed,
            })
        return results

    def _write_artifacts(self, artifact: dict[str, Any], output_dir: str | Path | None) -> None:
        target = Path(output_dir) if output_dir else Path(__file__).resolve().parents[3] / "artifacts" / "eval"
        target.mkdir(parents=True, exist_ok=True)
        (target / "latest.json").write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        metrics = artifact["metrics"]
        rows = "\n".join(
            f"| {case['case_id']} | {case['score']} | {case['retrieved_count']} | {case['context_estimated_tokens']} | {case['latency_ms']:.3f} |"
            for case in artifact["cases"]
        )
        markdown = f"""# Agent 离线回归评测 v2.1

- 评测版本：`{artifact['metric_version']}`
- 条件：{metrics['case_count']} 个 Golden Case、{artifact['conditions']['retrieval_query_count']} 条检索 Query、{artifact['conditions']['fault_injection_count']} 次工具故障注入、{artifact['conditions']['safety_probe_count']} 条安全探针
- 执行：本地可解释稀疏检索 + 确定性规则 Runtime；不调用外部模型，不写学习画像
- 延迟：只含单进程 Python 服务，不含 HTTP、网络模型调用和前端渲染

## 汇总指标

| 指标 | 结果 |
|---|---:|
| 任务完成率 | {metrics['task_completion_rate']:.0%} |
| 工具选择正确率 | {metrics['tool_selection_accuracy']:.0%} |
| Retrieval Recall@1 | {metrics['retrieval_recall_at_1']:.0%} |
| Retrieval Recall@3 | {metrics['retrieval_recall_at_3']:.0%} |
| 工具故障恢复率 | {metrics['recovery_rate']:.0%} |
| Checkpoint 重放通过率 | {metrics['checkpoint_replay_rate']:.0%} |
| 安全边界判定准确率 | {metrics['safety_pass_rate']:.0%} |
| 结构化输出率 | {metrics['structured_output_rate']:.0%} |
| 平均事实 F1 | {metrics['mean_fact_f1']:.0%} |
| P50 / P95 | {metrics['latency_p50_ms']:.3f} / {metrics['latency_p95_ms']:.3f} ms |

## 病例明细

| 病例 | 分数 | 检索条数 | 上下文估算 Token | 延迟(ms) |
|---|---:|---:|---:|---:|
{rows}

> Recall@K 使用“病例标题 + 标准事实标签 + 首个同义表达”的固定查询，衡量 19 条事实语料上的确定性检索回归，不代表开放问法或生产 RAG；毫秒级延迟不代表 VLM 推理速度。
"""
        (target / "latest.md").write_text(markdown, encoding="utf-8")

    def _rate(self, values) -> float:
        items = list(values)
        return round(sum(bool(value) for value in items) / max(len(items), 1), 4)

    def _percentile(self, values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        position = (len(values) - 1) * quantile
        lower, upper = int(position), min(int(position) + 1, len(values) - 1)
        return values[lower] * (1 - (position - lower)) + values[upper] * (position - lower)


portfolio_eval_service = PortfolioEvalService()


if __name__ == "__main__":
    print(json.dumps(portfolio_eval_service.run(), ensure_ascii=False, indent=2))

"""Run a bounded real-provider model-evaluation acceptance.

The provider is read from the local environment only. This script prints
redacted summaries; run artifacts contain answer-shaped outputs only and never
contain the API key or raw model reasoning.
"""

from __future__ import annotations

import argparse
import json

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from app.services.model_eval_service import run_evaluation


def _summary(result: dict[str, object]) -> dict[str, object]:
    aggregate = result.get("aggregate") or {}
    return {
        "eval_run_id": result.get("eval_run_id"),
        "dataset_id": result.get("dataset_id"),
        "dataset_version": result.get("dataset_version"),
        "status": result.get("status"),
        "sample_count": result.get("sample_count"),
        "fallback": result.get("fallback"),
        "aggregate": {
            "accuracy": aggregate.get("accuracy"),
            "valid_parse_rate": aggregate.get("valid_parse_rate"),
            "failure_rate": aggregate.get("failure_rate"),
            "latency_p50_ms": aggregate.get("latency_p50_ms"),
            "latency_p95_ms": aggregate.get("latency_p95_ms"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded real-provider evaluation acceptance")
    parser.add_argument("--text-samples", type=int, default=5)
    parser.add_argument("--vlm-samples", type=int, default=1)
    args = parser.parse_args()
    if not LLM_BASE_URL or not LLM_API_KEY or not LLM_MODEL:
        print(json.dumps({"status": "EXTERNAL_PROVIDER_ACCEPTANCE_PENDING", "reason": "local provider is not configured"}, ensure_ascii=False))
        return 2

    summaries: list[dict[str, object]] = []
    for dataset_id, sample_count in (
        ("cmexam-text-eval-v1", args.text_samples),
        ("endobench-vlm-eval-v1", args.vlm_samples),
    ):
        try:
            result = run_evaluation(
                dataset_id=dataset_id,
                base_url=LLM_BASE_URL,
                api_key=LLM_API_KEY,
                model=LLM_MODEL,
                sample_count=sample_count,
            )
            summaries.append(_summary(result))
        except Exception as exc:  # the artifact/report must show a real limitation
            summaries.append({"dataset_id": dataset_id, "status": "failed", "error_category": type(exc).__name__})
    print(json.dumps({"provider": "local OpenAI-compatible provider", "fallback": False, "runs": summaries}, ensure_ascii=False))
    return 0 if all(item.get("status") in {"completed", "completed_with_failures"} for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())

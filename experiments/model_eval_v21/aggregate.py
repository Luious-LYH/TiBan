"""Aggregate completed runs without inventing missing or failed results."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def pct_delta(value: float, baseline: float) -> float:
    return (value - baseline) / baseline if baseline else 0.0


def json_valid_rate(results_root: Path, run_id: str) -> float:
    path = results_root / run_id / "cases.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    valid = 0
    for row in rows:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", row["answer_raw"].strip(), flags=re.IGNORECASE)
        try:
            value = json.loads(cleaned)
            valid += int(isinstance(value, dict) and isinstance(value.get("answer"), str))
        except json.JSONDecodeError:
            pass
    return valid / len(rows) if rows else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results")
    parser.add_argument("--output", default="aggregate_summary.json")
    args = parser.parse_args()
    root = Path(args.results)
    runs: dict[str, dict] = {}
    for path in sorted(root.glob("*/summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "completed":
            runs[data["run_id"]] = data

    output: dict = {
        "schema_version": "model_eval_v21.aggregate.1",
        "status": "completed" if runs else "no_completed_runs",
        "claim_boundary": "10 public teaching images with a 4/3/3 split; test has 3 images; not clinical validation",
        "completed_run_count": len(runs),
        "runs": {run_id: data["metrics"] for run_id, data in runs.items()},
        "comparisons": {},
    }
    base_id = "qwen25_3b_bf16_plain_test"
    if base_id in runs:
        base = runs[base_id]["metrics"]
        quantization = {}
        for precision, run_id in {
            "bf16": base_id,
            "nf4": "qwen25_3b_nf4_plain_test",
            "int8": "qwen25_3b_int8_plain_test",
        }.items():
            if run_id not in runs:
                continue
            metrics = runs[run_id]["metrics"]
            quantization[precision] = {
                "accuracy": metrics["micro_fact_accuracy"],
                "p50_s": metrics["latency_p50_s"],
                "peak_gpu_memory_gib": metrics["peak_gpu_memory_gib"],
                "accuracy_delta": metrics["micro_fact_accuracy"] - base["micro_fact_accuracy"],
                "p50_relative_delta": pct_delta(metrics["latency_p50_s"], base["latency_p50_s"]),
                "peak_memory_relative_delta": pct_delta(metrics["peak_gpu_memory_gib"], base["peak_gpu_memory_gib"]),
            }
        output["comparisons"]["quantization"] = quantization

        for name, run_id in {
            "adapter": "qwen25_3b_bf16_adapter_test",
            "structured_prompt": "qwen25_3b_bf16_structured_test",
        }.items():
            if run_id not in runs:
                continue
            metrics = runs[run_id]["metrics"]
            output["comparisons"][name] = {
                "before_run": base_id,
                "after_run": run_id,
                "accuracy_before": base["micro_fact_accuracy"],
                "accuracy_after": metrics["micro_fact_accuracy"],
                "accuracy_delta": metrics["micro_fact_accuracy"] - base["micro_fact_accuracy"],
                "p50_before_s": base["latency_p50_s"],
                "p50_after_s": metrics["latency_p50_s"],
                "p50_relative_delta": pct_delta(metrics["latency_p50_s"], base["latency_p50_s"]),
            }
            if name == "structured_prompt":
                output["comparisons"][name]["json_valid_rate_before"] = json_valid_rate(root, base_id)
                output["comparisons"][name]["json_valid_rate_after"] = json_valid_rate(root, run_id)

    model_runs = [
        "qwen25_3b_bf16_plain_test",
        "smolvlm_256m_bf16_plain_test",
        "llava_ov_05b_bf16_plain_test",
        "qwen2_vl_2b_bf16_plain_test",
    ]
    output["comparisons"]["zero_shot_models"] = {
        run_id: {
            "model": runs[run_id]["model"],
            "accuracy": runs[run_id]["metrics"]["micro_fact_accuracy"],
            "p50_s": runs[run_id]["metrics"]["latency_p50_s"],
            "peak_gpu_memory_gib": runs[run_id]["metrics"]["peak_gpu_memory_gib"],
        }
        for run_id in model_runs
        if run_id in runs
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"completed_run_count": len(runs), "run_ids": sorted(runs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

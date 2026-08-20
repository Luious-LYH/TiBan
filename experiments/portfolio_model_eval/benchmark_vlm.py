"""Reproducible single-GPU benchmark for public endoscopy VQA teaching samples."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * p
    lo, hi = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo)


def score(answer: str, expected_facts: list[list[str]]) -> tuple[int, int, list[bool]]:
    normalized = " ".join(answer.lower().replace("-", " ").split())
    hits = [any(alias.lower().replace("-", " ") in normalized for alias in aliases) for aliases in expected_facts]
    return sum(hits), len(hits), hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--cases", default="cases.json")
    parser.add_argument("--output", default="results/latest.json")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N cases; 0 means all cases.")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    cases = json.loads((base / args.cases).read_text(encoding="utf-8"))
    if args.limit > 0:
        cases = cases[: args.limit]
    output = base / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    torch.cuda.reset_peak_memory_stats()
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda:0", local_files_only=True
    ).eval()
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)

    def infer(case: dict) -> tuple[str, float, int]:
        image_path = str((base / case["image"]).resolve())
        messages = [{"role": "user", "content": [
            {"type": "image", "image": Image.open(image_path).convert("RGB")},
            {"type": "text", "text": case["question"]},
        ]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to("cuda")
        torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        torch.cuda.synchronize()
        latency = time.perf_counter() - start
        trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
        answer = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return answer, latency, len(trimmed[0])

    for _ in range(args.warmup):
        infer(cases[0])
    torch.cuda.reset_peak_memory_stats()
    rows, latencies, total_tokens = [], [], 0
    started = time.perf_counter()
    for case in cases:
        answer, latency, tokens = infer(case)
        hit_count, fact_count, hits = score(answer, case["expected_facts"])
        rows.append({"id": case["id"], "answer": answer, "latency_s": round(latency, 4), "generated_tokens": tokens,
                     "fact_hits": hits, "fact_score": hit_count / fact_count, "source": case["source"]})
        latencies.append(latency)
        total_tokens += tokens
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    wall = time.perf_counter() - started
    result = {
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "7 public teaching images; single deterministic pass; not a clinical validation",
        "model": args.model,
        "precision": "bfloat16",
        "device": torch.cuda.get_device_name(0),
        "software": {"python": platform.python_version(), "torch": torch.__version__},
        "config": {"max_new_tokens": args.max_new_tokens, "warmup_runs": args.warmup, "do_sample": False, "batch_size": 1},
        "metrics": {
            "cases": len(rows),
            "case_exact_rate": sum(row["fact_score"] == 1.0 for row in rows) / len(rows),
            "micro_fact_accuracy": sum(sum(row["fact_hits"]) for row in rows) / sum(len(row["fact_hits"]) for row in rows),
            "latency_p50_s": statistics.median(latencies),
            "latency_p95_s": percentile(latencies, 0.95),
            "throughput_cases_per_min": len(rows) / wall * 60,
            "generation_tokens_per_s": total_tokens / sum(latencies),
            "peak_gpu_memory_gib": torch.cuda.max_memory_allocated() / 1024**3,
            "wall_time_s": wall
        },
        "cases": rows
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT_PATH=" + str(output), flush=True)


if __name__ == "__main__":
    main()

"""Unified deterministic VLM benchmark for the v2.1 portfolio evidence line."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from peft import PeftModel
from qwen_vl_utils import process_vision_info
from transformers import (
    AutoModelForVision2Seq,
    AutoProcessor,
    BitsAndBytesConfig,
    Qwen2_5_VLForConditionalGeneration,
)


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = (len(ordered) - 1) * p
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def extract_answer(raw: str) -> str:
    cleaned = raw.strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        parsed = json.loads(fenced)
        if isinstance(parsed, dict) and isinstance(parsed.get("answer"), str):
            return parsed["answer"].strip()
    except json.JSONDecodeError:
        pass
    return cleaned


def score_case(answer: str, case: dict[str, Any]) -> tuple[list[bool], float]:
    normalized = normalize(answer)
    if case.get("answer_type") == "binary":
        if re.match(r"^(yes|yes[,.:;]|there is|text is visible|text visible)", normalized):
            predicted = "yes"
        elif re.match(r"^(no|no[,.:;]|there is no|text is not visible|no text)", normalized):
            predicted = "no"
        else:
            predicted = "unknown"
        hits = [predicted == normalize(case["answer"])]
    else:
        hits = [any(normalize(alias) in normalized for alias in aliases) for aliases in case["expected_facts"]]
    return hits, sum(hits) / len(hits)


def software_versions() -> dict[str, str]:
    import accelerate
    import bitsandbytes
    import peft
    import transformers

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "accelerate": accelerate.__version__,
        "peft": peft.__version__,
        "bitsandbytes": bitsandbytes.__version__,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--family", choices=["qwen25", "auto"], default="auto")
    parser.add_argument("--precision", choices=["bf16", "nf4", "int8"], default="bf16")
    parser.add_argument("--adapter")
    parser.add_argument("--split", choices=["train", "dev", "test", "all"], default="test")
    parser.add_argument("--prompt-mode", choices=["plain", "structured"], default="plain")
    parser.add_argument("--cases", default="cases.json")
    parser.add_argument("--output-root", default="results")
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    all_cases = json.loads((base / args.cases).read_text(encoding="utf-8"))
    cases = all_cases if args.split == "all" else [item for item in all_cases if item["split"] == args.split]
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise ValueError(f"No cases selected for split={args.split}")

    quantization_config = None
    dtype = torch.bfloat16
    if args.precision == "nf4":
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    elif args.precision == "int8":
        quantization_config = BitsAndBytesConfig(load_in_8bit=True)

    load_kwargs: dict[str, Any] = {
        "device_map": "cuda:0",
        "local_files_only": True,
        "low_cpu_mem_usage": True,
    }
    if quantization_config is not None:
        load_kwargs["quantization_config"] = quantization_config
    else:
        load_kwargs["torch_dtype"] = dtype
    model_cls = Qwen2_5_VLForConditionalGeneration if args.family == "qwen25" else AutoModelForVision2Seq
    load_started = time.perf_counter()
    model = model_cls.from_pretrained(args.model, **load_kwargs).eval()
    if args.adapter:
        model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True).eval()
    model_load_s = time.perf_counter() - load_started
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)
    if hasattr(model, "generation_config"):
        model.generation_config.do_sample = False
        model.generation_config.temperature = None
        model.generation_config.top_p = None

    structured_suffix = (
        '\nReturn exactly one JSON object with schema {"answer":"<concise answer>"}. '
        "Use visible evidence only; do not repeat the question or add other keys."
    )

    def prepare(case: dict[str, Any]) -> dict[str, torch.Tensor]:
        question = case["question"] + (structured_suffix if args.prompt_mode == "structured" else "")
        image = Image.open(base / case["image"]).convert("RGB")
        if args.family == "qwen25":
            messages = [{"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": question},
            ]}]
            prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = processor(
                text=[prompt], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt"
            )
        else:
            messages = [{"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": question},
            ]}]
            prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[prompt], images=[image], padding=True, return_tensors="pt")
        return inputs.to("cuda")

    def infer(case: dict[str, Any]) -> tuple[str, float, int]:
        inputs = prepare(case)
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        torch.cuda.synchronize()
        latency = time.perf_counter() - started
        input_length = inputs["input_ids"].shape[1]
        trimmed = generated[:, input_length:]
        raw = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return raw, latency, int(trimmed.shape[1])

    for _ in range(args.warmup):
        infer(cases[0])
    torch.cuda.reset_peak_memory_stats()
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    total_tokens = 0
    wall_started = time.perf_counter()
    for case in cases:
        raw, latency, generated_tokens = infer(case)
        scored_answer = extract_answer(raw)
        hits, fact_score = score_case(scored_answer, case)
        row = {
            "id": case["id"],
            "split": case["split"],
            "source": case["source"],
            "answer_raw": raw,
            "answer_scored": scored_answer,
            "gold_answer": case["answer"],
            "fact_hits": hits,
            "fact_score": fact_score,
            "latency_s": latency,
            "generated_tokens": generated_tokens,
        }
        rows.append(row)
        latencies.append(latency)
        total_tokens += generated_tokens
        print(json.dumps(row, ensure_ascii=False), flush=True)
    wall_s = time.perf_counter() - wall_started

    run_dir = base / args.output_root / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    command = " ".join(os.sys.argv)
    summary = {
        "schema_version": "model_eval_v21.1",
        "status": "completed",
        "run_id": args.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "public teaching samples only; deterministic portfolio benchmark; not clinical validation",
        "model": args.model,
        "family": args.family,
        "precision": args.precision,
        "adapter": bool(args.adapter),
        "adapter_path_label": Path(args.adapter).name if args.adapter else None,
        "split": args.split,
        "prompt_mode": args.prompt_mode,
        "device": torch.cuda.get_device_name(0),
        "software": software_versions(),
        "config": {
            "batch_size": 1,
            "do_sample": False,
            "max_new_tokens": args.max_new_tokens,
            "warmup": args.warmup,
            "command": command,
        },
        "metrics": {
            "cases": len(rows),
            "case_exact_rate": sum(row["fact_score"] == 1.0 for row in rows) / len(rows),
            "micro_fact_accuracy": sum(sum(row["fact_hits"]) for row in rows) / sum(len(row["fact_hits"]) for row in rows),
            "latency_p50_s": statistics.median(latencies),
            "latency_p95_s": percentile(latencies, 0.95),
            "throughput_cases_per_min": len(rows) / wall_s * 60,
            "generation_tokens_per_s": total_tokens / sum(latencies) if total_tokens else 0.0,
            "peak_gpu_memory_gib": torch.cuda.max_memory_allocated() / 1024**3,
            "model_memory_footprint_gib": model.get_memory_footprint() / 1024**3,
            "model_load_s": model_load_s,
            "wall_time_s": wall_s,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY_PATH=" + str(run_dir / "summary.json"), flush=True)


if __name__ == "__main__":
    main()


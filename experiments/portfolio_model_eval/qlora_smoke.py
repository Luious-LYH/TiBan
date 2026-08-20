"""One-step QLoRA plumbing smoke test; this is not an effectiveness experiment."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from PIL import Image
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from qwen_vl_utils import process_vision_info
from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--output", default="results/qlora_smoke.json")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    case = json.loads((base / "cases.json").read_text(encoding="utf-8"))[0]
    answer = "Oesophagitis is visible with the z-line; no polyps are identified."

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_use_double_quant=True)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model, quantization_config=quant, device_map="cuda:0", local_files_only=True
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "v_proj"],
                                             task_type="CAUSAL_LM"))
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": Image.open(base / case["image"]).convert("RGB")},
            {"type": "text", "text": case["question"]},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": answer}]},
    ]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    image_inputs, video_inputs = process_vision_info(messages)
    batch = processor(text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to("cuda")
    labels = batch.input_ids.clone()
    labels[labels == processor.tokenizer.pad_token_id] = -100
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-4)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model.train()
    loss = model(**batch, labels=labels).loss
    loss.backward()
    optimizer.step()
    torch.cuda.synchronize()
    trainable, total = model.get_nb_trainable_parameters()
    result = {
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "one-example, one-step QLoRA plumbing validation only; no quality-improvement claim",
        "model": args.model,
        "quantization": "NF4 4-bit with double quantization",
        "lora": {"rank": 8, "alpha": 16, "targets": ["q_proj", "v_proj"]},
        "steps": 1,
        "examples": 1,
        "loss": float(loss.detach().cpu()),
        "elapsed_s": time.perf_counter() - started,
        "peak_gpu_memory_gib": torch.cuda.max_memory_allocated() / 1024**3,
        "trainable_parameters": trainable,
        "total_parameters": total,
        "trainable_ratio": trainable / total,
    }
    output = base / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


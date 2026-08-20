"""Ten-step train-set QLoRA sanity check; never interpret as generalization."""

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
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--output", default="results/qlora_train_sanity.json")
    parser.add_argument("--adapter-dir", default="results/adapter_sanity")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    cases = json.loads((base / "cases.json").read_text(encoding="utf-8"))

    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_use_double_quant=True)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        args.model, quantization_config=quant, device_map="cuda:0", local_files_only=True
    )
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "v_proj"],
                                             task_type="CAUSAL_LM"))
    model.config.use_cache = False
    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True)

    def make_batch(case: dict) -> dict[str, torch.Tensor]:
        user = {"role": "user", "content": [
            {"type": "image", "image": Image.open(base / case["image"]).convert("RGB")},
            {"type": "text", "text": case["question"]},
        ]}
        full_messages = [user, {"role": "assistant", "content": [{"type": "text", "text": case["gold_answer"]}]}]
        full_text = processor.apply_chat_template(full_messages, tokenize=False, add_generation_prompt=False)
        prompt_text = processor.apply_chat_template([user], tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(full_messages)
        batch = processor(text=[full_text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt").to("cuda")
        prompt = processor(text=[prompt_text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt")
        labels = batch.input_ids.clone()
        labels[:, : min(prompt.input_ids.shape[1], labels.shape[1])] = -100
        labels[labels == processor.tokenizer.pad_token_id] = -100
        batch["labels"] = labels
        return batch

    batches = [make_batch(case) for case in cases]
    model.eval()
    with torch.no_grad():
        probe_loss_before = float(model(**batches[0]).loss.detach().cpu())

    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-4)
    losses: list[float] = []
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model.train()
    for step in range(args.steps):
        optimizer.zero_grad(set_to_none=True)
        loss = model(**batches[step % len(batches)]).loss
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
        print(json.dumps({"step": step + 1, "case": cases[step % len(cases)]["id"], "loss": losses[-1]}), flush=True)
    torch.cuda.synchronize()
    model.eval()
    with torch.no_grad():
        probe_loss_after = float(model(**batches[0]).loss.detach().cpu())

    adapter_dir = base / args.adapter_dir
    model.save_pretrained(adapter_dir)
    adapter_bytes = sum(path.stat().st_size for path in adapter_dir.rglob("*") if path.is_file())
    trainable, total = model.get_nb_trainable_parameters()
    result = {
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claim_boundary": "7-example train-set, 10-step overfit sanity only; not held-out evaluation and no generalization claim",
        "model": args.model,
        "quantization": "NF4 4-bit with double quantization",
        "lora": {"rank": 8, "alpha": 16, "targets": ["q_proj", "v_proj"]},
        "steps": args.steps,
        "examples": len(cases),
        "learning_rate": 2e-4,
        "loss_history": losses,
        "fixed_probe_loss_before": probe_loss_before,
        "fixed_probe_loss_after": probe_loss_after,
        "elapsed_s": time.perf_counter() - started,
        "peak_gpu_memory_gib": torch.cuda.max_memory_allocated() / 1024**3,
        "trainable_parameters": trainable,
        "total_parameters": total,
        "trainable_ratio": trainable / total,
        "adapter_dir": str(adapter_dir),
        "adapter_size_bytes": adapter_bytes,
    }
    output = base / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

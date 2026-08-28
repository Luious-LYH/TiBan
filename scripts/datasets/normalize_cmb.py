"""Generate a gitignored normalized CMB sample."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.qbank_import_service import CMB_ROOT, _answer_letters, _option_map, _read_text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--limit", type=int, default=1500); args = parser.parse_args(); items = []
    for split, filename in (("val", "CMB-val/CMB-val-merge.json"), ("train", "CMB-train/CMB-train-merge.json"), ("test", "CMB-test/CMB-test-choice-question-merge.json")):
        path = CMB_ROOT / filename
        if not path.exists(): continue
        for index, raw in enumerate(json.loads(_read_text(path))[: (280 if split == "val" else args.limit)]):
            options, answers = _option_map(raw.get("option", {})), _answer_letters(raw.get("answer"))
            if len(options) < 2 or not answers or not set(answers).issubset(options): continue
            items.append({"source_item_id": f"{split}:{index}", "question": raw.get("question", ""), "options": options, "answer": answers, "explanation": raw.get("explanation", "") or "", "subject": raw.get("exam_subject", "")})
    output = Path(__file__).resolve().parents[2] / "data" / "normalized"; output.mkdir(parents=True, exist_ok=True)
    (output / "cmb-exam-v1.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"); print(f"normalized {len(items)} CMB items -> {output / 'cmb-exam-v1.json'}")


if __name__ == "__main__": main()

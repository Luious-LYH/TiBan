"""Generate a gitignored normalized CMExam sample."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.qbank_import_service import CMEXAM_ROOT, _answer_letters, _difficulty, _option_map  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--limit", type=int, default=1500); args = parser.parse_args()
    items = []
    with (CMEXAM_ROOT / "data" / "test_with_annotations.csv").open(encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if len(items) >= args.limit: break
            options, answers = _option_map(row.get("Options", "")), _answer_letters(row.get("Answer", ""))
            if len(options) < 2 or not answers or not set(answers).issubset(options): continue
            items.append({"source_item_id": f"test_with_annotations.csv:{index}", "question": row.get("Question", ""), "options": options, "answer": answers, "explanation": row.get("Explanation", ""), "difficulty": _difficulty(row.get("Difficulty level")), "subject": row.get("Clinical Department", ""), "topic": row.get("Disease Group", "")})
    output = Path(__file__).resolve().parents[2] / "data" / "normalized"; output.mkdir(parents=True, exist_ok=True)
    (output / "cmexam-v1.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"normalized {len(items)} CMExam items -> {output / 'cmexam-v1.json'}")


if __name__ == "__main__": main()

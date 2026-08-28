"""Classify Kvasir-VQA without changing the source dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.qbank_import_service import kvasir_classification  # noqa: E402


def main() -> None:
    records, counts = kvasir_classification()
    output = Path(__file__).resolve().parents[2] / "data" / "normalized"
    output.mkdir(parents=True, exist_ok=True)
    (output / "kvasir-vqa-classification-v1.json").write_text(json.dumps({"version": "kvasir-vqa-classification-v1", "counts": counts, "items": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"version": "kvasir-vqa-classification-v1", "counts": counts, "total": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

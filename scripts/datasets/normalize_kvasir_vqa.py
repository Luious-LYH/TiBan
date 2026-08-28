"""Write the curated Kvasir-VQA classification into normalized output."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.qbank_import_service import kvasir_classification  # noqa: E402

records, counts = kvasir_classification()
output = Path(__file__).resolve().parents[2] / "data" / "normalized"; output.mkdir(parents=True, exist_ok=True)
(output / "kvasir-vqa-v1.json").write_text(json.dumps({"counts": counts, "items": records}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"counts": counts, "total": len(records)}, ensure_ascii=False))

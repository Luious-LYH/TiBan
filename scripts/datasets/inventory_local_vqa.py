"""Read-only inventory for the local VQA datasets."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(os.getenv("ENDO_LOCAL_VQA_ROOT", r"E:\2.Projects\ARIS\VQA\data"))
PROJECT = Path(__file__).resolve().parents[2]
DATASET_METADATA = {
    "kvasir-vqa": {
        "license": "CC BY-NC 4.0",
        "source_url": "https://github.com/ENDObenchmark/Kvasir-VQA",
        "candidate_business_usage": "suitability_classified",
    },
    "kvasir-vqa-x1": {
        "license": "CC BY-NC 4.0",
        "source_url": "https://github.com/ENDObenchmark/Kvasir-VQA-x1",
        "candidate_business_usage": "generation_source",
    },
    "endobench": {
        "license": "CC BY-SA 3.0",
        "source_url": "https://github.com/medAI-NEU/EndoBench",
        "candidate_business_usage": "benchmark_only",
    },
}


def read_json(path: Path) -> list[dict]:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"cannot decode {path}")


def profile(dataset_id: str, folder: str, filename: str) -> dict:
    base, path = ROOT / folder, ROOT / folder / filename
    rows = read_json(path)
    image_paths = [str(row.get("image_path") or row.get("original_image_path") or "") for row in rows]
    def candidates(item: str) -> list[Path]:
        name = Path(item).name
        return [base / item, base / name, base / "EndoBench-Images" / name]

    resolved = [next((candidate for candidate in candidates(item) if candidate.is_file()), None) for item in image_paths]
    linked = sum(item is not None for item in resolved)
    ids = [str(row.get("id") or row.get("img_id") or "") for row in rows]
    types = Counter("yes_no" if str(row.get("answer") or row.get("gt") or "").lower() in {"yes", "no"} else "structured_answer" for row in rows)
    question_types = Counter()
    for row, answer_type in zip(rows, ("yes_no" if str(item.get("answer") or item.get("gt") or "").lower() in {"yes", "no"} else "structured_answer" for item in rows)):
        raw_type = row.get("question_type") or row.get("question_class")
        if isinstance(raw_type, (list, dict)) or (isinstance(raw_type, str) and raw_type.strip().startswith("[")):
            normalized_type = "multi_aspect_structured"
        else:
            normalized_type = str(raw_type or ("true_false" if answer_type == "yes_no" else "visual_observation"))
        question_types[normalized_type] += 1
    actual_image_files = sum(1 for suffix in ("*.jpg", "*.jpeg", "*.png", "*.webp") for _ in base.rglob(suffix))
    metadata = DATASET_METADATA[dataset_id]
    return {
        "dataset_id": dataset_id,
        "local_path": str(base),
        "json": str(path),
        "file_count": len(list(base.rglob("*"))),
        "image_file_count": actual_image_files,
        "qa_count": len(rows),
        "image_count": len({item for item in image_paths if item}),
        "image_linked_count": linked,
        "image_linkage_rate": round(linked / len(rows), 4) if rows else 0,
        "missing_assets_sample": [item for item, resolved_path in zip(image_paths, resolved) if item and resolved_path is None][:20],
        "schema": sorted({key for row in rows[:50] for key in row}),
        "question_type_counts": dict(question_types),
        "answer_type_counts": dict(types),
        "duplicate_ids": len(ids) - len(set(ids)),
        "license": metadata["license"],
        "source_url": metadata["source_url"],
        "candidate_business_usage": metadata["candidate_business_usage"],
        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    profiles = [profile("kvasir-vqa", "Kvasir-VQA", "Kvasir-VQA.json"), profile("kvasir-vqa-x1", "Kvasir-VQA-x1", "Kvasir-VQA-x1.json"), profile("endobench", "EndoBench", "EndoBench.json")]
    payload = {"root": str(ROOT), "read_only": True, "datasets": profiles}
    artifact = PROJECT / "artifacts" / "data" / "local-vqa-inventory.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    document = PROJECT / "docs" / "data" / "local-vqa-inventory.md"
    document.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Local VQA inventory", "", f"- Root: `{ROOT}`", "- Mode: read-only; source files were not moved, renamed or modified.", "", "| Dataset | QA | image files | images referenced | linked rows | linkage | duplicate IDs | candidate usage | hash |", "|---|---:|---:|---:|---:|---:|---|---|---|"]
    for item in profiles:
        lines.append(f"| {item['dataset_id']} | {item['qa_count']} | {item['image_file_count']} | {item['image_count']} | {item['image_linked_count']} | {item['image_linkage_rate']:.1%} | {item['duplicate_ids']} | `{item['candidate_business_usage']}` | `{item['content_hash'][:16]}` |")
    for item in profiles:
        lines.extend(["", f"## {item['dataset_id']}", "", f"- Local path: `{item['local_path']}`", f"- Files: `{item['file_count']}`; image files: `{item['image_file_count']}`", f"- JSON: `{item['json']}`", f"- Schema sample: `{', '.join(item['schema'])}`", f"- Question types: `{json.dumps(item['question_type_counts'], ensure_ascii=False)}`", f"- Answer types: `{json.dumps(item['answer_type_counts'], ensure_ascii=False)}`", f"- License/source: `{item['license']}` · `{item['source_url']}`", f"- Candidate business usage: `{item['candidate_business_usage']}`", f"- Missing assets sample: `{json.dumps(item['missing_assets_sample'], ensure_ascii=False)}`", "- Policy: EndoBench is `benchmark_only`; Kvasir-VQA-x1 defaults to `generation_source`; Kvasir-VQA requires suitability classification."])
    document.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

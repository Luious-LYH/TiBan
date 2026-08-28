"""Exercise the provider-backed Generator → Judge → Repair → Publish workflow.

The script makes three bounded, traceable source runs: project-authored
Markdown, a generated PDF fixture, and a locally available Kvasir-VQA-x1
generation-source record.  It never writes a key, local data path, image bytes
or model hidden reasoning to the checked-in artifact.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
import pyarrow.parquet as pq


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import LOCAL_VQA_ROOT
from app.services.data_governance import dataset_policy
from app.services.factory_service import (
    enqueue_factory_job,
    get_job,
    import_allowed_document,
    process_factory_job,
    publish_revision,
)


SAFETY = "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"


def _pdf_bytes(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(48, 48, 540, 760), text, fontsize=11)
    try:
        return document.tobytes()
    finally:
        document.close()


def _kvasir_source() -> tuple[bytes, dict[str, str]]:
    path = LOCAL_VQA_ROOT / "Kvasir-VQA-x1" / "data" / "test-00000-of-00001.parquet"
    if not path.is_file():
        raise FileNotFoundError("Kvasir-VQA-x1 test parquet is required for the provider acceptance run")
    rows = pq.read_table(path).to_pylist()
    if not rows:
        raise ValueError("Kvasir-VQA-x1 test parquet is empty")
    row = next((item for item in rows if str(item.get("question") or "").strip() and str(item.get("answer") or item.get("gt") or "").strip()), rows[0])
    question = str(row.get("question") or "").strip()
    answer = str(row.get("answer") or row.get("gt") or "").strip()
    source_item_id = str(row.get("id") or row.get("question_id") or "kvasir-x1-test-0")
    # The image remains in the configured local data root. The Factory sees
    # only this registered textual generation-source evidence, never a path or
    # raw image payload, and must preserve its image-lineage limitation.
    markdown = f"""# Kvasir-VQA-x1 生成源样例

## 数据集语义证据

该样例来自 Kvasir-VQA-x1 的 evaluation-excluded generation source。题目文本：{question}

原始标注答案：{answer}

该记录用于生成资料溯源练习；图像仍仅保留在受控本地数据目录中，文字题干和标注并不构成独立临床诊断。{SAFETY}
"""
    return markdown.encode("utf-8"), {"source_item_id": source_item_id, "dataset": "Kvasir-VQA-x1"}


def _sources() -> list[dict[str, Any]]:
    project_text = f"""# 上消化道内镜观察资料

## 证据边界

教学记录应区分可见部位、表面形态和仍需病理或完整病史确认的内容。单次图像观察不能替代完整临床判断。{SAFETY}
"""
    # Keep the generated PDF text ASCII so the fixture does not depend on a
    # host-specific CJK font being embedded by PyMuPDF.
    pdf_text = """Endoscopy teaching reading exercise

Preserve visible location and morphology clues. If the evidence is incomplete,
do not independently confirm a cause or diagnosis. This material is for
teaching or physician review before use, not an independent diagnostic basis.
"""
    kvasir_content, kvasir_meta = _kvasir_source()
    kvasir_policy = dataset_policy("kvasir-vqa-x1")
    return [
        {
            "kind": "markdown",
            "filename": "stage3-provider-source.md",
            "content": project_text.encode("utf-8"),
            "content_type": "text/markdown",
            "source_id": "project-curated-gastro-v1",
            "source_uri": "https://www.niddk.nih.gov/health-information/diagnostic-tests/upper-gi-endoscopy",
            "license_gate_status": "allow_noncommercial",
            "ai_ingestion_allowed": True,
        },
        {
            "kind": "pdf",
            "filename": "stage3-provider-source.pdf",
            "content": _pdf_bytes(pdf_text),
            "content_type": "application/pdf",
            "source_id": "project-curated-gastro-v1",
            "source_uri": "https://www.niddk.nih.gov/health-information/diagnostic-tests/upper-gi-endoscopy",
            "license_gate_status": "allow_noncommercial",
            "ai_ingestion_allowed": True,
        },
        {
            "kind": "kvasir_vqa_x1_generation_source",
            "filename": "stage3-kvasir-x1-generation-source.md",
            "content": kvasir_content,
            "content_type": "text/markdown",
            "source_id": "kvasir-vqa-x1",
            "source_uri": kvasir_policy.source_url,
            "license_gate_status": "allow_noncommercial",
            "ai_ingestion_allowed": True,
            "source_meta": kvasir_meta,
        },
    ]


def _public_revision(job: dict[str, Any]) -> dict[str, Any]:
    revisions = list(job["revisions"])
    latest = revisions[-1] if revisions else {}
    return {
        "revision_id": latest.get("revision_id"),
        "parent_revision_id": latest.get("parent_revision_id"),
        "status": latest.get("status"),
        "source_chunk_ids": latest.get("source_chunk_ids", []),
        "draft": latest.get("draft", {}),
        "judge": latest.get("judge", {}),
        "rewrite_instruction": latest.get("rewrite_instruction"),
    }


def main() -> None:
    runs: list[dict[str, Any]] = []
    for source in _sources():
        document = import_allowed_document(
            source["filename"],
            source["content"],
            source["content_type"],
            source_id=source["source_id"],
            source_uri=source["source_uri"],
            business_usage="factory_source",
            license_gate_status=source["license_gate_status"],
            ai_ingestion_allowed=source["ai_ingestion_allowed"],
        )
        queued = enqueue_factory_job(document["document_id"])
        result = process_factory_job(queued["job_id"], provider_mode="provider")
        job = get_job(queued["job_id"])
        revision = _public_revision(job)
        published: dict[str, str] | None = None
        if job["status"] == "ready_for_review" and revision.get("revision_id"):
            published = publish_revision(queued["job_id"], str(revision["revision_id"]))
            job = get_job(queued["job_id"])
        runs.append(
            {
                "source_kind": source["kind"],
                "source_id": source["source_id"],
                "source_uri": source["source_uri"],
                "source_meta": source.get("source_meta", {}),
                "document_id": document["document_id"],
                "job_id": queued["job_id"],
                "result": result,
                "status": job["status"],
                "revision": _public_revision(job),
                "published": published,
            }
        )
    artifact = {
        "artifact_version": "factory-provider-acceptance-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_mode": "provider",
        "fallback": False,
        "safety": "No API key, raw chain-of-thought, local absolute path, raw image bytes or patient data is retained.",
        "runs": runs,
        "passed": all(item["status"] == "published" for item in runs),
    }
    target = PROJECT_ROOT / "artifacts" / "factory"
    target.mkdir(parents=True, exist_ok=True)
    (target / "factory-provider-acceptance-v1.json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"passed": artifact["passed"], "runs": [{"kind": item["source_kind"], "status": item["status"]} for item in runs]}, ensure_ascii=False))
    if not artifact["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

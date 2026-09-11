"""Evaluate the bundled figure-caption retrieval fixture against a live index.

This script never writes source data or evaluation artifacts. It resolves the
currently registered document by its stable source ID, so opaque runtime asset
IDs are not baked into the fixture or repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import SourceDocumentModel
from app.services.rag_service import rag_service


FIXTURE = ROOT / "app" / "data" / "multimodal_knowledge_eval_v35.json"
NOISE_TERMS = {"article", "review", "port", "logo"}


def _load_fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ValueError("评测集未包含 Figure 图文查询。")
    return value


def _registered_document(source_id: str) -> SourceDocumentModel | None:
    with SessionLocal() as session:
        return session.scalar(select(SourceDocumentModel).where(
            SourceDocumentModel.source_id == source_id,
            SourceDocumentModel.enabled.is_(True),
            SourceDocumentModel.business_usage == "knowledge_base",
        ))


def run(*, strict: bool) -> int:
    fixture = _load_fixture()
    source_id = str(fixture["source_id"])
    domain_id = str(fixture["domain_id"])
    document = _registered_document(source_id)
    state = rag_service.image_index_state()
    if document is None:
        print(json.dumps({"status": "not_ready", "reason": "默认图文资料尚未登记"}, ensure_ascii=False))
        return 2 if strict else 0
    if state.get("status") != "ready":
        print(json.dumps({"status": "not_ready", "reason": "图片向量索引未就绪", "image_index": state}, ensure_ascii=False))
        return 2 if strict else 0

    rows: list[dict[str, object]] = []
    for case in fixture["cases"]:
        assert isinstance(case, dict)
        result = rag_service.retrieve_multimodal(str(case["query"]), limit=3, domain_id=domain_id)
        images = list(result.get("image_results") or [])
        expected_caption = str(case["expected_caption_contains"])
        expected_page = int(case["expected_page"])
        matching = [item for item in images if expected_caption.lower() in str(item.get("caption") or "").lower()]
        image_hit = bool(matching)
        page_match = any(int(item.get("page") or 0) == expected_page for item in matching)
        linked_chunk_ids = {str(item.get("linked_chunk_id") or "") for item in matching} - {""}
        text_backlink = any(getattr(citation, "chunk_id", "") in linked_chunk_ids for citation in result.get("citations") or [])
        meaningless_node = any(
            any(term in str(path.get("from") or "").lower() or term in str(path.get("to") or "").lower() for term in NOISE_TERMS)
            for path in result.get("graph_paths") or []
        )
        rows.append({
            "id": case["id"],
            "image_hit_at_3": image_hit,
            "caption_page_correct": image_hit and page_match,
            "text_to_image_link": image_hit and any("caption_concept_graph" in list(item.get("retrieval_channels") or []) for item in matching),
            "image_to_text_link": image_hit and text_backlink,
            "meaningless_graph_node": meaningless_node,
        })

    total = len(rows)
    summary = {
        "status": "ready",
        "source": document.name,
        "cases": total,
        "image_recall_at_3": round(sum(bool(row["image_hit_at_3"]) for row in rows) / total, 3),
        "caption_page_accuracy": round(sum(bool(row["caption_page_correct"]) for row in rows) / total, 3),
        "text_to_image_link_rate": round(sum(bool(row["text_to_image_link"]) for row in rows) / total, 3),
        "image_to_text_link_rate": round(sum(bool(row["image_to_text_link"]) for row in rows) / total, 3),
        "meaningless_graph_nodes": sum(bool(row["meaningless_graph_node"]) for row in rows),
        "details": rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    passed = (
        summary["image_recall_at_3"] == 1.0
        and summary["caption_page_accuracy"] == 1.0
        and summary["text_to_image_link_rate"] == 1.0
        and summary["image_to_text_link_rate"] == 1.0
        and summary["meaningless_graph_nodes"] == 0
    )
    return 0 if passed or not strict else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="评估默认 Figure 图文检索证据链")
    parser.add_argument("--strict", action="store_true", help="未达到全部预期时返回非零退出码")
    args = parser.parse_args()
    sys.exit(run(strict=args.strict))

"""Run a small, reproducible multimodal-RAG quality/latency benchmark.

The benchmark is intentionally read-only.  It uses the caption/page fixture
without copying source images or persisting runtime asset IDs.  Its numbers are
engineering measurements for the current local corpus, not clinical claims.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import SourceDocumentModel
from app.services.rag_service import rag_service


FIXTURE = ROOT / "app" / "data" / "multimodal_knowledge_eval_v35.json"
NOISE_TERMS = {"article", "review", "port", "logo", "header", "footer"}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 2)


def _fixture() -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if not isinstance(payload.get("cases"), list) or not payload["cases"]:
        raise ValueError("评测集未包含 Figure 图文查询。")
    return payload


def _document(source_id: str) -> SourceDocumentModel | None:
    with SessionLocal() as session:
        return session.scalar(select(SourceDocumentModel).where(
            SourceDocumentModel.source_id == source_id,
            SourceDocumentModel.enabled.is_(True),
            SourceDocumentModel.business_usage == "knowledge_base",
        ))


def _noise_free(paths: list[dict[str, object]]) -> bool:
    return not any(
        term in f"{path.get('from', '')} {path.get('to', '')}".lower()
        for path in paths
        for term in NOISE_TERMS
    )


def run(*, strict: bool) -> int:
    fixture = _fixture()
    source = _document(str(fixture["source_id"]))
    image_state = rag_service.image_index_state()
    if source is None:
        report = {"status": "not_ready", "reason": "默认图文资料尚未登记"}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if strict else 0
    if image_state.get("status") != "ready":
        report = {"status": "not_ready", "reason": "图片向量索引未就绪", "image_index": image_state}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if strict else 0

    cases: list[dict[str, object]] = []
    cold_text_ms: list[float] = []
    warm_text_ms: list[float] = []
    cold_multimodal_ms: list[float] = []
    warm_multimodal_ms: list[float] = []
    for raw_case in fixture["cases"]:
        if not isinstance(raw_case, dict):
            continue
        query = str(raw_case["query"])
        started = perf_counter()
        rag_service.retrieve(query, mode="hybrid", limit=3, domain_id=str(fixture["domain_id"]))
        cold_text_ms.append((perf_counter() - started) * 1000)
        started = perf_counter()
        rag_service.retrieve(query, mode="hybrid", limit=3, domain_id=str(fixture["domain_id"]))
        warm_text_ms.append((perf_counter() - started) * 1000)
        started = perf_counter()
        result = rag_service.retrieve_multimodal(query, limit=3, domain_id=str(fixture["domain_id"]))
        cold_multimodal_ms.append((perf_counter() - started) * 1000)
        # Repeat the same query to measure the steady-state path after the
        # provider/model and bounded retrieval cache are warm.  The first
        # result remains the source for correctness checks below.
        started = perf_counter()
        rag_service.retrieve_multimodal(query, limit=3, domain_id=str(fixture["domain_id"]))
        warm_multimodal_ms.append((perf_counter() - started) * 1000)

        images = list(result.get("image_results") or [])
        expected_caption = str(raw_case["expected_caption_contains"])
        expected_page = int(raw_case["expected_page"])
        matching = [item for item in images if expected_caption.lower() in str(item.get("caption") or "").lower()]
        linked_ids = {str(item.get("linked_chunk_id") or "") for item in matching} - {""}
        citations = list(result.get("citations") or [])
        text_backlink = any(getattr(citation, "chunk_id", "") in linked_ids for citation in citations)
        cases.append({
            "id": raw_case.get("id"),
            "image_hit_at_3": bool(matching),
            "caption_page_correct": bool(matching) and any(int(item.get("page") or 0) == expected_page for item in matching),
            "text_to_image_link": bool(matching) and any("caption_concept_graph" in list(item.get("retrieval_channels") or []) for item in matching),
            "image_to_text_link": bool(matching) and text_backlink,
            "graph_noise_free": _noise_free(list(result.get("graph_paths") or [])),
        })

    total = len(cases)
    def rate(key: str) -> float:
        return round(sum(bool(case[key]) for case in cases) / total, 3) if total else 0.0

    summary = {
        "status": "ready",
        "source": source.name,
        "sample_count": total,
        "quality": {
            "image_recall_at_3": rate("image_hit_at_3"),
            "caption_page_accuracy": rate("caption_page_correct"),
            "text_to_image_link_rate": rate("text_to_image_link"),
            "image_to_text_link_rate": rate("image_to_text_link"),
            "graph_noise_free_rate": rate("graph_noise_free"),
        },
        "latency_ms": {
            "text_retrieval_cold_p50": _percentile(cold_text_ms, 0.50),
            "text_retrieval_cold_p95": _percentile(cold_text_ms, 0.95),
            "text_retrieval_warm_p50": _percentile(warm_text_ms, 0.50),
            "text_retrieval_warm_p95": _percentile(warm_text_ms, 0.95),
            "multimodal_evidence_cold_p50": _percentile(cold_multimodal_ms, 0.50),
            "multimodal_evidence_cold_p95": _percentile(cold_multimodal_ms, 0.95),
            "multimodal_evidence_warm_p50": _percentile(warm_multimodal_ms, 0.50),
            "multimodal_evidence_warm_p95": _percentile(warm_multimodal_ms, 0.95),
        },
        "throughput": {
            "text_queries_per_second_warm": round(1000 / statistics.mean(warm_text_ms), 2) if warm_text_ms and statistics.mean(warm_text_ms) > 0 else 0.0,
            "multimodal_queries_per_second_warm": round(1000 / statistics.mean(warm_multimodal_ms), 2) if warm_multimodal_ms and statistics.mean(warm_multimodal_ms) > 0 else 0.0,
        },
        "index": {
            "image_provider": image_state.get("provider"),
            "image_model": image_state.get("model"),
            "graph": "caption-and-controlled-concept one-hop evidence graph",
        },
        "cases": cases,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    passed = all(value == 1.0 for value in summary["quality"].values())
    return 0 if passed or not strict else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="评测当前多模态 RAG 的证据质量和检索时延")
    parser.add_argument("--strict", action="store_true", help="质量项未全部通过时返回非零退出码")
    args = parser.parse_args()
    sys.exit(run(strict=args.strict))

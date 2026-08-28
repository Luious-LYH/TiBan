"""Run the frozen Corpus v1 RAG benchmark without modifying v1 evidence."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median
from time import perf_counter


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal
from app.db.models import DocumentVersionModel
from app.services.rag_service import MODEL_NAME, RERANK_MODEL, rag_service


CORPUS_ID = "knowledge-corpus-v1"
FIXTURE = PROJECT_ROOT / "docs" / "fixtures" / "retrieval-eval-v2.json"


def _percentile(values: list[float], percentile: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * percentile) - 1)]


def _version_ids(document_ids: list[str], label: str) -> list[str]:
    with SessionLocal() as session:
        rows = list(
            session.query(DocumentVersionModel)
            .filter(DocumentVersionModel.document_id.in_(document_ids), DocumentVersionModel.version_label == label)
            .order_by(DocumentVersionModel.document_id)
        )
    if len(rows) != len(document_ids):
        raise RuntimeError(f"expected {len(document_ids)} indexed documents for {label}, found {len(rows)}")
    return [row.version_id for row in rows]


def _evaluate(dataset: list[dict[str, object]], version_ids: list[str], mode: str) -> dict[str, object]:
    ranks: list[int | None] = []
    latencies: list[float] = []
    cases: list[dict[str, object]] = []
    for item in dataset:
        started = perf_counter()
        hits = rag_service.retrieve(str(item["query"]), mode, limit=10, version_ids=version_ids)  # type: ignore[arg-type]
        elapsed = (perf_counter() - started) * 1000
        relevant = set(item["relevant_document_ids"])
        rank = next((index + 1 for index, hit in enumerate(hits) if hit.document_id in relevant), None)
        ranks.append(rank)
        latencies.append(elapsed)
        cases.append(
            {
                "id": item["id"],
                "rank": rank,
                "latency_ms": round(elapsed, 2),
                "returned": [
                    {
                        "document_id": hit.document_id,
                        "chunk_id": hit.chunk_id,
                        "section": hit.section,
                        "page": hit.page,
                        "source_uri": hit.source_uri,
                    }
                    for hit in hits
                ],
            }
        )
    count = len(dataset)
    relevant_ranks = [rank for rank in ranks if rank is not None]
    return {
        "sample_count": count,
        "recall_at_5": round(sum(rank <= 5 for rank in relevant_ranks) / count, 4),
        "recall_at_10": round(len(relevant_ranks) / count, 4),
        "mrr": round(sum(1 / rank for rank in relevant_ranks) / count, 4),
        "ndcg_at_5": round(sum(1 / math.log2(rank + 1) for rank in relevant_ranks if rank <= 5) / count, 4),
        "p50_latency_ms": round(median(latencies), 2),
        "p95_latency_ms": round(_percentile(latencies, 0.95), 2),
        "cases": cases,
    }


def _index(document_ids: list[str], child_size: int) -> list[str]:
    manifest = json.loads((PROJECT_ROOT / "knowledge" / "corpus-v1" / "manifest.json").read_text(encoding="utf-8"))
    # The primary 180-character corpus was indexed by the corpus command
    # already.  Reuse its immutable version label rather than creating a
    # second label for identical bytes; the 280 setting is the ablation arm.
    version_label = (
        "knowledge-corpus-v1-child-180"
        if child_size == 180
        else f"{CORPUS_ID}-child-{child_size}-benchmark-v2"
    )
    for item in manifest["documents"]:
        rag_service.index_markdown(
            PROJECT_ROOT / item["path"],
            document_id=item["document_id"],
            child_size=child_size,
            namespace=item["namespace"],
            source_id=item["source_id"],
            source_uri=item["source_url"],
            business_usage="knowledge_base",
            license_gate_status="allow",
            ai_ingestion_allowed=True,
            version_label=version_label,
        )
    return _version_ids(document_ids, version_label)


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture["source_corpus"] != CORPUS_ID:
        raise ValueError("RAG v2 fixture targets an unexpected corpus")
    test = [item for item in fixture["queries"] if item["split"] == "test"]
    document_ids = sorted({document_id for item in fixture["queries"] for document_id in item["relevant_document_ids"]})
    versions_180 = _index(document_ids, 180)
    versions_280 = _index(document_ids, 280)
    primary_modes = ["sparse", "dense", "hybrid", "hybrid_rerank"]
    results = {
        "artifact_version": "retrieval-eval-v2-artifact-v1",
        "dataset_version": fixture["dataset_version"],
        "dataset_hash": fixture["dataset_hash"],
        "review_policy": fixture["review_policy"],
        "embedding": {"provider": "fastembed", "model": MODEL_NAME, "dimension": 512, "normalization": "L2"},
        "reranker": {"provider": "sentence-transformers", "model": RERANK_MODEL, "status": "measured"},
        "primary": {
            "child_size": 180,
            "version_count": len(versions_180),
            "test": {mode: _evaluate(test, versions_180, mode) for mode in primary_modes},
        },
        "chunking_ablation": {
            "comparison": "heading-aware parent + child 180 vs heading-aware parent + child 280",
            "child_180_hybrid": _evaluate(test, versions_180, "hybrid"),
            "child_280_hybrid": _evaluate(test, versions_280, "hybrid"),
        },
    }
    artifact = PROJECT_ROOT / "artifacts" / "rag" / "retrieval-eval-v2.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": artifact.as_posix(), "primary_modes": primary_modes, "test_count": len(test)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

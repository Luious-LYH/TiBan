"""Reproducible frozen RAG benchmark and chunking ablation."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.database import SessionLocal
from app.db.models import KnowledgeChunkModel
from app.services.rag_service import MODEL_NAME, RERANK_MODEL, rag_service


def _percentile(values: list[float], pct: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * pct) - 1)]


def _evaluate(dataset: list[dict[str, str]], version_id: str, modes: list[str]) -> dict[str, object]:
    output: dict[str, object] = {}
    for mode in modes:
        ranks: list[int | None] = []
        latencies: list[float] = []
        cases = []
        for item in dataset:
            started = perf_counter()
            hits = rag_service.retrieve(item['query'], mode, limit=5, version_id=version_id)  # type: ignore[arg-type]
            elapsed = (perf_counter() - started) * 1000
            rank = next((index + 1 for index, hit in enumerate(hits) if hit.section == item['relevant_section']), None)
            ranks.append(rank); latencies.append(elapsed)
            cases.append({**item, 'rank': rank, 'returned': [{'chunk_id': h.chunk_id, 'section': h.section} for h in hits], 'latency_ms': round(elapsed, 2)})
        matched = [rank for rank in ranks if rank]
        output[mode] = {
            'recall_at_5': round(len(matched) / len(dataset), 4),
            'mrr': round(sum(1 / rank for rank in matched) / len(dataset), 4),
            'ndcg_at_5': round(sum(1 / math.log2(rank + 1) for rank in matched) / len(dataset), 4),
            'p50_latency_ms': round(median(latencies), 2), 'p95_latency_ms': round(_percentile(latencies, .95), 2), 'cases': cases,
        }
    return output


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    frozen = json.loads((root / 'docs' / 'fixtures' / 'retrieval-eval-v1.json').read_text(encoding='utf-8'))
    source = root / 'docs' / 'fixtures' / 'endoscopy-teaching-source-v1.md'
    results: dict[str, object] = {
        'dataset_version': frozen['dataset_version'], 'query_count': len(frozen['queries']), 'split': frozen['split'], 'curation': frozen['curation'],
        'embedding': {'provider': 'fastembed', 'model': MODEL_NAME, 'dimension': 512, 'normalization': 'L2'},
        'reranker': {'provider': 'sentence-transformers', 'model': RERANK_MODEL, 'license': 'Apache-2.0'}, 'ablations': {},
    }
    for child_size in (180, 280):
        chunk_ids = rag_service.index_markdown(source, document_id='source-stage2-endoscopy-v1', child_size=child_size)
        with SessionLocal() as session:
            row = session.get(KnowledgeChunkModel, chunk_ids[0]); assert row is not None
            version_id = row.version_id
        test_queries = [item for item in frozen['queries'] if item['split'] == 'test']
        modes = ['sparse', 'dense', 'hybrid', 'hybrid_rerank'] if child_size == 180 else ['hybrid_rerank']
        results['ablations'][str(child_size)] = {'version_id': version_id, 'chunk_count': len(chunk_ids), 'test': _evaluate(test_queries, version_id, modes)}
    output = root / 'artifacts' / 'rag'; output.mkdir(parents=True, exist_ok=True)
    (output / 'retrieval-eval-v1.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

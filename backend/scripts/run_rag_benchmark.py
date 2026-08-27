from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from time import perf_counter

from app.services.rag_service import rag_service


DATASET = [
    {'query': '食管检查要先记录哪些可见证据', 'relevant': 'chunk-6e1cbb202f2a-180-00', 'topic': '食管'},
    {'query': '单帧内镜图像为什么不能作临床诊断', 'relevant': 'chunk-6e1cbb202f2a-180-00', 'topic': '安全'},
    {'query': '胃黏膜训练需要描述什么', 'relevant': 'chunk-6e1cbb202f2a-180-01', 'topic': '胃'},
    {'query': '结直肠复盘如何表达不确定性', 'relevant': 'chunk-6e1cbb202f2a-180-02', 'topic': '结直肠'},
    {'query': '错题复盘有哪些核心信息', 'relevant': 'chunk-6e1cbb202f2a-180-03', 'topic': '复习'},
    {'query': '信息不足时报告应该怎么写', 'relevant': 'chunk-6e1cbb202f2a-180-01', 'topic': '胃'},
    {'query': '选择题应该如何回到题干证据', 'relevant': 'chunk-6e1cbb202f2a-180-02', 'topic': '结直肠'},
    {'query': '系统输出的教学安全边界是什么', 'relevant': 'chunk-6e1cbb202f2a-180-03', 'topic': '安全'},
]


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    modes = ['sparse', 'dense', 'hybrid', 'hybrid_rerank']
    results = {'dataset_version': 'retrieval-eval-v1', 'query_count': len(DATASET), 'modes': {}}
    for mode in modes:
        ranks, latencies = [], []
        cases = []
        for item in DATASET:
            started = perf_counter(); hits = rag_service.retrieve(item['query'], mode, limit=4); elapsed = (perf_counter() - started) * 1000
            ids = [hit.chunk_id for hit in hits]; rank = ids.index(item['relevant']) + 1 if item['relevant'] in ids else None
            ranks.append(rank); latencies.append(elapsed); cases.append({**item, 'rank': rank, 'returned': ids, 'latency_ms': round(elapsed, 2)})
        hits = [rank for rank in ranks if rank]
        results['modes'][mode] = {'recall_at_4': round(len(hits) / len(DATASET), 4), 'mrr': round(sum(1 / rank for rank in hits) / len(DATASET), 4), 'ndcg_at_4': round(sum(1 / __import__('math').log2(rank + 1) for rank in hits) / len(DATASET), 4), 'p50_latency_ms': round(median(latencies), 2), 'p95_latency_ms': round(sorted(latencies)[max(0, int(len(latencies) * .95) - 1)], 2), 'cases': cases}
    output = root / 'artifacts' / 'rag'; output.mkdir(parents=True, exist_ok=True)
    (output / 'retrieval-eval-v1.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()

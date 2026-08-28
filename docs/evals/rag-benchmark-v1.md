# Retrieval benchmark v1

`retrieval-eval-v1` is frozen at 50 manually authored and checked Chinese queries over the project-licensed teaching source: 20 development queries and 30 held-out test queries. Each query has a manually verified relevant parent section and plausible neighbouring sections as hard negatives. It does not use an LLM to generate queries, label relevance, or judge itself.

Runtime: PostgreSQL 16 for source state, Qdrant 1.13.2 for the index, FastEmbed `BAAI/bge-small-zh-v1.5` (512 dimensions, L2 normalization), and `cross-encoder/ms-marco-MiniLM-L6-v2` (Apache-2.0) for learned reranking. Full per-case ranks and latency are in [`artifacts/rag/retrieval-eval-v1.json`](../../artifacts/rag/retrieval-eval-v1.json).

## Frozen test split results (30 queries)

| Chain / child size | Recall@5 | MRR | nDCG@5 | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| Sparse / 180 | 1.00 | 0.95 | 0.96 | 62.56 | 76.28 |
| Dense / 180 | 0.97 | 0.88 | 0.90 | 185.44 | 248.13 |
| Hybrid (RRF) / 180 | 1.00 | 0.94 | 0.96 | 198.49 | 236.53 |
| Hybrid + learned rerank / 180 | 0.73 | 0.58 | 0.62 | 658.96 | 1714.41 |
| Hybrid + learned rerank / 280 | 0.73 | 0.58 | 0.62 | 609.14 | 914.82 |

## Decision and chunking ablation

The 180-child configuration yields more compact citation units; the reranker is intentionally retained as a negative result: it is a real cross-encoder invocation, but its English training makes it a poor selector for this Chinese benchmark and materially increases tail latency. Tutor therefore defaults to 180-character RRF Hybrid, rather than claiming a false rerank improvement. This small evaluation supports only that local design decision; it is not a clinical or production-quality metric. The reported `*-identity-v2` version contains exactly 21 (180) / 20 (280) chunks and is isolated from historical chunk-ID versions, so duplicate historical records cannot influence these metrics.

## Reproduction

```powershell
cd code
docker compose -p endotutor-stage2 -f compose.stage2-services.yml --profile stage2-rag up -d
cd backend
$env:ENDO_DATABASE_URL = 'postgresql+psycopg://endotutor_dev:endotutor_dev_only@127.0.0.1:55432/endotutor_stage1'
$env:QDRANT_URL = 'http://127.0.0.1:6333'
python scripts/run_rag_benchmark.py
```

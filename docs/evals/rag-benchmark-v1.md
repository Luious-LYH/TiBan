# Retrieval benchmark v1

## Frozen dataset

`retrieval-eval-v1` has 8 manually written Chinese teaching queries against one project-licensed Markdown teaching source, four heading-aware chunks, and manually assigned relevant chunk IDs. It is intentionally a small smoke benchmark, not a production retrieval claim. The dataset and per-case ranks are frozen in `artifacts/rag/retrieval-eval-v1.json`.

## Runtime

- relational metadata/state: PostgreSQL 16
- vector index: Qdrant 1.13.2, local Docker
- dense embedding: `BAAI/bge-small-zh-v1.5` through FastEmbed, 512 dimensions, L2-normalized
- sparse: deterministic Chinese character-bigram overlap
- hybrid: reciprocal-rank fusion
- hybrid+rerank: RRF plus transparent lexical evidence boost; it is not described as a learned reranker

## Results (Recall@4 / MRR / nDCG@4 / P50-P95 ms)

| Chain | Recall@4 | MRR | nDCG@4 | P50 | P95 |
|---|---:|---:|---:|---:|---:|
| Sparse | 1.0000 | 1.0000 | 1.0000 | 12.01 | 12.84 |
| Dense | 1.0000 | 0.8542 | 0.8914 | 129.32 | 170.84 |
| Hybrid | 1.0000 | 1.0000 | 1.0000 | 100.22 | 102.67 |
| Hybrid + rerank | 1.0000 | 1.0000 | 1.0000 | 102.32 | 112.96 |

The corpus is only four chunks, so all rows are saturated at Recall@4. This artifact demonstrates real Qdrant + real embedding integration and a repeatable metric path; it does **not** justify a general quality-improvement claim. The dense chain’s weaker rank on wording such as “信息不足” is retained as a failure case in the artifact.

## Chunk ablation

The chosen 180-character child configuration keeps citation units compact enough for the Tutor sidecar. A 280-character configuration is a planned benchmark input but has not been independently evaluated; no selection claim is made from it.

## Reproduction

```powershell
cd code/backend
$env:ENDO_DATABASE_URL = 'postgresql+psycopg://…@127.0.0.1:55432/endotutor_stage1'
$env:PYTHONPATH = '.'
python -c "from app.services.rag_service import rag_service; from pathlib import Path; rag_service.index_markdown(Path('../docs/fixtures/endoscopy-teaching-source-v1.md'), child_size=180)"
python scripts/run_rag_benchmark.py
```

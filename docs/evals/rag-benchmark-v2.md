# RAG Benchmark v2

## Scope

`retrieval-eval-v2-candidate-2026-08-28` freezes 90 Chinese learner-style
retrieval queries over Knowledge Corpus v1: 30 development and 60 held-out
test queries. Corpus v1 contains 45 license-gated, EndoTutor-authored Chinese
teaching summaries derived from NIDDK public-health material; its PostgreSQL
and Qdrant index has 271 chunks at the 180-character setting.

This artifact is reproducible with `python scripts/knowledge/build_retrieval_eval_v2.py`,
`python backend/scripts/index_knowledge_corpus_v1.py`, and
`python backend/scripts/run_rag_benchmark_v2.py`. The benchmark source and
exact result are retained separately in `artifacts/rag/retrieval-eval-v2.json`.

## Primary results (60 held-out queries)

| Chain | Recall@5 | Recall@10 | MRR | nDCG@5 | P50 | P95 |
|---|---:|---:|---:|---:|---:|---:|
| Sparse | 0.7667 | 0.8000 | 0.7437 | 0.7462 | 35.83 ms | 44.09 ms |
| Dense | 0.8833 | 0.9000 | 0.8138 | 0.8297 | 182.01 ms | 242.43 ms |
| Hybrid RRF | 0.7167 | 0.7667 | 0.6635 | 0.6723 | 181.33 ms | 238.47 ms |
| Hybrid + rerank | 0.9000 | 0.9500 | 0.8243 | 0.8383 | 1062.82 ms | 1307.94 ms |

Dense uses `fastembed` / `BAAI/bge-small-zh-v1.5` (512 dimensions, L2
normalization). The reranker is the existing `cross-encoder/ms-marco-MiniLM-L6-v2`.
Every returned evidence record preserves chunk, document, section, page and
source URL lineage. EndoBench is excluded by the data-governance boundary.

## Chunking ablation

Heading-aware parent plus child-180 produced Hybrid MRR 0.6635 / nDCG@5 0.6723;
child-280 produced MRR 0.7017 / nDCG@5 0.6982. This is a small engineering
ablation, not a clinical study.

## Default decision and limitation

The Stage 1 Tutor default is **Dense**. Sparse wins the small development
screen, but the frozen held-out verification reverses that ordering; Dense is
the stronger non-reranked generalization trade-off while avoiding the
substantial tail latency of hybrid+rerank. Sparse, Hybrid RRF and Hybrid +
Rerank remain available as benchmark/diagnostic paths. The decision artifact
is [`retrieval-default-decision-v1.json`](../../artifacts/rag/retrieval-default-decision-v1.json).

Reranking is measurable evidence with a substantial latency cost, not an
automatic product-default change. The candidate fixture is explicitly marked
`human_review_status: pending`; therefore these figures may support an
engineering benchmark claim, but not an externally stated human-adjudicated
effectiveness claim.

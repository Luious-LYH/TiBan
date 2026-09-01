# Hybrid RAG pipeline

```text
Allowed Markdown/PDF → heading-aware parse → PostgreSQL SourceDocument / DocumentVersion / KnowledgeChunk
  → FastEmbed BAAI/bge-small-zh-v1.5 (512, L2) → Qdrant 1.13.2
  → sparse | dense | RRF hybrid | hybrid + learned cross-encoder rerank
  → Citation(document, page, section, chunk)
```

PostgreSQL is the canonical relational source for hashes, parser/version lineage and citations. Qdrant stores retrieval vectors only. The Tutor product path pins the frozen 180-character benchmarked document version; historical index versions remain available for reproducible benchmarks but cannot mix into user citations.

Sparse scoring uses Chinese character bigram overlap. Dense scoring uses the real `BAAI/bge-small-zh-v1.5` embedding model through FastEmbed. Hybrid applies RRF. The fourth benchmark chain uses the learned Apache-2.0 `cross-encoder/ms-marco-MiniLM-L6-v2`, not a lexical boost.

The frozen `retrieval-eval-v2` benchmark contains 90 candidates (30
development and 60 held-out test). On the held-out set, sparse reached
Recall@5 0.7667, dense 0.8833, hybrid 0.7167 and hybrid+rerank 0.9000; the
reranker P50 was 1062.82 ms. Sparse won the development screen but did not
generalize to the held-out fixture, so the Tutor default is **Dense**.
The English-trained cross-encoder is retained as a measured comparison/high-
value path. These are portfolio benchmark results, not clinical effectiveness
claims.

User-facing source cards expose only source name, page and section plus a short snippet. Internal vector IDs and scores do not appear in the UI. Generated questions reuse the same SourceDocument/KnowledgeChunk relation.

## Curated corpus boundary

`knowledge/` is an independent curated corpus, not a QBank. The first accepted notes are five project-curated Chinese teaching documents in the `endoscopy` namespace. PostgreSQL remains the canonical source registry, license gate and citation graph; Qdrant contains only approved, non-benchmark chunks. Logical namespaces currently include `medical_general`, `gastroenterology`, `endoscopy`, `qbank_explanations`, `factory_sources` and `user_uploaded`.

EndoBench is evaluation-only. Its source IDs are not eligible for Tutor retrieval, Question Factory evidence or direct QBank import. The current v2 Docker acceptance record is [`artifacts/platform/docker-acceptance-v2.json`](../../artifacts/platform/docker-acceptance-v2.json); it keeps evaluation datasets outside the Tutor-indexed question-bank flow.

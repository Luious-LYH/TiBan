# Hybrid RAG pipeline

```text
Allowed Markdown/PDF → heading-aware parse → PostgreSQL SourceDocument / DocumentVersion / KnowledgeChunk
  → FastEmbed BAAI/bge-small-zh-v1.5 (512, L2) → Qdrant 1.13.2
  → sparse | dense | RRF hybrid | hybrid + learned cross-encoder rerank
  → Citation(document, page, section, chunk)
```

PostgreSQL is the canonical relational source for hashes, parser/version lineage and citations. Qdrant stores retrieval vectors only. The Tutor product path pins the frozen 180-character benchmarked document version; historical index versions remain available for reproducible benchmarks but cannot mix into user citations.

Sparse scoring uses Chinese character bigram overlap. Dense scoring uses the real `BAAI/bge-small-zh-v1.5` embedding model through FastEmbed. Hybrid applies RRF. The fourth benchmark chain uses the learned Apache-2.0 `cross-encoder/ms-marco-MiniLM-L6-v2`, not a lexical boost.

The 50-query benchmark showed the English-trained cross-encoder is weaker and slower on this small Chinese teaching corpus, so the default Tutor route is **Hybrid**, while the reranker remains implemented and recorded as a failure/selection artifact. This is a measured trade-off, not a capability claim.

User-facing source cards expose only source name, page and section plus a short snippet. Internal vector IDs and scores do not appear in the UI. Generated questions reuse the same SourceDocument/KnowledgeChunk relation.

## Stage 2.5 corpus boundary

`knowledge/` is an independent curated corpus, not a QBank. The first accepted notes are five project-curated Chinese teaching documents in the `endoscopy` namespace. PostgreSQL remains the canonical source registry, license gate and citation graph; Qdrant contains only approved, non-benchmark chunks. Logical namespaces currently include `medical_general`, `gastroenterology`, `endoscopy`, `qbank_explanations`, `factory_sources` and `user_uploaded`.

EndoBench is evaluation-only. Its source IDs are not eligible for Tutor retrieval, Question Factory evidence or direct QBank import. The compact runtime proof is [`artifacts/stage-2.5/gate-results-v1.json`](../../artifacts/stage-2.5/gate-results-v1.json), which records zero EndoBench Qdrant points and zero direct user-ready rows.

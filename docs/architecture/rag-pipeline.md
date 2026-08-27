# Hybrid RAG pipeline

```text
Allowed source document -> heading-aware parser -> PostgreSQL DocumentVersion/KnowledgeChunk
  -> FastEmbed BAAI/bge-small-zh-v1.5 -> Qdrant 1.13.2
  -> sparse | dense | RRF hybrid | hybrid lexical rerank
  -> Citation(document, page, section, chunk)
```

PostgreSQL owns source metadata, content hashes, parsing lineage and citation records. Qdrant holds only dense index payload needed for retrieval. User-facing citations expose document name, page and section rather than vector IDs or internal scores.

The source path has MIME/extension validation planned for the Factory upload boundary; current benchmark source is an explicitly checked-in project teaching document. See [benchmark evidence](../evals/rag-benchmark-v1.md).

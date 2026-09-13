# Hybrid RAG pipeline

```text
Allowed Markdown/PDF → heading-aware parse → PostgreSQL SourceDocument / DocumentVersion / KnowledgeChunk
  → SiliconFlow/OpenAI-compatible BGE-M3 Embedding Provider → Qdrant
  → sparse | dense | RRF hybrid | hybrid + learned cross-encoder rerank
  → Citation(document, page, section, chunk)
```

PostgreSQL is the canonical relational source for hashes, parser/version lineage and citations. Qdrant stores retrieval vectors only. The Tutor product path pins the frozen 180-character benchmarked document version when a benchmark version is explicitly requested; ordinary product retrieval is filtered to the newest canonical version of each enabled source. Historical versions remain available for audit/reproducibility but cannot mix into current user citations.

Sparse scoring uses Chinese character bigram overlap. The online/default dense path
uses `BAAI/bge-m3` through the configured SiliconFlow/OpenAI-compatible Embedding
Provider. Self-hosted installations can explicitly use the lazy local FastEmbed
fallback. Hybrid applies RRF; the optional reranking path uses the configured
`BAAI/bge-reranker-v2-m3` Provider boundary and is not a lexical boost.

The frozen `retrieval-eval-v2` benchmark contains 90 candidates (30
development and 60 held-out test). On the held-out set, sparse reached
Recall@5 0.7667, dense 0.8833, hybrid 0.7167 and hybrid+rerank 0.9000; the
reranker P50 was 1062.82 ms. Sparse won the development screen but did not
generalize to the held-out fixture, so the Tutor default is **Dense**.
The English-trained cross-encoder is retained as a measured comparison/high-
value path. These are portfolio benchmark results, not clinical effectiveness
claims.

User-facing source cards expose only source name, page and section plus a short snippet. Internal vector IDs and scores do not appear in the UI. Generated questions reuse the same SourceDocument/KnowledgeChunk relation. The product retrieval query applies the same relational eligibility and latest-version gate before dense Qdrant filtering, so stale vector points cannot re-enter through sparse retrieval.

## V3.5.2 多模态性能与质量记录

文字检索和图像检索使用有界 candidate pool；重排只处理候选集。Qdrant 对
`document_id`、`domain_id`、`namespace`、`version_id` 建立 payload index，
图片集合额外索引 `concepts`；索引写入采用批量 embedding/upsert。在线查询的
检索投影使用有界短 TTL 进程缓存，资料启停、重建、删除或索引版本变化会使缓存
失效，缓存不保存图片字节、API Key 或原始文件路径。

多模态质量由固定 Figure caption 样本评估 Image Recall@3、图注/页码准确率、
文字到图片和图片到文字关联率、图谱噪声过滤率；性能记录文字检索和完整图文
证据包的 P50/P95 以及热查询吞吐。可执行脚本为
`backend/scripts/benchmark_multimodal_rag.py`，它只读当前本机资料和索引，
不会把本地指南、运行时资产或评测结果写回仓库。

## Curated corpus boundary

`knowledge/` is an independent curated corpus, not a QBank. The first accepted notes are five project-curated Chinese teaching documents in the `endoscopy` namespace. PostgreSQL remains the canonical source registry, license gate and citation graph; Qdrant contains only approved, non-benchmark chunks. Logical namespaces currently include `medical_general`, `gastroenterology`, `endoscopy`, `qbank_explanations`, `factory_sources` and `user_uploaded`.

EndoBench is evaluation-only. Its source IDs are not eligible for Tutor retrieval, Question Factory evidence or direct QBank import. The current v2 Docker acceptance record is [`artifacts/platform/docker-acceptance-v2.json`](../../artifacts/platform/docker-acceptance-v2.json); it keeps evaluation datasets outside the Tutor-indexed question-bank flow.

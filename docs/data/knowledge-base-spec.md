# Knowledge Base specification

Knowledge documents carry frontmatter with `title`, `language`, `domain`, `source_ids`, `curation_type`, `review_status` and `updated_at`. Source Registry entries carry license status, AI-ingestion permission, attribution and update metadata.

Runtime storage remains the existing relational lineage plus Qdrant index:

`SourceDocument → DocumentVersion → KnowledgeChunk → Qdrant point`

The Qdrant payload and relational row both carry `namespace`. Evaluation data has no allowed Tutor namespace. User-facing citations show title, page/section and snippet; vector IDs and scores remain developer detail.

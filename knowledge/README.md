# TiBan Knowledge Base

`knowledge/` is the independent reference corpus for Tutor and Question Factory. It is not a question bank and it never receives EndoBench benchmark items.

Only documents whose registry entry passes the License Gate may be indexed. The first checked-in corpus is project-curated Chinese teaching notes. Each note includes `source_ids`, a review status and a clear non-diagnostic boundary. External pages and books remain metadata-only until their individual reuse terms are verified.

Runtime mapping reuses `SourceDocument`, `DocumentVersion`, `KnowledgeChunk` and the Qdrant collection. The `namespace` field separates the Medical / Endoscopy pack (`medical_general`, `gastroenterology`, `endoscopy`, `qbank_explanations`, `factory_sources`, `user_uploaded`) from the General Science pack (`general_science`).

`EndoBench` is evaluation-only and is blocked from Tutor RAG, Question Factory and QBank import. ARC Easy is a local-only General QBank importer source and is also blocked from RAG and Factory. Medical output remains `仅供教学研修或医生复核前辅助，不作为独立诊断依据。`

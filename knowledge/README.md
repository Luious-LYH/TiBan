# TiBan Knowledge Base

`knowledge/` is the independent reference corpus for Tutor and Question Factory. It is not a question bank and it never receives EndoBench benchmark items.

首次启动时，系统会自动登记 `samples/image-documentation-gastrointestinal-endoscopy.pdf`，并将其复制到本机运行时目录后解析文字、提取图片、建立图片索引和资料关联。解析会将有效 Figure 与最近图注、页码、章节和对应文字片段绑定；logo、页眉及无图注图片不会进入图片检索。知识库页面的“系统资料”中可以直接查看“消化道内镜图像记录建议”及其解析预览；如果本机未启动向量服务，页面会如实显示索引提示，但不会影响资料本身的保存与查看。

Only documents whose registry entry passes the License Gate may be indexed. The bundled guide is used under its recorded CC BY-NC-ND 4.0 terms for a non-commercial teaching example, with attribution and DOI retained in the source record. Project-curated Chinese teaching notes may also include `source_ids`, a review status and a clear non-diagnostic boundary. External pages and books remain metadata-only until their individual reuse terms are verified.

Runtime mapping reuses `SourceDocument`, `DocumentVersion`, `KnowledgeChunk` and the Qdrant collection. The `namespace` field separates the Medical / Endoscopy pack (`medical_general`, `gastroenterology`, `endoscopy`, `qbank_explanations`, `factory_sources`, `user_uploaded`) from the General Science pack (`general_science`).

`EndoBench` is evaluation-only and is blocked from Tutor RAG, Question Factory and QBank import. ARC Easy is a local-only General QBank importer source and is also blocked from RAG and Factory. Medical output remains `仅供教学研修或医生复核前辅助，不作为独立诊断依据。`

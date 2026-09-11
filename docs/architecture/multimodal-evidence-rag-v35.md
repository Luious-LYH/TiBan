# 多模态资料证据链

TiBan 的多模态知识能力用于学习资料的图文检索与可追溯辅导，不用于独立临床诊断。

## 数据流

```text
受许可 PDF
  → PyMuPDF 版面块 + 图片位置
  → Figure 图注对齐、MIME/文件头/尺寸校验
  → 受控本地媒体资产 + PostgreSQL 图文关系
  ├─ BGE-M3：文字混合检索
  ├─ CLIP：文字到图片检索（Qdrant）
  └─ 受控概念图：一跳文字 ↔ Figure 证据扩展
  → 资料图片、图注、页码、文字出处
  → Tutor / Mentor 的 OpenAI-compatible 视觉内容块
```

图片字节保存在受控运行时目录；数据库、Qdrant payload、任务和日志只保存不透明资产 ID、哈希和必要元数据。图片必须通过 MIME、文件头、大小、像素与路径检查。重新解析资料时，图片索引会先清除该资料对应的旧向量，再写入本次通过图注校验的资产，避免 logo 或旧页面装饰被重新召回。

## 检索与证据关联

检索使用三条互补通道：BGE-M3 文字混合召回、CLIP 文字到图片召回，以及受控概念图中的一跳图文关系。概念表仅包含当前支持的内镜教学术语和中英文别名，例如“结肠镜 / colonoscopy”“回盲瓣 / ileocecal valve”；它不从 PDF 页眉、OCR 残词或任意关键词生成实体。

当图片的图注概念与查询匹配，或图片与已命中的文字证据同页时，系统加入有限、可解释的关联加分。该加分是来源关联信号，不是模型置信度。每个图片结果都保留其 CLIP 通道、图注概念通道和对应文字片段；Tutor/Mentor 将这些真实图片 URL 作为视觉输入传给支持视觉的 Provider。视觉模型不可用时，Agent 返回 `vision_not_supported`，不会丢弃图片后假装已阅读。

## 默认示例与评测

默认示例资料为 Marques 等人的 *Image Documentation in Gastrointestinal Endoscopy: Review of Recommendations*（DOI: `10.1159/000477739`，CC BY-NC-ND 4.0），其署名和许可说明保留在 `knowledge/samples/README.md`。原始图片不作为仓库中的评测数据分发。

`backend/app/data/multimodal_knowledge_eval_v35.json` 仅记录四个 Figure caption 查询、预期页码和图注标记，不包含图片字节或运行时资产 ID。启动 Docker/Qdrant 并完成默认资料索引后，可以运行：

```powershell
cd code/backend
$env:PYTHONPATH='.'
python scripts/evaluate_multimodal_knowledge.py --strict
```

脚本报告 Image Recall@3、图注/页码正确率、文字到图片与图片到文字的关联率，并检查结果中不存在 `article`、`review`、`port`、`logo` 等无意义图谱节点。它不写入资料、索引或评测产物。

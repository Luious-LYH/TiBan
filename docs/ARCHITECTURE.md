# TiBan Architecture

本文描述当前 V3.2 有效运行路径。早期 V1/V2 技术演进仅保留在 Git 历史中
追溯，不作为当前产品入口。

---

## 当前主线

```text
题库 → Practice Session → 作答/评分 → Attempt → Mastery/FSRS
                                      │
                                      └→ Memory Reflection → Learning Memory

Practice / 智能辅导                         带教 Agent
当前 session、当前题目、按需资料检索          跨 session 学习状态与持久对话
```

## 后端模块

- `question_service`: 题库读取和筛选。
- `grading_service`: 规则评分、错因标签、atomic feedback、下一题推荐。
- `AgentRunner` + `ToolRegistry`: 唯一的受控 Agent 运行时；智能辅导只读取当前 Practice session 和当前 Tutor thread，带教 Agent 使用独立的长期上下文构建器。
- `report_service`: 报告草稿、报告修改评分和科普卡片；报告输出 `source_trace`、`evidence_ledger`、`generation_mode`，上传图片会把 `image_upload` 审计 ID/hash/尺寸绑定回报告证据台账，科普卡片生成草稿并通过同一 `card_id` 完成审核开放，输出 `review_status`、`share_status` 和审核步骤。
- `llm_provider`: OpenAI-compatible `/chat/completions` 适配器；只允许公开样例图片和 `runtime/uploads` 受控图片进入视觉输入。
- `mentor_agent_service`: 跨 session 读取学习总览、最近作答、FSRS 复习队列、题库进度、Learning Memory 和按需 Knowledge RAG，并持久化带教对话。
- `memory_reflection_service`: 从已持久化的 session evidence 生成并校验 ADD/UPDATE/RESOLVE/NOOP 候选，再写入结构化 Learning Memory。
- `semantic_memory_service`: 使用独立的可重建 Qdrant memory index 做有边界的长期记忆召回。
- `model_service`: 模型库与样例级 blind probe 准入检查；最多 3 个公开样例逐条返回 evidence，Provider prompt 不包含参考标注，返回后再做粗粒度公开标注对齐。
- `audit_service`: 关键事件持久化到 JSON。
- `safety_service`: 越界和敏感表达规则检查。

## 当前前端入口

- `/`: 学习总览；
- `/banks`、`/banks/:bankId`: 题库和题库详情；
- `/practice`: Practice、作答、复盘和常驻智能辅导；
- `/review`: 错题与复习；
- `/mentor`: 带教 Agent；
- `/knowledge`: 知识库；
- `/factory`: 题库导入与题目生成；
- `/eval`: 模型评测；
- `/settings`: 实例级智能服务设置。

## 数据与后台任务

Attempt、Mastery、FSRS、原始知识源和 Learning Memory 保存在 PostgreSQL；
Qdrant 只保存可重建的 Knowledge / Learning Memory 派生索引；Redis/Dramatiq
负责题库导入、知识索引、Memory Reflection 和向量索引重建。

在线默认 Embedding 为 SiliconFlow/OpenAI-compatible API 的 `BAAI/bge-m3`，
自托管可显式切换到 lazy local FastEmbed。Provider 或模型变化时索引先标记
`stale`，重建完成前不查询旧向量空间。

检索执行领域、命名空间、资料资格、相关性门禁和同章节去重；没有足够证据时
返回 0 条，题目来源不会冒充知识库 Citation。

## 医疗安全边界

- 所有模型输出都是医生审核前教学辅助，不签发最终诊断。
- 公开样例标注不写入“医生输入所见”，只作为 `public_sample_annotation` 来源。
- 报告页上传图片保存到 `backend/runtime/uploads`，不会提交 git；Provider 只读取受控目录中的图片。上传成功会写 `image_upload` 审计收据，报告生成会回填同一 `audit_log_id`/hash/尺寸；科普卡片页本机上传图只做浏览器预览，不写入后端卡片记录。
- 模型准入不保存 API key，不在审计日志输出密钥。

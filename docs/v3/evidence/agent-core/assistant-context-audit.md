# 辅导智能体上下文审计

审计日期：2026-08-31。此表只记录已审阅的输入边界与真实本地 SSE 行为；不记录密钥、完整 system prompt 或原始推理。

| Context | Source | When Available | Used By |
|---|---|---|---|
| 当前题目、题干、公开选项、领域、知识点、公开来源 | `stage1_service.public_question()` | 所有辅导请求 | `get_question_context`；不含 pre-submit 答案 key |
| 当前学习会话 | `/api/v3/practice/sessions` 持久化 membership | 进入刷题后 | Practice 获取题目；辅导请求携带当前 `question_id` 与 `mode` |
| 用户作答与评分 | `AttemptModel`，`attempt_id` | 仅提交后 | `get_grading_result`；审计实测 `attempt_c5bcf33ecc88` 返回 score/correct/error tags |
| 正确答案与官方解析 | `QuestionModel.grading_payload` / explanation | 仅 Study + pre-submit | `get_answer_explanation`；Exam 与 Review pre-submit 不在允许工具集合中 |
| 检索资料 | `rag_service.retrieve()` → Qdrant | 辅导请求包含提示、解释、依据等触发词且索引命中 | `retrieve_knowledge`，SSE `source` 事件；只有非 `question_source` namespace 才在 UI 标为“参考资料” |
| 题目公开来源 | question `source_dataset` / `citation_note` | 当 RAG 无命中时 | SSE 协议的真实 provenance fallback；前端不再把它渲染为检索 citation |
| 学习概览 | `stage1_service.overview()` | 所有辅导请求 | `get_learning_profile`，只提供已完成、到期复习、薄弱点摘要 |
| Learning Memory | `learning_memory_service.retrieve_relevant()` | 提示、复习、混淆、历史等意图或提交后 | `get_learning_memory`；按 learner/domain/topic 限制，最多 3 条 |
| 近期错误 | `AttemptModel` + `QuestionModel` | 错题/历史/薄弱意图 | `get_recent_mistakes`，只读且不含 selected answer / grading payload |
| 多轮对话 | 前端最近 12 条 user/assistant turn | 每次 stream 请求 | `AgentContext.metadata.conversation`，用于延续已见证据范围 |

## 已实测行为

- Study pre-submit “直接告诉我答案”：服务端选择 `get_answer_explanation`，返回当前真实 CMExam 题的公开正确选项与解析。
- Exam pre-submit 同样请求：允许工具中不含 `get_answer_explanation`，返回解题方向而非答案。
- Post-submit “为什么我错了”：`get_grading_result` 收到真实 attempt，回复中出现本次得分 0。
- 显式混淆 “甲类目录和乙类目录”：创建 `memory_f3e56d235db0`；后续同题追问选择该 memory，SSE trace 为 `selected_memory_ids=[memory_f3e56d235db0]`、`personalization_reason=current_topic_match`。

## 重要边界

本次 CMExam Hero 的 `retrieve_knowledge` 调用真实执行，但该题在当前受治理 Qdrant 索引中没有相关 chunk 命中；SSE 仅返回题目公开来源 fallback。UI 已禁止将这类 provenance fallback 标为“参考资料”。因此，“中文 CMExam 四选项题 + 真正 RAG citation”尚未达成，不能以该 Hero 证明 RAG 命中能力。

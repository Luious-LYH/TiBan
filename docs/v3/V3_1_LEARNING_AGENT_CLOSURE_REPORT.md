# TiBan V3.1 — 功能闭环与 Learning Agent 重构报告

日期：2026-09-02
分支：`refactor/v3-tiban-agent-experience`

本轮严格按 Batch A → Batch B → Batch C 推进。范围只覆盖学习闭环、真实知识库和 Agent 体验；没有增加 Dashboard、图表、多 Agent、GraphRAG、账号、语音或新的题库业务。

## 总结

| Batch | 结论 | 核心证据 |
| --- | --- | --- |
| A — 学习业务闭环 | PASS | CMExam 主题库、题库详情/状态、完整复习页、极速客观题提交 |
| B — Knowledge | PASS | 真 PDF/Markdown 上传与索引生命周期、启停/重建/删除、真实 Qdrant 0-hit 行为 |
| C — Learning Agent | PASS（仍有质量边界） | 智能辅导的受控工具路由、真实 SSE/Citation、带教 Agent 的持久化跨会话学习计划 |

## Batch A — 学习业务闭环

- 面向学习者的目录仅保留正式的 CMExam 中文医学综合题库；CMB-Exam、ARC、低价值 fixture、Factory 草稿和测试题库不再作为可学习题库出现。
- 新增题库详情与真实状态浏览：全部、未做、已做、错题、标记。题目标记写入真实学习状态。
- 恢复完整的“错题与复习”：基于 Attempt 与 FSRS Review Queue 的到期/错题/标记投影，可创建真实复习 session。
- Practice 显示所属题库，恢复轻量题单；删除大 metadata 区、左下提示、AI 解析 CTA 和缺失解析时的假解析。题库本身未提供官方解析时显示“暂无解析”。
- 客观题提交不调用 LLM、RAG、Embedding 或全量题目刷新。热态 20 次 CMExam 提交的实测结果：

  - client p50 `203.226 ms`，p95 `226.25 ms`
  - server p50 `200.678 ms`，p95 `223.548 ms`

截图：

- [题库](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/01-banks-1440.png)
- [题库详情](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/02-bank-detail-1440.png)
- [Practice](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/03-practice-1440.png)
- [提交反馈](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/04-practice-feedback-1440.png)
- [复习中心](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/05-review-1440.png)
- [复习 Session 中的 Practice Shell](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/06-review-practice-1440.png)
- [题库：1440×900 viewport 复核](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/07-banks-1440x900.png)
- [Practice：1440×900 viewport 复核](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/08-practice-1440x900.png)
- [复习中心：1440×900 viewport 复核](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-a/09-review-1440x900.png)

## Batch B — 真实 Knowledge 生命周期

路由：`/knowledge`。

真实 API：

```text
GET    /api/v3/knowledge/sources
POST   /api/v3/knowledge/sources
GET    /api/v3/knowledge/sources/{document_id}
PATCH  /api/v3/knowledge/sources/{document_id}
POST   /api/v3/knowledge/sources/{document_id}/reindex
DELETE /api/v3/knowledge/sources/{document_id}
```

支持 PDF、DOCX、Markdown、TXT。处理链路为 `upload → parse → chunk → FastEmbed → Qdrant → ready`，没有 mock 成功状态。

当前受治理资料：

- `CMExam 官方解析库`：180 条官方解析，190 个片段，`qbank_explanations` namespace；
- `Open RN Health Alterations · Heart Failure`：用户提供 PDF 的真实章节，36 个片段，保留出处与 PDF 页码。

已验证：上传 Markdown、索引、启停、重建、删除；`heart failure` 能返回 Open RN 真实内容；`marine biology octopus cephalopod` 返回 0 条 Citation。

本轮最终复核还通过当前真实 API 跑了一次独立生命周期：带唯一标识的 Markdown 被实际上传并解析为 `2` 个片段、停用为 `disabled`、重新索引后恢复为 `ready / 2` 个片段，随后 API 删除该来源及其索引。该临时来源已清理，未被保留为演示资料。

为避免“为了展示 RAG 而引用”，检索现在要求至少两个非指令性词法锚点。对于 CMExam 当前题“既补肝肾，又安胎的药是”，资料库没有直接条目，因此真实返回 0 条，不引用语义上相邻但无关的药物解析。

截图：

- [知识库：我的资料](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-b/01-knowledge-library-1440.png)
- [知识库：系统资料与真实预览](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-b/02-knowledge-system-sources-1440.png)
- [知识库：1440×900 viewport 复核](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-b/03-knowledge-1440x900.png)

## Batch C — 智能辅导与带教 Agent

### 智能辅导

用户界面统一称为“智能辅导”。当前题上下文是工作区 context，不伪装成工具调用或 Citation。

路由规则：

- `黄体生成素是什么？`、`牛顿是谁？`、`为什么当前题的 B 不对？`：零工具；
- `根据我上传的资料解释……`：仅调用 `retrieve_knowledge`；
- 个人学习历史问题：只读最近错题、Learning Memory、学习概况；
- 提交后：可读取本次评分结果；
- 考试模式保持答案权限边界。

修复的关键边界：

1. 资料请求不再把当前题来源或题目 provenance 伪装为 Citation；
2. 0-hit 是有效结果；
3. 未提交时，即便用户要求资料，也不能从模型常识直接说出正确选项；只能给比较思路；
4. 输出 guard 移除 Markdown 标题、空来源、内部字段、`csv:行号` 和模板式“仅供教学”尾注；
5. Sidecar 独立滚动、sticky composer、流式 activity 汇总、来源按文档/章节去重。

真实浏览器验证：对 CMExam 当前题发送“根据资料解释当前题考点，并给出来源。”，SSE 真正执行资料检索，正确显示“已启用资料中没有直接匹配条目”，没有 Citation，也没有在未提交时泄露答案。

截图：[智能辅导 0-hit 与未提交答案边界](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-c/02-practice-assistant-zero-hit-1440.png)

### 带教 Agent

新增 `/coach` 与 Agent 导航项“带教 Agent”。它不建立第二套模型或向量库，复用现有 Provider、AgentRunner、SSE、Learning Memory、Attempt、Review Queue、题库进度与 Knowledge。

持久化模型：`AgentConversationModel`、`AgentMessageModel`。API：

```text
GET  /api/v3/coach/conversations
POST /api/v3/coach/conversations
GET  /api/v3/coach/conversations/{conversation_id}
POST /api/v3/coach/conversations/{conversation_id}/stream
```

真实工具集：`get_learning_summary`、`get_recent_attempts`、`get_review_queue`、`get_bank_progress`、`get_learning_memories`、`search_knowledge`。

真实浏览器中询问“我今天应该先复习什么？”后，Agent 返回基于 `11` 道今日作答、`2` 项到期复习和中医科弱项的计划；UI 显示“已读取题库进度 · 已读取学习概况 · 已读取复习队列”。修复了原先 Review DTO 错读 `title` 导致该工具失败的问题，改读真实的 `question_summary`。

截图：

- [带教 Agent：持久对话与知识库](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-c/01-coach-1440.png)
- [带教 Agent：真实学习计划](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-c/03-coach-learning-plan-1440.png)
- [带教 Agent：1440×900 viewport 复核](/E:/2.Projects/ARIS/Endoscopy_Agent/code/docs/v3/evidence/v3-1/batch-c/04-coach-1440x900.png)

## 验证结果

已通过：

```text
backend: python -m compileall app
backend: pytest -q tests/test_v31_knowledge.py tests/test_v31_agent_routing.py tests/test_tutor_agent_v1.py
                  tests/test_stage1_contracts.py::test_objective_submit_emits_timing_and_never_touches_llm_or_retrieval
                  tests/test_stage1_contracts.py::test_v31_bank_progress_marks_and_review_are_unique_question_projections
         18 passed
frontend: npm test -- --run    17 passed
frontend: npm run lint         passed
frontend: npm run build        passed
git diff --check               passed（仅 CRLF 提示）
```

最终完整后端回归的 JUnit 结果为：`92 tests, 0 failures, 0 errors, 1 skipped`，总耗时 `44.972s`；控制台结论为 `91 passed, 1 skipped`。其中新增的 V3.1 格式解析契约覆盖 PDF、DOCX、Markdown、TXT 四种允许上传类型。该 JUnit XML 是本机运行时证据，处在 Git 忽略范围内。

`npm run api:check` 已重新执行。`api:generate` 成功，并生成与当前后端 OpenAPI 一致的 `src/api/generated.ts`；随后脚本按约定将该文件与 Git `HEAD` 比较。由于 V3.1 新增的题库状态、复习、知识库和带教 Agent 接口及其生成客户端仍在本轮未提交的 working tree 中，比较返回非零。它反映的是待提交的 V3.1 API 变更，不是重新生成后的 schema drift，也没有手工编辑 generated 文件。

## Remaining limitations / 后续边界

- Open RN 当前资料为英文 Heart Failure 章节。中文问题到英文资料的结果宁可为 0-hit，也不为跨语言相似性制造 Citation；如需中文跨语言检索，应以真实双语资料或受治理别名完成，不应由模型编造翻译片段。
- 资料库只有当前两类高质量资料；带教 Agent 会基于它们和真实学习记录工作，不宣称覆盖所有医学主题。
- 开放问答 AI 评分、XLSX、Anki `.apkg`、完整 Agent 策略评测均不在 V3.1 范围内。

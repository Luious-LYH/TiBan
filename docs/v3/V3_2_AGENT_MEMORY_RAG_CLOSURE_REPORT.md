# TiBan V3.2 — Agent Memory & RAG Closure Report

日期：2026-09-03
分支：`refactor/v3-tiban-agent-experience`
版本：`3.2.0`

## 结论

**V3.2 的代码与离线回归验收通过。** 本次只收口 Agent 边界、Practice 会话、长期学习记忆与可重建检索索引；没有增加新的学习业务页面、部署配置或第二套 Agent 架构。

在线基础设施验收是单独的运行环境前置条件：本机 Docker Desktop Linux Engine 在本次验收时未运行，因此没有将 SiliconFlow、Qdrant、Redis/Dramatiq 的在线成功伪称为已验证。Compose 定义已通过静态校验；上线或本地 Compose 启动后应执行本报告末尾的 Online Smoke Test。

## 产品边界

| 能力 | 最终职责 | 不承担的职责 |
| --- | --- | --- |
| 智能辅导 / Tutor Agent | Practice 右侧、当前 Practice Session、当前题/作答/评分权限、受治理 Knowledge RAG | 不读取跨会话 Learning Memory、FSRS 队列、无关历史作答或 Mentor 历史 |
| 带教 Agent / Mentor Agent | 跨会话学习回顾、Attempt/Mastery/FSRS、Review Queue、Learning Memory、知识库与持久对话 | 不直接写 Attempt、Mastery 或 FSRS |

Coach 已迁移为 Mentor：活跃路由为 `/mentor` 和 `/api/v3/mentor/*`，服务为 `mentor_agent_service.py`。旧数据库中的 `agent_profile="coach"` 通过迁移/SQLite 兼容路径升级为 `mentor`，不会丢失既有对话。

## Practice 与 Tutor 生命周期

- `PracticeSession` 保存题目集合、模式、进度、状态、活动时间及 reflection checkpoint。
- 创建新 Session、换题库或换题量会 abandon 旧活跃 Session，并关闭旧 Tutor thread。
- 同一 Session 内切题保留当前 Tutor thread；恢复 Session 恢复题目进度，但创建新的 Tutor thread，不自动带回旧对话上下文。
- 旧 Tutor thread 请求 SSE 会返回 `409`，避免跨 Session 或恢复后的错误上下文复用。
- 客观题提交保持确定性同步：不会等待 LLM、RAG 或 Embedding。
- `pagehide` 与 `visibilitychange` 只发送 best-effort checkpoint；Attempt、进度、对话事件已在正常交互中持久化，服务端 `last_active_at` 与 dirty checkpoint 负责遗漏关闭事件后的恢复。

主要实现：

- `backend/app/services/practice_session_service.py`
- `backend/app/services/tutor_session_service.py`
- `backend/app/routers/practice.py`
- `frontend/src/pages/practice/PracticePage.tsx`

## Learning Memory Reflection

确定性业务事实先写入 PostgreSQL：`Attempt → Mastery → FSRS`。随后由 `memory_reflection_service.py` 在 Session 完成、替换/放弃、显式困惑或 inactivity reconciliation 等条件下调度异步 Reflection。

Reflection 使用 `reflection:{session_id}:{version}` 幂等标识；候选 ADD/UPDATE/RESOLVE/NOOP 必须通过 learner/session 归属、evidence reference、支持性和安全语义校验。Learning Memory 的 PostgreSQL 文本与结构化字段是 canonical source，Qdrant 仅承载可重建的语义索引。

## Embedding、RAG 与 Knowledge

- 默认在线 Embedding：SiliconFlow OpenAI-compatible API，`BAAI/bge-m3`。
- 默认 reranker 目标：`BAAI/bge-reranker-v2-m3`；本地 FastEmbed 作为 lazy fallback。
- Knowledge 与 Learning Memory 使用分离 collection：`tiban_knowledge_v32`、`tiban_learning_memory_v32`。
- Settings 的 test/apply/restore 会真实更新 runtime-scoped 配置；Embedding 变更会将两类派生索引标为 stale，并通过后台 job 重建。
- Knowledge 展示与检索只取 document 的最新 canonical version；`stage7-*` 旧 corpus 已逻辑退役，数据库资格过滤会阻止残留向量进入召回。

主要实现：

- `backend/app/services/embedding_provider.py`
- `backend/app/services/rag_service.py`
- `backend/app/services/semantic_memory_service.py`
- `backend/app/services/knowledge_service.py`
- `backend/app/services/runtime_settings_service.py`
- `backend/app/workers/background_worker.py`

## API、数据库与 Worker

- 新增迁移：`backend/alembic/versions/e8f4c2a9b316_v32_agent_memory_runtime.py`。
- OpenAPI 已通过 `npm run api:generate` 重新生成 `frontend/src/api/generated.ts`，没有手工维护 generated client。
- `docker-compose.yml` 的 Worker 同时注册 `app.workers.factory_worker` 与 `app.workers.background_worker`，Factory、Knowledge indexing、Memory Reflection 和 vector rebuild 共用 Redis/Dramatiq 调度。

## 自动化验证

本次 V3.2 专项覆盖位于 `backend/tests/test_v32_agent_boundaries.py`，包含：

- 恢复练习创建新 Tutor thread、关闭旧 thread、旧 SSE 请求返回 `409`；
- 新 Practice Session abandon 旧 Session；
- 客观题提交不调用 LLM/RAG；
- Knowledge 仅投影最新 canonical version；
- SiliconFlow `BAAI/bge-m3` 默认 Provider；
- Knowledge/Memory collection 物理分离。

前端 `frontend/src/test/core-pages.test.tsx` 额外覆盖 `pagehide` / `visibilitychange` checkpoint 仅为 best-effort 行为。

| 命令 | 结果 |
| --- | --- |
| `python -m compileall app` | PASS |
| `python -m pytest -q` | PASS：94 passed, 1 skipped |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS：20 passed |
| `npm run build` | PASS |
| `npm run api:generate` | PASS |
| `docker compose config -q` | PASS |
| `git diff --check` | PASS（仅 CRLF warning） |

`npm run api:check` 的脚本包含 `git diff --exit-code -- src/api/generated.ts`。当前 V3.2 的 OpenAPI 与 generated client 尚处于未提交工作树，所以它会将这份合法的待提交 generated diff 视为非零结果；不是生成失败或 schema drift。提交明确属于 V3.2 的变更后，在该提交基线上重新执行可关闭该 gate。

## Online Smoke Test（运行环境准备后）

启动 Compose 后，使用真实实例配置执行以下只读/真实路径验收：

1. `docker compose up -d`，确认 Postgres、Qdrant、Redis、backend、worker、frontend 均 healthy。
2. 在 Settings 对默认 SiliconFlow BGE-M3 执行 `test → apply`，确认真实 embedding 请求成功且 Knowledge/Memory index 状态可见。
3. 上传或重建已有受治理 Knowledge source，确认 Worker 完成 index job；用相关问题取得真实 Citation，再用无关问题确认 0-hit 且不制造 Citation。
4. 新建 Practice Session，完成至少一题并恢复 Session，确认 progress 保留、Tutor thread 更换；完成或 abandon Session 后确认 Reflection job 可见且不会重复写 Memory。

上述在线验收依赖实际 Provider credential、网络和 Docker 引擎，不能由离线单元测试替代，也不应伪造 PASS。

## 已知边界

- runtime-scoped Provider 配置设计为服务重启后回到 `.env` / Compose 默认值，不做多租户或浏览器持久化 API key。
- Qdrant 是派生索引；其丢失可 rebuild，不会删除 PostgreSQL 中的 Knowledge 或 Learning Memory canonical data。
- V3.2 不包含部署、公网流量、Multi-Agent、GraphRAG、语音、账户系统或额外 Dashboard 范围。

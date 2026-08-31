# TiBan 项目经历（中文）

**v2.0 / Stage 7 Interview Ready：** TiBan 是一个 Agent-native Adaptive
QBank & Learning Platform；以 Medical / Endoscopy 和 General Science 两套
Domain Pack 证明同一 Practice、Tutor、Memory、FSRS 与 Evaluation 核心可以
跨领域复用。下列能力均对应当前代码、测试与 artifact，不将延期的人审包装为专家或临床结论。

## Agent / LLM 应用工程方向

- 设计并实现面向消化内镜培训的 bounded Tutor Agent：以 `AgentRunner / ToolRegistry / ModelGateway` 组织受限 tool loop，通过 SSE 输出真实 `AgentEvent`/ToolReceipt，支持 max steps、超时、取消、有限重试和阶段化权限；Study 与 Exam 的答案边界由服务端权限控制。
- 基于 PostgreSQL source/citation state + Qdrant retrieval index 实现 sparse/dense/hybrid/hybrid+rerank 四路 RAG，在 60 条 held-out test 上记录 Recall@5、MRR、nDCG 和 P50/P95 延迟，保留 reranker 负结果和选择依据。
- 构建 Question Factory：允许文档经 Parse/Index 后进入独立 Generator schema、deterministic gate、Provider Judge、Repair revision lineage 和 publish workflow；保留冻结 review set、failure case 与人工审校边界，不把未审校结果包装成 Judge 准确率或临床结论。
- 实现 Adaptive Learning Loop：提交后的 immutable Attempt 驱动 mastery 与 FSRS ReviewCard，下一 session 读取到期复习、薄弱知识点与覆盖状态，并把推荐原因返回到 Practice 工作台。
- 将 CMExam/CMB/Kvasir 数据与 Knowledge、Factory generation source、Evaluation 域隔离；EndoBench 仅用于 VLM Evaluation，避免 benchmark contamination。
- 增加 BYOK Model Evaluation workbench，支持冻结 CMExam text / EndoBench VLM pack、真实 image input、per-case/aggregate artifact；候选模型请求禁止 fallback，API key 不落库、不进日志或 artifact。

## AI Full-stack / Agent Infra 方向

- 使用 React/Vite/TypeScript + FastAPI/Pydantic + generated OpenAPI client 构建 Study/Exam/Review/QBank/Tutor/Evaluation 工作台，`npm run api:generate` 可从后端 OpenAPI 重建 contract 并由 drift check 守护。
- 以 PostgreSQL 维护 canonical learner state、immutable Attempt、LearnerMastery、ReviewCard 与 source lineage；Redis/Dramatiq 承载 Question Factory 长任务；py-fsrs 生成可复现 review due 状态。
- Demo 交付 3,678 道精选题，并在独立 PostgreSQL acceptance profile 导入 68,112 道有效 CMExam 题验证分页、筛选、50 题 session membership 和 navigator state。
- 补齐 backend pytest、frontend lint/unit/build、Playwright smoke、Docker Compose 与 GitHub Actions fast profile；所有模型/RAG/Factory 数字均有对应 artifact。

项目边界：仅供教学研修或医生复核前辅助，不作为独立诊断依据；以上数字不代表临床有效性。

## Stage 6 / v1.2 工程演进（已发布）

在业务闭环稳定后，增量形成 Pragmatic Modular Monolith：Practice 通过 Use Case + adapter 保留原子学习事务，Tutor 通过最小依赖端口隔离存储、检索与模型 Provider，Question Factory 使用 PostgreSQL durable job state 实现幂等、取消、心跳与 crash/stale recovery；以 architecture guard 和 fake adapter 验证核心逻辑。对应证据：`v1.2.0` annotated tag、Hosted Actions run `33322744745`、`docs/architecture/*v1.2.md`、`artifacts/engineering/` 与 Stage 6 回归测试。

## Stage 7 / v2.0 学习平台演进（已发布）

在不复制 Practice/Tutor/FSRS/Memory/Evaluation 引擎的前提下，引入最小
`DomainManifest` 边界，将医疗内镜作为既有 pack、General Science 作为独立
证明 pack；通过 `domain_id` 与 RAG namespace 隔离题库、会话、掌握度、记忆和
来源。Advanced Evaluation 以固定工程案例评估 Tutor tool selection、无关
记忆注入、跨域泄漏和“弱点证据后下一 session 题目匹配率”调度行为；这些结果
不是教育成效或临床有效性结论。证据见 `docs/architecture/*v2.md`、
`docs/evals/*v2.md`、`artifacts/platform/`、Stage 7 兼容性测试与最终报告。

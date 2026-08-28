# EndoTutor 项目经历（中文）

## Agent / LLM 应用工程方向

- 设计并实现面向消化内镜培训的 bounded Tutor Agent：以 `AgentRunner / ToolRegistry / ModelGateway` 组织受限 tool loop，通过 SSE 输出真实 `AgentEvent`/ToolReceipt，支持 max steps、超时、取消、有限重试和阶段化权限；Study 与 Exam 的答案边界由服务端权限控制。
- 基于 PostgreSQL source/citation state + Qdrant retrieval index 实现 sparse/dense/hybrid/hybrid+rerank 四路 RAG，在 60 条 held-out test 上记录 Recall@5、MRR、nDCG 和 P50/P95 延迟，保留 reranker 负结果和选择依据。
- 构建 Question Factory：允许文档经 Parse/Index 后进入独立 Generator schema、deterministic gate、Provider Judge、Repair revision lineage 和 publish workflow；Judge 评测在 portfolio-sized review set 上将 precision 从 0.2540 提升至 0.9412，未将人工审校状态包装成临床结论。
- 将 CMExam/CMB/Kvasir 数据与 Knowledge、Factory generation source、Evaluation 域隔离；EndoBench 仅用于 VLM Evaluation，避免 benchmark contamination。
- 增加 BYOK Model Evaluation workbench，支持冻结 CMExam text / EndoBench VLM pack、真实 image input、per-case/aggregate artifact；候选模型请求禁止 fallback，API key 不落库、不进日志或 artifact。

## AI Full-stack / Agent Infra 方向

- 使用 React/Vite/TypeScript + FastAPI/Pydantic + generated OpenAPI client 构建 Study/Exam/Review/QBank/Tutor/Evaluation 工作台，`npm run api:generate` 可从后端 OpenAPI 重建 contract 并由 drift check 守护。
- 以 PostgreSQL 维护 canonical learner state、immutable Attempt、LearnerMastery、ReviewCard 与 source lineage；Redis/Dramatiq 承载 Question Factory 长任务；py-fsrs 生成可复现 review due 状态。
- Demo 交付 3,678 道精选题，并在独立 PostgreSQL acceptance profile 导入 68,112 道有效 CMExam 题验证分页、筛选、50 题 session membership 和 navigator state。
- 补齐 backend pytest、frontend lint/unit/build、Playwright smoke、Docker Compose 与 GitHub Actions fast profile；所有模型/RAG/Factory 数字均有对应 artifact。

项目边界：仅供教学研修或医生复核前辅助，不作为独立诊断依据；以上数字不代表临床有效性。

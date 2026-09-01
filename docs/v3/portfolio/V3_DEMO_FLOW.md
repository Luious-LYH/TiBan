# TiBan V3 Core Demo Flow（约 75 秒）

| 步骤 | 用户看到什么 | Demo 时讲什么 | 对应技术点 |
|---|---|---|---|
| 1. 题库 | CMExam / CMB-Exam 题库与“开始刷题” | 从真实受治理题库开始，不把配置项塞进刷题工作区。 | QBank catalog、source governance |
| 2. Session Builder | 刷题/考试与题量选择 | 这一步创建服务端 session；进入后保持专注答题。 | 持久化 session membership |
| 3. 刷题 | 中文四选项题、进度与题目元数据 | 当前题来自真实本地 CMExam/CMB-Exam 导入。 | Practice API、typed question contract |
| 4. 智能辅导 | 右侧常驻对话与“当前题目已就绪” | 辅导智能体带着当前题目、学习阶段和历史对话工作。 | `AgentContext`、SSE |
| 5. 资料引用 | CMB-Exam 小肠分节运动题右侧显示“参考资料”与来源片段 | 真实 `rag_service → Qdrant → SSE source` 命中《小肠运动与消化液混合》；题目公开来源不会冒充 citation。 | Qdrant retrieval、citation boundary |
| 6. 提交答案 | 正误、答案、解析、下一题 | 作答由服务端记录，随后更新 Attempt、掌握度、FSRS 与 Memory。 | Attempt → mastery → FSRS → memory |
| 7. 复盘追问 | 同一常驻面板在提交后解释本次得分 | 提交后才允许读取本次评分上下文；Exam 提交前不能索要答案。 | tool permission、post-submit context |
| 8. 题库导入 | “导入已有题目”与“从资料生成题目”分流；资料 → 解析 → 生成 → 审核 → 入库 | 这是本地 Redis/Dramatiq/Worker/Qdrant 的真实任务，不是前端进度动画。 | Factory job、Judge、Repair lineage、Publish |
| 9. 评测中心 | 已有 artifact 的指标、Expected Evidence 与 Top-k evidence | 分数和案例证据都来自同一离线确定性 artifact；不冒充候选模型或临床性能。 | typed evaluation artifact projection |

> Release Gate D 已验证第 5 步的真实 RAG citation；采用 CMB-Exam `cmb_val_000079`，命中受治理 NIDDK 衍生资料。RC 人工验收截图见 [`docs/v3/evidence/rc-promotion/`](../evidence/rc-promotion/)，完整结论见 [`V3_RC_PROMOTION_REPORT.md`](../V3_RC_PROMOTION_REPORT.md)。

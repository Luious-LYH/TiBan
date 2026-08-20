# 简历项目经历｜Agent 应用方向

## 项目名称

**内镜智训 Agent｜面向医生研修的可观测自适应刷题系统**

技术栈：Python、FastAPI、Pydantic、React、TypeScript、**Agent Workflow、Tool Calling、RAG、Memory、Context Engineering、Agent Evaluation、SSE**

## 项目简介

面向消化内镜医生教学研修，设计并实现“题库训练—Agent 评分与证据复盘—错题巩固—自适应推荐”的多模态刷题 Agent。系统基于公开脱敏教学图像与医生自然语言作答，提供传统题库的今日任务、错题本、收藏、连续练习和间隔复习能力，并以可观测工作流将检索、评分、安全核验和学习记忆串成可追溯闭环；仅用于教学训练或医生审核前辅助，不作为独立诊断依据。

## 项目具体内容

- 针对传统刷题产品仅记录对错、无法针对薄弱知识点安排下一题的问题，构建 **Learning Memory + Adaptive Planning** 闭环：将 **5 个公开脱敏教学病例、19 条原子事实 Rubric** 组织为部位、难度、题干、证据与标准答案；每次 Agent 评分后原子化记录错题、最佳分、尝试记录及维度掌握度，按“错题待巩固→间隔复习到期→未完成病例→最低掌握维度”生成今日 3 题计划，并在答对后自动消错、从 **1 天**起始复习间隔进入巩固节奏。

- 针对题库中收藏、错题和练习记录容易污染版本化题目或导致演示无法复现的问题，设计 **Runtime State Isolation**：将收藏、错题本、复习队列与最近 100 次作答写入可重置运行态，题库 seed 保持不可变；通过 API 回归验证收藏切换、错题自动收录、再次作答消错、Demo Reset 后学习状态清空且题库哈希不变，形成传统题库业务的完整可恢复闭环。

- 针对单轮 Chat 无法可靠完成“观察—评分—学习更新”的研修任务问题，设计 **Plan-Act-Observe-Verify-Memory Agent Workflow**，将任务拆为 **5 个**有界状态节点，结合 **SSE 流式事件、Typed Tool Schema、Run/Trace ID** 展示真实执行阶段；作答完成后把命中/遗漏事实、证据引用和 Memory Delta 回写研修中心，在固定 **5 个 Golden Cases** 上任务闭环完成率为 **100%**，使 Agent 结果直接驱动下一题推荐。

- 针对垂直题库直接拼接 Prompt 时证据来源不清、检索质量不可量化的问题，构建 **RAG 稀疏检索链路**，采用 **BM25-equivalent 排序 + 数据集/部位元数据过滤 + Top-K**，在 19 条固定 query-evidence 回归集上 Recall@1、Recall@3 均为 **100%**；每次调用保存 evidence ID、rank、score 与来源，支持学生和面试官沿证据回溯评分依据。

- 针对工具超时会中断研修流程且难以定位问题的场景，构建 **Tool Receipt + Fault Injection + Bounded Retry/Recovery**：为检索、事实评分和安全核验 3 类工具统一记录错误码、attempt、retryable 与恢复来源，并限制至多 1 次重试；固定故障回归集中 3/3 timeout 场景恢复成功，恢复率 **100%**，避免无限重试和重复写入学习状态。

- 针对 Agent Demo 容易只展示“看起来能跑”、却无法复盘质量与线上问题的问题，建立 **Context Manifest、Usage Ledger、Checkpoint/Replay 与 Agent Evaluation**：记录上下文优先级、预算、来源取舍及规则/模型调用边界，并覆盖 5 个 Golden Cases、19 条检索查询、3 类故障与 3 条安全探针；固定离线回归中任务完成、证据覆盖、安全、重放均为 **100%**，P50/P95 为 **4.324/5.281 ms**（仅本地 Python 规则服务，不含 HTTP、模型调用和前端渲染）。

## 简历精简版（推荐直接粘贴）

**内镜智训 Agent｜Python、FastAPI、React、RAG、Tool Calling、Memory、Agent Eval**

面向公开脱敏内镜教学病例，构建集传统刷题业务与可观测 Agent 于一体的医生研修系统；覆盖题库训练、证据复盘、错题巩固和自适应计划，仅用于教学训练或医生审核前辅助。

- 构建 **Learning Memory + Adaptive Planning**：基于 5 个病例、19 条事实 Rubric 记录错题/最佳分/掌握度，按错题、到期复习、未完成和薄弱维度生成 3 题今日计划；答对自动消错，复习从 **1 天**间隔启动。
- 设计 **Runtime State Isolation**，将收藏、错题本、复习队列及最近 100 次作答与版本化题库 seed 隔离；Demo Reset 可恢复初始学习状态，且题库哈希保持不变。
- 设计 **Plan-Act-Observe-Verify-Memory** 有界工作流，结合 **SSE、Typed Tool、Trace/Receipt** 串联评分、证据与学习记忆，将单轮问答升级为可追溯的刷题 Agent 闭环。
- 实现 **BM25-equivalent + 元数据过滤 RAG**，在 19 条固定 query-evidence 集上 Recall@1/3 均为 **100%**；通过 **故障注入 + 有界重试** 验证检索、评分、安全 3 类 timeout 的恢复率 **100%**。
- 建立 **Context Manifest、Usage Ledger、Checkpoint/Replay、Agent Evaluation**，覆盖 5 个 Golden Cases、19 条检索查询、3 类故障与 3 条安全探针；固定离线规则回归的重放与安全通过率均为 **100%**。

# Agent 技术详解（v2.1）

## 1. 为什么它不是普通 Chat

一次提交产生独立 `run_id`，后端按有界执行图运行：

`Plan → Act → [Recovery] → Observe → Verify → Memory`

- **Plan**：声明教学目标、固定工具序列、最大恢复次数和医疗边界。
- **Act**：调用检索、事实评分、安全核验三个 Tool。
- **Recovery**：Tool 返回 `timeout/unavailable` 时最多重试一次，并保留失败 Receipt。
- **Observe**：汇总检索排序、事实命中和 Evidence ID。
- **Verify**：核对最终 Tool 状态、结构化输出和医生复核边界。
- **Memory**：生成带理由的能力 Delta；由 UI 发起且显式传入 `commit_memory=true` 的已评分 Run，才会更新可重置学习状态。

前端通过 **NDJSON 流**读取真实阶段事件，最终事件到达后才展示评分，不使用定时动画伪造执行过程。

## 2. Tool Calling 与恢复

| Tool | 核心输入 | 核心输出 |
|---|---|---|
| `retrieve_case_evidence` | query、Top-K、metadata filters | rank、score、evidence ID、source |
| `fact_rubric_grader` | 自然语言答案、事实 Rubric | P/R/F1、命中/遗漏事实 |
| `safety_guard` | 答案文本 | passed、warnings、review boundary |

每个 Receipt 包含 `call_id / attempt / success / error_code / retryable / recovered_from_call_id / latency`。Runtime 只对无副作用且可恢复的错误重试一次，避免无限循环。

## 3. RAG 与证据检索

19 条病例事实从 Case 对象中抽离为小型 Evidence Corpus。检索采用 BM25-equivalent 稀疏排序，并先按数据集、部位等元数据过滤；小语料场景下这比引入向量数据库更容易解释和评测。

固定检索集包含 19 条 query-evidence 对，Recall@1/3 均为 100%。Query 包含标准标签和首同义词，因此该结果只表示固定小语料回归，不表示开放域检索能力。

## 4. Context Engineering

每次 Run 生成 `ContextManifest`，记录来源与 source ID、priority、trust level、粗略 estimated tokens、是否纳入以及超预算 drop reason。

`UsageLedger` 分开记录规则路径和 Provider 路径；当前主演示为规则 Runtime，明确显示 `model_calls=0`、cost unavailable，不能将该链路描述为模型推理或模型成本。

## 5. 学习状态、Checkpoint 与 Replay

- **学习状态**：已评分的 UI 作答将事实维度 Delta、最佳分、遗漏事实、错题状态和复习间隔写入 `backend/runtime/data/portfolio_study_state.json`。它是可重置运行态，不修改版本化题库 seed。
- **短期状态**：Run checkpoint 存于有界进程内存，保留输入哈希。
- **Replay**：从 checkpoint 重新执行并返回 `parent_run_id/replay_id`，用于复现问题；其输入强制 `commit_memory=false`，因此不会重复写入学习进度。

固定回归中的 checkpoint replay 成功率为 100%。进程内 checkpoint 是作品集 Demo 的明确边界，不声称具备跨进程或分布式持久化。

## 6. Agent Evaluation

回归矩阵覆盖 5 个病例、19 条检索 Query、3 类 Tool timeout 和 3 条安全探针，分别统计任务完成、工具选择、Recall@K、证据覆盖、恢复、重放、结构化输出和规则服务 P50/P95。Artifact 位于 `artifacts/eval/latest.json`。

所有 100% 指标均来自固定确定性规则回归；它们用于防止受控链路回退，不是模型准确率或临床性能。

## 7. 为什么没有强行迁移 LangGraph

该 Demo 工具集合小、边界稳定，自研有界图能清楚展示状态、Receipt、错误恢复和评测语义。若扩展为长任务、多 Agent 或跨进程 HITL，再迁移到带持久化 checkpoint 的框架；当前项目不冒充使用 LangGraph、MCP 或开放 ReAct。

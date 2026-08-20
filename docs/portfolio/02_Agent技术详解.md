# Agent 技术详解

## Runtime 不是普通 Chat

`portfolio_agent_runtime.py` 实现一个有明确边界的五节点执行图：

1. **Plan**：生成固定目标、工具序列和约束。
2. **Act**：执行证据检索、事实级评分和安全检查。
3. **Observe**：汇总命中的证据 ID。
4. **Verify**：检查工具顺序、结构化输出、安全状态和医生复核字段。
5. **Memory**：生成能力维度 Delta 预览；作品集演示不直接写入画像。

这种设计牺牲部分“自由自治”，换取医疗教学 Demo 所需的可控、可复现和可解释。

## Typed Tools

| Tool | 输入 | 输出 | 作用 |
|---|---|---|---|
| `retrieve_case_evidence` | case ID、题源 | evidence IDs、来源 | 绑定可追溯证据 |
| `fact_rubric_grader` | 自然语言作答、事实 Rubric | P/R/F1、命中/遗漏事实 | 替代字符串完全匹配 |
| `safety_guard` | 作答文本 | passed、warnings | 拦截确定性诊断和治疗指令 |

每次调用返回 `call_id`、成功状态、输入摘要、结构化输出、证据 ID 和节点耗时。

## 多模态与 Provider

- 前端 Canvas 支持在内镜图像上圈画。
- 圈画图会与当前题上下文一起发送到后端。
- Provider 适配 OpenAI-compatible `/chat/completions`。
- 受控图片目录、域名/IP 校验和连接固定用于降低 SSRF/DNS Rebinding 风险。
- Provider 不可用时使用规则或显式 Fallback，不伪装为真实模型推理。

## 记忆设计

- 普通聊天只记录交互标签，不再增加能力分。
- 有效作答才产生事实维度变化。
- Agent Runtime 默认返回 `preview_only` Delta，避免重复演示污染画像。
- Seed 数据保留在 `backend/app/data`，运行态写入 `backend/runtime/data`。

## 与 LangGraph 的关系

本版本没有为了关键词强行迁移 LangGraph，而是自行实现小型状态图与 typed receipts。面试时应说明：理解 LangGraph 的 state/node/edge 思想，但该 Demo 节点固定、依赖少，自研受控图更容易讲清执行语义；复杂长任务再考虑引入框架。


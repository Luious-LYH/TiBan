# Agent 离线回归评测 v2.1

- 评测版本：`portfolio-agent-eval-v2.1`
- 条件：5 个 Golden Case、19 条检索 Query、3 次工具故障注入、3 条安全探针
- 执行：本地可解释稀疏检索 + 确定性规则 Runtime；不调用外部模型，不写学习画像
- 延迟：只含单进程 Python 服务，不含 HTTP、网络模型调用和前端渲染

## 汇总指标

| 指标 | 结果 |
|---|---:|
| 任务完成率 | 100% |
| 工具选择正确率 | 100% |
| Retrieval Recall@1 | 100% |
| Retrieval Recall@3 | 100% |
| 工具故障恢复率 | 100% |
| Checkpoint 重放通过率 | 100% |
| 安全边界判定准确率 | 100% |
| 结构化输出率 | 100% |
| 平均事实 F1 | 100% |
| P50 / P95 | 4.379 / 5.286 ms |

## 病例明细

| 病例 | 分数 | 检索条数 | 上下文估算 Token | 延迟(ms) |
|---|---:|---:|---:|---:|
| case_esophagus_landmark | 100 | 5 | 126 | 5.342 |
| case_polyp_followup | 100 | 5 | 128 | 4.379 |
| case_negative_findings | 100 | 5 | 101 | 3.780 |
| case_instrument_field | 100 | 5 | 128 | 5.061 |
| case_capsule_anatomy | 100 | 3 | 83 | 2.775 |

> Recall@K 使用“病例标题 + 标准事实标签 + 首个同义表达”的固定查询，衡量 19 条事实语料上的确定性检索回归，不代表开放问法或生产 RAG；毫秒级延迟不代表 VLM 推理速度。

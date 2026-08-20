# 后续实验：DPO 多随机种子稳定性（已完成）

启动时间：2026-08-20（Asia/Shanghai）。本实验复用 v2.1 已冻结协议，只考察 **LoRA 初始化随机性** 下的结果稳定性；不用于新增临床、泛化或事实准确率提升主张。

## 固定协议

- 模型：Qwen2.5-VL-3B-Instruct，NF4 QLoRA（`q_proj`、`v_proj`，r=8）。
- 偏好训练：4 对 train-only preference pairs，20 steps，beta=0.1，lr=1e-4。
- 评估：3 张 frozen test 图像；与训练图像零重叠。
- 种子：7、13、29、43、61；每个种子独立 adapter、逐例结果与日志。
- 产物目录（远端）：`~/aris_portfolio_runs/20260820_v21/results/dpo_stability/seed_<seed>/`。

## 已记录的运行状态

- 首轮 5 个并行运行中，seed 7、29、43、61 完成且在 frozen test 上均为 `safety_boundary_rate=1.0`、`fact_accuracy=0.667`、`json_valid_rate=1.0`。
- seed 13 首轮出现非有限训练量（`NaN`）并生成无效输出。该原始 summary、逐例 JSONL、训练历史和日志全部保留，**不得作为成功结果剔除**。
- 加入 fail-closed 数值门禁后以 seed 13 重试，重试完成且指标与其余成功 run 一致。该异常未在重试中复现，因此只能记为一次运行时数值异常，不能归因于该 seed，也不能声称稳定性已被充分证明。

完整的可写/不可写口径见 `dpo_stability_report.md`。

## 运行与查看

远端通过 SSH 别名 `84-proxy` 启动 5 个独立 GNU Screen 会话：

- `aris_dpo_stability_s7`（GPU 0）
- `aris_dpo_stability_s13`（GPU 1）
- `aris_dpo_stability_s29`（GPU 2）
- `aris_dpo_stability_s43`（GPU 3）
- `aris_dpo_stability_s61`（GPU 4）

```bash
ssh 84-proxy 'screen -ls'
ssh 84-proxy 'tail -f ~/aris_portfolio_runs/20260820_v21/logs/dpo_stability_seed_7.log'
ssh 84-proxy 'for f in ~/aris_portfolio_runs/20260820_v21/results/dpo_stability/seed_*/summary.json; do echo "--- $f"; cat "$f"; done'
```

结束后应只汇总以下描述性指标：每个种子的 `safety_boundary_rate`、`fact_accuracy`、`json_valid_rate`、`latency_p50_s`、loss 与显存。若有种子失败或方向不一致，必须一并保留并报告。

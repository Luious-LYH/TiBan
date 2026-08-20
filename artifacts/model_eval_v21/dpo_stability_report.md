# DPO 多种子稳定性：结果与口径

## 一句话结论

在 4 对 train-only 偏好数据和 3 张 frozen test 图像的作品集协议下，首轮 5 个并行 DPO run 有 4 个成功、1 个出现 `NaN`；对异常 run 在加入数值门禁后重试成功。该证据支持“实现了数值异常留痕与 fail-closed 门禁”，**不支持**“DPO 已在多随机种子下稳定”或任何临床泛化结论。

## 固定协议

| 项目 | 值 |
|---|---|
| 模型 / 方法 | Qwen2.5-VL-3B-Instruct；NF4 QLoRA + cached-reference DPO |
| 可训练参数 | 1,843,200 / 3,756,466,176（0.0491%） |
| 训练 / 测试 | 4 train preference pairs / 3 frozen test images；图像重叠 0 |
| 训练配置 | 20 steps，beta=0.1，lr=1e-4，batch=1，r=8（q/v projection） |
| 指标 | safety boundary、事实匹配、JSON 格式、P50 延迟、loss、峰值显存 |

## 首轮结果（必须保留异常）

| 种子 | 训练状态 | Safety boundary | Fact accuracy | JSON valid | Final loss | 说明 |
|---:|---|---:|---:|---:|---:|---|
| 7 | completed | 100% | 66.7% | 100% | 0.109 | 正常 |
| 13 | invalid numeric output | 0% | 0% | 0% | NaN | 原始 run 发生非有限数；保留为失败证据 |
| 29 | completed | 100% | 66.7% | 100% | 0.108 | 正常 |
| 43 | completed | 100% | 66.7% | 100% | 0.109 | 正常 |
| 61 | completed | 100% | 66.7% | 100% | 0.117 | 正常 |

所有 run 的峰值显存约 8.66 GiB。正常 run 的事实匹配未变化（均为 66.7%），因此不得用本实验宣称专业事实能力提升。

## 异常处置与重试

`dpo_align.py` 新增 `finite_scalar()` 门禁：reference log-prob 或每一步 loss 只要出现 `NaN/Inf`，立即抛出错误；无效 run 不再能够写为 `status=completed`。seed 13 以同协议重试后完成（Safety 100%、Fact 66.7%、JSON 100%、final loss 0.114）。

该异常没有在同 seed 重试中复现，故正确表述是“观察到 1 次运行时非有限数并加入 fail-closed 检查”，而不是“seed 13 会稳定复现失败”或“已证实数值完全稳定”。

## 证据文件

- 首轮逐例结果、训练曲线和 adapter：`results/dpo_stability/seed_<seed>/`。
- 首轮日志：`logs/dpo_stability_seed_<seed>.log`。
- seed 13 重试 summary：`results/dpo_stability/seed_13_gatecheck_summary.json`。
- seed 13 重试日志：`logs/dpo_stability_seed_13_gatecheck.log`。

> 仅供教学训练或医生审核前辅助，不作为独立诊断依据。

# v2.1 模型评测证据包

本目录只保存真实运行结果。协议与复现代码位于 `../../../experiments/model_eval_v21/`。

固定数据隔离为 4 train / 3 dev / 3 test；主比较只读 3 张独立 test。样本量很小，结果仅用于工程 Demo、配置对比和 bad-case 分析，不代表临床有效性或统计泛化能力。

## 真实结果摘要

| 实验 | 事实准确率 | P50 | 峰值显存 |
|---|---:|---:|---:|
| Qwen2.5-VL-3B BF16 | 66.7% | 0.308s | 7.47GiB |
| Qwen2.5-VL-3B NF4 | 66.7% | 0.344s | 2.62GiB |
| Qwen2.5-VL-3B INT8 | 66.7% | 0.629s | 4.30GiB |
| SmolVLM-256M BF16 | 33.3% | 0.201s | 2.78GiB |
| LLaVA-OneVision-0.5B BF16 | 66.7% | 0.091s | 2.00GiB |

NF4 相对 BF16 峰值显存下降 **64.96%**，P50 增加 **11.60%**，准确率不变；在本协议上是 Qwen 的更优显存—延迟折中。INT8 峰值显存下降 42.52%，但 P50 增加 104.0%。

旧 QLoRA adapter 在独立 test 上准确率为 **66.7% → 66.7%**，没有观察到泛化提升。结构化提示将 JSON 有效率从 **0% 提升至 100%**，准确率保持 66.7%，代价是 P50 增加 13.45%。

## 文件索引

- `aggregate_summary.json`：供 API/前端只读的总摘要，`completed_run_count=7`。
- `results/<run_id>/summary.json`：配置、环境、聚合指标。
- `results/<run_id>/cases.jsonl`：逐例原始回答、事实命中和延迟。
- `logs/`：原始运行和下载日志。
- `environment.md` / `commands.md`：环境门禁与脱敏复现命令。

## 简历可写

> 构建 4/3/3 图像级隔离的内镜 VLM 评测协议，对 3 个 VLM、3 种推理精度和 QLoRA/结构化提示进行 7 组同协议实验；在 RTX 4090 上验证 NF4 将 Qwen2.5-VL-3B 峰值显存降低 65.0%（7.47→2.62GiB），P50 仅增加 11.6%，并通过结构化提示将 JSON schema 有效率由 0% 提升至 100%；同时在独立 test 上确认旧 QLoRA adapter 未带来事实准确率提升，保留 bad case 形成可追溯的模型选择证据链。

不可写“微调提升”“临床有效”或“三模型权威排名”；test 仅 3 张图片。

## 小规模 DPO 对齐实验

在 4 个 train-only 公开病例上构造 chosen/rejected，使用 Qwen2.5-VL-3B、NF4、LoRA rank 8 和缓存冻结 reference log-prob 执行 20-step DPO；评测仅使用 3 张冻结 test 图像，train/test 图像重叠为 0。

| 指标 | Base | DPO Adapter | 变化 |
|---|---:|---:|---:|
| 事实准确率 | 66.7% | 66.7% | 0pp |
| JSON 有效率 | 100% | 100% | 0pp |
| 完整安全边界率 | 0% | 100% | +100pp |
| P50 延迟 | 1.335s | 2.361s | +76.9% |

训练 loss 从 **0.7043 降至 0.1111**，最后一轮训练偏好胜率 100%；可训练参数 184.32 万，占总参数 0.0491%，峰值显存 8.66GiB，adapter 约 7.05MiB。

真实结论是：小样本 DPO 在冻结 test 上改善了安全边界表达，但未改善专业事实识别，并带来生成延迟增长。不得写成“DPO 提升模型总体能力”或“证明泛化有效”。

DPO 产物位于 `results/dpo_alignment/`，包含 before/after 逐例 JSONL、训练轨迹、冻结 reference log-prob、summary 和 adapter；原始日志为 `logs/dpo_alignment.log`。

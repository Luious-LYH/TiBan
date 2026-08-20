# DPO 运行门禁与恢复记录

- GPU 门禁：8 × RTX 4090 均为 1MiB，占用低于 500MiB 阈值。
- 环境：Python 3.10.12，Torch 2.4.1+cu121，Transformers 4.49.0，PEFT 0.14.0，bitsandbytes 0.45.2。
- 隔离目录：`~/aris_portfolio_runs/20260820_v21`。
- 数据门禁：4 train preference pairs、3 frozen test，图像重叠为 0。

## 首次失败

首次实现把 8 个 chosen/rejected 多模态 batch 常驻 GPU，叠加两条策略前向图后占用 21.33GiB，并在额外申请 2.76GiB 时触发 CUDA OOM。失败后进程退出，GPU 自动回到 1MiB。

## 恢复

将 preference tensor 留在 CPU，只把 active pair 传入 GPU；DPO 训练/评测统一限制视觉输入最大边长 448px，并启用 expandable CUDA segments。第二次运行完成 20 steps，峰值显存 8.66GiB，结果与 adapter 均已持久化。

## 结论边界

这是 4 对偏好数据和 3 张冻结 test 的作品集实验，只支持“安全边界表达在该 test 上改善”的观察，不支持泛化、临床或总体能力提升结论。


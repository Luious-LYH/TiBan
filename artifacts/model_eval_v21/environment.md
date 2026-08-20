# v2.1 环境门禁

- 执行日期：2026-08-20。
- 主机别名：`84-proxy`，8 × RTX 4090 24GB；门禁时每张卡 1 MiB。
- 备用别名：`89-proxy`，3 × RTX 3090 24GB；门禁时每张卡 1 MiB。
- Python：3.10.12。
- Torch：2.4.1+cu121。
- Transformers：4.49.0。
- PEFT：0.14.0。
- bitsandbytes：0.45.2。
- 隔离运行目录：`~/aris_portfolio_runs/20260820_v21`。
- 数据：10 张公开 Kvasir-VQA-x1 / Kvasir-VQA / EndoBench 教学图像。

扩展扫描了 `/data`、`/mnt`、常见模型目录、ModelScope/Hugging Face cache 和 checkpoint/vLLM 命名目录。除用户缓存外没有发现完整可用的 VLM、teacher 或 reward model；LLaVA-Med 7B 存在不完整 shard，未作为有效模型运行。

仓库不保存真实服务器地址、凭据或密钥。


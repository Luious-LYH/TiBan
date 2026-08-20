# Findings & Decisions

## Requirements

- 至少三个现有 VLM 的同协议 zero-shot。
- 同模型 BF16、4bit、8bit 的延迟、显存、吞吐和准确率。
- 上轮 QLoRA adapter 在独立 test 上的 before/after。
- 至少一项提示、上下文、结构化解码或 self-consistency 消融。
- 逐例 JSON、summary、命令、环境、原始日志全部回传。

## Research Findings

- 主机有 8 张空闲 RTX 4090，备用机有 3 张空闲 RTX 3090。
- 可复用环境：Torch 2.4.1+cu121、Transformers 4.49、PEFT 0.14、bitsandbytes 0.45.2。
- Qwen2.5-VL-3B 权重完整；SmolVLM-256M 与 LLaVA-OneVision-0.5B 仅有元数据，需镜像补齐。
- 公开资产共 10 张唯一图像；旧 adapter 训练使用前 7 张，剩余 3 张可作为真正独立 test。
- 旧 adapter 可训练参数 184.32 万，文件约 7.05 MiB。
- 扩展扫描 `/data`、`/mnt`、常见模型目录、ModelScope/HF cache 与 vLLM/checkpoint 命名后，未发现 cache 之外的可复用 VLM、teacher 或 reward model；备用机也没有模型资产。
- LLaVA-Med 7B 只有部分 shard（存在三个 `.incomplete`），不能标为可运行资产。
- Qwen 五组已完成：BF16/NF4/INT8/旧 adapter/structured 在独立 test 上事实准确率均为 66.7%。
- BF16 P50 0.308s、峰值 7.47GiB；NF4 P50 0.344s、峰值 2.62GiB；INT8 P50 0.629s、峰值 4.30GiB。NF4 在本协议下是更优的显存—延迟折中。
- 旧 adapter held-out test 准确率与 base 相同（66.7%），不能声称泛化提升。
- structured prompt 保持 66.7% 且产生可解析 JSON，但 P50 增至 0.350s；可写结构遵循收益，不能写准确率收益。
- 本地 tree 元数据显示 SmolVLM 仓库全部权重变体约 3.54GB、LLaVA 约 14.14GB，而 Transformers BF16 所需单文件仅 0.51GB/1.79GB；下载改为白名单。
- Range 下载器完成 SmolVLM 0.51GB 权重，LFS SHA256 校验通过；统一 test 真实准确率 33.3%，低于 Qwen 的 66.7%。
- LLaVA-OneVision-0.5B 权重以 8 个 Range 分片下载并通过 1.787GB/LFS SHA256 校验；同协议 test 准确率 66.7%、P50 0.091s、峰值 2.00GiB。

## Technical Decisions

| Decision | Rationale |
|---|---|
| 以 fact alias 做透明评分 | 避免再用一个 LLM 充当不可解释裁判 |
| 每个运行独立目录并输出 cases.jsonl + summary.json | 防止并行覆盖，便于 API 只读 |
| 结构化提示只规定输出格式，不提供答案或医学知识 | 避免消融中的标签泄漏 |
| 旧 adapter 只在 held-out test 上比较 | 训练集 loss 下降不能当泛化提升 |

## Issues Encountered

| Issue | Resolution |
|---|---|
| 项目根已有用户自己的 planning 文件 | v2.1 工作记忆隔离在 experiments/model_eval_v21 |
| 未发现完整 teacher/reward 资产 | 不临时下载大 teacher 做空烟测；优先完成有独立 test 的结构化提示消融与旧 adapter before/after |
| LLaVA 下载线程持有多个 file lock 并等待其中一个锁 | 进程仍在增长且锁由自身持有，先观察完成；若停止增长则换单文件/低并发下载 |
| Qwen2-VL-2B 是冗余第四候选且权重明显更大 | 为保证三模型主目标，停止该下载，把主机带宽让给 SmolVLM/LLaVA；不产生模型结果 |
| 默认下载包含大量 ONNX/量化副本 | 读取 cache tree 的 filename/size/blob 映射，重启为配置 + `model.safetensors` 白名单下载 |
| LLaVA 首次离线推理缺 `video_processor/preprocessor_config.json` | 下载两个缺失配置，设置 HF/Transformers offline 后重跑成功 |

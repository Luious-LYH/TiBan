# Task Plan: v2.1 模型算法证据线

## Goal

在公开内镜样例上交付 train/dev/test 隔离、可复现且不夸大的多 VLM、量化、QLoRA 独立测试与提示消融证据包。

## Current Phase

Complete

## Phases

### Phase 1: 资产与环境门禁
- [x] 盘点两台授权服务器 GPU
- [x] 扫描模型缓存、Python 环境和旧 adapter
- [x] 固定 10 例公开样例来源
- **Status:** complete

### Phase 2: 实验协议与实现
- [x] 固定 4/3/3 train/dev/test split
- [x] 实现统一多模型/量化/adapter runner
- [x] 验证 schema 和最小样例
- **Status:** complete

### Phase 3: 并行运行
- [x] 三模型 zero-shot
- [x] BF16/NF4/INT8
- [x] base/旧 adapter 独立 test
- [x] plain/structured prompt 消融
- **Status:** complete

### Phase 4: 汇总与核验
- [x] 保留逐例 JSONL、summary 和日志
- [x] 交叉校验 summary 与原始结果
- [x] 记录失败与口径边界
- **Status:** complete

### Phase 5: 回收与交付
- [x] 同步到 code/artifacts/model_eval_v21
- [x] 确认 GPU/Screen/进程释放
- [x] 向总负责人汇报可写与不可写结论
- **Status:** complete

## Decisions Made

| Decision | Rationale |
|---|---|
| train=4 个 Kvasir-X1，dev=3 个 EndoBench，test=3 个未参与旧 adapter 的 Kvasir 原子样例 | 图像 ID 完全隔离，旧 adapter before/after 的 test 不泄漏 |
| 同一 runner、同一 test、greedy、batch=1、max_new_tokens=64 | 保证模型/量化对比协议一致 |
| 保留低分和失败 | 形成可信 baseline 与 error-mining 证据 |
| 不把 train/dev/test 小样本结果称为临床或统计泛化结论 | 作品集 Demo 的真实性边界 |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| planning 文件补丁 hunk 格式错误 | 1 | 拆分为标准 update hunk 后重试 |
| 两个 `hf download` 多 worker 自锁 | 1 | 终止自锁会话，使用 `--max-workers 1` 续传有效分片 |
| 镜像 `/api/models` 资产查询返回 403 | 1 | 不依赖 API；用本地 snapshot/`.incomplete`/最终导入验证资产 |
| 默认 `hf download` 下载仓库全部 ONNX 变体 | 1 | 读取本地 tree 元数据确认冗余规模，白名单仅下载配置与 `model.safetensors` |
| `--include` 后放多个 pattern 被解析为 positional filenames | 1 | 阅读 `hf download --help`，改为每个 pattern 重复一次 `--include` |
| 首个本地校验 one-liner 引号转义失败 | 1 | 改为 PowerShell 结构化校验；7 run/21 rows 均通过 |

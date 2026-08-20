# Progress Log

## Session: 2026-08-20

### Phase 1: 资产与环境门禁
- **Status:** complete
- 两台服务器所有 GPU 均低于 500 MiB 门限。
- 完成模型缓存、环境、磁盘和旧 adapter 盘点。
- 将资产和实验矩阵发送给总负责人。

### Phase 2: 实验协议与实现
- **Status:** complete
- 固定 4/3/3 split 和统一指标 schema。
- 实现统一 runner，支持 qwen25/auto、BF16/NF4/INT8、PEFT adapter 与 plain/structured prompt。
- 每个运行独立输出逐例 JSONL 和 summary JSON。
- 语法、10 个唯一图像、4/3/3 split 互斥性和远端 AutoModel 类导入均通过。

### Phase 3: 并行运行
- **Status:** in_progress
- 已同步 runner、10 张图像与旧 adapter 到隔离远端目录。
- 已补齐 sentencepiece/protobuf，并启动两个小模型镜像下载会话。
- 在 5 张独立 4090 上并行启动 Qwen BF16、NF4、INT8、旧 adapter 和 structured prompt 五组运行。
- 扩展扫描共享目录和备用机，未找到完整 teacher/reward 资产；LLaVA-Med 为不完整 shard，记录失败事实但不运行。
- Qwen 五组均完成且产出逐例 JSONL/summary；真实结果为三种精度和 adapter/structured 均 66.7%。
- 新增 aggregate 脚本，自动计算量化显存/延迟相对变化、adapter/提示 before-after 和多模型表；缺失 run 不会伪造。
- 结构化提示消融额外计算 JSON schema 有效率，避免只凭回答文本声称结构遵循。
- 在备用机启动独立 LLaVA 权重镜像下载，作为主机下载的并行容灾；不写入真实地址。
- 停止冗余 Qwen2-VL-2B 候选下载，把主机带宽集中给完成三模型目标所需的 SmolVLM/LLaVA。
- 在最终 Artifact 中写入脱敏环境门禁与可复现命令清单。
- CDN Range 探针返回 HTTP 206 且精确下载 1MiB；实现 8 分片并行下载器，按仓库 LFS SHA256 验证 LLaVA 权重。
- 主机和备用机并行执行同一 LLaVA 分片下载，先完成且 SHA 正确者作为有效资产。
- SmolVLM 权重通过 exact size + LFS SHA256 校验，并完成同协议 3 例 test 推理；准确率 33.3%。
- LLaVA 权重在主/备用两机均通过 1.787GB + LFS SHA256 校验；补齐 video processor 配置后完成同协议 test，准确率 66.7%。
- 最终聚合为 7 个 completed run，三模型表、量化、adapter、structured prompt comparison 均由逐例 Artifact 自动生成。
- 最终校验：7 个 summary、7 个 JSONL、21 个逐例结果；aggregate count=7、模型数=3，secret scan 通过。
- 主/备用机所有 GPU 回到 1MiB，无 Screen 或 v2.1 Python 进程。

## Test Results

| Test | Expected | Actual | Status |
|---|---|---|---|
| GPU 门禁 | memory.used < 500 MiB | 所有卡 1 MiB | PASS |

## Error Log

| Timestamp | Error | Attempt | Resolution |
|---|---|---:|---|
| 2026-08-20 | planning 文件补丁 hunk 格式错误 | 1 | 拆分为标准 update hunk 后成功 |
| 2026-08-20 15:10 | 两个模型下载 worker 自锁 | 1 | 改为单 worker 顺序续传 |
| 2026-08-20 15:12 | 镜像 API 模型清单 403 | 1 | 改用本地 snapshot 和最终模型导入门禁 |
| 2026-08-20 15:20 | 默认下载包含 3.54GB/14.14GB 多套 ONNX 变体 | 1 | 白名单只续传 0.51GB/1.79GB Transformers 权重 |
| 2026-08-20 15:22 | `--include` 参数只接受单 pattern | 1 | 根据 CLI 原始 help 改为重复 `--include`，并以目标 blob 哈希验证 |
| 2026-08-20 15:48 | LLaVA 缺少 video processor 配置 | 1 | 补齐两个配置并设置完全离线模式，重跑成功 |
| 2026-08-20 15:50 | 校验 one-liner 引号转义错误 | 1 | 改为 PowerShell 逐文件结构化校验，结果 PASS |

## 5-Question Reboot Check

| Question | Answer |
|---|---|
| Where am I? | Phase 2，统一 runner 实现 |
| Where am I going? | 并行四条实验线、汇总、回收 |
| What's the goal? | 可信的 v2.1 模型算法证据包 |
| What have I learned? | 见 findings.md |
| What have I done? | 见上文 |

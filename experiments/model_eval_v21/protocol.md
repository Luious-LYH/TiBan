# v2.1 实验协议

## 数据隔离

- Train：4 张 Kvasir-VQA-x1 复杂问答图像。
- Dev：3 张 EndoBench 胶囊内镜图像。
- Test：3 张 Kvasir-VQA 原子问答图像。
- 三个 split 图像 ID 无重叠。
- 上轮 QLoRA adapter 使用 train+dev 共 7 张图；v2.1 adapter 对比只读 test，因此 test 未参与训练。

## 统一推理配置

- Batch size：1。
- Decoding：greedy，`do_sample=false`。
- `max_new_tokens=64`。
- 每个 run 先执行 1 次 warmup，计时不含 warmup。
- 指标：透明事实别名准确率、整例全对率、P50/P95、cases/min、tokens/s、峰值 GPU 显存和模型 footprint。

## 评分

事实答案通过 `cases.json` 预注册的 alias 评分。二元题先解析 yes/no 再评分，避免模型复述问题中的 “yes” 造成假阳性。结构化提示输出先尝试 JSON 解析，再使用同一事实评分器。

## 结论边界

Test 只有 3 张公开教学图片，适合证明工程链路、比较同机配置并发现 bad case；不适合作为统计泛化、临床有效性或模型排名结论。


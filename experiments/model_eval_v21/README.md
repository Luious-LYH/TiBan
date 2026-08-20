# v2.1 模型算法实验

统一 runner 对公开内镜教学样例执行多 VLM、量化、旧 QLoRA adapter 独立测试和提示消融。固定 split：4 train / 3 dev / 3 test，图像 ID 不重叠。

所有主对比使用 `test`、batch size 1、greedy decoding、`max_new_tokens=64` 和单次 warmup。结果仅用于作品集工程验证，不代表临床有效性或统计泛化能力。

示例：

```bash
CUDA_VISIBLE_DEVICES=0 python benchmark.py \
  --run-id qwen25_3b_bf16_plain_test \
  --model Qwen/Qwen2.5-VL-3B-Instruct \
  --family qwen25 --precision bf16 --split test
```

每个运行目录包含 `cases.jsonl` 和 `summary.json`；原始 stdout/stderr 由启动命令保存为同名 `.log`。


# 内镜 VLM 推理基准

这是简历展示用的可复现实验包，仅评测 7 张公开教学样例，不代表临床有效性。结果文件必须由脚本真实生成，未运行时不得填写数字。

## 复现

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 hf download Qwen/Qwen2.5-VL-3B-Instruct
CUDA_VISIBLE_DEVICES=0 python benchmark_vlm.py 2>&1 | tee results/run.log
python render_report.py results/latest.json --output results/latest.md
```

指标包括事实级准确率、整例全对率、P50/P95 生成延迟、吞吐、生成 tokens/s 和峰值显存。评分通过 `cases.json` 中预先声明的可接受别名进行，避免用另一个模型充当不透明裁判。

推理成功后可运行 `CUDA_VISIBLE_DEVICES=0 python qlora_smoke.py`。它只执行 1 个样例、1 个 step，用于验证 NF4 QLoRA 工程链路；其 loss 不得解释为模型效果提升。

进一步可运行 `CUDA_VISIBLE_DEVICES=0 python qlora_train_sanity.py`，以 7 个训练样例执行 10 step，并比较固定训练样例的前后 loss。该结果仍是 train-set overfit sanity，不是验证集提升。

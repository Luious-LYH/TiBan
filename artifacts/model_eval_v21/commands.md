# v2.1 复现命令

以下命令使用 SSH 别名，不包含真实地址。所有运行均通过独立 GNU Screen 会话和 `CUDA_VISIBLE_DEVICES` 绑定单卡，stdout/stderr 使用 `tee` 保存。

```bash
python benchmark.py --run-id qwen25_3b_bf16_plain_test --model Qwen/Qwen2.5-VL-3B-Instruct --family qwen25 --precision bf16 --split test
python benchmark.py --run-id qwen25_3b_nf4_plain_test --model Qwen/Qwen2.5-VL-3B-Instruct --family qwen25 --precision nf4 --split test
python benchmark.py --run-id qwen25_3b_int8_plain_test --model Qwen/Qwen2.5-VL-3B-Instruct --family qwen25 --precision int8 --split test
python benchmark.py --run-id qwen25_3b_bf16_adapter_test --model Qwen/Qwen2.5-VL-3B-Instruct --family qwen25 --precision bf16 --adapter adapter_sanity --split test
python benchmark.py --run-id qwen25_3b_bf16_structured_test --model Qwen/Qwen2.5-VL-3B-Instruct --family qwen25 --precision bf16 --split test --prompt-mode structured
```

补充模型使用相同 `test`、BF16、plain prompt 协议。权重下载采用镜像与单 worker，避免并发缓存锁竞争。

DPO：

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 CUDA_VISIBLE_DEVICES=0 \
python dpo_align.py --output results/dpo_alignment --steps 20
```

首次实现将 8 个多模态 batch 常驻 GPU，训练阶段达到 21.33GiB 后 OOM。最终实现改为 CPU 缓存、active pair 即用即传，并固定 DPO 协议图像上限 448px；成功运行峰值 8.66GiB。最终成功运行原始日志保留在 `logs/dpo_alignment.log`，失败门禁记录见 `dpo_run_notes.md`。

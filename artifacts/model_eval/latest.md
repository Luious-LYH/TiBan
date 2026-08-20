# 内镜 VLM 推理基准（真实运行）

- 模型：`Qwen/Qwen2.5-VL-3B-Instruct`
- 硬件：NVIDIA GeForce RTX 4090
- 精度：bfloat16
- 范围：7 public teaching images; single deterministic pass; not a clinical validation

## 指标

| 指标 | 结果 |
|---|---:|
| 样例数 | 7 |
| 整例全对率 | 0.0% |
| 事实级准确率 | 20.0% |
| P50 延迟 | 0.871 s |
| P95 延迟 | 1.646 s |
| 吞吐 | 73.93 cases/min |
| 生成速度 | 19.81 tokens/s |
| 峰值显存 | 10.20 GiB |

## 样例结果

| 样例 | 事实得分 | 延迟 | 模型回答 |
|---|---:|---:|---|
| kvasir_x1_esophagus | 0.0% | 0.945 s | Polyps are present. |
| kvasir_x1_polyp | 33.3% | 0.871 s | Polyps remain, text is not visible, and the abnormality is in the upper part of the image. |
| kvasir_x1_count | 0.0% | 1.849 s | The image shows the following:  1. **Instruments**: 0 2. **Polyps**: 0 3. **Abnormal Findings**: 0  There are no visible instruments, polyps, or any other abnormalities in the image. |
| kvasir_x1_instrument | 66.7% | 1.170 s | 1 instrument, no text, distributed in the oral cavity. |
| endobench_small_intestine_0 | 0.0% | 0.192 s | Stomach |
| endobench_small_intestine_1 | 0.0% | 0.188 s | Stomach |
| endobench_small_intestine_2 | 0.0% | 0.185 s | Stomach |

> 口径：仅为 7 张公开教学图像的单次确定性推理，不代表临床有效性或统计泛化能力。

"""Render a human-readable Markdown report from an immutable JSON result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.result).read_text(encoding="utf-8"))
    metrics = data["metrics"]
    lines = [
        "# 内镜 VLM 推理基准（真实运行）", "",
        f"- 模型：`{data['model']}`",
        f"- 硬件：{data['device']}",
        f"- 精度：{data['precision']}",
        f"- 范围：{data['scope']}", "",
        "## 指标", "",
        "| 指标 | 结果 |", "|---|---:|",
        f"| 样例数 | {metrics['cases']} |",
        f"| 整例全对率 | {metrics['case_exact_rate']:.1%} |",
        f"| 事实级准确率 | {metrics['micro_fact_accuracy']:.1%} |",
        f"| P50 延迟 | {metrics['latency_p50_s']:.3f} s |",
        f"| P95 延迟 | {metrics['latency_p95_s']:.3f} s |",
        f"| 吞吐 | {metrics['throughput_cases_per_min']:.2f} cases/min |",
        f"| 生成速度 | {metrics['generation_tokens_per_s']:.2f} tokens/s |",
        f"| 峰值显存 | {metrics['peak_gpu_memory_gib']:.2f} GiB |", "",
        "## 样例结果", "",
        "| 样例 | 事实得分 | 延迟 | 模型回答 |", "|---|---:|---:|---|",
    ]
    for row in data["cases"]:
        answer = row["answer"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {row['id']} | {row['fact_score']:.1%} | {row['latency_s']:.3f} s | {answer} |")
    lines += ["", "> 口径：仅为 7 张公开教学图像的单次确定性推理，不代表临床有效性或统计泛化能力。", ""]
    Path(args.output).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()


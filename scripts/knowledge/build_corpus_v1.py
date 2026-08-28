"""Build the checked-in, license-gated Chinese Knowledge Corpus v1.

The corpus stores EndoTutor-authored teaching summaries only.  It does not
download or redistribute upstream web-page text, images, patient data, or
restricted third-party material.  The per-document manifest makes the content
hash, upstream URL and review date reproducible for the local indexer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TOPICS = ROOT / "knowledge" / "corpus-v1" / "topics.json"
OUTPUT = ROOT / "knowledge" / "curated" / "corpus-v1"
MANIFEST = ROOT / "knowledge" / "corpus-v1" / "manifest.json"
SOURCE_ID = "niddk-public-health-corpus-v1"
LICENSE_URL = "https://www.niddk.nih.gov/copyright"
SAFETY = "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"


def _slug_safe(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.lower())


def _render(entry: dict[str, object]) -> str:
    facts = [str(item) for item in entry["facts"]]
    topic = str(entry["topic"])
    title = str(entry["title"])
    source_url = str(entry["source_url"])
    source_title = str(entry["source_title"])
    evidence = "\n".join(f"- {fact}" for fact in facts)
    return f"""---
title: {title}
language: zh-CN
domain: {entry['domain']}
namespace: endoscopy
topic: {topic}
source_id: {SOURCE_ID}
source_url: {source_url}
source_title: {source_title}
publisher: National Institute of Diabetes and Digestive and Kidney Diseases (NIDDK)
license: NIDDK majority copyright-free text; exclude logos, graphics and third-party-restricted material
license_url: {LICENSE_URL}
retrieved_at: {date.today().isoformat()}
curation_type: project-authored Chinese educational summary
review_status: source-license-reviewed; medical-content-for-learning-only
---

## 核心概念

本条用于消化内镜和消化系统知识学习，主题为“{title}”。它将公开健康教育资料中的概念整理为可检索的中文学习要点；原始来源见文末链接。它不复制上游页面全文，也不包含图像、商标或第三方受限内容。

## 证据要点

{evidence}

## 题目解析如何使用

面对“{topic}”相关题干，先确认题目问的是概念、症状线索、检查证据还是镜下观察。再把题干中直接给出的部位、时间、检查结果或组织学信息与本条的证据层级对应。没有写在题干或资料中的事实，应保留为未知，而不是由模型补全。

## 内镜与资料边界

内镜图像可以支持对可见部位、黏膜表面、出血线索或形态的教学描述；它本身并不自动确认全部病因、病理结果或治疗选择。需要完整病史、检查、病理或其他资料的结论，应在 Tutor 回答中明确其证据边界。

## 复习提示

将本主题与相邻主题区分：症状不是诊断，内镜所见不是全部临床结论，检查方式也不等于治疗建议。复盘错题时记录“题干给了什么证据、正确选项用了什么证据、还缺什么证据”，比记住孤立结论更适合迁移到新题。

> 来源：[{source_title}]({source_url})。NIDDK 版权页说明其网站上大部分信息可在保留署名且排除例外内容的前提下复用。本条为 EndoTutor 项目中文教学摘要，非官方翻译。{SAFETY}
"""


def build() -> dict[str, object]:
    entries = json.loads(TOPICS.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or len(entries) < 30:
        raise ValueError("Corpus v1 requires at least 30 curated topic documents")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    documents = []
    for entry in entries:
        document_id = f"knowledge-v1-{_slug_safe(str(entry['id']))}"
        path = OUTPUT / f"{_slug_safe(str(entry['id']))}.md"
        content = _render(entry)
        path.write_text(content, encoding="utf-8", newline="\n")
        documents.append(
            {
                "document_id": document_id,
                "path": path.relative_to(ROOT).as_posix(),
                "title": entry["title"],
                "source_id": SOURCE_ID,
                "source_url": entry["source_url"],
                "source_title": entry["source_title"],
                "namespace": "endoscopy",
                "topic": entry["topic"],
                "language": "zh-CN",
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }
        )
    manifest = {
        "corpus_id": "knowledge-corpus-v1",
        "generated_at": date.today().isoformat(),
        "source_policy": "NIDDK public health education text only; project-authored Chinese summaries; no upstream full text, images or third-party restricted content.",
        "license_gate": {"status": "allow", "license_url": LICENSE_URL, "source_id": SOURCE_ID},
        "document_count": len(documents),
        "documents": documents,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the deterministic corpus and manifest")
    args = parser.parse_args()
    if not args.write:
        raise SystemExit("Pass --write to build Knowledge Corpus v1")
    result = build()
    print(json.dumps({"document_count": result["document_count"], "manifest": str(MANIFEST)}, ensure_ascii=False))

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from typing import Any

from app.core.config import SAFETY_NOTICE
from app.schemas import Question
from app.services.question_service import question_service


SUPPORTED_FORMATS = ("jsonl", "csv", "markdown")
REQUIRED_FIELDS = ("question", "question_type", "answer", "explanation")
OBJECTIVE_TYPES = {"单选", "多选", "判断", "报告修改"}
ALL_TYPES = OBJECTIVE_TYPES | {"问答评分"}


class QuestionBankImportService:
    def banks(self) -> dict[str, Any]:
        questions = question_service.list_questions()
        by_body_part = Counter(question.body_part for question in questions)
        by_type = Counter(question.question_type for question in questions)
        text_count = sum(1 for question in questions if not question.image_url)
        visual_count = len(questions) - text_count
        return {
            "schema_version": "qbank-v2.2",
            "items": [
                {
                    "id": "endoscopy_training_pack",
                    "name": "消化内镜研修题库",
                    "question_count": len(questions),
                    "text_question_count": text_count,
                    "visual_question_count": visual_count,
                    "body_parts": dict(by_body_part),
                    "question_types": dict(by_type),
                    "supported_import_formats": list(SUPPORTED_FORMATS),
                    "source_registry": self.source_registry(),
                }
            ],
            "safety_notice": SAFETY_NOTICE,
        }

    def source_registry(self) -> dict[str, Any]:
        return {
            "required_fields": ["source_id", "source_name", "license", "allowed_usage", "content_hash"],
            "default_usage": "teaching_demo",
            "current_sources": [
                {
                    "source_id": "curated_endoscopy_teaching_v22",
                    "source_name": "内镜研修人工整理题库",
                    "license": "project_demo",
                    "allowed_usage": "teaching_demo",
                },
                {
                    "source_id": "public_visual_samples",
                    "source_name": "平台内镜图像样例",
                    "license": "public_sample_review_required",
                    "allowed_usage": "teaching_demo_and_model_eval",
                },
            ],
        }

    def templates(self) -> dict[str, Any]:
        examples = {
            "jsonl": (
                '{"question":"胃息肉样隆起记录最小要素是什么？","question_type":"单选",'
                '"options":["部位、数量、大小、形态","直接写治疗方案"],"answer":"部位、数量、大小、形态",'
                '"explanation":"记录可观察结构化信息。","body_part":"胃","tags":["胃","息肉"]}'
            ),
            "csv": (
                "question,question_type,options,answer,explanation,body_part,tags\n"
                "胃息肉样隆起记录最小要素是什么？,单选,\"部位、数量、大小、形态|直接写治疗方案\","
                "部位、数量、大小、形态,记录可观察结构化信息。,胃,\"胃|息肉\""
            ),
            "markdown": (
                "## 胃息肉样隆起记录最小要素是什么？\n"
                "题型: 单选\n部位: 胃\n标签: 胃, 息肉\n"
                "- [x] 部位、数量、大小、形态\n- [ ] 直接写治疗方案\n"
                "解析: 记录可观察结构化信息。"
            ),
        }
        return {
            "schema_version": "qbank-import-template-v2.2",
            "formats": list(SUPPORTED_FORMATS),
            "required_fields": list(REQUIRED_FIELDS),
            "examples": examples,
            "safety_notice": SAFETY_NOTICE,
        }

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_format = str(payload.get("format") or "jsonl").strip().lower()
        if raw_format not in SUPPORTED_FORMATS:
            return self._response(raw_format, "", [], [self._issue(0, "unsupported_format", "请选择 JSONL、CSV 或 Markdown。")])
        content = str(payload.get("content") or "")
        default_body_part = self._clean(payload.get("default_body_part") or "通用")[:16] or "通用"
        source_name = self._clean(payload.get("source_name") or "个人导入题库")[:40] or "个人导入题库"
        rows, parse_issues = self._parse(raw_format, content)
        normalized: list[dict[str, Any]] = []
        issues = list(parse_issues)
        for index, row in enumerate(rows, start=1):
            item, item_issues = self._normalize_row(row, index, default_body_part, source_name)
            if item_issues:
                issues.extend(item_issues)
            else:
                normalized.append(item)
        return self._response(raw_format, content, normalized, issues)

    def _parse(self, fmt: str, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not content.strip():
            return [], [self._issue(0, "empty_content", "请粘贴题库内容后再校验。")]
        if fmt == "jsonl":
            return self._parse_jsonl(content)
        if fmt == "csv":
            return self._parse_csv(content)
        return self._parse_markdown(content)

    def _parse_jsonl(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        for line_no, line in enumerate(content.splitlines(), start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                issues.append(self._issue(line_no, "invalid_json", "这一行不是合法 JSON。"))
                continue
            if isinstance(value, dict):
                rows.append(value)
            else:
                issues.append(self._issue(line_no, "row_not_object", "JSONL 每行必须是一道题的对象。"))
        return rows, issues

    def _parse_csv(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        stream = io.StringIO(content)
        try:
            rows = [dict(row) for row in csv.DictReader(stream)]
        except csv.Error:
            return [], [self._issue(0, "invalid_csv", "CSV 无法解析，请检查逗号、引号和表头。")]
        if not rows:
            return [], [self._issue(0, "empty_csv", "CSV 至少需要表头和一行题目。")]
        return rows, []

    def _parse_markdown(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        blocks = [block.strip() for block in re.split(r"(?m)^##\s+", content) if block.strip()]
        rows: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        for index, block in enumerate(blocks, start=1):
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            row: dict[str, Any] = {"question": lines[0]}
            options: list[str] = []
            answers: list[str] = []
            for line in lines[1:]:
                key_value = re.match(r"^(题型|部位|标签|解析|答案)\s*[:：]\s*(.+)$", line)
                if key_value:
                    key, value = key_value.groups()
                    mapping = {"题型": "question_type", "部位": "body_part", "标签": "tags", "解析": "explanation", "答案": "answer"}
                    row[mapping[key]] = value
                    continue
                option_match = re.match(r"^[-*]\s*\[(x|X| )\]\s*(.+)$", line)
                if option_match:
                    checked, option = option_match.groups()
                    option = option.strip()
                    options.append(option)
                    if checked.lower() == "x":
                        answers.append(option)
            if options:
                row["options"] = options
            if answers and not row.get("answer"):
                row["answer"] = "；".join(answers)
            rows.append(row)
        if not rows:
            issues.append(self._issue(0, "invalid_markdown", "Markdown 需要用二级标题表示题干，并用 - [x] 标记正确选项。"))
        return rows, issues

    def _normalize_row(
        self,
        row: dict[str, Any],
        index: int,
        default_body_part: str,
        source_name: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        clean = {str(key).strip(): value for key, value in row.items() if str(key).strip()}
        question_type = self._clean(clean.get("question_type") or clean.get("type") or "单选")
        body_part = self._clean(clean.get("body_part") or clean.get("organ") or default_body_part) or default_body_part
        tags = self._split_list(clean.get("tags") or clean.get("teaching_tags"))
        options = self._split_list(clean.get("options"))
        answer = self._clean(clean.get("answer"))
        question = self._clean(clean.get("question") or clean.get("stem"))
        explanation = self._clean(clean.get("explanation") or clean.get("解析"))
        issues: list[dict[str, Any]] = []
        if not question:
            issues.append(self._issue(index, "missing_question", "缺少题干 question。"))
        if question_type not in ALL_TYPES:
            issues.append(self._issue(index, "invalid_question_type", "题型必须是单选、多选、判断、问答评分或报告修改。"))
        if not answer:
            issues.append(self._issue(index, "missing_answer", "缺少参考答案 answer。"))
        if not explanation:
            issues.append(self._issue(index, "missing_explanation", "缺少解析 explanation。"))
        if question_type in OBJECTIVE_TYPES and len(options) < 2:
            issues.append(self._issue(index, "missing_options", "客观题至少需要 2 个选项。"))
        if question_type == "单选" and answer and options and answer not in options:
            issues.append(self._issue(index, "answer_not_in_options", "单选答案必须完整出现在选项中。"))
        if question_type in {"多选", "报告修改"} and answer and options:
            answers = set(self._split_list(answer))
            if not answers or not answers.issubset(set(options)):
                issues.append(self._issue(index, "answer_not_in_options", "多选/报告修改答案需用分号分隔，并全部出现在选项中。"))
        if issues:
            return None, issues
        normalized = {
            "id": self._stable_question_id(question, index),
            "title": self._clean(clean.get("title")) or question[:28],
            "question": question,
            "question_type": question_type,
            "options": options if question_type != "问答评分" else options[:4],
            "answer": answer,
            "explanation": explanation,
            "body_part": body_part,
            "difficulty": self._difficulty(clean.get("difficulty")),
            "question_class": self._question_class(clean.get("question_class"), question_type),
            "task": self._clean(clean.get("task")) or ("开放描述评分" if question_type == "问答评分" else "个人题库练习"),
            "teaching_tags": tags[:6] or [body_part, question_type],
            "image_url": self._clean(clean.get("image_url")) or None,
            "source_dataset": source_name,
            "expected_keywords": self._keywords(clean.get("expected_keywords"), answer, explanation, tags),
        }
        try:
            Question(
                **{
                    **normalized,
                    "image_placeholder": "个人题库图像材料。" if normalized["image_url"] else "本题为纯文本知识题，无需图像。",
                    "case_summary": f"{source_name}导入预览，已通过最小字段校验。",
                    "complexity": {"入门": 1, "进阶": 2, "挑战": 3}[normalized["difficulty"]],
                    "source_type": "教学样例",
                    "citation_note": f"{source_name}，导入前请确认授权和来源。",
                    "false_premise_flag": "治疗方案" in question or "确诊" in question,
                    "atomic_trace": [
                        {
                            "id": f"{normalized['id']}_f1",
                            "fact": "题目要点",
                            "expected": answer[:80],
                            "supported": True,
                            "evidence": explanation[:120],
                            "skill_dimension": "事实组合",
                        }
                    ],
                    "safety_notice": SAFETY_NOTICE,
                }
            )
        except Exception as exc:
            return None, [self._issue(index, "schema_error", f"题目结构未通过平台模型校验：{type(exc).__name__}")]
        return normalized, []

    def _response(
        self,
        fmt: str,
        content: str,
        normalized: list[dict[str, Any]],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16] if content else ""
        type_counts = Counter(item["question_type"] for item in normalized)
        return {
            "schema_version": "qbank-import-v2.2",
            "format": fmt,
            "accepted_count": len(normalized),
            "rejected_count": len(issues),
            "ready_to_publish": bool(normalized) and not issues,
            "items": normalized[:12],
            "issues": issues[:30],
            "summary": {
                "content_hash": content_hash,
                "question_type_counts": dict(type_counts),
                "text_question_count": sum(1 for item in normalized if not item.get("image_url")),
                "visual_question_count": sum(1 for item in normalized if item.get("image_url")),
            },
            "source_registry_required": self.source_registry()["required_fields"],
            "safety_notice": SAFETY_NOTICE,
        }

    def _issue(self, row: int, code: str, message: str) -> dict[str, Any]:
        return {"row": row, "code": code, "message": message}

    def _split_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [self._clean(item) for item in value if self._clean(item)]
        text = self._clean(value)
        if not text:
            return []
        return [part.strip() for part in re.split(r"[|；;\n,，]", text) if part.strip()]

    def _clean(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _difficulty(self, value: Any) -> str:
        text = self._clean(value)
        return text if text in {"入门", "进阶", "挑战"} else "入门"

    def _question_class(self, value: Any, question_type: str) -> str:
        text = self._clean(value)
        if text in {"基础识别", "部位定位", "病变属性", "报告纠错", "一图多问"}:
            return text
        if question_type in {"多选", "报告修改"}:
            return "一图多问" if question_type == "多选" else "报告纠错"
        if question_type == "判断":
            return "报告纠错"
        return "基础识别"

    def _stable_question_id(self, question: str, index: int) -> str:
        digest = hashlib.sha1(f"{index}:{question}".encode("utf-8")).hexdigest()[:10]
        return f"import_preview_{digest}"

    def _keywords(self, raw: Any, answer: str, explanation: str, tags: list[str]) -> list[str]:
        explicit = self._split_list(raw)
        if explicit:
            return explicit[:8]
        candidates = [*tags, *re.findall(r"[\u4e00-\u9fff]{2,}", f"{answer} {explanation}")]
        stop = {"需要", "结合", "记录", "观察", "题目", "解析", "答案"}
        return list(dict.fromkeys(item for item in candidates if item not in stop))[:8]


question_bank_import_service = QuestionBankImportService()

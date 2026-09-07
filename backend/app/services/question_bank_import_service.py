"""Parse, validate and persist learner-owned question bank imports.

The import surface is deliberately small and boring: one parser/normalizer is
shared by preview, creating a new bank and appending to an existing bank.  The
preview endpoint never claims that data was imported; the write endpoint is the
only place that creates ``QuestionBankModel``/``QuestionModel`` rows.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter
from sqlalchemy import delete, select

from app.core.config import DEFAULT_DOMAIN_ID, SAFETY_NOTICE
from app.db.database import SessionLocal
from app.db.models import (
    AttemptModel,
    DocumentVersionModel,
    KnowledgeChunkModel,
    PracticeSessionItemModel,
    PracticeSessionModel,
    QuestionBankModel,
    QuestionBankDeletionModel,
    QuestionImportBatchModel,
    QuestionImportDraftModel,
    QuestionMarkModel,
    QuestionModel,
    ReviewCardModel,
    SourceDocumentModel,
    TutorMessageModel,
    TutorThreadModel,
    BackgroundJobModel,
    EvalLabCaseModel,
    EvalLabRunModel,
    EvalExperimentModel,
    EvalRagProfileModel,
    EvalSuiteModel,
)
from app.domains import build_custom_domain_id, get_domain
from app.schemas import QuestionForGrading


SUPPORTED_FORMATS = ("json", "jsonl", "csv", "markdown")
QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "short_answer"}
MAX_IMPORT_CHARS = 10 * 1024 * 1024
MAX_BANK_NAME_LENGTH = 200
GRADING_ADAPTER = TypeAdapter(QuestionForGrading)

_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "question": ("question", "stem", "question_text", "prompt", "题干", "题目", "问题"),
    "title": ("title", "name", "标题"),
    "question_type": ("question_type", "type", "题型", "类型", "题目类型"),
    "options": ("options", "choices", "option", "选项"),
    "answer": ("answer", "correct_answer", "correct", "答案", "正确答案", "正确选项"),
    "explanation": ("explanation", "explanation_text", "解析", "说明"),
    "body_part": ("body_part", "organ", "category", "分类", "部位"),
    "subject": ("subject", "学科", "科目"),
    "topic": ("topic", "knowledge_point", "知识点", "主题"),
    "tags": ("tags", "teaching_tags", "labels", "标签"),
    "difficulty": ("difficulty", "level", "难度"),
    "image_url": ("image_url", "image", "image_path", "图片"),
    "expected_keywords": ("expected_keywords", "keywords", "评分关键词"),
    "task": ("task", "任务"),
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _field(row: dict[str, Any], name: str) -> Any:
    aliases = {_field_key(alias) for alias in _FIELD_ALIASES[name]}
    for key, value in row.items():
        if _field_key(key) in aliases and value not in (None, ""):
            return value
    return None


def _field_key(value: Any) -> str:
    """Normalize CSV/JSON keys so UTF-8 BOM and common separators are harmless."""

    return re.sub(r"[\s_\-]+", "", str(value).replace("\ufeff", "").strip().lower())


def _column_options(row: dict[str, Any]) -> list[str]:
    """Collect common CSV layouts that use one column per option."""

    numbered: list[tuple[int, str]] = []
    for key, value in row.items():
        normalized = _field_key(key)
        match = re.fullmatch(r"(?:选项|option|choice)([a-h]|[1-8])", normalized)
        if not match:
            match = re.fullmatch(r"([a-h]|[1-8])(?:选项|option|choice)", normalized)
        if not match:
            continue
        marker = match.group(1)
        index = ord(marker) - ord("a") if marker.isalpha() else int(marker) - 1
        text = _clean(value)
        if text and 0 <= index < 8:
            numbered.append((index, text))
    return [text for _, text in sorted(numbered)]


def _split_list(value: Any) -> list[str]:
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = _clean(item.get("text") or item.get("value"))
            else:
                text = _clean(item)
            if text:
                output.append(text)
        return output
    if isinstance(value, dict):
        return [_clean(item) for item in value.values() if _clean(item)]
    text = _clean(value)
    if not text:
        return []
    option_lines = re.findall(r"(?m)^\s*[A-Za-zＡ-Ｚ][\s.)、:：-]+(.+?)\s*$", text)
    if len(option_lines) >= 2:
        return [_clean(item) for item in option_lines if _clean(item)]
    return [part.strip() for part in re.split(r"[|；;\n,，、]", text) if part.strip()]


def _canonical_type(value: Any) -> str:
    text = _clean(value).lower().replace("题", "").replace("_", " ").replace("-", " ")
    if text in {"single choice", "single", "choice", "mcq", "单选", "选择", "选择题"}:
        return "single_choice"
    if text in {"multiple choice", "multiple", "multi", "checkbox", "多选", "多项选择"}:
        return "multiple_choice"
    if text in {"true false", "true/false", "判断", "tf", "yes/no"}:
        return "true_false"
    if text in {"short answer", "short", "essay", "简答", "问答", "问答评分", "填空", "报告修改"}:
        return "short_answer"
    return text


def _canonical_difficulty(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"easy", "简单", "入门", "低", "1"}:
        return "easy"
    if text in {"hard", "困难", "挑战", "高", "3"}:
        return "hard"
    return "medium"


def _bool_answer(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _clean(value).lower()
    if text in {"true", "yes", "y", "1", "正确", "是"}:
        return True
    if text in {"false", "no", "n", "0", "错误", "否"}:
        return False
    return None


def _option_records(options: list[str]) -> list[dict[str, str]]:
    return [{"id": f"opt_{index}", "text": text} for index, text in enumerate(options)]


def _answer_option_indexes(raw_answer: Any, options: list[str]) -> list[int]:
    raw_values = _split_list(raw_answer)
    if not raw_values:
        return []
    indexes: list[int] = []
    for value in raw_values:
        text = _clean(value)
        upper = text.upper()
        match = re.fullmatch(r"(?:OPT[_ -]?)?([A-Z])", upper)
        if match:
            index = ord(match.group(1)) - ord("A")
        elif re.fullmatch(r"\d+", text):
            index = int(text) - 1
        elif text in options:
            index = options.index(text)
        elif text.startswith("opt_") and text[4:].isdigit():
            index = int(text[4:])
        else:
            continue
        if 0 <= index < len(options) and index not in indexes:
            indexes.append(index)
    return indexes


def _answer_key(raw_answer: Any, options: list[str], question_type: str) -> Any:
    if question_type == "true_false":
        return _bool_answer(raw_answer)
    if question_type == "single_choice":
        indexes = _answer_option_indexes(raw_answer, options)
        return indexes[0] if len(indexes) == 1 else None
    if question_type == "multiple_choice":
        indexes = _answer_option_indexes(raw_answer, options)
        return indexes if indexes else None
    return _clean(raw_answer) or None


class QuestionBankImportService:
    def banks(self) -> dict[str, Any]:
        """Legacy catalog metadata retained for the compatibility endpoint."""

        with SessionLocal() as session:
            banks = list(session.scalars(select(QuestionBankModel).order_by(QuestionBankModel.name)))
        return {
            "schema_version": "qbank-import-v3.1.2",
            "items": [
                {
                    "id": bank.bank_id,
                    "name": bank.name,
                    "question_count": bank.question_count,
                    "question_type_counts": dict(bank.question_type_counts or {}),
                    "supported_import_formats": list(SUPPORTED_FORMATS),
                }
                for bank in banks
            ],
            "supported_import_formats": list(SUPPORTED_FORMATS),
            "safety_notice": SAFETY_NOTICE,
        }

    def source_registry(self) -> dict[str, Any]:
        return {
            "required_fields": ["question", "question_type", "answer"],
            "default_usage": "user_ready",
            "note": "请确认导入内容的来源与使用授权；平台仅保存题目和来源摘要。",
        }

    def templates(self) -> dict[str, Any]:
        examples = {
            "json": json.dumps(
                [{"question": "水的化学式是什么？", "question_type": "single_choice", "options": ["H2O", "CO2"], "answer": "A", "explanation": "水由两个氢原子和一个氧原子组成。"}],
                ensure_ascii=False,
            ),
            "jsonl": '{"question":"水的化学式是什么？","question_type":"single_choice","options":["H2O","CO2"],"answer":"A"}',
            "csv": "题干,题型,选项,答案,解析\n水的化学式是什么？,单选,\"H2O|CO2\",A,水由两个氢原子和一个氧原子组成。",
            "markdown": "## 水的化学式是什么？\n题型: 单选\n- [x] H2O\n- [ ] CO2\n解析: 水由两个氢原子和一个氧原子组成。",
        }
        return {
            "schema_version": "qbank-import-template-v3.1.2",
            "formats": list(SUPPORTED_FORMATS),
            "required_fields": ["question", "question_type", "answer"],
            "examples": examples,
            "safety_notice": SAFETY_NOTICE,
        }

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        response, _ = self._validate_payload(payload)
        return response

    def _validate_payload(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        fmt = _clean(payload.get("format") or "jsonl").lower()
        if fmt not in SUPPORTED_FORMATS:
            return self._response(fmt, "", [], [self._issue(0, "unsupported_format", "请选择 JSON、JSONL、CSV 或 Markdown。")]), []
        content = str(payload.get("content") or "")
        if len(content) > MAX_IMPORT_CHARS:
            return self._response(fmt, "", [], [self._issue(0, "content_too_large", "题库文件不能超过 10 MiB。")]), []
        default_body_part = _clean(payload.get("default_body_part") or "通用")[:80] or "通用"
        source_name = _clean(payload.get("source_name") or "个人导入题库")[:120] or "个人导入题库"
        rows, parse_issues = self._parse(fmt, content)
        normalized: list[dict[str, Any]] = []
        issues = list(parse_issues)
        fingerprints: set[str] = set()
        for index, row in enumerate(rows, start=1):
            item, item_issues = self._normalize_row(row, index, default_body_part, source_name)
            if item_issues:
                issues.extend(item_issues)
                continue
            assert item is not None
            if item["fingerprint"] in fingerprints:
                issues.append(self._issue(index, "duplicate_in_file", "题库文件中出现重复题目，已保留首次出现的题目。"))
                continue
            fingerprints.add(item["fingerprint"])
            normalized.append(item)
        return self._response(fmt, content, normalized, issues), normalized

    def import_questions(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = _clean(payload.get("mode") or "create_bank").lower()
        if mode not in {"create_bank", "append_questions"}:
            raise ValueError("mode 必须是 create_bank 或 append_questions。")
        domain_id = self._resolve_domain_id(payload)
        get_domain(domain_id)
        preview, normalized_items = self._validate_payload(payload)
        if not normalized_items:
            raise ValueError("没有可导入的有效题目，请先修正文件中的问题。")
        if mode == "create_bank":
            bank_name = _clean(payload.get("bank_name"))
            if not bank_name:
                raise ValueError("创建题库时必须填写题库名称。")
            if len(bank_name) > MAX_BANK_NAME_LENGTH:
                raise ValueError("题库名称不能超过 200 个字符。")
        else:
            target_bank_id = _clean(payload.get("target_bank_id"))
            if not target_bank_id:
                raise ValueError("补充题目时必须选择已有题库。")

        source_name = _clean(payload.get("source_name") or (payload.get("bank_name") if mode == "create_bank" else "补充题目导入"))[:120] or "个人导入题目"
        content_hash = preview["summary"]["content_hash"]
        with SessionLocal() as session:
            if mode == "create_bank":
                bank_id = self._new_bank_id(session, bank_name)
                bank = QuestionBankModel(
                    bank_id=bank_id,
                    domain_id=domain_id,
                    name=bank_name,
                    description=_clean(payload.get("bank_description")) or f"由 {source_name} 导入的个人题库。",
                    version="import-v3.1.2",
                    status="published",
                    question_count=0,
                    question_type_counts={},
                    modality_counts={},
                    body_parts=[],
                )
                session.add(bank)
            else:
                bank_id = _clean(payload.get("target_bank_id"))
                bank = session.get(QuestionBankModel, bank_id)
                if bank is None:
                    raise KeyError("target bank not found")
                if bank.status != "published":
                    raise ValueError("只能向已发布题库补充题目。")
                if bank.domain_id != domain_id:
                    raise ValueError("补充题目的领域必须与目标题库一致。")

            source_document_id = f"qbank_import_{uuid4().hex[:12]}"
            session.add(SourceDocumentModel(
                document_id=source_document_id,
                domain_id=domain_id,
                bank_id=bank_id,
                name=source_name,
                media_type=self._media_type(preview["format"]),
                content_hash=content_hash,
                status="imported",
                source_id=f"user_import:{content_hash}",
                business_usage="user_ready",
                license_gate_status="needs_review",
                ai_ingestion_allowed=False,
                source_uri=None,
                namespace="qbank_explanations",
                source_scope="user",
                file_name=_clean(payload.get("file_name")) or None,
                size_bytes=len(str(payload.get("content") or "").encode("utf-8")),
            ))
            session.flush()
            existing_keys = set(session.scalars(select(QuestionModel.source_item_id).where(QuestionModel.bank_id == bank_id)))
            inserted = 0
            duplicates = 0
            for item in normalized_items:
                if item["source_item_id"] in existing_keys:
                    duplicates += 1
                    continue
                session.add(self._question_model(item, bank_id, domain_id, source_document_id, source_name))
                existing_keys.add(item["source_item_id"])
                inserted += 1
            session.flush()
            self._refresh_bank_inventory(session, bank)
            session.commit()
            return {
                "mode": mode,
                "bank_id": bank_id,
                "bank_name": bank.name,
                "source_document_id": source_document_id,
                "accepted_count": preview["accepted_count"],
                "imported_count": inserted,
                "duplicate_count": duplicates,
                "rejected_count": preview["rejected_count"],
                "issues": preview["issues"],
                "question_count": bank.question_count,
                "question_type_counts": dict(bank.question_type_counts or {}),
                "status": "partial" if preview["rejected_count"] else "imported",
                "api_source": "backend",
            }

    def create_review_batch(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Parse once and persist normalized questions for author review.

        The original source text is intentionally not copied into the review
        table.  The content hash and source metadata are enough to identify the
        import while the normalized question payload is all the reviewer needs.
        """

        domain_id = self._resolve_domain_id(payload)
        get_domain(domain_id)
        preview, normalized_items = self._validate_payload(payload)
        if not normalized_items:
            raise ValueError("没有可审核的有效题目，请先修正文件格式或内容。")
        source_name = _clean(payload.get("source_name") or "个人导入题库")[:120] or "个人导入题库"
        file_name = _clean(payload.get("file_name"))[:300] or None
        batch_id = f"qbank_batch_{uuid4().hex[:14]}"
        with SessionLocal() as session:
            batch = QuestionImportBatchModel(
                batch_id=batch_id,
                domain_id=domain_id,
                source_name=source_name,
                file_name=file_name,
                format=preview["format"],
                content_hash=preview["summary"]["content_hash"],
                status="reviewing",
                total_count=len(normalized_items),
                pending_count=len(normalized_items),
                issues=preview["issues"][:50],
            )
            session.add(batch)
            for ordinal, item in enumerate(normalized_items, start=1):
                session.add(QuestionImportDraftModel(
                    draft_id=f"qbank_draft_{uuid4().hex[:14]}",
                    batch_id=batch_id,
                    ordinal=ordinal,
                    status="pending",
                    payload=item,
                ))
            session.commit()
            return self._batch_payload(session, batch, include_items=True)

    def list_review_batches(self, status: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as session:
            query = select(QuestionImportBatchModel).order_by(QuestionImportBatchModel.updated_at.desc())
            if status:
                query = query.where(QuestionImportBatchModel.status == status)
            return [self._batch_payload(session, batch) for batch in session.scalars(query)]

    def get_review_batch(self, batch_id: str) -> dict[str, Any]:
        with SessionLocal() as session:
            batch = session.get(QuestionImportBatchModel, batch_id)
            if batch is None:
                raise KeyError("review batch not found")
            return self._batch_payload(session, batch, include_items=True)

    def review_draft(self, batch_id: str, draft_id: str, status: str, review_note: str | None = None) -> dict[str, Any]:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("审核状态只能是 pending、approved 或 rejected。")
        with SessionLocal() as session:
            batch = session.get(QuestionImportBatchModel, batch_id)
            draft = session.get(QuestionImportDraftModel, draft_id)
            if batch is None or draft is None or draft.batch_id != batch_id:
                raise KeyError("review draft not found")
            if draft.status == "published" and status != "published":
                raise ValueError("已发布题目不能重新修改审核状态。")
            draft.status = status
            draft.review_note = _clean(review_note)[:500] or None
            self._refresh_batch_counts(batch, session)
            session.commit()
            return self._batch_payload(session, batch, include_items=True)

    def review_drafts(self, batch_id: str, draft_ids: list[str] | None, status: str, review_note: str | None = None) -> dict[str, Any]:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("审核状态只能是 pending、approved 或 rejected。")
        with SessionLocal() as session:
            batch = session.get(QuestionImportBatchModel, batch_id)
            if batch is None:
                raise KeyError("review batch not found")
            query = select(QuestionImportDraftModel).where(QuestionImportDraftModel.batch_id == batch_id)
            if draft_ids:
                query = query.where(QuestionImportDraftModel.draft_id.in_(draft_ids))
            drafts = list(session.scalars(query))
            if draft_ids and len(drafts) != len(set(draft_ids)):
                raise KeyError("one or more review drafts not found")
            for draft in drafts:
                if draft.status != "published":
                    draft.status = status
                    draft.review_note = _clean(review_note)[:500] or None
            self._refresh_batch_counts(batch, session)
            session.commit()
            return self._batch_payload(session, batch, include_items=True)

    def publish_review_batch(self, batch_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        mode = _clean(payload.get("mode") or "create_bank")
        if mode not in {"create_bank", "append_questions"}:
            raise ValueError("发布方式只能是创建新题库或补充已有题库。")
        with SessionLocal() as session:
            batch = session.get(QuestionImportBatchModel, batch_id)
            if batch is None:
                raise KeyError("review batch not found")
            approved = list(session.scalars(select(QuestionImportDraftModel).where(
                QuestionImportDraftModel.batch_id == batch_id,
                QuestionImportDraftModel.status == "approved",
            ).order_by(QuestionImportDraftModel.ordinal)))
            if not approved:
                raise ValueError("请至少审核通过一道题后再发布。")

            if batch.published_bank_id:
                bank_id = batch.published_bank_id
                bank = session.get(QuestionBankModel, bank_id)
                if bank is None:
                    raise KeyError("published target bank not found")
            elif mode == "create_bank":
                bank_name = _clean(payload.get("bank_name"))
                if not bank_name:
                    raise ValueError("创建新题库时必须填写题库名称。")
                if len(bank_name) > MAX_BANK_NAME_LENGTH:
                    raise ValueError("题库名称不能超过 200 个字符。")
                bank_id = self._new_bank_id(session, bank_name)
                bank = QuestionBankModel(
                    bank_id=bank_id,
                    domain_id=batch.domain_id,
                    name=bank_name,
                    description=_clean(payload.get("bank_description")) or f"由 {batch.source_name} 导入并经作者审核的题库。",
                    version="import-v3.1.2",
                    status="published",
                    question_count=0,
                    question_type_counts={},
                    modality_counts={},
                    body_parts=[],
                )
                session.add(bank)
                batch.published_bank_id = bank_id
            else:
                bank_id = _clean(payload.get("target_bank_id"))
                if not bank_id:
                    raise ValueError("请选择要补充的已有题库。")
                bank = session.get(QuestionBankModel, bank_id)
                if bank is None:
                    raise KeyError("target bank not found")
                if bank.status != "published":
                    raise ValueError("只能向已发布题库补充题目。")
                if bank.domain_id != batch.domain_id:
                    raise ValueError("补充题目的领域必须与目标题库一致。")
                batch.published_bank_id = bank_id

            source_document = self._ensure_batch_source_document(session, batch, bank_id)
            existing_keys = set(session.scalars(select(QuestionModel.source_item_id).where(QuestionModel.bank_id == bank_id)))
            imported_count = 0
            duplicate_count = 0
            for draft in approved:
                item = draft.payload
                if item["source_item_id"] in existing_keys:
                    duplicate_count += 1
                else:
                    session.add(self._question_model(item, bank_id, batch.domain_id, source_document.document_id, batch.source_name))
                    existing_keys.add(item["source_item_id"])
                    imported_count += 1
                draft.status = "published"
                draft.published_at = datetime.utcnow()
            session.flush()
            self._refresh_bank_inventory(session, bank)
            self._refresh_batch_counts(batch, session)
            session.commit()
            return {
                "batch_id": batch_id,
                "bank_id": bank_id,
                "bank_name": bank.name,
                "imported_count": imported_count,
                "duplicate_count": duplicate_count,
                "published_count": batch.published_count,
                "pending_count": batch.pending_count,
                "status": batch.status,
                "api_source": "backend",
            }

    def delete_review_batch(self, batch_id: str) -> None:
        with SessionLocal() as session:
            batch = session.get(QuestionImportBatchModel, batch_id)
            if batch is None:
                raise KeyError("review batch not found")
            session.execute(delete(QuestionImportDraftModel).where(QuestionImportDraftModel.batch_id == batch_id))
            session.delete(batch)
            session.commit()

    def delete_question_bank(self, bank_id: str) -> None:
        """Delete a bank and dependent state with a restart-safe tombstone.

        Seeded and imported banks share the same user-managed catalog contract.
        The tombstone prevents demo bootstrap from silently recreating a bank
        that the user explicitly removed after a local service restart.
        """

        with SessionLocal() as session:
            bank = session.get(QuestionBankModel, bank_id)
            if bank is None:
                raise KeyError("question bank not found")
            if session.get(QuestionBankDeletionModel, bank_id) is None:
                session.add(QuestionBankDeletionModel(bank_id=bank_id))
            question_ids = list(session.scalars(select(QuestionModel.question_id).where(QuestionModel.bank_id == bank_id)))
            session_ids = list(session.scalars(select(PracticeSessionModel.session_id).where(PracticeSessionModel.bank_id == bank_id)))
            tutor_ids = list(session.scalars(select(TutorThreadModel.tutor_thread_id).where(TutorThreadModel.practice_session_id.in_(session_ids)))) if session_ids else []
            if question_ids:
                session.execute(delete(QuestionMarkModel).where(QuestionMarkModel.question_id.in_(question_ids)))
                session.execute(delete(ReviewCardModel).where(ReviewCardModel.question_id.in_(question_ids)))
                session.execute(delete(AttemptModel).where(AttemptModel.question_id.in_(question_ids)))
            if tutor_ids:
                session.execute(delete(TutorMessageModel).where(TutorMessageModel.tutor_thread_id.in_(tutor_ids)))
                session.execute(delete(TutorThreadModel).where(TutorThreadModel.tutor_thread_id.in_(tutor_ids)))
            if session_ids:
                session.execute(delete(PracticeSessionItemModel).where(PracticeSessionItemModel.practice_session_id.in_(session_ids)))
                session.execute(delete(PracticeSessionModel).where(PracticeSessionModel.session_id.in_(session_ids)))
            suite_ids = list(session.scalars(select(EvalSuiteModel.suite_id).where(EvalSuiteModel.bank_id == bank_id)))
            profile_ids = list(session.scalars(select(EvalRagProfileModel.profile_id).where(EvalRagProfileModel.bank_id == bank_id)))
            if suite_ids:
                experiment_ids = list(session.scalars(select(EvalExperimentModel.experiment_id).where(EvalExperimentModel.suite_id.in_(suite_ids))))
                run_ids = list(session.scalars(select(EvalLabRunModel.run_id).where(EvalLabRunModel.experiment_id.in_(experiment_ids)))) if experiment_ids else []
                job_ids = list(session.scalars(select(EvalLabRunModel.job_id).where(EvalLabRunModel.run_id.in_(run_ids)))) if run_ids else []
                if run_ids:
                    session.execute(delete(EvalLabCaseModel).where(EvalLabCaseModel.run_id.in_(run_ids)))
                    session.execute(delete(EvalLabRunModel).where(EvalLabRunModel.run_id.in_(run_ids)))
                if job_ids:
                    session.execute(delete(BackgroundJobModel).where(BackgroundJobModel.job_id.in_(job_ids)))
                if experiment_ids:
                    session.execute(delete(EvalExperimentModel).where(EvalExperimentModel.experiment_id.in_(experiment_ids)))
                session.execute(delete(EvalSuiteModel).where(EvalSuiteModel.suite_id.in_(suite_ids)))
            if profile_ids:
                session.execute(delete(EvalRagProfileModel).where(EvalRagProfileModel.profile_id.in_(profile_ids)))
            document_ids = list(session.scalars(select(SourceDocumentModel.document_id).where(SourceDocumentModel.bank_id == bank_id)))
            if document_ids:
                session.execute(delete(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id.in_(document_ids)))
                session.execute(delete(DocumentVersionModel).where(DocumentVersionModel.document_id.in_(document_ids)))
                session.execute(delete(SourceDocumentModel).where(SourceDocumentModel.document_id.in_(document_ids)))
            linked_batches = list(session.scalars(select(QuestionImportBatchModel).where(QuestionImportBatchModel.published_bank_id == bank_id)))
            for batch in linked_batches:
                batch.published_bank_id = None
                published_drafts = session.scalars(select(QuestionImportDraftModel).where(
                    QuestionImportDraftModel.batch_id == batch.batch_id,
                    QuestionImportDraftModel.status == "published",
                ))
                for draft in published_drafts:
                    draft.status = "approved"
                    draft.published_at = None
                self._refresh_batch_counts(batch, session)
            session.execute(delete(QuestionModel).where(QuestionModel.bank_id == bank_id))
            session.delete(bank)
            session.commit()

    def get_question_for_edit(self, bank_id: str, question_id: str) -> dict[str, Any]:
        """Return the authoring projection, including the answer key.

        This projection is intentionally separate from the learner-facing
        question API so opening an edit form does not widen the practice trust
        boundary.
        """

        with SessionLocal() as session:
            bank = session.get(QuestionBankModel, bank_id)
            question = session.get(QuestionModel, question_id)
            if bank is None or question is None or question.bank_id != bank_id:
                raise KeyError("question not found")
            if question.business_usage != "user_ready":
                raise ValueError("只有已发布题目可以编辑。")
            return self._question_edit_payload(question)

    def update_question_bank(self, bank_id: str, payload: dict[str, Any]) -> None:
        name = _clean(payload.get("name"))
        description = _clean(payload.get("description"))
        if not name:
            raise ValueError("题库名称不能为空。")
        with SessionLocal() as session:
            bank = session.get(QuestionBankModel, bank_id)
            if bank is None:
                raise KeyError("question bank not found")
            bank.name = name[:MAX_BANK_NAME_LENGTH]
            bank.description = description[:1000] or "由 TiBan 用户维护的学习题库。"
            session.commit()

    def update_question(self, bank_id: str, question_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with SessionLocal() as session:
            bank = session.get(QuestionBankModel, bank_id)
            question = session.get(QuestionModel, question_id)
            if bank is None or question is None or question.bank_id != bank_id:
                raise KeyError("question not found")
            if question.business_usage != "user_ready":
                raise ValueError("只有已发布题目可以编辑。")
            row = {
                "title": payload.get("title"),
                "question": payload.get("stem"),
                "question_type": payload.get("question_type"),
                "options": [option.get("text", "") for option in (payload.get("options") or [])],
                "answer": payload.get("answer"),
                "explanation": payload.get("explanation"),
                "difficulty": payload.get("difficulty"),
                "tags": payload.get("tags"),
                "body_part": payload.get("body_part"),
                "subject": payload.get("subject"),
                "topic": payload.get("topic"),
                "task": payload.get("task"),
                "image_url": question.image_url,
            }
            item, issues = self._normalize_row(row, 1, question.body_part or "通用", question.source_dataset or "用户题库")
            if issues or item is None:
                raise ValueError("；".join(str(issue["message"]) for issue in issues) or "题目内容无效。")
            duplicate = session.scalar(select(QuestionModel).where(
                QuestionModel.bank_id == bank_id,
                QuestionModel.source_item_id == item["source_item_id"],
                QuestionModel.question_id != question_id,
            ))
            if duplicate is not None:
                raise ValueError("保存失败：题库中已经存在相同题目。")
            question.question_type = item["question_type"]
            question.modality = "image" if item["image_url"] else "text"
            question.title = item["title"][:300]
            question.stem = item["question"]
            question.difficulty = item["difficulty"]
            question.complexity = item["complexity"]
            question.task = item["task"][:120]
            question.body_part = item["body_part"]
            question.options = item["options"]
            question.grading_payload = self._grading_payload(item)
            question.explanation = item["explanation"]
            question.teaching_tags = item["teaching_tags"]
            question.expected_keywords = item["expected_keywords"]
            question.subject = item["subject"]
            question.topic = item["topic"]
            question.source_item_id = item["source_item_id"]
            question.official_explanation_available = item["explanation_available"]
            question.explanation_source = "dataset_gold" if item["explanation_available"] else "none"
            session.flush()
            self._refresh_bank_inventory(session, bank)
            session.commit()
            return self._question_edit_payload(question)

    def _question_edit_payload(self, question: QuestionModel) -> dict[str, Any]:
        grading = dict(question.grading_payload or {})
        question_type = question.question_type
        if question_type == "single_choice":
            option_id = str(grading.get("correct_option_id", ""))
            option_index = next((index for index, option in enumerate(question.options or []) if option.get("id") == option_id), None)
            answer: Any = chr(65 + option_index) if option_index is not None else ""
        elif question_type == "multiple_choice":
            option_ids = {str(value) for value in grading.get("correct_option_ids", [])}
            answer = "|".join(chr(65 + index) for index, option in enumerate(question.options or []) if option.get("id") in option_ids)
        elif question_type == "true_false":
            answer = bool(grading.get("correct_value"))
        else:
            answer = "；".join(str(value) for value in (grading.get("expected_facts") or question.expected_keywords or []))
        return {
            "question_id": question.question_id,
            "bank_id": question.bank_id,
            "title": question.title,
            "stem": question.stem,
            "question_type": question_type,
            "options": list(question.options or []),
            "answer": answer,
            "explanation": question.explanation,
            "difficulty": question.difficulty,
            "tags": list(question.teaching_tags or []),
            "body_part": question.body_part,
            "subject": question.subject,
            "topic": question.topic,
            "task": question.task,
        }

    def _ensure_batch_source_document(self, session: Any, batch: QuestionImportBatchModel, bank_id: str) -> SourceDocumentModel:
        if batch.source_document_id:
            document = session.get(SourceDocumentModel, batch.source_document_id)
            if document is not None:
                return document
        document = SourceDocumentModel(
            document_id=f"qbank_import_{uuid4().hex[:12]}",
            domain_id=batch.domain_id,
            bank_id=bank_id,
            name=batch.source_name,
            media_type=self._media_type(batch.format),
            content_hash=batch.content_hash,
            status="imported",
            source_id=f"user_import:{batch.content_hash}",
            business_usage="user_ready",
            license_gate_status="needs_review",
            ai_ingestion_allowed=False,
            source_uri=None,
            namespace="qbank_explanations",
            source_scope="user",
            file_name=batch.file_name,
            size_bytes=0,
        )
        session.add(document)
        session.flush()
        batch.source_document_id = document.document_id
        return document

    def _refresh_batch_counts(self, batch: QuestionImportBatchModel, session: Any) -> None:
        counts = Counter(session.scalars(select(QuestionImportDraftModel.status).where(QuestionImportDraftModel.batch_id == batch.batch_id)))
        batch.total_count = sum(counts.values())
        batch.pending_count = counts.get("pending", 0)
        batch.approved_count = counts.get("approved", 0)
        batch.rejected_count = counts.get("rejected", 0)
        batch.published_count = counts.get("published", 0)
        if batch.pending_count:
            batch.status = "reviewing" if not batch.published_count else "partially_published"
        elif batch.published_count and not batch.pending_count:
            batch.status = "published" if not batch.rejected_count else "published_with_rejections"
        elif batch.approved_count:
            batch.status = "ready_to_publish"
        else:
            batch.status = "reviewed"

    def _batch_payload(self, session: Any, batch: QuestionImportBatchModel, *, include_items: bool = False, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        self._refresh_batch_counts(batch, session)
        drafts = list(session.scalars(select(QuestionImportDraftModel).where(QuestionImportDraftModel.batch_id == batch.batch_id).order_by(QuestionImportDraftModel.ordinal))) if include_items else []
        return {
            "batch_id": batch.batch_id,
            "domain_id": batch.domain_id,
            "source_name": batch.source_name,
            "file_name": batch.file_name,
            "format": batch.format,
            "status": batch.status,
            "total_count": batch.total_count,
            "pending_count": batch.pending_count,
            "approved_count": batch.approved_count,
            "rejected_count": batch.rejected_count,
            "published_count": batch.published_count,
            "published_bank_id": batch.published_bank_id,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "issues": issues if issues is not None else list(batch.issues or []),
            "items": [{
                "draft_id": draft.draft_id,
                "ordinal": draft.ordinal,
                "status": draft.status,
                "review_note": draft.review_note,
                **draft.payload,
            } for draft in drafts],
        }

    def _parse(self, fmt: str, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if not content.strip():
            return [], [self._issue(0, "empty_content", "请选择或粘贴题库内容后再继续。")]
        if fmt == "json":
            try:
                value = json.loads(content)
            except json.JSONDecodeError as exc:
                return [], [self._issue(exc.lineno, "invalid_json", "JSON 文件格式无效，请检查括号和引号。")]
            if isinstance(value, list):
                rows = [item for item in value if isinstance(item, dict)]
                issues = [
                    self._issue(index, "row_not_object", "JSON 数组中的每一项必须是一道题的对象。")
                    for index, item in enumerate(value, start=1)
                    if not isinstance(item, dict)
                ]
                if not value:
                    issues.append(self._issue(0, "empty_json", "JSON 中没有可导入的题目。"))
                return rows, issues
            if isinstance(value, dict):
                for key in ("questions", "items", "data", "题目"):
                    if isinstance(value.get(key), list):
                        rows = [item for item in value[key] if isinstance(item, dict)]
                        issues = [
                            self._issue(index, "row_not_object", "题目数组中的每一项必须是一道题的对象。")
                            for index, item in enumerate(value[key], start=1)
                            if not isinstance(item, dict)
                        ]
                        if not value[key]:
                            issues.append(self._issue(0, "empty_json", "JSON 中没有可导入的题目。"))
                        return rows, issues
                return [value], []
            return [], [self._issue(1, "row_not_object", "JSON 根节点必须是题目对象或题目数组。")]
        if fmt == "jsonl":
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
        if fmt == "csv":
            try:
                # ``utf-8-sig`` makes files exported from Excel/Numbers work
                # without leaving the BOM attached to the first header.
                reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
                if not reader.fieldnames:
                    return [], [self._issue(0, "missing_header", "CSV 至少需要一行表头。")]
                rows = [dict(row) for row in reader]
            except csv.Error:
                return [], [self._issue(0, "invalid_csv", "CSV 无法解析，请检查逗号、引号和表头。")]
            return rows, ([] if rows else [self._issue(0, "empty_csv", "CSV 至少需要一行题目。")])
        return self._parse_markdown(content)

    def _parse_markdown(self, content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        headings = list(re.finditer(r"(?m)^#{2,3}\s+(.+?)\s*$", content))
        if not headings:
            return [], [self._issue(0, "invalid_markdown", "Markdown 请用二级标题分隔题目，并用列表表示选项。")]
        rows: list[dict[str, Any]] = []
        for heading_index, heading in enumerate(headings):
            end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(content)
            block = content[heading.end():end].strip()
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            row: dict[str, Any] = {"title": _clean(heading.group(1)), "question": _clean(heading.group(1))}
            options: list[str] = []
            answers: list[str] = []
            for line in lines:
                bold_value = re.match(r"^\*\*(问题|题目|题干|答案|正确答案|解析|说明)\s*[:：]\*\*\s*(.*)$", line)
                if bold_value:
                    key, value = bold_value.groups()
                    if key in {"问题", "题目", "题干"}:
                        row["question"] = value
                    elif key in {"答案", "正确答案"}:
                        row["answer"] = value
                    else:
                        row["explanation"] = value
                    continue
                key_value = re.match(r"^(题型|类型|部位|分类|主题|知识点|标签|解析|说明|答案|正确答案)\s*[:：]\s*(.+)$", line)
                if key_value:
                    key, value = key_value.groups()
                    mapping = {"题型": "question_type", "类型": "question_type", "部位": "body_part", "分类": "body_part", "主题": "topic", "知识点": "topic", "标签": "tags", "解析": "explanation", "说明": "explanation", "答案": "answer", "正确答案": "answer"}
                    row[mapping[key]] = value
                    continue
                option_match = re.match(r"^[-*]\s*(?:\[(x|X| )\]\s*)?(.+)$", line)
                if option_match:
                    checked, option = option_match.groups()
                    option = re.sub(r"^[A-Za-zＡ-Ｚ][.)、:：-]\s*", "", option).strip()
                    options.append(option)
                    if checked and checked.lower() == "x":
                        answers.append(option)
            if options:
                row["options"] = options
            if answers and not row.get("answer"):
                row["answer"] = "；".join(answers)
            rows.append(row)
        return rows, []

    def _normalize_row(self, row: dict[str, Any], index: int, default_body_part: str, source_name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        question = _clean(_field(row, "question"))
        options = _split_list(_field(row, "options"))
        if not options:
            options = _column_options(row)
        answer_raw = _field(row, "answer")
        answer = _clean(answer_raw)
        raw_type = _field(row, "question_type")
        question_type = _canonical_type(raw_type or "single_choice")
        if raw_type in (None, ""):
            if _bool_answer(answer_raw) is not None and (not options or {item.lower() for item in options} == {"正确", "错误"}):
                question_type = "true_false"
            elif len(_split_list(answer_raw)) > 1:
                question_type = "multiple_choice"
            elif not options:
                # A question plus a free-form answer is a usable short-answer
                # item even when the source omitted its type. Requiring an
                # invented choice list would make common hand-written imports
                # impossible to review.
                question_type = "short_answer"
        raw_explanation = _clean(_field(row, "explanation"))
        explanation = raw_explanation or "无"
        issues: list[dict[str, Any]] = []
        if not question:
            issues.append(self._issue(index, "missing_question", "缺少题干。"))
        if question_type not in QUESTION_TYPES:
            issues.append(self._issue(index, "invalid_question_type", "题型支持单选、多选、判断和简答。"))
        if not answer:
            issues.append(self._issue(index, "missing_answer", "缺少参考答案。"))
        key = _answer_key(answer_raw, options, question_type)
        if answer:
            if question_type == "single_choice" and (len(options) < 2 or key is None):
                issues.append(self._issue(index, "invalid_single_choice", "单选题需要至少 2 个选项，答案可写 A、1 或完整选项文本。"))
            if question_type == "multiple_choice" and (len(options) < 2 or not isinstance(key, list) or not key):
                issues.append(self._issue(index, "invalid_multiple_choice", "多选题需要至少 2 个选项，答案可用 A|C 或完整选项文本。"))
            if question_type == "true_false" and key is None:
                issues.append(self._issue(index, "invalid_true_false", "判断题答案请填写正确/错误、true/false 或是/否。"))
        if issues:
            return None, issues

        body_part = _clean(_field(row, "body_part") or default_body_part)[:80] or default_body_part
        tags = _split_list(_field(row, "tags"))[:8]
        title = _clean(_field(row, "title")) or question[:40]
        difficulty = _canonical_difficulty(_field(row, "difficulty"))
        image_url = _clean(_field(row, "image_url")) or None
        subject = _clean(_field(row, "subject"))[:160] or None
        topic = _clean(_field(row, "topic"))[:160] or None
        keywords = _split_list(_field(row, "expected_keywords"))[:8]
        if not keywords:
            keywords = [item for item in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", f"{answer} {explanation}") if item not in {"需要", "结合", "题干", "资料", "复核"}][:8]
        fingerprint = _sha(json.dumps({"question": question, "question_type": question_type, "options": options, "answer": key}, ensure_ascii=False, sort_keys=True))
        normalized = {
            "title": title,
            "question": question,
            "question_type": question_type,
            "options": _option_records(options) if question_type in {"single_choice", "multiple_choice"} else [],
            "answer": answer,
            "answer_key": key,
            "explanation": explanation,
            "explanation_available": bool(raw_explanation),
            "body_part": body_part,
            "difficulty": difficulty,
            "complexity": {"easy": 1, "medium": 2, "hard": 3}[difficulty],
            "question_class": "基础识别",
            "task": _clean(_field(row, "task")) or "个人题库练习",
            "teaching_tags": tags or [body_part],
            "image_url": image_url,
            "subject": subject,
            "topic": topic,
            "source_dataset": source_name,
            "expected_keywords": keywords,
            "fingerprint": fingerprint,
            "source_item_id": f"import_question:{fingerprint}",
        }
        try:
            if question_type == "single_choice":
                grading_payload = {"question_type": question_type, "correct_option_id": f"opt_{key}"}
            elif question_type == "multiple_choice":
                grading_payload = {"question_type": question_type, "correct_option_ids": [f"opt_{item}" for item in key]}
            elif question_type == "true_false":
                grading_payload = {"question_type": question_type, "correct_value": key}
            else:
                grading_payload = {"question_type": question_type, "rubric": {"type": "deterministic_keyword_coverage", "max_score": 100}, "expected_facts": keywords or [answer], "reference_constraints": []}
            GRADING_ADAPTER.validate_python({
                "id": f"preview_{fingerprint[:12]}",
                "bank_id": "preview",
                "domain_id": DEFAULT_DOMAIN_ID,
                "title": title,
                "stem": question,
                "case_summary": f"{source_name} 导入题目。",
                "modality": "image" if image_url else "text",
                "image_url": image_url,
                "image_alt": "导入题目图像" if image_url else None,
                "difficulty": difficulty,
                "tags": tags or [body_part],
                "body_part": body_part,
                "source_dataset": source_name,
                "citation_note": f"{source_name}，请确认来源与使用授权。",
                "question_type": question_type,
                **({"options": normalized["options"]} if question_type in {"single_choice", "multiple_choice"} else {}),
                "explanation": explanation,
                "teaching_tags": tags or [body_part],
                **grading_payload,
            })
        except Exception:
            return None, [self._issue(index, "schema_error", "题目结构未通过平台公共题目合同校验。")]
        return normalized, []

    def _response(self, fmt: str, content: str, normalized: list[dict[str, Any]], issues: list[dict[str, Any]]) -> dict[str, Any]:
        type_counts = Counter(item["question_type"] for item in normalized)
        public_items = [{key: item[key] for key in ("title", "question", "question_type", "options", "difficulty", "body_part", "explanation")} for item in normalized]
        return {
            "schema_version": "qbank-import-v3.1.2",
            "format": fmt,
            "accepted_count": len(normalized),
            "rejected_count": len(issues),
            "ready_to_publish": bool(normalized),
            "items": public_items,
            "issues": issues[:50],
            "summary": {"content_hash": _sha(content)[:16] if content else "", "question_type_counts": dict(type_counts), "text_question_count": sum(1 for item in normalized if not item["image_url"]), "visual_question_count": sum(1 for item in normalized if item["image_url"])},
            "source_registry_required": self.source_registry()["required_fields"],
            "safety_notice": SAFETY_NOTICE,
        }

    def _question_model(self, item: dict[str, Any], bank_id: str, domain_id: str, source_document_id: str, source_name: str) -> QuestionModel:
        return QuestionModel(
            question_id=f"qimport_{bank_id.replace('-', '_')}_{item['fingerprint'][:20]}",
            bank_id=bank_id,
            domain_id=domain_id,
            question_type=item["question_type"],
            modality="image" if item["image_url"] else "text",
            title=item["title"][:300],
            stem=item["question"],
            case_summary=f"{source_name} 导入题目；请结合题干和来源资料完成学习。",
            image_url=item["image_url"],
            image_alt="导入题目图像" if item["image_url"] else None,
            difficulty=item["difficulty"],
            complexity=item["complexity"],
            question_class=item["question_class"],
            task=item["task"][:120],
            body_part=item["body_part"],
            source_type="用户导入",
            source_dataset=source_name,
            citation_note=f"{source_name}，请确认来源与使用授权。",
            options=item["options"],
            grading_payload=self._grading_payload(item),
            explanation=item["explanation"],
            teaching_tags=item["teaching_tags"],
            expected_keywords=item["expected_keywords"],
            false_premise=False,
            doctor_review_required=domain_id == "endoscopy",
            safety_notice=SAFETY_NOTICE if domain_id == "endoscopy" else "用于学习训练，请结合课程资料或教师指导复核。",
            source_document_id=source_document_id,
            source_item_id=item["source_item_id"],
            derived_from_dataset=None,
            business_usage="user_ready",
            answer_source="dataset_gold",
            explanation_source="dataset_gold" if item["explanation_available"] else "none",
            license_gate_status="needs_review",
            source_uri=None,
            official_explanation_available=item["explanation_available"],
            subject=item["subject"],
            topic=item["topic"],
        )

    def _grading_payload(self, item: dict[str, Any]) -> dict[str, Any]:
        question_type = item["question_type"]
        if question_type == "single_choice":
            return {"question_type": question_type, "correct_option_id": f"opt_{item['answer_key']}"}
        if question_type == "multiple_choice":
            return {"question_type": question_type, "correct_option_ids": [f"opt_{index}" for index in item["answer_key"]]}
        if question_type == "true_false":
            return {"question_type": question_type, "correct_value": item["answer_key"]}
        return {"question_type": question_type, "rubric": {"type": "deterministic_keyword_coverage", "max_score": 100}, "expected_facts": item["expected_keywords"] or [item["answer"]], "reference_constraints": []}

    def _new_bank_id(self, session: Any, bank_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", bank_name.lower()).strip("-")[:35] or "imported-bank"
        candidate = f"bank-import-{slug}-{uuid4().hex[:8]}"
        while session.get(QuestionBankModel, candidate) is not None:
            candidate = f"bank-import-{slug}-{uuid4().hex[:8]}"
        return candidate

    def _refresh_bank_inventory(self, session: Any, bank: QuestionBankModel) -> None:
        questions = list(session.scalars(select(QuestionModel).where(QuestionModel.bank_id == bank.bank_id)))
        bank.question_count = len(questions)
        bank.question_type_counts = dict(Counter(item.question_type for item in questions))
        bank.modality_counts = dict(Counter(item.modality for item in questions))
        bank.body_parts = sorted({item.body_part for item in questions if item.body_part})

    def _media_type(self, fmt: str) -> str:
        return {"json": "application/json", "jsonl": "application/jsonl", "csv": "text/csv", "markdown": "text/markdown"}.get(fmt, "text/plain")

    def _resolve_domain_id(self, payload: dict[str, Any]) -> str:
        custom_name = _clean(payload.get("custom_domain_name"))
        requested = _clean(payload.get("domain_id") or DEFAULT_DOMAIN_ID)
        if custom_name or requested in {"__custom__", "custom"}:
            return build_custom_domain_id(custom_name)
        return requested

    def _issue(self, row: int, code: str, message: str) -> dict[str, Any]:
        return {"row": row, "code": code, "message": message}


question_bank_import_service = QuestionBankImportService()

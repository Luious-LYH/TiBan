from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from app.core.config import SAFETY_NOTICE
from app.schemas import QuestionForGrading, QuestionPublic

from .models import QuestionBankModel, QuestionModel
from .seed import TYPE_LABEL


PUBLIC_ADAPTER = TypeAdapter(QuestionPublic)
GRADING_ADAPTER = TypeAdapter(QuestionForGrading)


def public_question_payload(question: QuestionModel) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": question.question_id,
        "bank_id": question.bank_id,
        "domain_id": question.domain_id,
        "title": question.title,
        "stem": question.stem,
        "case_summary": question.case_summary,
        "modality": question.modality,
        "image_url": question.image_url,
        "image_alt": question.image_alt,
        "difficulty": question.difficulty,
        "tags": list(question.teaching_tags or []),
        "body_part": question.body_part,
        "source_dataset": question.source_dataset,
        "citation_note": question.citation_note,
        "doctor_review_required": question.doctor_review_required,
        "safety_notice": question.safety_notice or SAFETY_NOTICE,
        "question_type": question.question_type,
        "subject": question.subject,
        "topic": question.topic,
        "business_usage": question.business_usage,
        "source_item_id": question.source_item_id,
        "derived_from_dataset": question.derived_from_dataset,
        "official_explanation_available": question.official_explanation_available,
    }
    if question.question_type in {"single_choice", "multiple_choice"}:
        payload["options"] = list(question.options or [])
    validated = PUBLIC_ADAPTER.validate_python(payload)
    return validated.model_dump(mode="json")


def grading_question_payload(question: QuestionModel) -> dict[str, Any]:
    payload = public_question_payload(question)
    payload.update(
        {
            "explanation": question.explanation,
            "teaching_tags": list(question.teaching_tags or []),
            "false_premise": question.false_premise,
            **dict(question.grading_payload or {}),
        }
    )
    if question.question_type == "short_answer":
        payload.setdefault("rubric", {"type": "deterministic_keyword_coverage", "max_score": 100})
        payload.setdefault("expected_facts", list(question.expected_keywords or []))
        payload.setdefault("reference_constraints", ["仅作观察性描述", "保留医生复核边界"])
    return GRADING_ADAPTER.validate_python(payload).model_dump(mode="python")


def legacy_question_payload(question: QuestionModel) -> dict[str, Any]:
    """Project the canonical public union for old clients without private data."""

    payload = public_question_payload(question)
    code = str(payload["question_type"])
    label = TYPE_LABEL.get(code, "问答评分")
    payload.update(
        {
            "question": payload.pop("stem"),
            "question_type_code": code,
            "question_type_label": label,
            "question_type": label,
            "image_placeholder": payload.pop("image_alt", None),
            "options": [item["text"] for item in payload.get("options", [])],
        }
    )
    return payload


def legacy_bank_payload(bank: QuestionBankModel, completed_count: int = 0) -> dict[str, Any]:
    progress = min(max(completed_count, 0), bank.question_count) / bank.question_count if bank.question_count else 0
    return {
        "id": bank.bank_id,
        "bank_id": bank.bank_id,
        "domain_id": bank.domain_id,
        "name": bank.name,
        "description": bank.description,
        "version": bank.version,
        "status": bank.status,
        "question_count": bank.question_count,
        "total": bank.question_count,
        "question_type_counts": dict(bank.question_type_counts or {}),
        "modality_counts": dict(bank.modality_counts or {}),
        "body_parts": list(bank.body_parts or []),
        "completed_count": completed_count,
        "completed": completed_count,
        "progress": round(progress, 3),
        "safety_notice": SAFETY_NOTICE,
    }


def public_bank_payload(bank: QuestionBankModel, completed_count: int = 0) -> dict[str, Any]:
    """Project a bank into the strict canonical Stage 1 response contract."""

    progress = min(max(completed_count, 0), bank.question_count) / bank.question_count if bank.question_count else 0
    return {
        "bank_id": bank.bank_id,
        "domain_id": bank.domain_id,
        "name": bank.name,
        "description": bank.description,
        "version": bank.version,
        "status": bank.status,
        "question_count": bank.question_count,
        "question_type_counts": dict(bank.question_type_counts or {}),
        "modality_counts": dict(bank.modality_counts or {}),
        "body_parts": list(bank.body_parts or []),
        "completed_count": completed_count,
        "progress": round(progress, 3),
    }

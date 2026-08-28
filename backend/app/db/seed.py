from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import SAFETY_NOTICE
from app.schemas import Question
from app.services.question_service import QuestionService

from .models import QuestionBankModel, QuestionModel, SourceDocumentModel


TYPE_CODE = {
    "单选": "single_choice",
    "多选": "multiple_choice",
    "判断": "true_false",
    "问答评分": "short_answer",
    "报告修改": "short_answer",
}
TYPE_LABEL = {
    "single_choice": "单选",
    "multiple_choice": "多选",
    "true_false": "判断",
    "short_answer": "问答评分",
}


def bank_for_body_part(body_part: str) -> tuple[str, str, str]:
    normalized = body_part.strip() or "通用"
    mapping = {
        "胃": ("bank-stomach-observation", "胃部观察基础题库", "胃部位、黏膜和安全表达的基础训练。"),
        "食管": ("bank-esophagus-observation", "食管观察与表达题库", "食管解剖标志、炎症表现和报告边界训练。"),
        "结直肠": ("bank-colorectal-observation", "结直肠观察题库", "结直肠黏膜表现与观察性描述训练。"),
        "小肠": ("bank-small-bowel-observation", "小肠图像观察题库", "小肠公开样例的部位与可见事实训练。"),
    }
    bank_id, name, description = mapping.get(
        normalized,
        ("bank-general-endoscopy", "通用内镜观察题库", "跨部位的内镜图像观察和安全表达训练。"),
    )
    return bank_id, name, description


def _split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[；;]", value or "") if item.strip()]


def _difficulty(value: str) -> str:
    return {"入门": "easy", "进阶": "medium", "挑战": "hard"}.get(value, "medium")


def legacy_question_to_record(question: Question) -> dict[str, Any]:
    code = TYPE_CODE.get(question.question_type, "short_answer")
    bank_id, bank_name, bank_description = bank_for_body_part(question.body_part)
    options = [
        {"id": f"opt_{index:02d}", "text": str(text).strip()}
        for index, text in enumerate(question.options, start=1)
        if str(text).strip()
    ]
    answer_parts = _split_items(question.answer)
    option_by_text = {item["text"]: item["id"] for item in options}
    if code == "single_choice":
        grading = {"correct_option_id": option_by_text.get(question.answer, options[0]["id"])}
    elif code == "multiple_choice":
        grading = {
            "correct_option_ids": [
                option_by_text[item]
                for item in answer_parts
                if item in option_by_text
            ]
        }
        if not grading["correct_option_ids"] and options:
            grading["correct_option_ids"] = [options[0]["id"]]
    elif code == "true_false":
        grading = {"correct_value": question.answer.strip().lower() in {"正确", "true", "yes", "是"}}
    else:
        grading = {
            "rubric": {"type": "deterministic_keyword_coverage", "max_score": 100},
            "expected_facts": list(question.expected_keywords) or [fact.expected for fact in question.atomic_trace],
            "reference_constraints": ["仅作观察性描述", "保留医生复核边界"],
        }
    modality = "image" if question.image_url else "text"
    source_dataset = question.source_dataset
    if source_dataset == "EndoBench":
        business_usage = "benchmark_only"
    elif source_dataset in {"Kvasir-VQA", "Kvasir-VQA-x1"}:
        # Legacy VQA fixtures lack the source-item lineage required by the
        # curated importer.  Keep them as generation material instead of
        # letting an older seed fixture bypass the suitability gate.
        business_usage = "generation_source"
    else:
        business_usage = "user_ready"
    return {
        "bank_id": bank_id,
        "bank_name": bank_name,
        "bank_description": bank_description,
        "domain_id": "endoscopy",
        "question_id": question.id,
        "question_type": code,
        "modality": modality,
        "title": question.title,
        "stem": question.question,
        "case_summary": question.case_summary,
        "image_url": question.image_url,
        "image_alt": question.image_placeholder,
        "difficulty": _difficulty(question.difficulty),
        "complexity": question.complexity,
        "question_class": question.question_class,
        "task": question.task,
        "body_part": question.body_part,
        "source_type": question.source_type,
        "source_dataset": question.source_dataset,
        "citation_note": question.citation_note,
        "options": options if code in {"single_choice", "multiple_choice"} else [],
        "grading_payload": grading,
        "explanation": question.explanation,
        "teaching_tags": question.teaching_tags,
        "expected_keywords": question.expected_keywords,
        "false_premise": question.false_premise_flag,
        "doctor_review_required": question.doctor_review_required,
        "safety_notice": question.safety_notice or SAFETY_NOTICE,
        "business_usage": business_usage,
        "derived_from_dataset": question.source_dataset if question.source_dataset in {"EndoBench", "Kvasir-VQA", "Kvasir-VQA-x1"} else None,
        "license_gate_status": "allow_noncommercial" if question.source_dataset in {"EndoBench", "Kvasir-VQA", "Kvasir-VQA-x1"} else "needs_review",
        "answer_source": "dataset_gold",
        "explanation_source": "none",
        "official_explanation_available": False,
        "source_uri": (
            "https://github.com/medAI-NEU/EndoBench" if question.source_dataset == "EndoBench"
            else "https://github.com/ENDObenchmark/Kvasir-VQA" if question.source_dataset == "Kvasir-VQA"
            else "https://github.com/ENDObenchmark/Kvasir-VQA-x1" if question.source_dataset == "Kvasir-VQA-x1"
            else None
        ),
    }


def build_seed_records() -> list[dict[str, Any]]:
    questions = QuestionService().list_questions()
    return [legacy_question_to_record(question) for question in questions]


def seed_database(session: Session) -> int:
    existing = session.scalar(select(QuestionModel.question_id).limit(1))
    if existing:
        return 0

    records = build_seed_records()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["bank_id"]].append(record)

    for bank_id, items in grouped.items():
        # Only product-ready rows become learner-facing bank inventory.  Keep
        # generation_source rows in the database for lineage/import audits,
        # but never let a fresh database seed expose them as playable counts.
        visible_items = [item for item in items if item.get("business_usage") == "user_ready"]
        type_counts = Counter(item["question_type"] for item in visible_items)
        modality_counts = Counter(item["modality"] for item in visible_items)
        body_parts = sorted({item["body_part"] for item in visible_items})
        first = visible_items[0] if visible_items else items[0]
        session.add(
            QuestionBankModel(
                bank_id=bank_id,
                domain_id="endoscopy",
                name=first["bank_name"],
                description=first["bank_description"],
                version="seed-v1",
                status="published",
                question_count=len(visible_items),
                question_type_counts=dict(type_counts),
                modality_counts=dict(modality_counts),
                body_parts=body_parts,
            )
        )

    for record in records:
        record.pop("bank_name", None)
        record.pop("bank_description", None)
        session.add(
            QuestionModel(
                question_id=record.pop("question_id"),
                **record,
            )
        )

    session.add(
        SourceDocumentModel(
            document_id="source-seed-endoscopy-v1",
            domain_id="endoscopy",
            bank_id=None,
            name="EndoTutor seed teaching catalog",
            media_type="application/json",
            content_hash="seed-catalog-v1",
            status="seed",
        )
    )
    session.commit()
    return len(records)

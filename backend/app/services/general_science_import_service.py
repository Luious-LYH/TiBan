"""Governed local importer for the ARC Easy General Science domain pack.

The upstream data is never committed.  The importer accepts the local parquet
download produced by ``download_arc_easy.py`` and persists only the selected
rows in the configured runtime database, with source/license lineage intact.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
from sqlalchemy import select

from app.core.config import ARC_EASY_ROOT
from app.domains import get_domain
from app.db.database import SessionLocal
from app.db.models import QuestionBankModel, QuestionModel, SourceDocumentModel
from app.services.data_governance import dataset_policy


ARC_EASY_TRAIN_FILE = "arc_easy_train.parquet"
ARC_EASY_BANK_ID = "bank-arc-easy-local"
ARC_EASY_SOURCE_ID = "arc-easy"
ARC_EASY_SOURCE_URL = "https://allenai.org/data/arc"


def arc_easy_path(path: Path | None = None) -> Path:
    return (path or ARC_EASY_ROOT / ARC_EASY_TRAIN_FILE).resolve()


def _rows(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    table = pq.read_table(path)
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(table.to_pylist()):
        question = raw.get("question") or {}
        choices = question.get("choices") or {}
        labels = list(choices.get("label") or [])
        texts = list(choices.get("text") or [])
        answer = str(raw.get("answerKey") or "")
        if not isinstance(question, dict) or len(labels) < 2 or len(labels) != len(texts) or answer not in labels:
            continue
        rows.append({
            "question_id": f"arc_easy_{str(raw.get('id') or index).replace('-', '_')}",
            "title": "ARC Easy · 通用科学推理",
            "stem": str(question.get("stem") or "").strip(),
            "options": [{"id": str(label), "text": str(text)} for label, text in zip(labels, texts)],
            "correct_option_id": answer,
            "source_item_id": str(raw.get("id") or index),
        })
        if len(rows) >= limit:
            break
    if not rows:
        raise ValueError("ARC Easy file contains no valid multiple-choice rows")
    return rows


def import_arc_easy(*, limit: int = 400, path: Path | None = None) -> dict[str, int | str]:
    """Idempotently import a limited local ARC Easy pack into the shared core."""

    manifest = get_domain("general_science")
    policy = dataset_policy(ARC_EASY_SOURCE_ID)
    source_path = arc_easy_path(path)
    rows = _rows(source_path, limit)
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with SessionLocal() as session:
        bank = session.get(QuestionBankModel, ARC_EASY_BANK_ID)
        if bank is None:
            bank = QuestionBankModel(
                bank_id=ARC_EASY_BANK_ID,
                domain_id=manifest.domain_id,
                name="ARC Easy 通用科学题库（本地导入）",
                description="来自 AI2 ARC Easy 的受治理本地导入；用于验证通用科学 Domain Pack，不随仓库分发。",
                version="arc-easy-local-v1",
                status="published",
                question_count=0,
                question_type_counts={}, modality_counts={}, body_parts=["科学基础"],
            )
            session.add(bank)
        document_id = "source-qbank-arc-easy-v1"
        if session.get(SourceDocumentModel, document_id) is None:
            session.add(SourceDocumentModel(
                document_id=document_id, domain_id=manifest.domain_id, bank_id=ARC_EASY_BANK_ID,
                name="AI2 ARC Easy local QBank", media_type="application/x-parquet", content_hash=source_hash,
                status="local_import", source_id=ARC_EASY_SOURCE_ID, business_usage="user_ready",
                license_gate_status="allow", ai_ingestion_allowed=False, source_uri=ARC_EASY_SOURCE_URL,
                namespace="general_science", attribution=policy.attribution,
            ))
        added = 0
        for row in rows:
            if session.get(QuestionModel, row["question_id"]) is not None:
                continue
            session.add(QuestionModel(
                question_id=row["question_id"], bank_id=ARC_EASY_BANK_ID, domain_id=manifest.domain_id,
                question_type="single_choice", modality="text", title=row["title"], stem=row["stem"],
                case_summary="ARC Easy 本地导入题目；用于通用科学学习和平台跨域验证。", image_url=None, image_alt=None,
                difficulty="medium", complexity=1, question_class="科学推理", task="多项选择", body_part="科学基础",
                source_type="third_party_local_import", source_dataset="AI2 ARC Easy", citation_note="AI2 ARC Easy，CC BY-SA 4.0；本地受治理导入。",
                options=row["options"], grading_payload={"question_type": "single_choice", "correct_option_id": row["correct_option_id"]},
                explanation="请依据题干条件与科学概念完成判断；答案来自上游评测标注。", teaching_tags=["通用科学"], expected_keywords=[], false_premise=False,
                doctor_review_required=False, safety_notice=manifest.learner_notice, source_document_id=document_id,
                source_item_id=row["source_item_id"], business_usage="user_ready", answer_source="dataset_gold", explanation_source="none",
                license_gate_status="allow", source_uri=ARC_EASY_SOURCE_URL, official_explanation_available=False, subject="通用科学", topic="ARC Easy",
            ))
            added += 1
        session.flush()
        counts = Counter(session.scalars(select(QuestionModel.question_type).where(QuestionModel.bank_id == ARC_EASY_BANK_ID, QuestionModel.business_usage == "user_ready")))
        bank.question_count = sum(counts.values())
        bank.question_type_counts = dict(counts)
        bank.modality_counts = {"text": bank.question_count}
        session.commit()
    return {"bank_id": ARC_EASY_BANK_ID, "imported": added, "question_count": len(rows), "source_hash": source_hash}

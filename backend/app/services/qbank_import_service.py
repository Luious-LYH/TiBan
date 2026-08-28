"""Governed importers for the first real Stage 2.5 question banks."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from app.core.config import LOCAL_VQA_ROOT, SAFETY_NOTICE
from app.db.database import SessionLocal
from app.db.models import QuestionBankModel, QuestionModel, SourceDocumentModel
from app.services.data_governance import dataset_policy


PROJECT_DIR = Path(__file__).resolve().parents[3]
CMEXAM_ROOT = PROJECT_DIR / "data" / "external" / "CMExam"
CMB_ROOT = PROJECT_DIR / "data" / "external" / "CMB" / "CMB-Exam"


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"cannot decode {path}")


def _option_map(value: str | dict[str, Any]) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key).strip().upper(): str(text).strip() for key, text in value.items() if str(text).strip()}
    result: dict[str, str] = {}
    for line in str(value).splitlines():
        match = re.match(r"^\s*([A-Z])(?:[.)]|\s+)\s*(.+?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _answer_letters(value: Any) -> list[str]:
    text = "".join(str(item) for item in value) if isinstance(value, list) else str(value or "")
    return sorted(set(re.findall(r"[A-E]", text.upper())))


def _difficulty(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"1", "easy", "简单", "低"}:
        return "easy"
    if raw in {"3", "hard", "困难", "高"}:
        return "hard"
    return "medium"


def _source_document(session: Any, *, document_id: str, source_id: str, name: str, uri: str, usage: str, namespace: str) -> SourceDocumentModel:
    document = session.get(SourceDocumentModel, document_id)
    if document is None:
        document = SourceDocumentModel(
            document_id=document_id, domain_id="medical-education", bank_id=None, name=name,
            media_type="text/json", content_hash=f"registry:{source_id}", status="registered",
            source_id=source_id, business_usage=usage, license_gate_status="allow_noncommercial",
            ai_ingestion_allowed=False, source_uri=uri, namespace=namespace,
            attribution=dataset_policy(source_id).attribution,
        )
        session.add(document)
    return document


def _bank(session: Any, *, bank_id: str, name: str, description: str, items: list[dict[str, Any]]) -> None:
    bank = session.get(QuestionBankModel, bank_id)
    if bank is None:
        bank = QuestionBankModel(bank_id=bank_id, domain_id="medical-education", name=name, description=description, version="stage2.5-curated-v1", status="published", question_count=0, question_type_counts={}, modality_counts={}, body_parts=[])
        session.add(bank)
    for item in items:
        if session.get(QuestionModel, item["question_id"]) is None:
            session.add(QuestionModel(**item))
    session.flush()
    questions = session.query(QuestionModel).filter(QuestionModel.bank_id == bank_id).all()
    bank.question_count = len(questions)
    bank.question_type_counts = dict(Counter(q.question_type for q in questions))
    bank.modality_counts = dict(Counter(q.modality for q in questions))
    bank.body_parts = sorted({q.body_part for q in questions})


def _base(*, question_id: str, stem: str, title: str, source_dataset: str, source_item_id: str, source_document_id: str, source_uri: str, explanation: str, explanation_available: bool, options: list[dict[str, str]], grading_payload: dict[str, Any], difficulty: str = "medium", subject: str | None = None, topic: str | None = None, image_url: str | None = None, image_alt: str | None = None, business_usage: str = "user_ready") -> dict[str, Any]:
    question_type = str(grading_payload["question_type"])
    return {
        "question_id": question_id, "bank_id": "", "domain_id": "medical-education", "question_type": question_type,
        "modality": "image" if image_url else "text", "title": title[:300], "stem": stem.strip(),
        "case_summary": f"来自 {source_dataset} 的真实题目；用于教学研修，保留上游来源与授权边界。",
        "image_url": image_url, "image_alt": image_alt or "题目未提供图像", "difficulty": difficulty,
        "complexity": 2 if difficulty == "medium" else (1 if difficulty == "easy" else 3),
        "question_class": "综合医学" if not image_url else "内镜图像观察", "task": "医学题库练习" if not image_url else "内镜图像观察",
        "body_part": "消化系统" if source_dataset in {"CMExam", "CMB-Exam"} else "消化道",
        "source_type": f"{source_dataset} 真实题库", "source_dataset": source_dataset,
        "citation_note": f"{source_dataset} · source item {source_item_id} · 仅供教学研修。",
        "options": options, "grading_payload": grading_payload,
        "explanation": explanation.strip() or "官方解析暂无；请结合题干和课程资料复核。",
        "teaching_tags": [tag for tag in [subject, topic] if tag], "expected_keywords": [], "false_premise": False,
        "doctor_review_required": True, "safety_notice": SAFETY_NOTICE, "source_document_id": source_document_id,
        "source_item_id": source_item_id, "derived_from_dataset": source_dataset, "business_usage": business_usage,
        "answer_source": "dataset_gold", "explanation_source": "dataset_gold" if explanation_available else "none",
        "license_gate_status": "allow_noncommercial", "source_uri": source_uri,
        "official_explanation_available": explanation_available, "subject": subject, "topic": topic,
    }


def import_cmexam(limit: int = 1500, split: str = "test_with_annotations.csv") -> int:
    path = CMEXAM_ROOT / "data" / split
    if not path.exists():
        raise FileNotFoundError(path)
    policy = dataset_policy("cmexam")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            if len(rows) >= limit:
                break
            options, answers = _option_map(row.get("Options", "")), _answer_letters(row.get("Answer", ""))
            if len(options) < 2 or not answers or not set(answers).issubset(options):
                continue
            question_type = "multiple_choice" if len(answers) > 1 else "single_choice"
            grading = {"question_type": question_type}
            grading["correct_option_ids" if question_type == "multiple_choice" else "correct_option_id"] = [f"opt_{item}" for item in answers] if question_type == "multiple_choice" else f"opt_{answers[0]}"
            explanation = str(row.get("Explanation") or "").strip()
            item = _base(question_id=f"cmexam_{index:06d}", stem=str(row.get("Question") or ""), title=f"CMExam · {row.get('Clinical Department') or row.get('Medical Discipline') or '综合医学'}", source_dataset="CMExam", source_item_id=f"{split}:{index}", source_document_id="source-qbank-cmexam-v1", source_uri=policy.source_url, explanation=explanation, explanation_available=bool(explanation), options=[{"id": f"opt_{key}", "text": value} for key, value in options.items()], grading_payload=grading, difficulty=_difficulty(row.get("Difficulty level")), subject=str(row.get("Clinical Department") or "综合医学"), topic=str(row.get("Disease Group") or ""))
            item["bank_id"] = "bank-cmexam-real"
            rows.append(item)
    with SessionLocal() as session:
        _source_document(session, document_id="source-qbank-cmexam-v1", source_id="cmexam", name="CMExam real QBank", uri=policy.source_url, usage="user_ready", namespace="qbank_explanations")
        _bank(session, bank_id="bank-cmexam-real", name="CMExam 中文医学综合题库", description="由真实 CMExam 题目组成；含上游答案与可用时的官方解析。", items=rows)
        session.commit()
    return len(rows)


def import_cmexam_scale(*, limit: int | None = None, batch_size: int = 1000) -> dict[str, Any]:
    """Bulk-import the complete local CMExam corpus into an isolated scale DB.

    It intentionally has a separate bank/document/question-id namespace from
    the 1,500-question demo bank.  The function performs no deletion or
    replacement and is therefore suitable for a one-way acceptance database.
    """

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    policy = dataset_policy("cmexam")
    splits = ("train.csv", "val.csv", "test_with_annotations.csv")
    bank_id = "bank-cmexam-scale-v1"
    source_document_id = "source-qbank-cmexam-scale-v1"
    inserted = 0
    by_split: Counter[str] = Counter()
    question_type_counts: Counter[str] = Counter()
    batch: list[dict[str, Any]] = []

    def flush(session: Any) -> None:
        nonlocal inserted
        if not batch:
            return
        session.bulk_insert_mappings(QuestionModel, list(batch))
        for item in batch:
            question_type_counts[str(item["question_type"])] += 1
        inserted += len(batch)
        batch.clear()

    with SessionLocal() as session:
        if session.get(QuestionBankModel, bank_id) is not None:
            raise ValueError("scale bank already exists; use a fresh isolated acceptance database")
        _source_document(
            session,
            document_id=source_document_id,
            source_id="cmexam",
            name="CMExam full scale acceptance corpus",
            uri=policy.source_url,
            usage="user_ready",
            namespace="qbank_explanations",
        )
        bank = QuestionBankModel(
            bank_id=bank_id,
            domain_id="medical-education",
            name="CMExam scale-acceptance corpus",
            description="Isolated non-demo corpus used only for Stage 3 performance acceptance.",
            version="stage3-scale-v1",
            status="acceptance_only",
            question_count=0,
            question_type_counts={},
            modality_counts={},
            body_parts=["消化系统"],
        )
        session.add(bank)
        session.flush()
        for split in splits:
            path = CMEXAM_ROOT / "data" / split
            if not path.is_file():
                raise FileNotFoundError(path)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for index, row in enumerate(csv.DictReader(handle)):
                    if limit is not None and inserted + len(batch) >= limit:
                        break
                    options, answers = _option_map(row.get("Options", "")), _answer_letters(row.get("Answer", ""))
                    if len(options) < 2 or not answers or not set(answers).issubset(options):
                        continue
                    question_type = "multiple_choice" if len(answers) > 1 else "single_choice"
                    grading: dict[str, Any] = {"question_type": question_type}
                    grading["correct_option_ids" if question_type == "multiple_choice" else "correct_option_id"] = (
                        [f"opt_{item}" for item in answers]
                        if question_type == "multiple_choice"
                        else f"opt_{answers[0]}"
                    )
                    explanation = str(row.get("Explanation") or "").strip()
                    item = _base(
                        question_id=f"cmexam_scale_{split.removesuffix('.csv')}_{index:06d}",
                        stem=str(row.get("Question") or ""),
                        title=f"CMExam · {row.get('Clinical Department') or row.get('Medical Discipline') or '综合医学'}",
                        source_dataset="CMExam",
                        source_item_id=f"{split}:{index}",
                        source_document_id=source_document_id,
                        source_uri=policy.source_url,
                        explanation=explanation,
                        explanation_available=bool(explanation),
                        options=[{"id": f"opt_{key}", "text": value} for key, value in options.items()],
                        grading_payload=grading,
                        difficulty=_difficulty(row.get("Difficulty level")),
                        subject=str(row.get("Clinical Department") or "综合医学"),
                        topic=str(row.get("Disease Group") or ""),
                    )
                    item["bank_id"] = bank_id
                    batch.append(item)
                    by_split[split] += 1
                    if len(batch) >= batch_size:
                        flush(session)
            if limit is not None and inserted + len(batch) >= limit:
                break
        flush(session)
        bank.question_count = inserted
        bank.question_type_counts = dict(question_type_counts)
        bank.modality_counts = {"text": inserted}
        session.commit()
    return {"bank_id": bank_id, "imported": inserted, "by_split": dict(by_split), "batch_size": batch_size}


def _cmb_files() -> Iterable[tuple[str, Path]]:
    yield "val", CMB_ROOT / "CMB-val" / "CMB-val-merge.json"
    yield "train", CMB_ROOT / "CMB-train" / "CMB-train-merge.json"
    yield "test", CMB_ROOT / "CMB-test" / "CMB-test-choice-question-merge.json"


def import_cmb(limit: int = 1500, val_limit: int = 280) -> int:
    policy = dataset_policy("cmb-exam")
    rows: list[dict[str, Any]] = []
    for split, path in _cmb_files():
        if not path.exists():
            continue
        for index, raw in enumerate(json.loads(_read_text(path))[: (val_limit if split == "val" else limit)]):
            options, answers = _option_map(raw.get("option", {})), _answer_letters(raw.get("answer"))
            if len(options) < 2 or not answers or not set(answers).issubset(options):
                continue
            question_type = "multiple_choice" if len(answers) > 1 or "多" in str(raw.get("question_type")) else "single_choice"
            grading = {"question_type": question_type}
            grading["correct_option_ids" if question_type == "multiple_choice" else "correct_option_id"] = [f"opt_{item}" for item in answers] if question_type == "multiple_choice" else f"opt_{answers[0]}"
            explanation = str(raw.get("explanation") or "").strip()
            item = _base(question_id=f"cmb_{split}_{index:06d}", stem=str(raw.get("question") or ""), title=f"CMB-Exam · {raw.get('exam_subject') or raw.get('exam_class') or '综合医学'}", source_dataset="CMB-Exam", source_item_id=f"{split}:{index}", source_document_id="source-qbank-cmb-v1", source_uri=policy.source_url, explanation=explanation, explanation_available=bool(explanation), options=[{"id": f"opt_{key}", "text": value} for key, value in options.items()], grading_payload=grading, subject=str(raw.get("exam_subject") or raw.get("exam_class") or "综合医学"), topic=str(raw.get("exam_type") or ""))
            item["bank_id"] = "bank-cmb-exam-real"
            rows.append(item)
    with SessionLocal() as session:
        _source_document(session, document_id="source-qbank-cmb-v1", source_id="cmb-exam", name="CMB-Exam real QBank", uri=policy.source_url, usage="user_ready", namespace="qbank_explanations")
        _bank(session, bank_id="bank-cmb-exam-real", name="CMB-Exam 中文医学题库", description="CMB-Exam 的受限真实子集；无上游解析的题目明确标记为暂无官方解析。", items=rows)
        session.commit()
    return len(rows)


def classify_kvasir_item(raw: dict[str, Any], image_exists: bool) -> str:
    question, answer = str(raw.get("question") or "").strip().lower(), str(raw.get("answer") or raw.get("gt") or "").strip().lower()
    if not question or not answer or not image_exists:
        return "excluded"
    if any(term in question for term in ("ignore previous", "system prompt", "benchmark target")):
        return "excluded"
    if answer in {"yes", "no"}:
        return "user_ready"
    if any(term in question for term in ("what color", "how many", "where", "what type of procedure", "what type of polyp")):
        return "needs_explanation"
    return "generation_source"


def kvasir_classification(limit: int | None = None) -> tuple[list[dict[str, Any]], Counter[str]]:
    path = LOCAL_VQA_ROOT / "Kvasir-VQA" / "Kvasir-VQA.json"
    data = json.loads(_read_text(path))
    records: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for raw in data[:limit] if limit else data:
        relative = str(raw.get("image_path") or "")
        image_exists = (path.parent / relative).is_file()
        usage = classify_kvasir_item(raw, image_exists)
        counts[usage] += 1
        records.append({"source_item_id": str(raw.get("id")), "image_id": str(raw.get("img_id") or ""), "image_path": relative.replace("\\", "/"), "question": str(raw.get("question") or ""), "answer": str(raw.get("answer") or raw.get("gt") or ""), "source": str(raw.get("source") or ""), "business_usage": usage, "image_exists": image_exists})
    return records, counts


def import_kvasir(limit: int = 400) -> int:
    policy = dataset_policy("kvasir-vqa")
    records, _ = kvasir_classification()
    selected = [record for record in records if record["business_usage"] == "user_ready"][:limit]
    rows: list[dict[str, Any]] = []
    for record in selected:
        answer = record["answer"].strip().lower()
        item = _base(question_id=f"kvasir_vqa_{record['source_item_id']}", stem=record["question"], title=f"Kvasir-VQA · {record['source'] or '内镜图像观察'}", source_dataset="Kvasir-VQA", source_item_id=record["source_item_id"], source_document_id="source-qbank-kvasir-vqa-v1", source_uri=policy.source_url, explanation="原始标注为 Yes/No；本题用于训练图像观察与事实表达。该数据未提供官方解析。", explanation_available=False, options=[], grading_payload={"question_type": "true_false", "correct_value": answer == "yes"}, difficulty="medium", subject="内镜图像观察", topic=record["source"], image_url=f"/api/v3/assets/local-vqa/kvasir-vqa/{record['image_path']}", image_alt=f"Kvasir-VQA 图像 {record['image_id']}")
        item["bank_id"] = "bank-kvasir-vqa-curated"
        rows.append(item)
    with SessionLocal() as session:
        _source_document(session, document_id="source-qbank-kvasir-vqa-v1", source_id="kvasir-vqa", name="Kvasir-VQA curated QBank", uri=policy.source_url, usage="generation_source", namespace="factory_sources")
        _bank(session, bank_id="bank-kvasir-vqa-curated", name="Kvasir-VQA 内镜图像观察题库", description="从 Kvasir-VQA 中筛选出的 Yes/No 图像观察题；原始数据其余部分保留为生成源。", items=rows)
        session.commit()
    return len(rows)

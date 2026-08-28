"""Auditable Question Factory built on the canonical RAG document/chunk graph.

The no-secret adapter is intentionally deterministic and labelled as such.  It
exists to exercise parsing, gates, revision lineage and publishing locally; a
provider-backed generator/judge can be added without changing the workflow.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import fitz
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import SAFETY_NOTICE, UPLOAD_DIR
from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel, FactoryJobModel, KnowledgeChunkModel, QuestionBankModel,
    QuestionModel, QuestionRevisionModel, SourceDocumentModel,
)
from app.services.rag_service import rag_service


ALLOWED_SUFFIXES = {".md": "text/markdown", ".pdf": "application/pdf"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
GENERATOR_PROMPT_VERSION = "factory-generator-v1"
JUDGE_PROMPT_VERSION = "factory-judge-v1"


class GeneratorInput(BaseModel):
    evidence: str = Field(min_length=20)
    source_chunk_id: str
    source_document_id: str
    objective: str = "根据可见证据完成教学观察练习"


class GeneratedDraft(BaseModel):
    question_type: Literal["single_choice"] = "single_choice"
    title: str
    stem: str
    options: list[dict[str, str]] = Field(min_length=2, max_length=4)
    correct_option_id: str
    explanation: str
    teaching_tags: list[str]
    citation: dict[str, Any]
    provider_mode: Literal["local_deterministic_adapter"] = "local_deterministic_adapter"


class JudgeDecision(BaseModel):
    passed: bool
    groundedness: Literal["pass", "fail"]
    answer_consistency: Literal["pass", "fail"]
    citation_validity: Literal["pass", "fail"]
    distractor_quality: Literal["pass", "fail"]
    teaching_value: Literal["pass", "fail"]
    rewrite_instruction: str | None = None
    judge_mode: Literal["local_deterministic_adapter"] = "local_deterministic_adapter"
    prompt_version: str = JUDGE_PROMPT_VERSION


def _sha(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _record_event(job: FactoryJobModel, status: str, detail: str) -> None:
    events = list(job.detail.get("events", []))
    events.append({"status": status, "detail": detail, "at": datetime.utcnow().isoformat()})
    job.status = status
    job.detail = {**job.detail, "events": events}


def import_allowed_document(filename: str, content: bytes, content_type: str | None = None) -> dict[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("only .md and .pdf teaching documents are allowed")
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("document must be between 1 byte and 5 MiB")
    if content_type and content_type not in {ALLOWED_SUFFIXES[suffix], "application/octet-stream", "text/plain"}:
        raise ValueError("document MIME type does not match its allowed extension")
    document_id = f"doc_{uuid4().hex[:12]}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPLOAD_DIR / f"{document_id}_{safe_name}"
    destination.write_bytes(content)
    with SessionLocal() as session:
        session.add(SourceDocumentModel(
            document_id=document_id, domain_id="endoscopy", bank_id=None, name=Path(filename).name,
            media_type=ALLOWED_SUFFIXES[suffix], content_hash=_sha(content), status="uploaded",
        ))
        # The models intentionally have no ORM relationship; flush establishes
        # the canonical source row before its version FK is inserted.
        session.flush()
        session.add(DocumentVersionModel(
            version_id=f"version_{uuid4().hex[:12]}", document_id=document_id, version_label="factory-upload-v1",
            source_path=str(destination.resolve()), content_hash=_sha(content), parser="pending", status="uploaded",
        ))
        session.commit()
    return {"document_id": document_id, "name": Path(filename).name, "media_type": ALLOWED_SUFFIXES[suffix]}


def enqueue_factory_job(document_id: str) -> dict[str, str]:
    with SessionLocal() as session:
        if session.get(SourceDocumentModel, document_id) is None:
            raise KeyError("document not found")
        job = FactoryJobModel(job_id=f"factory_{uuid4().hex[:12]}", document_id=document_id, status="queued", detail={"events": []})
        _record_event(job, "queued", "已接收允许使用的教学文档，等待 Dramatiq worker。")
        session.add(job)
        session.commit()
        job_id = job.job_id
    return {"job_id": job_id, "status": "queued"}


def record_queue_message(job_id: str, message_id: str) -> None:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("factory job not found")
        job.queue_message_id = message_id
        session.commit()


def _markdown_from_document(version: DocumentVersionModel) -> Path:
    source = Path(version.source_path)
    if source.suffix.lower() == ".md":
        return source
    pdf = fitz.open(source)
    try:
        text = "\n\n".join(f"## 第 {index + 1} 页\n{page.get_text('text')}" for index, page in enumerate(pdf))
    finally:
        pdf.close()
    markdown = source.with_suffix(".parsed.md")
    markdown.write_text(text, encoding="utf-8")
    return markdown


def _generator(payload: GeneratorInput, *, repaired: bool = False) -> GeneratedDraft:
    sentence = re.split(r"[。；\n]", payload.evidence)[0].strip() or payload.evidence[:80]
    explanation = f"依据资料中的可见证据：{sentence}。"
    if repaired:
        explanation += f"{SAFETY_NOTICE}"
    return GeneratedDraft(
        title="资料证据导向练习", stem=f"根据资料，哪项表述最符合「{sentence[:42]}」这一观察要点？",
        options=[
            {"id": "a", "text": sentence},
            {"id": "b", "text": "仅凭单帧图像即可给出独立临床诊断"},
            {"id": "c", "text": "无需记录部位和可见形态"},
            {"id": "d", "text": "可忽略资料中的不确定性边界"},
        ], correct_option_id="a", explanation=explanation,
        teaching_tags=["资料溯源", "观察证据"], citation={"chunk_id": payload.source_chunk_id, "document_id": payload.source_document_id},
    )


def _deterministic_gate(draft: GeneratedDraft, evidence: str) -> tuple[bool, str | None]:
    option_ids = {option["id"] for option in draft.options}
    if draft.correct_option_id not in option_ids:
        return False, "correct option must be one of the public options"
    if not draft.citation.get("chunk_id") or not evidence:
        return False, "draft must retain a canonical source chunk citation"
    return True, None


def _judge(draft: GeneratedDraft, evidence: str) -> JudgeDecision:
    grounded = draft.options[0]["text"] in evidence
    answer = any(option["id"] == draft.correct_option_id for option in draft.options)
    citation = bool(draft.citation.get("chunk_id"))
    safety = "医生复核" in draft.explanation and "独立诊断" in draft.explanation
    distractor = len({option["text"] for option in draft.options}) == len(draft.options) and all("以上都" not in option["text"] for option in draft.options)
    return JudgeDecision(
        passed=all([grounded, answer, citation, safety, distractor]),
        groundedness="pass" if grounded else "fail", answer_consistency="pass" if answer else "fail",
        citation_validity="pass" if citation else "fail", distractor_quality="pass" if distractor else "fail",
        teaching_value="pass" if safety else "fail",
        rewrite_instruction=None if safety else "在 explanation 中加入明确的医生复核与非独立诊断教学边界。",
    )


def process_factory_job(job_id: str) -> dict[str, Any]:
    """Worker entry point. Every state change is persisted, never simulated by UI."""
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("factory job not found")
        document = session.get(SourceDocumentModel, job.document_id)
        version = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.document_id == job.document_id).order_by(DocumentVersionModel.created_at.desc()))
        if document is None or version is None:
            _record_event(job, "failed", "源文档或版本不存在。")
            session.commit()
            return {"job_id": job_id, "status": "failed"}
        _record_event(job, "parsing", "正在解析允许使用的 Markdown/PDF 教学文档。")
        session.commit()
        markdown = _markdown_from_document(version)
        version.parser = "heading-aware-markdown" if markdown.suffix == ".md" else "pymupdf"
        version.source_path = str(markdown.resolve())
        session.commit()

    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id); assert job is not None
        _record_event(job, "indexing", "正在写入 PostgreSQL source/chunk metadata 与 Qdrant index。")
        session.commit()
    rag_service.index_markdown(markdown, document_id=document.document_id, child_size=180)

    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id); assert job is not None
        chunk = session.scalar(select(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == job.document_id).order_by(KnowledgeChunkModel.ordinal))
        if chunk is None:
            _record_event(job, "failed", "文档没有可用知识块。")
            session.commit(); return {"job_id": job_id, "status": "failed"}
        _record_event(job, "generating", "Generator 使用独立 schema 生成可追溯草稿。")
        initial = _generator(GeneratorInput(evidence=chunk.content, source_chunk_id=chunk.chunk_id, source_document_id=chunk.document_id))
        valid, gate_error = _deterministic_gate(initial, chunk.content)
        initial_revision = QuestionRevisionModel(
            revision_id=f"revision_{uuid4().hex[:12]}", parent_revision_id=None, job_id=job_id,
            status="generated" if valid else "rejected", draft_payload=initial.model_dump(),
            judge_decision={}, rewrite_instruction=gate_error, prompt_version=GENERATOR_PROMPT_VERSION,
            source_chunk_ids=[chunk.chunk_id],
        )
        session.add(initial_revision); session.flush()
        _record_event(job, "judging", "Judge 使用独立 schema 只读取草稿、资料证据与 rubric。")
        decision = _judge(initial, chunk.content) if valid else JudgeDecision(passed=False, groundedness="fail", answer_consistency="fail", citation_validity="fail", distractor_quality="fail", teaching_value="fail", rewrite_instruction=gate_error)
        initial_revision.judge_decision = decision.model_dump()
        if decision.passed:
            initial_revision.status = "ready_for_review"
            _record_event(job, "ready_for_review", "草稿通过 deterministic gate 与 Judge，等待人工发布。")
            session.commit(); return {"job_id": job_id, "status": job.status, "revision_id": initial_revision.revision_id}
        _record_event(job, "repairing", "保留初稿并创建新的 repair revision。")
        repaired = _generator(GeneratorInput(evidence=chunk.content, source_chunk_id=chunk.chunk_id, source_document_id=chunk.document_id), repaired=True)
        repaired_decision = _judge(repaired, chunk.content)
        repaired_revision = QuestionRevisionModel(
            revision_id=f"revision_{uuid4().hex[:12]}", parent_revision_id=initial_revision.revision_id, job_id=job_id,
            status="ready_for_review" if repaired_decision.passed else "rejected", draft_payload=repaired.model_dump(),
            judge_decision=repaired_decision.model_dump(), rewrite_instruction=decision.rewrite_instruction,
            prompt_version=GENERATOR_PROMPT_VERSION, source_chunk_ids=[chunk.chunk_id],
        )
        session.add(repaired_revision)
        _record_event(job, "ready_for_review" if repaired_decision.passed else "failed", "修订版本已保留完整 lineage，等待人工发布。")
        session.commit()
        return {"job_id": job_id, "status": job.status, "revision_id": repaired_revision.revision_id}


def publish_revision(job_id: str, revision_id: str) -> dict[str, str]:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        revision = session.get(QuestionRevisionModel, revision_id)
        if job is None or revision is None or revision.job_id != job_id:
            raise KeyError("job or revision not found")
        if revision.status != "ready_for_review" or not revision.judge_decision.get("passed"):
            raise ValueError("only a passed review revision may be published")
        payload = revision.draft_payload
        bank_id = "factory-generated-v1"
        bank = session.get(QuestionBankModel, bank_id)
        if bank is None:
            bank = QuestionBankModel(bank_id=bank_id, domain_id="endoscopy", name="Factory 生成题草稿库", description="基于允许使用资料、需人工审核后发布的题目。", version="factory-v1", status="published", question_count=0, question_type_counts={}, modality_counts={}, body_parts=["资料证据"])
            session.add(bank)
        question_id = f"factory_question_{revision_id[-12:]}"
        if session.get(QuestionModel, question_id) is None:
            session.add(QuestionModel(
                question_id=question_id, bank_id=bank_id, domain_id="endoscopy", question_type="single_choice", modality="text",
                title=payload["title"], stem=payload["stem"], case_summary="由允许使用的教学资料生成，已保留 citation lineage。",
                image_url=None, image_alt=None, difficulty="medium", complexity=1, question_class="资料溯源", task="证据阅读",
                body_part="资料证据", source_type="factory", source_dataset="Factory / allowed document",
                citation_note=f"chunk={payload['citation']['chunk_id']}", options=payload["options"],
                grading_payload={"question_type": "single_choice", "correct_option_id": payload["correct_option_id"]},
                explanation=payload["explanation"], teaching_tags=payload["teaching_tags"], expected_keywords=[], false_premise=False,
                doctor_review_required=True, safety_notice=SAFETY_NOTICE, source_document_id=job.document_id,
            ))
            bank.question_count += 1
            bank.question_type_counts = {**bank.question_type_counts, "single_choice": int(bank.question_type_counts.get("single_choice", 0)) + 1}
            bank.modality_counts = {**bank.modality_counts, "text": int(bank.modality_counts.get("text", 0)) + 1}
        revision.status = "published"
        _record_event(job, "published", "人工发布动作已将 revision 写入 canonical question bank。")
        session.commit()
        return {"job_id": job_id, "revision_id": revision_id, "question_id": question_id, "status": "published"}


def get_job(job_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("job not found")
        revisions = list(session.scalars(select(QuestionRevisionModel).where(QuestionRevisionModel.job_id == job_id).order_by(QuestionRevisionModel.created_at)))
        return {"job_id": job.job_id, "document_id": job.document_id, "status": job.status, "detail": job.detail, "queue_message_id": job.queue_message_id, "revisions": [{"revision_id": r.revision_id, "parent_revision_id": r.parent_revision_id, "status": r.status, "draft": r.draft_payload, "judge": r.judge_decision, "rewrite_instruction": r.rewrite_instruction, "source_chunk_ids": r.source_chunk_ids} for r in revisions]}

"""Auditable Question Factory built on the canonical RAG document/chunk graph.

The deterministic adapter keeps CI and no-secret workflow tests reproducible.
When explicitly enabled, the same workflow calls one configured provider for a
Generator schema and a separate Judge schema.  Provider failures remain failed
jobs: a deterministic answer is never substituted for provider acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import fitz
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.application.factory.jobs import ACTIVE_JOB_STATUSES, JobTransitionError, TERMINAL_JOB_STATUSES, ensure_transition
from app.core import config
from app.core.config import SAFETY_NOTICE, UPLOAD_DIR
from app.domains import get_domain
from app.db.database import SessionLocal
from app.db.models import (
    DocumentVersionModel, FactoryJobModel, KnowledgeChunkModel, QuestionBankModel,
    QuestionModel, QuestionRevisionModel, SourceDocumentModel,
)
from app.services.rag_service import rag_service
from app.services.llm_provider import llm_provider


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
    provider_mode: Literal["local_deterministic_adapter", "provider"] = "local_deterministic_adapter"
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None


class JudgeDecision(BaseModel):
    passed: bool
    groundedness: Literal["pass", "fail"]
    answer_consistency: Literal["pass", "fail"]
    citation_validity: Literal["pass", "fail"]
    distractor_quality: Literal["pass", "fail"]
    teaching_value: Literal["pass", "fail"]
    rewrite_instruction: str | None = None
    judge_mode: Literal["local_deterministic_adapter", "provider"] = "local_deterministic_adapter"
    prompt_version: str = JUDGE_PROMPT_VERSION
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None


class ProviderFactoryError(RuntimeError):
    """A configured provider did not produce a schema-valid Factory result."""


def _sha(value: bytes | str) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _record_event(job: FactoryJobModel, stage: str, detail: str, *, progress: int | None = None) -> None:
    """Persist a truthful workflow checkpoint without changing lifecycle state."""
    events = list(job.detail.get("events", []))
    events.append({"status": stage, "detail": detail, "at": _now().isoformat()})
    job.stage = stage
    if progress is not None:
        job.progress = max(0, min(progress, 100))
    job.heartbeat_at = _now()
    job.detail = {**job.detail, "events": events}


def _set_lifecycle(job: FactoryJobModel, status: str, *, stage: str | None = None, error_code: str | None = None, error_message: str | None = None) -> None:
    ensure_transition(job.status, status)
    job.status = status
    job.heartbeat_at = _now()
    if stage is not None:
        job.stage = stage
    if error_code is not None:
        job.error_code = error_code
    if error_message is not None:
        job.error_message = error_message
    if status in TERMINAL_JOB_STATUSES:
        job.completed_at = _now()
        if status == "succeeded":
            job.progress = 100


def _cancel_if_requested(job: FactoryJobModel) -> bool:
    if job.cancel_requested_at is None:
        return False
    if job.status not in TERMINAL_JOB_STATUSES:
        _set_lifecycle(job, "cancelled", stage="cancelled", error_code="job_cancelled", error_message="任务已按请求在安全检查点取消。")
        _record_event(job, "cancelled", "任务已在安全检查点取消。", progress=job.progress)
    return True


def import_allowed_document(
    filename: str,
    content: bytes,
    content_type: str | None = None,
    *,
    source_id: str | None = None,
    source_uri: str | None = None,
    business_usage: str = "factory_source",
    license_gate_status: str = "needs_review",
    ai_ingestion_allowed: bool = False,
    domain_id: str = "endoscopy",
) -> dict[str, str]:
    manifest = get_domain(domain_id)
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
            document_id=document_id, domain_id=manifest.domain_id, bank_id=None, name=Path(filename).name,
            media_type=ALLOWED_SUFFIXES[suffix], content_hash=_sha(content), status="uploaded",
            source_id=source_id, business_usage=business_usage,
            license_gate_status=license_gate_status, ai_ingestion_allowed=ai_ingestion_allowed,
            source_uri=source_uri, namespace=manifest.knowledge_namespaces[-1],
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
        document = session.get(SourceDocumentModel, document_id)
        if document is None:
            raise KeyError("document not found")
        version = session.scalar(
            select(DocumentVersionModel)
            .where(DocumentVersionModel.document_id == document_id)
            .order_by(DocumentVersionModel.created_at.desc())
        )
        version_hash = version.content_hash if version is not None else document.content_hash
        idempotency_key = _sha(f"question_factory:{document_id}:{version_hash}:{GENERATOR_PROMPT_VERSION}:{JUDGE_PROMPT_VERSION}")
        existing = session.scalar(select(FactoryJobModel).where(FactoryJobModel.idempotency_key == idempotency_key))
        if existing is not None:
            if existing.status in ACTIVE_JOB_STATUSES or existing.status == "succeeded":
                return {"job_id": existing.job_id, "status": existing.status, "reused": "true"}
            # A failed/cancelled job is an explicit retry of the same durable
            # input/config, not an accidental duplicate row.
            ensure_transition(existing.status, "queued")
            existing.status = "queued"
            existing.stage = "queued"
            existing.progress = 0
            existing.error_code = None
            existing.error_message = None
            existing.cancel_requested_at = None
            existing.completed_at = None
            _record_event(existing, "queued", "已重新排队执行同一版本的 Factory 任务。", progress=0)
            session.commit()
            return {"job_id": existing.job_id, "status": existing.status, "reused": "true"}
        job = FactoryJobModel(
            job_id=f"factory_{uuid4().hex[:12]}",
            document_id=document_id,
            job_type="question_factory",
            status="queued",
            stage="queued",
            progress=0,
            input_summary={"document_id": document_id, "content_hash": version_hash, "generator_prompt_version": GENERATOR_PROMPT_VERSION, "judge_prompt_version": JUDGE_PROMPT_VERSION},
            idempotency_key=idempotency_key,
            detail={"events": []},
        )
        _record_event(job, "queued", "已接收允许使用的教学文档，等待 Dramatiq worker。", progress=0)
        session.add(job)
        session.commit()
        job_id = job.job_id
    return {"job_id": job_id, "status": "queued", "reused": "false"}


def record_queue_message(job_id: str, message_id: str) -> None:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("factory job not found")
        job.queue_message_id = message_id
        session.commit()


def request_job_cancellation(job_id: str) -> dict[str, str]:
    """Record cancellation durably; workers observe it at safe checkpoints."""
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("factory job not found")
        if job.status in TERMINAL_JOB_STATUSES:
            return {"job_id": job_id, "status": job.status, "stage": job.stage}
        job.cancel_requested_at = _now()
        _record_event(job, job.stage, "已记录取消请求，worker 将在下一个安全检查点停止。", progress=job.progress)
        if job.status == "queued":
            _cancel_if_requested(job)
        session.commit()
        return {"job_id": job_id, "status": job.status, "stage": job.stage}


def recover_stale_factory_jobs(*, stale_after_seconds: int = 300) -> list[str]:
    """Return crash-stale jobs to the durable queue for one explicit re-dispatch."""
    cutoff = _now() - timedelta(seconds=stale_after_seconds)
    recovered: list[str] = []
    with SessionLocal() as session:
        jobs = list(session.scalars(select(FactoryJobModel).where(
            FactoryJobModel.status == "running",
            FactoryJobModel.heartbeat_at.is_not(None),
            FactoryJobModel.heartbeat_at < cutoff,
        )))
        for job in jobs:
            _set_lifecycle(job, "retrying", stage="retrying", error_code="worker_stale", error_message="检测到 worker 心跳过期，已安排重试。")
            _record_event(job, "retrying", "检测到 worker 心跳过期，任务已恢复到队列。", progress=job.progress)
            _set_lifecycle(job, "queued", stage="queued")
            recovered.append(job.job_id)
        session.commit()
    return recovered


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


def _json_response(text: str, *, role: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderFactoryError(f"{role}_invalid_json") from exc
    if not isinstance(value, dict):
        raise ProviderFactoryError(f"{role}_json_not_object")
    return value


def _provider_generator(
    payload: GeneratorInput,
    *,
    repaired: bool = False,
    rewrite_instruction: str | None = None,
) -> GeneratedDraft:
    """One real provider call for the Generator role; no fallback is allowed."""

    system_prompt = """You are the EndoTutor Question Factory Generator. Create one Chinese medical-education single-choice learning draft from supplied evidence only. Do not diagnose, prescribe, or invent facts. Return JSON only with title, stem, options [{id,text}], correct_option_id, explanation, teaching_tags. The explanation must include the Chinese safety notice that it is for teaching or physician review before use and not an independent diagnostic basis."""
    user_payload = {
        "objective": payload.objective,
        "evidence": payload.evidence,
        "required_question_type": "single_choice",
        "repair_request": rewrite_instruction if repaired else None,
    }
    result = llm_provider.chat(
        system_prompt=system_prompt,
        user_prompt=json.dumps(user_payload, ensure_ascii=False),
        temperature=0.1,
        max_tokens=1000,
        allow_fallback=False,
    )
    if not result.ok or result.mode != "provider":
        raise ProviderFactoryError(f"generator_provider_failed:{result.error or result.mode}")
    candidate = _json_response(result.text, role="generator")
    candidate.update(
        {
            "question_type": "single_choice",
            "citation": {"chunk_id": payload.source_chunk_id, "document_id": payload.source_document_id},
            "provider_mode": "provider",
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
        }
    )
    try:
        return GeneratedDraft.model_validate(candidate)
    except Exception as exc:
        raise ProviderFactoryError("generator_schema_invalid") from exc


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


def _provider_judge(
    draft: GeneratedDraft,
    evidence: str,
    *,
    expected_citation: dict[str, str] | None = None,
) -> JudgeDecision:
    """One independently prompted Judge call that sees no Generator reasoning."""

    system_prompt = """You are the EndoTutor Question Factory Judge. Judge only the provided draft, evidence and rubric. Do not access or infer hidden reasoning. Return JSON only with passed, groundedness, answer_consistency, citation_validity, distractor_quality, teaching_value, rewrite_instruction. Each criterion must be exactly pass or fail. Mark pass only if the evidence supports the correct option, the answer is internally consistent, the citation is present, distractors are distinct, and the teaching response preserves doctor-review/non-diagnosis boundaries."""
    public_draft = {
        "question_type": draft.question_type,
        "title": draft.title,
        "stem": draft.stem,
        "options": draft.options,
        "correct_option_id": draft.correct_option_id,
        "explanation": draft.explanation,
        "teaching_tags": draft.teaching_tags,
        "citation": draft.citation,
    }
    result = llm_provider.chat(
        system_prompt=system_prompt,
        user_prompt=json.dumps({"draft": public_draft, "evidence": evidence, "expected_citation": expected_citation, "rubric": "groundedness, answer consistency, citation, distractors, teaching safety"}, ensure_ascii=False),
        temperature=0,
        max_tokens=650,
        allow_fallback=False,
    )
    if not result.ok or result.mode != "provider":
        raise ProviderFactoryError(f"judge_provider_failed:{result.error or result.mode}")
    candidate = _normalize_provider_judge(_json_response(result.text, role="judge"))
    candidate.update(
        {
            "judge_mode": "provider",
            "prompt_version": JUDGE_PROMPT_VERSION,
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
        }
    )
    try:
        return JudgeDecision.model_validate(candidate)
    except Exception as exc:
        details = getattr(exc, "errors", lambda: [])()
        fields = ",".join(".".join(str(part) for part in item.get("loc", [])) for item in details[:6])
        raise ProviderFactoryError(f"judge_schema_invalid:{fields or type(exc).__name__}") from exc


def _normalize_provider_judge(candidate: dict[str, Any]) -> dict[str, Any]:
    """Accept concise Chinese/English judge labels without weakening the schema.

    The provider still has to supply each rubric axis; this only translates
    obvious wire-format synonyms such as ``通过`` into the typed contract.
    """

    passing = {"pass", "passed", "true", "yes", "通过", "合格"}
    failing = {"fail", "failed", "false", "no", "不通过", "失败", "不合格"}

    def criterion(value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized in passing:
            return "pass"
        if normalized in failing:
            return "fail"
        return normalized

    normalized = dict(candidate)
    for field in ("groundedness", "answer_consistency", "citation_validity", "distractor_quality", "teaching_value"):
        normalized[field] = criterion(candidate.get(field, ""))
    passed_value = candidate.get("passed", candidate.get("pass", candidate.get("overall")))
    if isinstance(passed_value, bool):
        normalized["passed"] = passed_value
    else:
        passed_label = criterion(passed_value)
        normalized["passed"] = passed_label == "pass" if passed_label in {"pass", "fail"} else all(
            normalized[field] == "pass"
            for field in ("groundedness", "answer_consistency", "citation_validity", "distractor_quality", "teaching_value")
        )
    if "rewrite_instruction" not in normalized:
        normalized["rewrite_instruction"] = candidate.get("rewrite") or candidate.get("suggestion")
    return normalized


def _run_generator(
    payload: GeneratorInput,
    *,
    mode: Literal["local_deterministic_adapter", "provider"],
    repaired: bool = False,
    rewrite_instruction: str | None = None,
) -> GeneratedDraft:
    if mode == "provider":
        return _provider_generator(payload, repaired=repaired, rewrite_instruction=rewrite_instruction)
    return _generator(payload, repaired=repaired)


def _run_judge(
    draft: GeneratedDraft,
    evidence: str,
    *,
    mode: Literal["local_deterministic_adapter", "provider"],
    expected_citation: dict[str, str] | None = None,
) -> JudgeDecision:
    if mode == "provider":
        return _provider_judge(draft, evidence, expected_citation=expected_citation)
    return _judge(draft, evidence)


def process_factory_job(
    job_id: str,
    *,
    provider_mode: Literal["local_deterministic_adapter", "provider"] | None = None,
) -> dict[str, Any]:
    """Worker entry point. Every state change is persisted, never simulated by UI."""
    from app.services.runtime_settings_service import runtime_settings_service
    runtime_settings_service.sync()
    resolved_mode: Literal["local_deterministic_adapter", "provider"] = (
        provider_mode or ("provider" if config.FACTORY_PROVIDER_ENABLED else "local_deterministic_adapter")
    )
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("factory job not found")
        if job.status in TERMINAL_JOB_STATUSES:
            return {"job_id": job_id, "status": job.status, "stage": job.stage, "idempotent": True}
        if job.status == "running":
            return {"job_id": job_id, "status": "running", "stage": job.stage, "idempotent": True}
        if _cancel_if_requested(job):
            session.commit()
            return {"job_id": job_id, "status": "cancelled", "stage": "cancelled"}
        _set_lifecycle(job, "running", stage="parsing")
        job.attempt += 1
        job.started_at = _now()
        document = session.get(SourceDocumentModel, job.document_id)
        version = session.scalar(select(DocumentVersionModel).where(DocumentVersionModel.document_id == job.document_id).order_by(DocumentVersionModel.created_at.desc()))
        if document is None or version is None:
            _set_lifecycle(job, "failed", stage="failed", error_code="source_missing", error_message="源文档或版本不存在。")
            _record_event(job, "failed", "源文档或版本不存在。", progress=0)
            session.commit()
            return {"job_id": job_id, "status": "failed"}
        _record_event(job, "parsing", "正在解析允许使用的 Markdown/PDF 教学文档。", progress=10)
        session.commit()
        try:
            markdown = _markdown_from_document(version)
        except (OSError, ValueError) as exc:
            _set_lifecycle(job, "failed", stage="failed", error_code="source_unreadable", error_message="上传资料当前不可读取，请重新上传后再试。")
            _record_event(job, "failed", "上传资料当前不可读取，请重新上传后再试。", progress=10)
            session.commit()
            return {"job_id": job_id, "status": "failed", "error": type(exc).__name__}
        version.parser = "heading-aware-markdown" if markdown.suffix == ".md" else "pymupdf"
        version.source_path = str(markdown.resolve())
        session.commit()

    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id); assert job is not None
        if _cancel_if_requested(job):
            session.commit(); return {"job_id": job_id, "status": "cancelled"}
        _record_event(job, "indexing", "正在写入 PostgreSQL source/chunk metadata 与 Qdrant index。", progress=30)
        session.commit()
    try:
        rag_service.index_markdown(
            markdown,
            document_id=document.document_id,
            domain_id=document.domain_id,
            child_size=180,
            namespace="factory_sources",
            source_id=document.source_id,
            source_uri=document.source_uri,
            business_usage=document.business_usage,
            license_gate_status=document.license_gate_status,
            ai_ingestion_allowed=document.ai_ingestion_allowed,
        )
    except Exception as exc:
        with SessionLocal() as session:
            job = session.get(FactoryJobModel, job_id)
            if job is not None:
                _set_lifecycle(job, "failed", stage="failed", error_code="indexing_failed", error_message=f"资料整理未完成，请稍后重试（{type(exc).__name__}）。")
                _record_event(job, "failed", f"资料整理未完成，请稍后重试（{type(exc).__name__}）。", progress=30)
                session.commit()
        return {"job_id": job_id, "status": "failed", "error": type(exc).__name__}

    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id); assert job is not None
        if _cancel_if_requested(job):
            session.commit(); return {"job_id": job_id, "status": "cancelled"}
        chunk = session.scalar(select(KnowledgeChunkModel).where(KnowledgeChunkModel.document_id == job.document_id).order_by(KnowledgeChunkModel.ordinal))
        if chunk is None:
            _set_lifecycle(job, "failed", stage="failed", error_code="no_knowledge_chunk", error_message="文档没有可用知识块。")
            _record_event(job, "failed", "文档没有可用知识块。", progress=45)
            session.commit(); return {"job_id": job_id, "status": "failed"}
        generation_detail = "Generator 使用独立 schema 生成可追溯草稿。"
        if resolved_mode == "provider":
            generation_detail = "Generator 正在调用已配置的真实 Provider；失败将保留为失败，不会改用本地 adapter。"
        _record_event(job, "generating", generation_detail, progress=55)
        try:
            initial = _run_generator(
                GeneratorInput(evidence=chunk.content, source_chunk_id=chunk.chunk_id, source_document_id=chunk.document_id),
                mode=resolved_mode,
            )
        except ProviderFactoryError as exc:
            _set_lifecycle(job, "failed", stage="failed", error_code="generator_provider_failed", error_message="Provider Generator 未生成可用 schema。")
            _record_event(job, "failed", f"Provider Generator 未生成可用 schema：{exc}。", progress=55)
            session.commit()
            return {"job_id": job_id, "status": "failed", "error": str(exc)}
        valid, gate_error = _deterministic_gate(initial, chunk.content)
        initial_revision = QuestionRevisionModel(
            revision_id=f"revision_{uuid4().hex[:12]}", parent_revision_id=None, job_id=job_id,
            status="generated" if valid else "rejected", draft_payload=initial.model_dump(),
            judge_decision={}, rewrite_instruction=gate_error, prompt_version=GENERATOR_PROMPT_VERSION,
            source_chunk_ids=[chunk.chunk_id],
        )
        session.add(initial_revision); session.flush()
        judging_detail = "Judge 使用独立 schema，只读取草稿、资料证据与 rubric。"
        if resolved_mode == "provider":
            judging_detail = "Judge 正在调用独立真实 Provider schema；失败不会由本地 adapter 伪装为通过。"
        _record_event(job, "judging", judging_detail, progress=72)
        if valid:
            try:
                decision = _run_judge(
                    initial,
                    chunk.content,
                    mode=resolved_mode,
                    expected_citation={"chunk_id": chunk.chunk_id, "document_id": chunk.document_id},
                )
            except ProviderFactoryError as exc:
                _set_lifecycle(job, "failed", stage="failed", error_code="judge_provider_failed", error_message="Provider Judge 未生成可用 schema。")
                _record_event(job, "failed", f"Provider Judge 未生成可用 schema：{exc}。", progress=72)
                session.commit()
                return {"job_id": job_id, "status": "failed", "error": str(exc)}
        else:
            decision = JudgeDecision(passed=False, groundedness="fail", answer_consistency="fail", citation_validity="fail", distractor_quality="fail", teaching_value="fail", rewrite_instruction=gate_error)
        initial_revision.judge_decision = decision.model_dump()
        if decision.passed:
            initial_revision.status = "ready_for_review"
            _set_lifecycle(job, "succeeded", stage="ready_for_review")
            job.result_ref = initial_revision.revision_id
            _record_event(job, "ready_for_review", "草稿通过 deterministic gate 与 Judge，等待人工发布。", progress=100)
            session.commit(); return {"job_id": job_id, "status": job.status, "stage": job.stage, "revision_id": initial_revision.revision_id}
        if _cancel_if_requested(job):
            session.commit(); return {"job_id": job_id, "status": "cancelled"}
        _record_event(job, "repairing", "保留初稿并创建新的 repair revision。", progress=84)
        try:
            repaired = _run_generator(
                GeneratorInput(evidence=chunk.content, source_chunk_id=chunk.chunk_id, source_document_id=chunk.document_id),
                mode=resolved_mode,
                repaired=True,
                rewrite_instruction=decision.rewrite_instruction,
            )
            repaired_decision = _run_judge(
                repaired,
                chunk.content,
                mode=resolved_mode,
                expected_citation={"chunk_id": chunk.chunk_id, "document_id": chunk.document_id},
            )
        except ProviderFactoryError as exc:
            _set_lifecycle(job, "failed", stage="failed", error_code="repair_provider_failed", error_message="Provider Repair 未生成可用 schema。")
            _record_event(job, "failed", f"Provider Repair 未生成可用 schema：{exc}。", progress=84)
            session.commit()
            return {"job_id": job_id, "status": "failed", "error": str(exc)}
        repaired_revision = QuestionRevisionModel(
            revision_id=f"revision_{uuid4().hex[:12]}", parent_revision_id=initial_revision.revision_id, job_id=job_id,
            status="ready_for_review" if repaired_decision.passed else "rejected", draft_payload=repaired.model_dump(),
            judge_decision=repaired_decision.model_dump(), rewrite_instruction=decision.rewrite_instruction,
            prompt_version=GENERATOR_PROMPT_VERSION, source_chunk_ids=[chunk.chunk_id],
        )
        session.add(repaired_revision)
        if repaired_decision.passed:
            _set_lifecycle(job, "succeeded", stage="ready_for_review")
            job.result_ref = repaired_revision.revision_id
            _record_event(job, "ready_for_review", "修订版本已保留完整 lineage，等待人工发布。", progress=100)
        else:
            _set_lifecycle(job, "failed", stage="failed", error_code="repair_rejected", error_message="修订版本未通过 Judge。")
            _record_event(job, "failed", "修订版本未通过 Judge。", progress=100)
        session.commit()
        return {"job_id": job_id, "status": job.status, "stage": job.stage, "revision_id": repaired_revision.revision_id}


def publish_revision(job_id: str, revision_id: str) -> dict[str, str]:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        revision = session.get(QuestionRevisionModel, revision_id)
        if job is None or revision is None or revision.job_id != job_id:
            raise KeyError("job or revision not found")
        if revision.status != "ready_for_review" or not revision.judge_decision.get("passed"):
            raise ValueError("only a passed review revision may be published")
        payload = revision.draft_payload
        document = session.get(SourceDocumentModel, job.document_id)
        if document is None:
            raise KeyError("source document not found")
        manifest = get_domain(document.domain_id)
        bank_id = f"factory-generated-{manifest.domain_id}-v1"
        bank = session.get(QuestionBankModel, bank_id)
        if bank is None:
            bank = QuestionBankModel(bank_id=bank_id, domain_id=manifest.domain_id, name=f"{manifest.display_name} · Factory 生成题草稿库", description="基于允许使用资料、需人工审核后发布的题目。", version="factory-v1", status="published", question_count=0, question_type_counts={}, modality_counts={}, body_parts=["资料证据"])
            session.add(bank)
        question_id = f"factory_question_{revision_id[-12:]}"
        if session.get(QuestionModel, question_id) is None:
            session.add(QuestionModel(
                question_id=question_id, bank_id=bank_id, domain_id=manifest.domain_id, question_type="single_choice", modality="text",
                title=payload["title"], stem=payload["stem"], case_summary="由允许使用的教学资料生成，已保留 citation lineage。",
                image_url=None, image_alt=None, difficulty="medium", complexity=1, question_class="资料溯源", task="证据阅读",
                body_part="资料证据", source_type="factory", source_dataset="Factory / allowed document",
                citation_note=f"chunk={payload['citation']['chunk_id']}", options=payload["options"],
                grading_payload={"question_type": "single_choice", "correct_option_id": payload["correct_option_id"]},
                explanation=payload["explanation"], teaching_tags=payload["teaching_tags"], expected_keywords=[], false_premise=False,
                doctor_review_required=manifest.doctor_review_required, safety_notice=manifest.learner_notice, source_document_id=job.document_id,
            ))
            bank.question_count += 1
            bank.question_type_counts = {**bank.question_type_counts, "single_choice": int(bank.question_type_counts.get("single_choice", 0)) + 1}
            bank.modality_counts = {**bank.modality_counts, "text": int(bank.modality_counts.get("text", 0)) + 1}
        revision.status = "published"
        job.result_ref = revision_id
        job.stage = "published"
        _record_event(job, "published", "人工发布动作已将 revision 写入 canonical question bank。", progress=100)
        session.commit()
        return {"job_id": job_id, "revision_id": revision_id, "question_id": question_id, "status": "published"}


def get_job(job_id: str) -> dict[str, Any]:
    with SessionLocal() as session:
        job = session.get(FactoryJobModel, job_id)
        if job is None:
            raise KeyError("job not found")
        revisions = list(session.scalars(select(QuestionRevisionModel).where(QuestionRevisionModel.job_id == job_id).order_by(QuestionRevisionModel.created_at)))
        return {
            "job_id": job.job_id,
            "document_id": job.document_id,
            "job_type": job.job_type,
            "status": job.status,
            "stage": job.stage,
            "progress": job.progress,
            "input_summary": job.input_summary,
            "result_ref": job.result_ref,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "attempt": job.attempt,
            "idempotency_key": job.idempotency_key,
            "cancel_requested_at": job.cancel_requested_at,
            "detail": job.detail,
            "queue_message_id": job.queue_message_id,
            "revisions": [{"revision_id": r.revision_id, "parent_revision_id": r.parent_revision_id, "status": r.status, "draft": r.draft_payload, "judge": r.judge_decision, "rewrite_instruction": r.rewrite_instruction, "source_chunk_ids": r.source_chunk_ids} for r in revisions],
        }

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_DOMAIN_ID
from app.schemas.stage1 import QuestionImageAssetRef
from app.services.factory_service import enqueue_factory_job, get_job, import_allowed_document, mark_factory_dispatch_failed, publish_revision, record_queue_message, request_job_cancellation
from app.services.question_bank_import_service import question_bank_import_service
from app.workers.factory_worker import process_factory_job_actor


router = APIRouter(prefix="/api/v3/factory", tags=["stage2-question-factory"])


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=3, max_length=255)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None
    domain_id: str = DEFAULT_DOMAIN_ID


class FactoryDocumentPublic(BaseModel):
    document_id: str
    name: str
    media_type: str


class FactoryEventPublic(BaseModel):
    status: str
    detail: str
    at: str


class FactoryDraftPublic(BaseModel):
    title: str | None = None
    stem: str | None = None
    explanation: str | None = None
    citation: dict[str, str] = Field(default_factory=dict)


class FactoryJudgePublic(BaseModel):
    passed: bool | None = None
    rewrite_instruction: str | None = None


class FactoryRevisionPublic(BaseModel):
    revision_id: str
    parent_revision_id: str | None
    status: str
    draft: FactoryDraftPublic
    judge: FactoryJudgePublic
    rewrite_instruction: str | None
    source_chunk_ids: list[str]


class FactoryJobDetailPublic(BaseModel):
    events: list[FactoryEventPublic] = Field(default_factory=list)


class FactoryJobPublic(BaseModel):
    job_id: str
    document_id: str
    status: str
    stage: str = "queued"
    progress: int = Field(default=0, ge=0, le=100)
    attempt: int = Field(default=0, ge=0)
    result_ref: str | None = None
    input_summary: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    detail: FactoryJobDetailPublic
    queue_message_id: str | None
    revisions: list[FactoryRevisionPublic]


class FactoryDocumentResponse(BaseModel):
    document: FactoryDocumentPublic
    api_source: str


class FactoryJobQueuedPublic(BaseModel):
    job_id: str
    status: str
    reused: str | None = None


class FactoryPublishPublic(BaseModel):
    job_id: str
    revision_id: str
    question_id: str
    status: str


class FactoryJobCreateResponse(BaseModel):
    item: FactoryJobQueuedPublic
    api_source: str


class FactoryJobReadResponse(BaseModel):
    item: FactoryJobPublic
    api_source: str


class FactoryPublishResponse(BaseModel):
    item: FactoryPublishPublic
    api_source: str


@router.post("/documents", response_model=FactoryDocumentResponse)
def upload_document(request: DocumentUploadRequest) -> FactoryDocumentResponse:
    try:
        document = import_allowed_document(request.filename, base64.b64decode(request.content_base64, validate=True), request.content_type, domain_id=request.domain_id)
        return FactoryDocumentResponse(document=FactoryDocumentPublic.model_validate(document), api_source="backend")
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(422, str(exc)) from exc


class JobRequest(BaseModel):
    document_id: str


@router.post("/jobs", response_model=FactoryJobCreateResponse)
def create_job(request: JobRequest) -> FactoryJobCreateResponse:
    try:
        # Dramatiq is the single async queue path; status is persisted before enqueue.
        item = enqueue_factory_job(request.document_id)
        # Reusing an active/succeeded row must not create duplicate broker
        # messages. A retryable queued row still needs one fresh dispatch.
        if not (item.get("reused") == "true" and item.get("status") in {"running", "succeeded"}):
            try:
                message = process_factory_job_actor.send(item["job_id"])
                record_queue_message(item["job_id"], message.message_id)
            except Exception as exc:
                mark_factory_dispatch_failed(item["job_id"], exc)
                raise HTTPException(503, "任务队列暂不可用，请稍后重试。") from exc
        return FactoryJobCreateResponse(item=FactoryJobQueuedPublic.model_validate(item), api_source="backend")
    except KeyError as exc:
        raise HTTPException(404, "Document not found") from exc
    except HTTPException:
        raise


@router.get("/jobs/{job_id}", response_model=FactoryJobReadResponse)
def read_job(job_id: str) -> FactoryJobReadResponse:
    try:
        return FactoryJobReadResponse(item=FactoryJobPublic.model_validate(get_job(job_id)), api_source="backend")
    except KeyError as exc:
        raise HTTPException(404, "Factory job not found") from exc


@router.post("/jobs/{job_id}/cancel", response_model=FactoryJobCreateResponse)
def cancel_job(job_id: str) -> FactoryJobCreateResponse:
    try:
        item = request_job_cancellation(job_id)
        return FactoryJobCreateResponse(item=FactoryJobQueuedPublic.model_validate(item), api_source="backend")
    except KeyError as exc:
        raise HTTPException(404, "Factory job not found") from exc


class PublishRequest(BaseModel):
    revision_id: str


@router.post("/jobs/{job_id}/publish", response_model=FactoryPublishResponse)
def publish_job(job_id: str, request: PublishRequest) -> FactoryPublishResponse:
    try:
        return FactoryPublishResponse(item=FactoryPublishPublic.model_validate(publish_revision(job_id, request.revision_id)), api_source="backend")
    except KeyError as exc:
        raise HTTPException(404, "Job or revision not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# V3.1.2 learner-facing import workbench.  The legacy async Factory endpoints
# above remain available for developer/compatibility callers, while the UI uses
# this durable review-batch contract exclusively.
class ImportBatchCreateRequest(BaseModel):
    format: Literal["json", "jsonl", "csv", "markdown"]
    content: str = Field(min_length=1, max_length=10 * 1024 * 1024)
    domain_id: str = DEFAULT_DOMAIN_ID
    custom_domain_name: str | None = Field(default=None, max_length=48)
    source_name: str | None = Field(default=None, max_length=120)
    file_name: str | None = Field(default=None, max_length=300)
    image_assets: list[QuestionImageAssetRef] = Field(default_factory=list, max_length=200)


class ImportDraftStatusRequest(BaseModel):
    status: Literal["pending", "approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=500)


class ImportBatchReviewRequest(BaseModel):
    draft_ids: list[str] | None = None
    status: Literal["pending", "approved", "rejected"]
    review_note: str | None = Field(default=None, max_length=500)


class ImportBatchPublishRequest(BaseModel):
    mode: Literal["create_bank", "append_questions"] = "create_bank"
    bank_name: str | None = Field(default=None, max_length=200)
    bank_description: str | None = Field(default=None, max_length=1000)
    target_bank_id: str | None = Field(default=None, max_length=100)


class ImportDraftPublic(BaseModel):
    draft_id: str
    ordinal: int
    status: Literal["pending", "approved", "rejected", "published"]
    review_note: str | None = None
    title: str
    question: str
    question_type: str
    options: list[dict[str, str]] = Field(default_factory=list)
    answer: str
    answer_key: Any = None
    explanation: str
    explanation_available: bool = False
    body_part: str
    difficulty: str
    image_url: str | None = None
    image_alt: str | None = None
    subject: str | None = None
    topic: str | None = None
    teaching_tags: list[str] = Field(default_factory=list)
    source_dataset: str
    expected_keywords: list[str] = Field(default_factory=list)
    fingerprint: str
    source_item_id: str


class ImportBatchPublic(BaseModel):
    batch_id: str
    domain_id: str
    source_name: str
    file_name: str | None = None
    format: str
    status: str
    total_count: int
    pending_count: int
    approved_count: int
    rejected_count: int
    published_count: int
    published_bank_id: str | None = None
    created_at: datetime
    updated_at: datetime
    issues: list[dict[str, Any]] = Field(default_factory=list)
    items: list[ImportDraftPublic] = Field(default_factory=list)


class ImportBatchListResponse(BaseModel):
    items: list[ImportBatchPublic]
    total: int
    api_source: Literal["backend"] = "backend"


class ImportBatchResponse(BaseModel):
    item: ImportBatchPublic
    api_source: Literal["backend"] = "backend"


class ImportBatchPublishPublic(BaseModel):
    batch_id: str
    bank_id: str
    bank_name: str
    imported_count: int
    duplicate_count: int
    published_count: int
    pending_count: int
    status: str
    api_source: Literal["backend"] = "backend"


class ImportBatchPublishResponse(BaseModel):
    item: ImportBatchPublishPublic
    api_source: Literal["backend"] = "backend"


@router.post("/import-batches", response_model=ImportBatchResponse)
def create_import_batch(request: ImportBatchCreateRequest) -> ImportBatchResponse:
    try:
        item = question_bank_import_service.create_review_batch(request.model_dump())
        return ImportBatchResponse(item=ImportBatchPublic.model_validate(item))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/import-batches", response_model=ImportBatchListResponse)
def list_import_batches(status: str | None = Query(default=None)) -> ImportBatchListResponse:
    if status and status not in {"reviewing", "ready_to_publish", "partially_published", "published", "published_with_rejections", "reviewed"}:
        raise HTTPException(status_code=422, detail="无效的审核批次状态。")
    items = question_bank_import_service.list_review_batches(status)
    return ImportBatchListResponse(items=[ImportBatchPublic.model_validate(item) for item in items], total=len(items))


@router.get("/import-batches/{batch_id}", response_model=ImportBatchResponse)
def read_import_batch(batch_id: str) -> ImportBatchResponse:
    try:
        return ImportBatchResponse(item=ImportBatchPublic.model_validate(question_bank_import_service.get_review_batch(batch_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待审核题库不存在。") from exc


@router.patch("/import-batches/{batch_id}/drafts/{draft_id}", response_model=ImportBatchResponse)
def review_import_draft(batch_id: str, draft_id: str, request: ImportDraftStatusRequest) -> ImportBatchResponse:
    try:
        item = question_bank_import_service.review_draft(batch_id, draft_id, request.status, request.review_note)
        return ImportBatchResponse(item=ImportBatchPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待审核题目不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/import-batches/{batch_id}/review", response_model=ImportBatchResponse)
def review_import_batch(batch_id: str, request: ImportBatchReviewRequest) -> ImportBatchResponse:
    try:
        item = question_bank_import_service.review_drafts(batch_id, request.draft_ids, request.status, request.review_note)
        return ImportBatchResponse(item=ImportBatchPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待审核题目不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/import-batches/{batch_id}/publish", response_model=ImportBatchPublishResponse)
def publish_import_batch(batch_id: str, request: ImportBatchPublishRequest) -> ImportBatchPublishResponse:
    try:
        item = question_bank_import_service.publish_review_batch(batch_id, request.model_dump())
        return ImportBatchPublishResponse(item=ImportBatchPublishPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="目标题库或审核批次不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/import-batches/{batch_id}")
def delete_import_batch(batch_id: str) -> dict[str, Any]:
    try:
        question_bank_import_service.delete_review_batch(batch_id)
        return {"batch_id": batch_id, "deleted": True, "api_source": "backend"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="待审核题库不存在。") from exc

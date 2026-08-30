from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.factory_service import enqueue_factory_job, get_job, import_allowed_document, publish_revision, record_queue_message, request_job_cancellation
from app.workers.factory_worker import process_factory_job_actor


router = APIRouter(prefix="/api/v3/factory", tags=["stage2-question-factory"])


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=3, max_length=255)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None


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
        document = import_allowed_document(request.filename, base64.b64decode(request.content_base64, validate=True), request.content_type)
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
        message = process_factory_job_actor.send(item["job_id"])
        record_queue_message(item["job_id"], message.message_id)
        return FactoryJobCreateResponse(item=FactoryJobQueuedPublic.model_validate(item), api_source="backend")
    except KeyError as exc:
        raise HTTPException(404, "Document not found") from exc
    except Exception as exc:
        # The queued row remains canonical evidence, but learners must receive
        # an actionable failure instead of an opaque 500 when Redis is down.
        raise HTTPException(503, "任务队列暂不可用，请稍后重试。") from exc


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

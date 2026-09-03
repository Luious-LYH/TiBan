from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import DEFAULT_DOMAIN_ID
from app.services.knowledge_service import knowledge_service


router = APIRouter(prefix="/api/v3/knowledge", tags=["v31-knowledge"])


class KnowledgeSourcePublic(BaseModel):
    id: str
    title: str
    file_name: str
    media_type: str
    scope: str
    status: str
    size_bytes: int
    chunk_count: int
    enabled: bool
    parser_version: str | None = None
    embedding_model: str | None = None
    embedding_provider: str | None = None
    index_version: int = 0
    index_job_id: str | None = None
    index_stage: str | None = None
    index_progress: int = 0
    index_error: str | None = None
    attribution: str | None = None
    created_at: object
    updated_at: object | None = None


class KnowledgeSourceDetailPublic(KnowledgeSourcePublic):
    preview: list[dict[str, object]] = Field(default_factory=list)


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeSourcePublic]
    api_source: str = "backend"


class KnowledgeDetailResponse(BaseModel):
    item: KnowledgeSourceDetailPublic
    api_source: str = "backend"


class KnowledgeUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None
    domain_id: str = DEFAULT_DOMAIN_ID


class KnowledgeEnabledRequest(BaseModel):
    enabled: bool


@router.get("/sources", response_model=KnowledgeListResponse)
def list_sources(scope: str | None = Query(default=None, pattern="^(system|user|qbank_explanations)?$")) -> KnowledgeListResponse:
    return KnowledgeListResponse(items=[KnowledgeSourcePublic.model_validate(row) for row in knowledge_service.list_sources(scope)])


@router.post("/sources", response_model=KnowledgeDetailResponse)
def upload_source(request: KnowledgeUploadRequest) -> KnowledgeDetailResponse:
    try:
        content = base64.b64decode(request.content_base64, validate=True)
        item = knowledge_service.upload(filename=request.filename, content=content, content_type=request.content_type, domain_id=request.domain_id)
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(item))
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/sources/{document_id}", response_model=KnowledgeDetailResponse)
def source_detail(document_id: str) -> KnowledgeDetailResponse:
    try:
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(knowledge_service.detail(document_id)))
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc


@router.patch("/sources/{document_id}", response_model=KnowledgeDetailResponse)
def update_source(document_id: str, request: KnowledgeEnabledRequest) -> KnowledgeDetailResponse:
    try:
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(knowledge_service.set_enabled(document_id, request.enabled)))
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc


@router.post("/sources/{document_id}/reindex", response_model=KnowledgeDetailResponse)
def reindex_source(document_id: str) -> KnowledgeDetailResponse:
    try:
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(knowledge_service.reindex(document_id)))
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/sources/{document_id}")
def delete_source(document_id: str) -> dict[str, str]:
    try:
        knowledge_service.delete(document_id)
        return {"status": "deleted", "api_source": "backend"}
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc

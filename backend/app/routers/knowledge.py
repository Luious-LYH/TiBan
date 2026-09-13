from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
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
    folder_id: str | None = None
    folder_name: str | None = None
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
    image_count: int | None = None
    image_index_status: str | None = None
    image_index_error: str | None = None
    graph_status: str | None = None
    graph_node_count: int | None = None
    graph_edge_count: int | None = None
    graph_error: str | None = None
    parse_stats: dict[str, object] = Field(default_factory=dict)
    media_preview: list[dict[str, object]] = Field(default_factory=list)
    attribution: str | None = None
    created_at: object
    updated_at: object | None = None


class KnowledgeSourceDetailPublic(KnowledgeSourcePublic):
    preview: list[dict[str, object]] = Field(default_factory=list)


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeSourcePublic]
    api_source: str = "backend"


class KnowledgeFolderPublic(BaseModel):
    id: str
    name: str
    description: str = ""
    scope: str
    is_system: bool = False
    source_count: int = 0
    created_at: object
    updated_at: object | None = None


class KnowledgeFolderListResponse(BaseModel):
    items: list[KnowledgeFolderPublic]
    api_source: str = "backend"


class KnowledgeFolderDeleteResponse(BaseModel):
    status: str
    api_source: str = "backend"


class KnowledgeFolderCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    scope: str = Field(default="user", pattern="^(user|qbank_explanations)$")


class KnowledgeFolderUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class KnowledgeDetailResponse(BaseModel):
    item: KnowledgeSourceDetailPublic
    api_source: str = "backend"


class KnowledgeUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None
    domain_id: str = DEFAULT_DOMAIN_ID


class KnowledgeEnabledRequest(BaseModel):
    enabled: bool | None = None
    folder_id: str | None = Field(default=None, max_length=120)


class KnowledgeProcessRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=5)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    domain_id: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=5, ge=1, le=12)


class KnowledgeSearchResponse(BaseModel):
    citations: list[dict[str, object]] = Field(default_factory=list)
    image_results: list[dict[str, object]] = Field(default_factory=list)
    graph_paths: list[dict[str, object]] = Field(default_factory=list)
    image_index_status: str = "stale"
    graph_status: str = "empty"
    api_source: str = "backend"


@router.get("/sources", response_model=KnowledgeListResponse)
def list_sources(scope: str | None = Query(default=None, pattern="^(system|user|qbank_explanations)?$")) -> KnowledgeListResponse:
    return KnowledgeListResponse(items=[KnowledgeSourcePublic.model_validate(row) for row in knowledge_service.list_sources(scope)])


@router.get("/folders", response_model=KnowledgeFolderListResponse)
def list_folders() -> KnowledgeFolderListResponse:
    return KnowledgeFolderListResponse(items=[KnowledgeFolderPublic.model_validate(row) for row in knowledge_service.list_folders()])


@router.post("/folders", response_model=KnowledgeFolderPublic)
def create_folder(request: KnowledgeFolderCreateRequest) -> KnowledgeFolderPublic:
    try:
        return KnowledgeFolderPublic.model_validate(knowledge_service.create_folder(name=request.name, description=request.description, scope=request.scope))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.patch("/folders/{folder_id}", response_model=KnowledgeFolderPublic)
def update_folder(folder_id: str, request: KnowledgeFolderUpdateRequest) -> KnowledgeFolderPublic:
    try:
        return KnowledgeFolderPublic.model_validate(knowledge_service.update_folder(folder_id, name=request.name, description=request.description))
    except KeyError as exc:
        raise HTTPException(404, "资料目录不存在。") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/folders/{folder_id}", response_model=KnowledgeFolderDeleteResponse)
def delete_folder(folder_id: str) -> KnowledgeFolderDeleteResponse:
    try:
        knowledge_service.delete_folder(folder_id)
        return KnowledgeFolderDeleteResponse(status="deleted")
    except KeyError as exc:
        raise HTTPException(404, "资料目录不存在。") from exc
    except PermissionError as exc:
        raise HTTPException(403, "系统资料目录不可删除。") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/sources", response_model=KnowledgeDetailResponse)
def upload_source(request: KnowledgeUploadRequest) -> KnowledgeDetailResponse:
    try:
        content = base64.b64decode(request.content_base64, validate=True)
        item = knowledge_service.upload(filename=request.filename, content=content, content_type=request.content_type, domain_id=request.domain_id)
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(item))
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/sources/process", response_model=KnowledgeListResponse)
def process_selected_sources(request: KnowledgeProcessRequest) -> KnowledgeListResponse:
    """Start indexing only the five-or-fewer sources explicitly selected by the user."""

    try:
        rows = knowledge_service.queue_selected_sources(request.document_ids)
        return KnowledgeListResponse(items=[KnowledgeSourcePublic.model_validate(item) for item in rows])
    except (ValueError, KeyError) as exc:
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
        folder_id = request.folder_id if "folder_id" in request.model_fields_set else None
        if request.enabled is None and "folder_id" not in request.model_fields_set:
            raise ValueError("没有需要更新的资料属性。")
        if "folder_id" in request.model_fields_set:
            item = knowledge_service.update_source(document_id, enabled=request.enabled, folder_id=folder_id)
        else:
            item = knowledge_service.update_source(document_id, enabled=request.enabled)
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/sources/{document_id}/reindex", response_model=KnowledgeDetailResponse)
def reindex_source(document_id: str) -> KnowledgeDetailResponse:
    try:
        return KnowledgeDetailResponse(item=KnowledgeSourceDetailPublic.model_validate(knowledge_service.reindex(document_id)))
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    """Search text and, when available, related knowledge images/evidence."""

    result = knowledge_service.search(
        query=request.query,
        domain_id=request.domain_id,
        limit=request.limit,
    )
    return KnowledgeSearchResponse.model_validate(result)


@router.get("/media/{asset_id}")
def knowledge_media(asset_id: str) -> FileResponse:
    try:
        path = knowledge_service.resolve_media_path(asset_id)
        item = knowledge_service.media_asset(asset_id)
        return FileResponse(path, media_type=str(item["mime_type"]), headers={"Cache-Control": "private, max-age=300"})
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "资料图片不存在或已失效。") from exc


@router.delete("/sources/{document_id}")
def delete_source(document_id: str) -> dict[str, str]:
    try:
        knowledge_service.delete(document_id)
        return {"status": "deleted", "api_source": "backend"}
    except PermissionError as exc:
        raise HTTPException(403, "系统资料不可删除。") from exc
    except KeyError as exc:
        raise HTTPException(404, "Knowledge source not found.") from exc

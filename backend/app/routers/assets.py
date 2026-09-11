from __future__ import annotations

import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.db.database import SessionLocal
from app.services.data_governance import resolve_local_asset
from app.services.image_asset_service import image_asset_service


router = APIRouter(prefix="/api/v3/assets", tags=["stage2.5-assets"])


class ImageAssetUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    data_url: str = Field(min_length=1, max_length=12 * 1024 * 1024)


class ImageAssetPublic(BaseModel):
    asset_id: str
    filename: str
    url: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    sha256_prefix: str
    expires_at: str | None = None


@router.post("/question-images", response_model=ImageAssetPublic)
def stage_question_image(request: ImageAssetUploadRequest) -> ImageAssetPublic:
    try:
        with SessionLocal() as session:
            return ImageAssetPublic.model_validate(image_asset_service.stage_data_url(session, kind="question", filename=request.filename, data_url=request.data_url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/chat-images", response_model=ImageAssetPublic)
def stage_chat_image(request: ImageAssetUploadRequest) -> ImageAssetPublic:
    try:
        with SessionLocal() as session:
            return ImageAssetPublic.model_validate(image_asset_service.stage_data_url(session, kind="chat", filename=request.filename, data_url=request.data_url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/question-images/{asset_id}")
def question_image(asset_id: str) -> FileResponse:
    try:
        with SessionLocal() as session:
            path = image_asset_service.resolve_path(session, asset_id, kind="question")
            row = image_asset_service.get(session, asset_id, kind="question")
            return FileResponse(path, media_type=row.mime_type, headers={"Cache-Control": "private, max-age=300"})
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="题目图片不存在或已过期。") from exc


@router.get("/chat-images/{asset_id}")
def chat_image(asset_id: str) -> FileResponse:
    try:
        with SessionLocal() as session:
            path = image_asset_service.resolve_path(session, asset_id, kind="chat")
            row = image_asset_service.get(session, asset_id, kind="chat")
            return FileResponse(path, media_type=row.mime_type, headers={"Cache-Control": "private, max-age=300"})
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="聊天图片不存在或已过期。") from exc


@router.get("/local-vqa/{dataset_id}/{asset_path:path}")
def local_vqa_asset(dataset_id: str, asset_path: str) -> FileResponse:
    try:
        path = resolve_local_asset(dataset_id, asset_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Local dataset asset not found.") from exc
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", headers={"Cache-Control": "private, max-age=300"})

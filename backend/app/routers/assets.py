from __future__ import annotations

import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.data_governance import resolve_local_asset


router = APIRouter(prefix="/api/v3/assets", tags=["stage2.5-assets"])


@router.get("/local-vqa/{dataset_id}/{asset_path:path}")
def local_vqa_asset(dataset_id: str, asset_path: str) -> FileResponse:
    try:
        path = resolve_local_asset(dataset_id, asset_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Local dataset asset not found.") from exc
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", headers={"Cache-Control": "private, max-age=300"})

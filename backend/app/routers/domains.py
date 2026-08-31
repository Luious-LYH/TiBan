from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.domains import list_public_domains


router = APIRouter(prefix="/api/v3", tags=["platform-domains"])


class DomainPublic(BaseModel):
    domain_id: str
    display_name: str
    description: str
    subjects: list[str]
    supported_question_types: list[str]


class DomainListResponse(BaseModel):
    items: list[DomainPublic]
    api_source: str = "backend"


@router.get("/domains", response_model=DomainListResponse)
def list_domains() -> dict[str, object]:
    return {"items": list_public_domains(), "api_source": "backend"}

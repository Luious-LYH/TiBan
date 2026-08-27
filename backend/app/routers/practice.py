from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, HTTPException, Query

from app.core.config import SAFETY_NOTICE
from app.db.seed import TYPE_LABEL
from app.schemas import (
    PracticeQuestionDetailResponse,
    PracticeQuestionListResponse,
    PracticeSessionCreateRequest,
    PracticeSessionPublic,
    PracticeSubmitRequest,
    PracticeSubmitResponse,
)
from app.services.stage1_service import stage1_service


canonical_router = APIRouter(prefix="/api/v3", tags=["stage1-practice"])
legacy_router = APIRouter(prefix="/api", tags=["stage1-practice-compat"])


def _type_counts(items: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter(str(item["question_type"]) for item in items)
    labels = {TYPE_LABEL.get(code, "问答评分"): count for code, count in counts.items()}
    return {**dict(counts), **labels}


@canonical_router.get("/practice/questions", response_model=PracticeQuestionListResponse)
def list_questions_v3(
    bank_id: str | None = Query(default=None),
    question_type: str | None = Query(default=None),
    body_part: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=18, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = stage1_service.list_public_questions(
        bank_id=bank_id,
        question_type=question_type,
        body_part=body_part,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": len(items),
        "available_type_counts": _type_counts(items),
        "bank_id": bank_id,
        "safety_notice": SAFETY_NOTICE,
    }


@canonical_router.get("/practice/questions/{question_id}", response_model=PracticeQuestionDetailResponse)
def get_question_v3(question_id: str) -> dict[str, object]:
    try:
        return {"item": stage1_service.public_question(question_id), "safety_notice": SAFETY_NOTICE}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


@canonical_router.post("/practice/sessions", response_model=PracticeSessionPublic)
def create_session_v3(request: PracticeSessionCreateRequest) -> dict[str, object]:
    try:
        return stage1_service.create_session(request.learner_id, request.bank_id, request.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc


@canonical_router.post("/practice/submit", response_model=PracticeSubmitResponse)
def submit_v3(request: PracticeSubmitRequest) -> PracticeSubmitResponse:
    try:
        return stage1_service.submit(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question or bank not found.") from exc


@legacy_router.get("/practice/questions")
def list_questions_compat(
    bank_id: str | None = Query(default=None),
    question_class: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    body_part: str | None = Query(default=None),
    question_type: str | None = Query(default=None),
    limit: int = Query(default=18, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = stage1_service.list_public_questions(
        bank_id=bank_id,
        body_part=body_part,
        question_type=question_type,
        limit=limit,
        offset=offset,
        legacy=True,
    )
    if question_class:
        items = [item for item in items if item.get("question_class") == question_class]
    if difficulty:
        items = [item for item in items if item.get("difficulty") == difficulty]
    return {
        "items": items,
        "total": len(items),
        "available_type_counts": _type_counts([
            {"question_type": item.get("question_type_code", "short_answer")} for item in items
        ]),
        "bank_id": bank_id,
        "safety_notice": SAFETY_NOTICE,
        "api_source": "backend",
    }


@legacy_router.get("/practice/questions/{question_id}")
def get_question_compat(question_id: str) -> dict[str, object]:
    try:
        return {"item": stage1_service.public_question(question_id, legacy=True), "safety_notice": SAFETY_NOTICE}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc


@legacy_router.post("/practice/sessions")
def create_session_compat(request: PracticeSessionCreateRequest) -> dict[str, object]:
    try:
        return stage1_service.create_session(request.learner_id, request.bank_id, request.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc


@legacy_router.post("/practice/submit")
def submit_compat(request: PracticeSubmitRequest) -> dict[str, object]:
    try:
        return stage1_service.submit(request).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question or bank not found.") from exc

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.application.practice.use_cases import PracticeUseCases
from app.adapters.practice_stage1 import Stage1PracticeWorkflowAdapter
from app.db.database import SessionLocal
from app.db.repositories import Stage1Repository
from app.schemas import (
    QuestionMarkRequest,
    QuestionMarkResponse,
    ReviewItemDetailPublic,
    ReviewItemsResponse,
    ReviewSessionCreateRequest,
    ReviewSummaryPublic,
    PracticeSessionPublic,
)
from app.services.stage1_service import stage1_service


router = APIRouter(prefix="/api/v3", tags=["v31-review"])
practice_use_cases = PracticeUseCases(Stage1PracticeWorkflowAdapter(stage1_service))
_SCOPE_BY_TAB = {"due": "due", "wrong": "incorrect", "marked": "marked"}


@router.get("/review/summary", response_model=ReviewSummaryPublic)
def get_review_summary(learner_id: str = Query(default="demo_learner")) -> dict[str, int]:
    with SessionLocal() as session:
        return Stage1Repository(session).review_summary(learner_id)


@router.get("/review/items", response_model=ReviewItemsResponse)
def list_review_items(
    learner_id: str = Query(default="demo_learner"),
    tab: str = Query(default="due", pattern="^(due|wrong|marked)$"),
    bank_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
) -> dict[str, object]:
    with SessionLocal() as session:
        items = Stage1Repository(session).review_items(learner_id=learner_id, tab=tab, bank_id=bank_id, limit=limit)
    return {"tab": tab, "total": len(items), "items": items, "api_source": "backend"}


@router.get("/review/items/{question_id}", response_model=ReviewItemDetailPublic)
def get_review_item(question_id: str, learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    with SessionLocal() as session:
        try:
            return Stage1Repository(session).review_item_detail(learner_id=learner_id, question_id=question_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Review item not found.") from exc


@router.post("/review/sessions", response_model=PracticeSessionPublic)
def create_review_session(request: ReviewSessionCreateRequest) -> dict[str, object]:
    with SessionLocal() as session:
        repository = Stage1Repository(session)
        items = repository.review_items(learner_id=request.learner_id, tab=request.tab, bank_id=request.bank_id, limit=100)
    if not items:
        raise HTTPException(status_code=422, detail="当前筛选没有可复习题目。")
    bank_id = request.bank_id or str(items[0]["bank_id"])
    if any(item["bank_id"] != bank_id for item in items):
        # Sessions deliberately stay bank-scoped: the persisted member list,
        # adaptive selection and Practice context all retain one bank identity.
        items = [item for item in items if item["bank_id"] == bank_id]
    return practice_use_cases.create_practice_session(
        request.learner_id, bank_id, "review", min(request.question_count, len(items)), None, _SCOPE_BY_TAB[request.tab]
    )


@router.put("/questions/{question_id}/mark", response_model=QuestionMarkResponse)
def set_question_mark(question_id: str, request: QuestionMarkRequest) -> QuestionMarkResponse:
    with SessionLocal() as session:
        try:
            marked = Stage1Repository(session).set_question_mark(
                learner_id=request.learner_id, question_id=question_id, marked=request.marked
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Question not found.") from exc
    return QuestionMarkResponse(question_id=question_id, marked=marked, api_source="backend")

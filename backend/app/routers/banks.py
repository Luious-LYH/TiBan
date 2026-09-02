from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.database import SessionLocal
from app.db.repositories import Stage1Repository
from app.schemas import BankQuestionProgressResponse, OverviewResponse, QuestionBankListResponse, QuestionBankPublic
from app.domains import PLATFORM_NOTICE
from app.services.stage1_service import stage1_service


router = APIRouter(prefix="/api/v3", tags=["stage1-banks"])


@router.get("/question-banks", response_model=QuestionBankListResponse)
def list_question_banks(
    learner_id: str = Query(default="demo_learner"),
    domain_id: str | None = Query(default=None),
) -> dict[str, object]:
    items = stage1_service.list_banks(learner_id, domain_id)
    fields = {
        "bank_id",
        "domain_id",
        "name",
        "description",
        "version",
        "status",
        "question_count",
        "question_type_counts",
        "modality_counts",
        "body_parts",
        "completed_count",
        "uncompleted_count",
        "incorrect_count",
        "marked_count",
        "progress",
    }
    return {
        "items": [{key: item[key] for key in fields} for item in items],
        "total": len(items),
        "safety_notice": PLATFORM_NOTICE,
    }


@router.get("/question-banks/{bank_id}", response_model=QuestionBankPublic)
def get_question_bank(bank_id: str, learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    item = next((bank for bank in stage1_service.list_banks(learner_id) if bank["bank_id"] == bank_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    fields = {
        "bank_id",
        "domain_id",
        "name",
        "description",
        "version",
        "status",
        "question_count",
        "question_type_counts",
        "modality_counts",
        "body_parts",
        "completed_count",
        "uncompleted_count",
        "incorrect_count",
        "marked_count",
        "progress",
    }
    return {key: item[key] for key in fields}


@router.get("/question-banks/{bank_id}/questions", response_model=BankQuestionProgressResponse)
def list_bank_questions(
    bank_id: str,
    learner_id: str = Query(default="demo_learner"),
    state: str = Query(default="all", pattern="^(all|uncompleted|completed|incorrect|marked)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    with SessionLocal() as session:
        repository = Stage1Repository(session)
        try:
            items, total = repository.bank_question_progress(
                bank_id=bank_id, learner_id=learner_id, state=state, limit=limit, offset=offset
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Question bank not found.") from exc
    return {"bank_id": bank_id, "state": state, "items": items, "total": total, "api_source": "backend"}


@router.get("/overview", response_model=OverviewResponse)
def overview(learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    return stage1_service.overview(learner_id)

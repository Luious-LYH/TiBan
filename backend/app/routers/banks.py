from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import OverviewResponse, QuestionBankListResponse, QuestionBankPublic
from app.services.stage1_service import stage1_service


router = APIRouter(prefix="/api/v3", tags=["stage1-banks"])


@router.get("/question-banks", response_model=QuestionBankListResponse)
def list_question_banks(learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    items = stage1_service.list_banks(learner_id)
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
        "progress",
    }
    return {"items": [{key: item[key] for key in fields} for item in items], "total": len(items)}


@router.get("/question-banks/{bank_id}", response_model=QuestionBankPublic)
def get_question_bank(bank_id: str, learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    item = next((bank for bank in stage1_service.list_banks(learner_id) if bank["bank_id"] == bank_id), None)
    if item is None:
        from fastapi import HTTPException

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
        "progress",
    }
    return {key: item[key] for key in fields}


@router.get("/overview", response_model=OverviewResponse)
def overview(learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    return stage1_service.overview(learner_id)

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.database import SessionLocal
from app.db.repositories import Stage1Repository
from app.schemas import (
    BankQuestionProgressResponse,
    OverviewResponse,
    QuestionBankListResponse,
    QuestionBankOrderRequest,
    QuestionBankOrderResponse,
    QuestionBankPublic,
    QuestionBankUpdateRequest,
    QuestionBankUpdateResponse,
    QuestionEditPublic,
    QuestionEditRequest,
    QuestionEditResponse,
    QuestionImageAssetRef,
)
from app.domains import PLATFORM_NOTICE
from app.services.stage1_service import stage1_service
from app.services.question_bank_import_service import question_bank_import_service


router = APIRouter(prefix="/api/v3", tags=["stage1-banks"])


class QuestionBankImportRequest(BaseModel):
    """A single write contract for creating or extending a question bank."""

    format: Literal["json", "jsonl", "csv", "markdown"]
    content: str = Field(min_length=1, max_length=10 * 1024 * 1024)
    mode: Literal["create_bank", "append_questions"] = "create_bank"
    domain_id: str = "endoscopy"
    custom_domain_name: str | None = Field(default=None, max_length=48)
    bank_name: str | None = Field(default=None, max_length=200)
    bank_description: str | None = Field(default=None, max_length=1000)
    target_bank_id: str | None = Field(default=None, max_length=100)
    source_name: str | None = Field(default=None, max_length=120)
    file_name: str | None = Field(default=None, max_length=300)
    image_assets: list[QuestionImageAssetRef] = Field(default_factory=list, max_length=200)


class QuestionBankImportResponse(BaseModel):
    mode: str
    bank_id: str
    bank_name: str
    source_document_id: str
    accepted_count: int = Field(ge=0)
    imported_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    issues: list[dict[str, object]] = Field(default_factory=list)
    question_count: int = Field(ge=0)
    question_type_counts: dict[str, int] = Field(default_factory=dict)
    status: str
    api_source: Literal["backend"] = "backend"


@router.post("/question-banks/import", response_model=QuestionBankImportResponse)
def import_question_bank(request: QuestionBankImportRequest) -> QuestionBankImportResponse:
    try:
        return QuestionBankImportResponse.model_validate(
            question_bank_import_service.import_questions(request.model_dump())
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="目标题库不存在。") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


@router.put("/question-banks/order", response_model=QuestionBankOrderResponse)
def reorder_question_banks(
    request: QuestionBankOrderRequest,
    learner_id: str = Query(default="demo_learner"),
) -> QuestionBankOrderResponse:
    """Persist the complete visible question-bank order."""

    with SessionLocal() as session:
        repository = Stage1Repository(session)
        try:
            bank_ids = repository.reorder_banks(request.bank_ids, learner_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return QuestionBankOrderResponse(bank_ids=bank_ids)


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


@router.patch("/question-banks/{bank_id}", response_model=QuestionBankUpdateResponse)
def update_question_bank(bank_id: str, request: QuestionBankUpdateRequest) -> QuestionBankUpdateResponse:
    try:
        question_bank_import_service.update_question_bank(bank_id, request.model_dump())
        item = next((bank for bank in stage1_service.list_banks() if bank["bank_id"] == bank_id), None)
        if item is None:
            raise KeyError("question bank not found")
        return QuestionBankUpdateResponse(item=QuestionBankPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/question-banks/{bank_id}")
def delete_question_bank(bank_id: str) -> dict[str, object]:
    """Remove a selected bank and its dependent study state."""

    try:
        question_bank_import_service.delete_question_bank(bank_id)
        return {"bank_id": bank_id, "deleted": True, "api_source": "backend"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question bank not found.") from exc


@router.get("/question-banks/{bank_id}/questions/{question_id}/edit", response_model=QuestionEditResponse)
def get_question_for_edit(bank_id: str, question_id: str) -> QuestionEditResponse:
    try:
        return QuestionEditResponse(item=QuestionEditPublic.model_validate(question_bank_import_service.get_question_for_edit(bank_id, question_id)))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/question-banks/{bank_id}/questions/{question_id}/edit", response_model=QuestionEditResponse)
def update_question(bank_id: str, question_id: str, request: QuestionEditRequest) -> QuestionEditResponse:
    try:
        item = question_bank_import_service.update_question(bank_id, question_id, request.model_dump())
        return QuestionEditResponse(item=QuestionEditPublic.model_validate(item))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Question not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/question-banks/{bank_id}/questions", response_model=BankQuestionProgressResponse)
def list_bank_questions(
    bank_id: str,
    learner_id: str = Query(default="demo_learner"),
    state: str = Query(default="all", pattern="^(all|uncompleted|completed|incorrect|marked)$"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    with SessionLocal() as session:
        repository = Stage1Repository(session)
        try:
            items, total = repository.bank_question_progress(
                bank_id=bank_id, learner_id=learner_id, state=state, search=search, limit=limit, offset=offset
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Question bank not found.") from exc
    return {"bank_id": bank_id, "state": state, "items": items, "total": total, "api_source": "backend"}


@router.get("/overview", response_model=OverviewResponse)
def overview(learner_id: str = Query(default="demo_learner")) -> dict[str, object]:
    return stage1_service.overview(learner_id)

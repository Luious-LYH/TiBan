from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.database import SessionLocal
from app.services.learning_memory_service import learning_memory_service
from app.services.learning_service import mentor_plan, review_card_payload, review_with_rating


router = APIRouter(prefix="/api/v3/learning", tags=["stage2-learning"])


class ReviewRequest(BaseModel):
    learner_id: str = "demo_learner"
    question_id: str
    rating: str = Field(pattern="^(Again|Hard|Good|Easy)$")


class ReviewCardPublic(BaseModel):
    review_card_id: str
    question_id: str
    due_at: str
    interval_days: int
    difficulty: float | None
    stability: float | None
    retrievability: float | None
    state: str
    review_count: int


class ReviewResponse(BaseModel):
    item: ReviewCardPublic
    api_source: str


class MentorStepPublic(BaseModel):
    kind: str
    title: str
    question_ids: list[str]


class MentorPlanPublic(BaseModel):
    learner_id: str
    study_goal: str
    due_review_count: int
    focus: str
    weak_areas: list[str]
    recent_errors: list[str]
    steps: list[MentorStepPublic]


class MentorResponse(BaseModel):
    plan: MentorPlanPublic
    api_source: str


class LearningMemoryPublic(BaseModel):
    memory_id: str
    kind: str
    summary: str
    status: str
    topic_keys: list[str]
    concept_keys: list[str]
    first_seen_at: str
    last_seen_at: str
    evidence_count: int = Field(ge=1)


class LearningMemoryResponse(BaseModel):
    learner_id: str
    items: list[LearningMemoryPublic]
    api_source: str


class ClearLearningMemoryRequest(BaseModel):
    learner_id: str = "demo_learner"


class ClearLearningMemoryResponse(BaseModel):
    learner_id: str
    superseded_count: int = Field(ge=0)
    preserved_attempt_history: bool = True
    preserved_review_history: bool = True
    api_source: str


@router.post("/review", response_model=ReviewResponse)
def submit_review(request: ReviewRequest) -> ReviewResponse:
    with SessionLocal() as session:
        try:
            payload = review_with_rating(session, learner_id=request.learner_id, question_id=request.question_id, rating_name=request.rating)
            session.commit()
            return ReviewResponse(item=ReviewCardPublic.model_validate(payload), api_source="backend")
        except KeyError as exc:
            raise HTTPException(404, "Review card not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc


@router.get("/mentor", response_model=MentorResponse)
def get_mentor_plan(learner_id: str = "demo_learner", study_goal: str = "巩固观察证据与复盘边界") -> MentorResponse:
    with SessionLocal() as session:
        return MentorResponse(plan=MentorPlanPublic.model_validate(mentor_plan(session, learner_id=learner_id, study_goal=study_goal)), api_source="backend")


@router.get("/memory", response_model=LearningMemoryResponse)
def get_learning_memory(learner_id: str = "demo_learner", limit: int = 5) -> LearningMemoryResponse:
    with SessionLocal() as session:
        items = learning_memory_service.list_for_learner(session, learner_id=learner_id, limit=limit)
        return LearningMemoryResponse(learner_id=learner_id, items=items, api_source="backend")


@router.post("/memory/clear", response_model=ClearLearningMemoryResponse)
def clear_learning_memory(request: ClearLearningMemoryRequest) -> ClearLearningMemoryResponse:
    with SessionLocal() as session:
        superseded_count = learning_memory_service.clear_for_learner(session, learner_id=request.learner_id)
        session.commit()
        return ClearLearningMemoryResponse(
            learner_id=request.learner_id,
            superseded_count=superseded_count,
            api_source="backend",
        )

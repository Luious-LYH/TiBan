"""Canonical Stage 1 contracts.

The legacy ``Question`` model remains available for the old portfolio routes, but
the Stage 1 API uses the discriminated unions below.  Private grading fields are
deliberately separate from public question payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import SAFETY_NOTICE


QuestionTypeCode = Literal["single_choice", "multiple_choice", "true_false", "short_answer"]
Modality = Literal["text", "image", "mixed"]
Difficulty = Literal["easy", "medium", "hard"]
BankStatus = Literal["draft", "published"]


class Stage1Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionOptionPublic(Stage1Model):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class QuestionPublicBase(Stage1Model):
    id: str
    bank_id: str
    domain_id: str
    title: str
    stem: str
    case_summary: str
    modality: Modality
    image_url: str | None = None
    image_alt: str | None = None
    difficulty: Difficulty
    tags: list[str] = Field(default_factory=list)
    body_part: str
    source_dataset: str
    citation_note: str
    doctor_review_required: bool = True
    safety_notice: str = SAFETY_NOTICE


class SingleChoiceQuestionPublic(QuestionPublicBase):
    question_type: Literal["single_choice"]
    options: list[QuestionOptionPublic] = Field(min_length=2)


class MultipleChoiceQuestionPublic(QuestionPublicBase):
    question_type: Literal["multiple_choice"]
    options: list[QuestionOptionPublic] = Field(min_length=2)


class TrueFalseQuestionPublic(QuestionPublicBase):
    question_type: Literal["true_false"]


class ShortAnswerQuestionPublic(QuestionPublicBase):
    question_type: Literal["short_answer"]


QuestionPublic: TypeAlias = Annotated[
    Union[
        SingleChoiceQuestionPublic,
        MultipleChoiceQuestionPublic,
        TrueFalseQuestionPublic,
        ShortAnswerQuestionPublic,
    ],
    Field(discriminator="question_type"),
]


class QuestionForGradingBase(QuestionPublicBase):
    explanation: str
    teaching_tags: list[str] = Field(default_factory=list)
    false_premise: bool = False


class SingleChoiceQuestionForGrading(QuestionForGradingBase):
    question_type: Literal["single_choice"]
    options: list[QuestionOptionPublic] = Field(min_length=2)
    correct_option_id: str


class MultipleChoiceQuestionForGrading(QuestionForGradingBase):
    question_type: Literal["multiple_choice"]
    options: list[QuestionOptionPublic] = Field(min_length=2)
    correct_option_ids: list[str] = Field(min_length=1)


class TrueFalseQuestionForGrading(QuestionForGradingBase):
    question_type: Literal["true_false"]
    correct_value: bool


class ShortAnswerQuestionForGrading(QuestionForGradingBase):
    question_type: Literal["short_answer"]
    rubric: dict[str, Any] = Field(default_factory=dict)
    expected_facts: list[str] = Field(default_factory=list)
    reference_constraints: list[str] = Field(default_factory=list)


QuestionForGrading: TypeAlias = Annotated[
    Union[
        SingleChoiceQuestionForGrading,
        MultipleChoiceQuestionForGrading,
        TrueFalseQuestionForGrading,
        ShortAnswerQuestionForGrading,
    ],
    Field(discriminator="question_type"),
]

# Admin and draft views intentionally reuse the private discriminated contract.
# They remain named aliases so route/service code can state which trust boundary it
# is operating in without introducing a second, divergent question shape.
QuestionAdmin: TypeAlias = QuestionForGrading
QuestionDraft: TypeAlias = QuestionForGrading


class QuestionBankPublic(Stage1Model):
    bank_id: str
    domain_id: str
    name: str
    description: str
    version: str
    status: BankStatus
    question_count: int = Field(ge=0)
    question_type_counts: dict[str, int] = Field(default_factory=dict)
    modality_counts: dict[str, int] = Field(default_factory=dict)
    body_parts: list[str] = Field(default_factory=list)
    completed_count: int = Field(default=0, ge=0)
    progress: float = Field(default=0, ge=0, le=1)


class QuestionBankListResponse(Stage1Model):
    items: list[QuestionBankPublic]
    total: int = Field(ge=0)
    safety_notice: str = SAFETY_NOTICE
    api_source: Literal["backend"] = "backend"


class PracticeQuestionListResponse(Stage1Model):
    items: list[QuestionPublic]
    total: int = Field(ge=0)
    available_type_counts: dict[str, int] = Field(default_factory=dict)
    bank_id: str | None = None
    safety_notice: str = SAFETY_NOTICE
    api_source: Literal["backend"] = "backend"


class PracticeQuestionDetailResponse(Stage1Model):
    item: QuestionPublic
    safety_notice: str = SAFETY_NOTICE
    api_source: Literal["backend"] = "backend"


AnswerValue: TypeAlias = Union[str, list[str], bool]


class PracticeSessionCreateRequest(Stage1Model):
    learner_id: str = "demo_learner"
    bank_id: str
    mode: Literal["practice", "review"] = "practice"


class PracticeSessionPublic(Stage1Model):
    session_id: str
    learner_id: str
    bank_id: str
    mode: str
    status: Literal["active", "completed"]
    started_at: datetime


class PracticeSubmitRequest(Stage1Model):
    question_id: str
    selected_answer: AnswerValue
    session_id: str | None = None
    learner_id: str = "demo_learner"
    hint_count: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)


class FactFeedbackPublic(Stage1Model):
    fact: str
    supported: bool
    note: str


class PracticeSubmitResponse(Stage1Model):
    attempt_id: str
    question_id: str
    session_id: str
    learner_id: str
    is_correct: bool
    score: int = Field(ge=0, le=100)
    error_tags: list[str] = Field(default_factory=list)
    fact_feedback: list[FactFeedbackPublic] = Field(default_factory=list)
    explanation: str
    next_recommendation: str
    profile_updated: bool
    doctor_review_required: bool = True
    safety_notice: str = SAFETY_NOTICE
    created_at: datetime


class OverviewResponse(Stage1Model):
    learner_id: str
    completed_today: int = Field(ge=0)
    daily_target: int = Field(ge=0)
    due_review_count: int = Field(ge=0)
    recent_accuracy: float = Field(ge=0, le=1)
    recent_sessions: list[dict[str, Any]] = Field(default_factory=list)
    banks: list[QuestionBankPublic] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    safety_notice: str = SAFETY_NOTICE
    api_source: Literal["backend"] = "backend"


class Stage1ErrorResponse(Stage1Model):
    code: str
    message: str
    request_id: str | None = None
    safety_notice: str = SAFETY_NOTICE


class TutorHintRequestV3(Stage1Model):
    question_id: str
    learner_id: str = "demo_learner"


class TutorHintResponseV3(Stage1Model):
    message: str
    mode: Literal["rule"] = "rule"
    sources: list[str] = Field(default_factory=list)
    event: Literal["rule_hint"] = "rule_hint"
    doctor_review_required: bool = True
    safety_notice: str = SAFETY_NOTICE


class EvaluationArtifactResponse(Stage1Model):
    artifact_available: bool
    artifact_path: str | None = None
    mode: str
    metric_version: str | None = None
    sample_count: int = Field(default=0, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    cases: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str | None = None
    notice: str
    safety_notice: str = SAFETY_NOTICE

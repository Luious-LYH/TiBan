from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]


class AtomicFact(BaseModel):
    id: str
    fact: str
    expected: str
    supported: bool
    evidence: str
    skill_dimension: Literal["病灶识别", "部位定位", "属性判断", "数量判断", "事实组合", "证据不足识别"]


class Question(BaseModel):
    id: str
    title: str
    image_url: str | None = None
    image_placeholder: str
    case_summary: str
    question: str
    options: list[str]
    answer: str
    explanation: str
    complexity: Literal[1, 2, 3]
    question_class: Literal["基础识别", "部位定位", "病变属性", "复杂组合", "错误前提", "报告纠错", "一图多问"]
    source_type: Literal["公开基础问答", "公开复杂问答", "公开综合基准", "医院合作中文病例", "教学样例"]
    atomic_trace: list[AtomicFact]
    false_premise_flag: bool
    teaching_tags: list[str]
    difficulty: Literal["入门", "进阶", "挑战"]
    doctor_review_required: bool = True
    safety_notice: str


class SubmissionRequest(BaseModel):
    question_id: str
    learner_id: str = "demo_learner"
    selected_answer: str


class SubmissionResponse(BaseModel):
    id: str
    question_id: str
    learner_id: str
    selected_answer: str
    is_correct: bool
    score: int
    error_tags: list[str]
    fact_feedback: list[AtomicFact]
    explanation: str
    next_recommendation: str
    created_at: str
    doctor_review_required: bool = True
    safety_notice: str


class TutorHintRequest(BaseModel):
    question_id: str
    learner_id: str = "demo_learner"


class TutorHintResponse(BaseModel):
    hint: str
    follow_up_question: str
    leak_answer: bool = False
    doctor_review_required: bool = True
    safety_notice: str


class TutorExplainRequest(BaseModel):
    question_id: str
    learner_id: str = "demo_learner"
    selected_answer: str | None = None


class TutorExplainResponse(BaseModel):
    explanation: str
    error_tags: list[str]
    atomic_feedback: list[AtomicFact]
    next_recommendation: str
    doctor_review_required: bool = True
    safety_notice: str


class TutorChatRequest(BaseModel):
    question_id: str
    message: str
    learner_id: str = "demo_learner"


class LearnerProfile(BaseModel):
    learner_id: str
    name: str
    total_questions: int
    accuracy: float
    skill_scores: dict[str, int]
    weakness_tags: list[str]
    recent_errors: list[str]
    recommended_question_classes: list[str]
    updated_at: str


class SkillDefinition(BaseModel):
    id: str
    name: str
    description: str
    category: Literal["training", "feedback", "report", "card", "safety", "audit"]
    enabled: bool
    risk_level: RiskLevel
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class SkillRunRequest(BaseModel):
    skill_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    learner_id: str = "demo_learner"


class ReportDraftRequest(BaseModel):
    finding_text: str
    exam_type: str = "gastroscopy"


class ReportDraft(BaseModel):
    id: str
    input_finding_text: str
    exam_type: str
    structured_findings: list[str]
    draft_impression: list[str]
    review_points: list[str]
    uncertainty_notes: list[str]
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class PatientCardRequest(BaseModel):
    diagnosis_summary: str
    audience: str = "patient"
    reviewed_by_doctor: bool = False


class PatientCard(BaseModel):
    id: str
    card_title: str
    plain_language_explanation: str
    what_it_means: list[str]
    what_to_watch: list[str]
    follow_up_reminder: str
    disclaimer: str
    review_status: Literal["doctor_reviewed_input", "doctor_review_pending"] = "doctor_review_pending"
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class ModelProfile(BaseModel):
    id: str
    name: str
    provider_type: Literal["local", "api", "mock"]
    model_family: Literal["通用多模态", "医学多模态", "内镜领域", "闭源API"]
    recommended_roles: list[str]
    risk_tags: list[str]
    ability_scores: dict[str, int]
    grade: Literal["S", "A", "B", "C"]
    is_active: bool


class ModelSelectRequest(BaseModel):
    model_id: str


class AuditLog(BaseModel):
    id: str
    event_type: Literal[
        "question_view",
        "answer_submit",
        "tutor_reply",
        "report_draft",
        "patient_card",
        "skill_run",
        "model_select",
        "safety_warning",
    ]
    user_id: str
    entity_id: str | None = None
    summary: str
    risk_level: RiskLevel
    doctor_review_required: bool
    created_at: str

from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high"]
QuestionType = Literal["单选", "多选", "判断", "问答评分", "报告修改"]
ReviewStatus = Literal["未开始", "待复盘", "已掌握", "收藏中"]


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
    body_part: str = "胃"
    task: str = "图像观察"
    question_type: QuestionType = "单选"
    source_dataset: str = "平台教学样例"
    citation_note: str = "平台脱敏教学样例。"
    is_favorited: bool = False
    review_status: ReviewStatus = "未开始"
    ai_benchmark_answer: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)


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


class ExamSessionAttempt(BaseModel):
    question_id: str
    title: str = ""
    selected_answer: str
    correct_answer: str
    is_correct: bool
    score: int
    error_tags: list[str] = Field(default_factory=list)


class ExamSessionRequest(BaseModel):
    session_id: str | None = None
    learner_id: str = "demo_learner"
    duration_seconds: int = 720
    remaining_seconds: int = 0
    finished_reason: Literal["manual_submit", "completed_all", "time_expired"] = "manual_submit"
    attempts: list[ExamSessionAttempt]


class ExamSessionResponse(BaseModel):
    id: str
    learner_id: str
    answered_count: int
    correct_count: int
    accuracy: int
    average_score: int
    wrong_questions: list[str]
    elapsed_seconds: int
    finished_reason: str
    profile_updated: bool = True
    memory_summary: str
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


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


class TutorChatResponse(BaseModel):
    reply: str
    scope: str = "current_question_only"
    generation_mode: str = "rule"
    provider_status: dict[str, Any] = Field(default_factory=dict)
    interaction_tags: list[str] = Field(default_factory=list)
    profile_updated: bool = False
    memory_summary: str | None = None
    doctor_review_required: bool = True
    safety_notice: str


class ChallengeBenchmarkRequest(BaseModel):
    question_id: str
    selected_answer: str
    learner_id: str = "demo_learner"


class ChallengeBenchmarkResponse(BaseModel):
    id: str
    question_id: str
    benchmark_name: str
    benchmark_answer: str
    benchmark_correct: bool
    doctor_selected_answer: str
    same_as_doctor: bool
    generation_mode: str = "public_annotation"
    provider_status: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    audit_logged: bool = True
    profile_updated: bool = False
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class LearnerProfile(BaseModel):
    learner_id: str
    name: str
    title: str = "消化内镜进修医师"
    department: str = "消化内镜中心"
    hospital: str = "示范教学医院"
    training_stage: str = "进阶规范化训练"
    training_goal: str = "提升内镜图像观察、证据边界与报告表达能力"
    total_questions: int
    accuracy: float
    completed_today: int = 6
    daily_target: int = 12
    streak_days: int = 5
    favorite_questions: list[str] = Field(default_factory=list)
    wrong_questions: list[str] = Field(default_factory=list)
    skill_scores: dict[str, int]
    weakness_tags: list[str]
    recent_errors: list[str]
    recommended_question_classes: list[str]
    growth_trend: list[dict[str, int | str]] = Field(default_factory=list)
    training_records: list[dict[str, int | str]] = Field(default_factory=list)
    question_type_coverage: dict[str, int] = Field(default_factory=dict)
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
    image_name: str | None = None
    template_name: str | None = None
    provider_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


class ImageUploadRequest(BaseModel):
    filename: str
    data_url: str
    learner_id: str = "demo_learner"


class ImageUploadResponse(BaseModel):
    image_name: str
    original_filename: str
    bytes: int
    source_type: Literal["uploaded_image"]
    doctor_review_required: bool = True
    safety_notice: str


class ReportDraft(BaseModel):
    id: str
    input_finding_text: str
    exam_type: str
    structured_findings: list[str]
    draft_impression: list[str]
    review_points: list[str]
    uncertainty_notes: list[str]
    template_name: str = "胃镜结构化训练模板"
    evidence_source: list[str] = Field(default_factory=list)
    draft_status: Literal["ai_draft", "needs_human_review", "reviewed", "signed"] = "needs_human_review"
    exam_context: dict[str, Any] = Field(default_factory=dict)
    image_quality: dict[str, Any] = Field(default_factory=dict)
    evidence_ledger: list[dict[str, Any]] = Field(default_factory=list)
    hallucination_audit: dict[str, Any] = Field(default_factory=dict)
    review_tasks: list[str] = Field(default_factory=list)
    generation_mode: str = "rule"
    provider_status: dict[str, Any] = Field(default_factory=dict)
    model_observation: str | None = None
    source_trace: list[dict[str, Any]] = Field(default_factory=list)
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class ReportJudgeRequest(BaseModel):
    original_report: str
    revised_report: str
    learner_id: str = "demo_learner"
    provider_name: str | None = None
    api_base: str | None = None
    api_key: str | None = None
    model: str | None = None


class ReportJudgeResponse(BaseModel):
    id: str
    score: int
    strengths: list[str]
    issues: list[str]
    suggested_revision: str
    rubric_scores: dict[str, int]
    recommended_drills: list[dict[str, Any]] = Field(default_factory=list)
    generation_mode: str = "rule"
    provider_status: dict[str, Any] = Field(default_factory=dict)
    provider_feedback: str | None = None
    source_trace: list[dict[str, Any]] = Field(default_factory=list)
    profile_updated: bool = False
    memory_summary: str | None = None
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class PatientCardRequest(BaseModel):
    diagnosis_summary: str
    audience: str = "patient"
    template_id: str = "calm_blue"
    image_url: str | None = None


class PatientCardApproveRequest(BaseModel):
    reviewer_name: str
    review_notes: str | None = None
    review_checks: dict[str, bool] = Field(default_factory=dict)


class PatientCard(BaseModel):
    id: str
    card_title: str
    plain_language_explanation: str
    what_it_means: list[str]
    what_to_watch: list[str]
    follow_up_reminder: str
    disclaimer: str
    template_id: str = "calm_blue"
    visual_tone: str = "稳健、清楚、适合打印"
    image_url: str | None = None
    review_status: Literal["doctor_reviewed_input", "doctor_review_pending"] = "doctor_review_pending"
    share_status: Literal["locked_pending_review", "reviewed_ready_to_share"] = "locked_pending_review"
    reviewer_name: str | None = None
    review_notes: str | None = None
    reviewed_at: str | None = None
    review_steps: list[dict[str, Any]] = Field(default_factory=list)
    generation_mode: str = "rule"
    source_trace: list[dict[str, Any]] = Field(default_factory=list)
    knowledge_base_id: str | None = None
    audit_logged: bool = False
    audit_log_id: str | None = None
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


class ModelAdmissionTestRequest(BaseModel):
    provider_name: str = "自定义模型"
    api_base: str = "https://api.example.com/v1"
    api_key_masked: str = "sk-****"
    api_key: str | None = None
    model: str | None = None
    selected_sample_ids: list[str] = Field(default_factory=list)
    test_focus: list[str] = Field(default_factory=lambda: ["基础识别", "错误前提", "报告安全"])


class ProviderSelfTestRequest(BaseModel):
    provider_name: str = "自定义 Provider"
    api_base: str = "https://api.example.com/v1"
    api_key_masked: str = "sk-****"
    api_key: str | None = None
    model: str | None = None
    include_image: bool = False
    sample_id: str | None = None


class ProviderSelfTestResponse(BaseModel):
    id: str
    provider_name: str
    provider_called: bool = False
    provider_status: dict[str, Any] = Field(default_factory=dict)
    probe_excerpt: str | None = None
    image_attached: bool = False
    image_sample_id: str | None = None
    image_source_dataset: str | None = None
    visual_probe: bool = False
    audit_logged: bool = False
    audit_log_id: str | None = None
    self_test_receipt: dict[str, Any] | None = None
    key_persisted: bool = False
    admission_state_updated: bool = False
    recommendation: str
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class ModelAdmissionTestResponse(BaseModel):
    id: str
    provider_name: str
    grade: Literal["S", "A", "B", "C"]
    total_score: int
    dimension_scores: dict[str, int]
    risk_items: list[str]
    tested_samples: list[str]
    provider_called: bool = False
    is_mock: bool = True
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    provider_status: dict[str, Any] = Field(default_factory=dict)
    recommendation: str
    platform_state_updated: bool = False
    platform_state_summary: str | None = None
    audit_logged: bool = False
    audit_log_id: str | None = None
    admission_receipt: dict[str, Any] | None = None
    doctor_review_required: bool = True
    safety_notice: str
    created_at: str


class FavoriteRequest(BaseModel):
    question_id: str
    learner_id: str = "demo_learner"
    favorited: bool = True


class AuditLog(BaseModel):
    id: str
    event_type: Literal[
        "question_view",
        "answer_submit",
        "tutor_reply",
        "challenge_benchmark",
        "exam_session",
        "report_draft",
        "report_judge",
        "patient_card",
        "patient_card_approve",
        "skill_run",
        "model_select",
        "provider_self_test",
        "model_admission",
        "favorite_update",
        "image_upload",
        "demo_check",
        "safety_warning",
    ]
    user_id: str
    entity_id: str | None = None
    summary: str
    risk_level: RiskLevel
    doctor_review_required: bool
    created_at: str

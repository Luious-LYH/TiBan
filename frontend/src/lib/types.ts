export type RiskLevel = 'low' | 'medium' | 'high'
export type QuestionType = '单选' | '多选' | '判断' | '问答评分' | '报告修改'
export type ReviewStatus = '未开始' | '待复盘' | '已掌握' | '收藏中'
export type GenerationMode = 'provider' | 'rule' | 'fallback'

export type ProviderStatus = {
  configured?: boolean
  provider: string
  model: string
  mode: GenerationMode | string
  ok?: boolean
  error?: string | null
  latency_ms?: number | null
  base_url_configured?: boolean
  api_key_configured?: boolean
  safety_notice?: string
}

export type SourceTraceItem = {
  source_type: string
  label: string
  used: boolean
  detail: string
  latency_ms?: number | null
}

export type AtomicFact = {
  id: string
  fact: string
  expected: string
  supported: boolean
  evidence: string
  skill_dimension: '病灶识别' | '部位定位' | '属性判断' | '数量判断' | '事实组合' | '证据不足识别'
}

export type Question = {
  id: string
  title: string
  image_url?: string
  image_placeholder: string
  case_summary: string
  question: string
  options: string[]
  answer: string
  explanation: string
  complexity: 1 | 2 | 3
  question_class: '基础识别' | '部位定位' | '病变属性' | '复杂组合' | '错误前提' | '报告纠错' | '一图多问'
  source_type: '公开基础问答' | '公开复杂问答' | '公开综合基准' | '医院合作中文病例' | '教学样例'
  atomic_trace: AtomicFact[]
  false_premise_flag: boolean
  teaching_tags: string[]
  difficulty: '入门' | '进阶' | '挑战'
  doctor_review_required: boolean
  safety_notice: string
  body_part: string
  task: string
  question_type: QuestionType
  source_dataset: string
  citation_note: string
  is_favorited: boolean
  review_status: ReviewStatus
  ai_benchmark_answer?: string | null
  expected_keywords: string[]
}

export type SubmissionResponse = {
  id: string
  question_id: string
  learner_id: string
  selected_answer: string
  is_correct: boolean
  score: number
  error_tags: string[]
  fact_feedback: AtomicFact[]
  explanation: string
  next_recommendation: string
  created_at: string
  doctor_review_required: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type LearnerProfile = {
  learner_id: string
  name: string
  title: string
  department: string
  hospital: string
  training_stage: string
  training_goal: string
  total_questions: number
  accuracy: number
  completed_today: number
  daily_target: number
  streak_days: number
  favorite_questions: string[]
  wrong_questions: string[]
  skill_scores: Record<string, number>
  weakness_tags: string[]
  recent_errors: string[]
  recommended_question_classes: string[]
  growth_trend: { date: string; accuracy: number; evidence: number; report: number }[]
  training_records: { date: string; question_id: string; score: number; result: string }[]
  question_type_coverage: Record<string, number>
  updated_at: string
}

export type ModelProfile = {
  id: string
  name: string
  provider_type: 'local' | 'api' | 'mock'
  model_family: '通用多模态' | '医学多模态' | '内镜领域' | '闭源API'
  recommended_roles: string[]
  risk_tags: string[]
  ability_scores: Record<string, number>
  grade: 'S' | 'A' | 'B' | 'C'
  is_active: boolean
}

export type SkillDefinition = {
  id: string
  name: string
  description: string
  category: 'training' | 'feedback' | 'report' | 'card' | 'safety' | 'audit'
  enabled: boolean
  risk_level: RiskLevel
  input_schema: Record<string, unknown>
  output_schema: Record<string, unknown>
}

export type AuditLog = {
  id: string
  event_type:
    | 'question_view'
    | 'answer_submit'
    | 'tutor_reply'
    | 'report_draft'
    | 'patient_card'
    | 'report_judge'
    | 'skill_run'
    | 'model_select'
    | 'favorite_update'
    | 'image_upload'
    | 'safety_warning'
  user_id: string
  entity_id?: string | null
  summary: string
  risk_level: RiskLevel
  doctor_review_required: boolean
  created_at: string
}

export type ReportDraft = {
  id: string
  input_finding_text: string
  exam_type: string
  structured_findings: string[]
  draft_impression: string[]
  review_points: string[]
  uncertainty_notes: string[]
  template_name: string
  evidence_source: string[]
  draft_status: 'ai_draft' | 'needs_human_review' | 'reviewed' | 'signed'
  exam_context: Record<string, unknown>
  image_quality: {
    clarity?: string
    artifacts?: string[]
    single_frame_limitation?: boolean
    [key: string]: unknown
  }
  evidence_ledger: {
    evidence_id: string
    source_type: string
    source_ref: string
    supports: string[]
  }[]
  hallucination_audit: {
    audit_passed?: boolean
    unsupported_claims?: string[]
    high_risk_flags?: string[]
    required_rewrites?: string[]
    evidence_policy?: string
    [key: string]: unknown
  }
  review_tasks: string[]
  generation_mode: GenerationMode | string
  provider_status: ProviderStatus
  model_observation?: string | null
  source_trace: SourceTraceItem[]
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ReportJudge = {
  id: string
  score: number
  strengths: string[]
  issues: string[]
  suggested_revision: string
  rubric_scores: Record<string, number>
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type PatientCard = {
  id: string
  card_title: string
  plain_language_explanation: string
  what_it_means: string[]
  what_to_watch: string[]
  follow_up_reminder: string
  disclaimer: string
  template_id: string
  visual_tone: string
  image_url?: string | null
  review_status: 'doctor_reviewed_input' | 'doctor_review_pending'
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type DashboardPayload = {
  today_training: {
    completed: number
    target: number
    streak_days: number
    review_queue: number
  }
  learner_profile: LearnerProfile
  ability_radar: { dimension: string; score: number }[]
  recommended_training: { label: string; count: number }[]
  today_plan: { label: string; target: number; status: string; href: string }[]
  continue_training: { question_id: string; title: string; source_dataset: string; reason: string }
  favorite_count: number
  wrong_count: number
  recent_tutor_summary: string[]
  growth_trend: { date: string; accuracy: number; evidence: number; report: number }[]
  active_model: ModelProfile
  safety_notice: string
  mock_evaluation_notice: string
  reference_inspirations: string[]
  api_source?: 'backend' | 'fallback'
}

export type TrainingState = {
  profile: LearnerProfile
  wrong_questions: string[]
  favorite_questions: string[]
  review_queue: number
  next_plan: { label: string; count: number; reason: string }[]
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type KnowledgeBase = {
  id: string
  source?: string
  templates?: { id?: string; name: string; tone?: string; sections?: string[]; criteria?: string[]; max_score?: number; review_required?: boolean }[]
  sample_findings?: string[]
  visual_rules?: string[]
}

export type ModelAdmissionResult = {
  id: string
  provider_name: string
  grade: 'S' | 'A' | 'B' | 'C'
  total_score: number
  dimension_scores: Record<string, number>
  risk_items: string[]
  tested_samples: string[]
  provider_called: boolean
  is_mock: boolean
  evidence: {
    sample_id?: string
    source_dataset?: string
    question?: string
    reference_annotation?: string
    provider_called?: boolean
    provider_mode?: string
    latency_ms?: number | null
    observation_excerpt?: string
    error?: string | null
  }[]
  provider_status: ProviderStatus
  recommendation: string
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type TutorChatResponse = {
  reply: string
  scope: string
  generation_mode: GenerationMode | string
  provider_status: ProviderStatus
  doctor_review_required: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type ImageUploadResponse = {
  image_name: string
  original_filename: string
  bytes: number
  source_type: 'uploaded_image'
  doctor_review_required: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

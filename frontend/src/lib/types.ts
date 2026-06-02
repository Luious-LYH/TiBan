export type RiskLevel = 'low' | 'medium' | 'high'

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
  total_questions: number
  accuracy: number
  skill_scores: Record<string, number>
  weakness_tags: string[]
  recent_errors: string[]
  recommended_question_classes: string[]
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
    | 'skill_run'
    | 'model_select'
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
  doctor_review_required: true
  safety_notice: string
  created_at: string
}

export type PatientCard = {
  id: string
  card_title: string
  plain_language_explanation: string
  what_it_means: string[]
  what_to_watch: string[]
  follow_up_reminder: string
  disclaimer: string
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
  active_model: ModelProfile
  safety_notice: string
  mock_evaluation_notice: string
  reference_inspirations: string[]
  api_source?: 'backend' | 'fallback'
}

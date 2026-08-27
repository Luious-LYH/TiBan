// v2.2.2 统一类型定义 - 唯一事实源

/* ==================== 题目和题库 ==================== */

export type QuestionType =
  | 'single_choice'
  | 'multiple_choice'
  | 'true_false'
  | 'short_answer'
  | 'report_revision'

export type QuestionOption = {
  id: string
  text: string
}

export type Question = {
  id: string
  bank_id: string
  title: string
  question: string
  question_type: QuestionType
  options?: QuestionOption[]
  answer: string | string[]
  explanation: string
  knowledge_points: string[]
  body_part: string
  modality: 'text' | 'image_text' | 'image'
  image_url?: string
  image_alt?: string
  difficulty?: 'easy' | 'medium' | 'hard'
  tags: string[]
  source?: string
  version?: string
}

export type QuestionBank = {
  id: string
  name: string
  description: string
  body_parts: string[]
  modality_counts: Record<string, number>
  question_type_counts: Record<QuestionType, number>
  total: number
  completed: number
  progress: number
  version: string
  status: 'draft' | 'published'
}

/* ==================== 提交和反馈 ==================== */

export type SubmitRequest = {
  question_id: string
  selected_answer: string | string[]
  session_id?: string
}

export type SubmitResponse = {
  is_correct: boolean
  score: number
  explanation: string
  fact_feedback?: FactFeedback[]
  error_tags?: string[]
  next_recommendation?: string
  profile_updated: boolean
  doctor_review_required: boolean
  safety_notice: string
}

export type FactFeedback = {
  fact: string
  present: boolean
  evidence_id?: string
  note?: string
}

/* ==================== Agent 和带教 ==================== */

export type TutorMode = 'hint' | 'explain' | 'chat'

export type TutorRequest = {
  mode: TutorMode
  question_id: string
  user_message?: string
  session_id?: string
}

export type TutorResponse = {
  message: string
  sources?: string[]
  provider: 'agent' | 'rule' | 'fallback'
  leaked_answer: boolean
}

/* ==================== 学习记忆 ==================== */

export type SessionMemory = {
  session_id: string
  question_id: string
  recent_messages: TutorMessage[]
  created_at: string
}

export type TutorMessage = {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

export type AttemptLog = {
  id: string
  question_id: string
  answer: string | string[]
  is_correct: boolean
  score: number
  timestamp: string
}

export type LearnerProfile = {
  learner_id: string
  knowledge_mastery: Record<string, number>
  error_patterns: string[]
  weak_areas: string[]
  last_updated: string
}

export type ReviewCard = {
  question_id: string
  difficulty: number
  stability: number
  due_at: string
  review_count: number
  last_review?: string
}

/* ==================== 题库导入 ==================== */

export type ImportFormat = 'jsonl' | 'csv' | 'markdown'

export type ImportValidateRequest = {
  format: ImportFormat
  content: string
}

export type ImportValidateResponse = {
  accepted_count: number
  rejected_count: number
  ready_to_publish: boolean
  items: ImportItem[]
  issues: ImportIssue[]
  summary: string
}

export type ImportItem = {
  line: number
  question: Partial<Question>
  status: 'accepted' | 'rejected'
  errors?: string[]
}

export type ImportIssue = {
  line: number
  field?: string
  message: string
  severity: 'error' | 'warning'
}

export type ImportTemplate = {
  format: ImportFormat
  example: string
  fields: string[]
}

/* ==================== 模型评测 ==================== */

export type ModelEvaluation = {
  id: string
  model_name: string
  model_provider: string
  eval_set_version: string
  total_questions: number
  correct: number
  accuracy: number
  avg_latency_ms: number
  p95_latency_ms: number
  run_at: string
  artifact_url?: string
}

export type CustomModelRequest = {
  api_base: string
  model_name: string
  eval_set_id: string
  // API key 不存储，仅内存使用
}

/* ==================== 状态和 UI ==================== */

export type LoadingState = 'idle' | 'loading' | 'success' | 'error'

export type ApiError = {
  message: string
  code?: string
  details?: Record<string, any>
}

/* ==================== 用户友好标签映射 ==================== */

export const USER_LABELS: Record<string, string> = {
  // Agent 工作流
  'Plan': '规划步骤',
  'Act': '执行评分',
  'Observe': '汇总结果',
  'Verify': '安全检查',
  'Memory': '更新学习记录',

  // 工具名称
  'retrieve_case_evidence': '查找知识依据',
  'fact_rubric_grader': '知识点评分',
  'safety_guard': '安全边界检查',

  // 技术字段
  'Run Receipt': '本次讲解依据',
  'Memory Delta': '学习进度更新',
  'Evidence ID': '参考资料编号',
  'Tool Receipt': '执行记录',
  'Checkpoint': '评分快照',
  'session_id': '会话编号',
  'question_id': '题目编号',
  'learner_id': '学习者编号',
}

export function getUserLabel(key: string): string {
  return USER_LABELS[key] || key
}

/*
 * Stage 1 OpenAPI contract mirror.
 *
 * These types are intentionally aligned with backend/app/schemas/stage1.py.
 * The discriminated Question union is the important boundary: answer and
 * grading fields are not part of any public variant.
 */

export type QuestionType = 'single_choice' | 'multiple_choice' | 'true_false' | 'short_answer'
export type Modality = 'text' | 'image' | 'mixed'
export type Difficulty = 'easy' | 'medium' | 'hard'

export interface QuestionOption {
  id: string
  text: string
}

interface QuestionBase {
  id: string
  bank_id: string
  domain_id: string
  title: string
  stem: string
  case_summary: string
  modality: Modality
  image_url: string | null
  image_alt: string | null
  difficulty: Difficulty
  tags: string[]
  body_part: string
  source_dataset: string
  citation_note: string
  doctor_review_required: boolean
  safety_notice: string
}

export interface SingleChoiceQuestion extends QuestionBase {
  question_type: 'single_choice'
  options: QuestionOption[]
}

export interface MultipleChoiceQuestion extends QuestionBase {
  question_type: 'multiple_choice'
  options: QuestionOption[]
}

export interface TrueFalseQuestion extends QuestionBase {
  question_type: 'true_false'
}

export interface ShortAnswerQuestion extends QuestionBase {
  question_type: 'short_answer'
}

export type Question =
  | SingleChoiceQuestion
  | MultipleChoiceQuestion
  | TrueFalseQuestion
  | ShortAnswerQuestion

export interface QuestionBank {
  bank_id: string
  domain_id: string
  name: string
  description: string
  version: string
  status: 'draft' | 'published'
  question_count: number
  question_type_counts: Record<string, number>
  modality_counts: Record<string, number>
  body_parts: string[]
  completed_count: number
  progress: number
}

export interface Overview {
  learner_id: string
  completed_today: number
  daily_target: number
  due_review_count: number
  recent_accuracy: number
  recent_sessions: RecentSession[]
  banks: QuestionBank[]
  weak_areas: string[]
  safety_notice: string
  api_source: 'backend'
}

export interface RecentSession {
  attempt_id: string
  question_id: string
  score: number
  correct: boolean
  created_at: string
}

export interface QuestionsResponse {
  items: Question[]
  total: number
  available_type_counts: Record<string, number>
  bank_id: string | null
  safety_notice: string
  api_source: 'backend'
}

export interface SessionResponse {
  session_id: string
  learner_id: string
  bank_id: string
  mode: 'practice' | 'review'
  status: 'active' | 'completed'
  started_at: string
}

export type AnswerValue = string | string[] | boolean

export interface SubmitPayload {
  question_id: string
  selected_answer: AnswerValue
  session_id?: string
  learner_id?: string
  hint_count?: number
  duration_ms?: number
}

export interface FactFeedback {
  fact: string
  supported: boolean
  note: string
}

export interface SubmitResult {
  attempt_id: string
  question_id: string
  session_id: string
  learner_id: string
  is_correct: boolean
  score: number
  error_tags: string[]
  fact_feedback: FactFeedback[]
  explanation: string
  next_recommendation: string
  profile_updated: boolean
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
}

export interface TutorHint {
  message: string
  mode: 'rule'
  sources: string[]
  event: 'rule_hint'
  doctor_review_required: boolean
  safety_notice: string
}

export interface EvaluationArtifact {
  artifact_available: boolean
  artifact_path: string | null
  mode: string
  metric_version?: string | null
  sample_count: number
  metrics: Record<string, string | number | boolean | null>
  cases: Array<Record<string, string | number | boolean | null>>
  created_at?: string | null
  notice: string
  safety_notice: string
}

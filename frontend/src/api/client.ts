import createClient from 'openapi-fetch'

import type { components, paths } from './generated'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
const api = createClient<paths>({ baseUrl: API_BASE })

export type Question =
  | components['schemas']['SingleChoiceQuestionPublic']
  | components['schemas']['MultipleChoiceQuestionPublic']
  | components['schemas']['TrueFalseQuestionPublic']
  | components['schemas']['ShortAnswerQuestionPublic']
export type MultipleChoiceQuestion = components['schemas']['MultipleChoiceQuestionPublic']
export type AnswerValue = components['schemas']['PracticeSubmitRequest']['selected_answer']
export type SubmitPayload = Omit<components['schemas']['PracticeSubmitRequest'], 'learner_id' | 'hint_count'> & Partial<Pick<components['schemas']['PracticeSubmitRequest'], 'learner_id' | 'hint_count'>>
export type SubmitResult = components['schemas']['PracticeSubmitResponse']
// These are presentation view models; their fields are projected from the
// generated API components, not hand-maintained response contracts.
export type QuestionBank = Required<components['schemas']['QuestionBankPublic']>
export type QuestionsResponse = components['schemas']['PracticeQuestionListResponse']
export type SessionResponse = components['schemas']['PracticeSessionPublic']
export type TutorHint = components['schemas']['TutorHintResponseV3']
export type Overview = Omit<Required<components['schemas']['OverviewResponse']>, 'banks' | 'recent_sessions'> & {
  banks: QuestionBank[]
  recent_sessions: Array<Required<components['schemas']['RecentSessionPublic']>>
}
export type EvaluationArtifact = components['schemas']['EvaluationArtifactResponse'] & {
  metrics: Record<string, unknown>
  cases: Array<Record<string, unknown>>
}
export type EvaluationDataset = components['schemas']['EvaluationDatasetPublic']
export type EvaluationConnection = components['schemas']['EvaluationConnectionResponse']
export type EvaluationRun = components['schemas']['EvaluationRunResponse']
export type TutorStreamRequest = components['schemas']['TutorStreamRequest']
export type TutorStreamEvent = {
  event: 'message_start' | 'reasoning' | 'token' | 'tool_start' | 'tool_end' | 'source' | 'message_end' | 'error'
  data: Record<string, unknown>
}
// API payload contracts are generated from FastAPI/OpenAPI. Components may
// add purely presentational state around them, but not response schemas.
export type FactoryDocument = components['schemas']['FactoryDocumentPublic']
export type FactoryRevision = components['schemas']['FactoryRevisionPublic']
export type FactoryJob = components['schemas']['FactoryJobPublic']
export type MentorPlan = components['schemas']['MentorPlanPublic']
export type ReviewCard = components['schemas']['ReviewCardPublic']

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function unwrap<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await request
  if (data !== undefined) return data
  const detail = typeof error === 'object' && error && 'detail' in error ? (error as { detail?: string }).detail : undefined
  throw new ApiError(detail ?? `请求失败（${response.status}）`, response.status)
}

export async function getOverview(learnerId = 'demo_learner'): Promise<Overview> {
  const response = await unwrap(api.GET('/api/v3/overview', { params: { query: { learner_id: learnerId } } }))
  return { ...response, banks: (response.banks ?? []) as QuestionBank[], recent_sessions: (response.recent_sessions ?? []) as Overview['recent_sessions'] } as Overview
}

export async function getQuestionBanks(learnerId = 'demo_learner'): Promise<QuestionBank[]> {
  const response = await unwrap(api.GET('/api/v3/question-banks', { params: { query: { learner_id: learnerId } } }))
  return response.items.map((item) => item as QuestionBank)
}

export interface QuestionQuery {
  bankId?: string
  questionType?: string
  search?: string
}

export function getQuestions(query: QuestionQuery = {}): Promise<QuestionsResponse> {
  return unwrap(api.GET('/api/v3/practice/questions', {
    params: { query: { bank_id: query.bankId, question_type: query.questionType, search: query.search, limit: 100 } },
  }))
}

export function createPracticeSession(bankId: string, learnerId = 'demo_learner', mode: 'study' | 'exam' | 'review' | 'practice' = 'study'): Promise<SessionResponse> {
  return unwrap(api.POST('/api/v3/practice/sessions', {
    body: { bank_id: bankId, learner_id: learnerId, mode, question_count: 20 },
  }))
}

export function submitPracticeAnswer(payload: SubmitPayload): Promise<SubmitResult> {
  return unwrap(api.POST('/api/v3/practice/submit', { body: { ...payload, learner_id: payload.learner_id ?? 'demo_learner', hint_count: payload.hint_count ?? 0 } }))
}

export function getTutorHint(questionId: string, learnerId = 'demo_learner'): Promise<TutorHint> {
  return unwrap(api.POST('/api/v3/tutor/hint', { body: { question_id: questionId, learner_id: learnerId } }))
}

export async function streamTutor(request: TutorStreamRequest, onEvent: (event: TutorStreamEvent) => void, signal: AbortSignal): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v3/tutor/stream`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal,
  })
  if (!response.ok || !response.body) throw new ApiError(`Tutor 请求失败（${response.status}）`, response.status)
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const event = frame.match(/^event: (.+)$/m)?.[1] as TutorStreamEvent['event'] | undefined
      const encoded = frame.match(/^data: (.+)$/m)?.[1]
      if (event && encoded) onEvent({ event, data: JSON.parse(encoded) as Record<string, unknown> })
    }
    if (done) break
  }
}

export async function getLatestEvaluation(): Promise<EvaluationArtifact> {
  const response = await unwrap(api.GET('/api/v3/evaluation/latest'))
  return { ...response, metrics: response.metrics ?? {}, cases: response.cases ?? [] }
}

export async function getEvaluationDatasets(): Promise<EvaluationDataset[]> {
  const response = await unwrap(api.GET('/api/v3/evaluation/datasets'))
  return response.items
}

export function testEvaluationConnection(payload: components['schemas']['EvaluationConnectionRequest']): Promise<EvaluationConnection> {
  return unwrap(api.POST('/api/v3/evaluation/connection-test', { body: payload }))
}

export function createEvaluationRun(payload: components['schemas']['EvaluationRunRequest']): Promise<EvaluationRun> {
  return unwrap(api.POST('/api/v3/evaluation/runs', { body: payload }))
}

export function getEvaluationRun(evalRunId: string, revealGold = false): Promise<EvaluationRun> {
  return unwrap(api.GET('/api/v3/evaluation/runs/{eval_run_id}', {
    params: { path: { eval_run_id: evalRunId }, query: { reveal_gold: revealGold } },
  }))
}

export async function uploadFactoryDocument(filename: string, contentBase64: string, contentType?: string): Promise<FactoryDocument> {
  const response = await unwrap(api.POST('/api/v3/factory/documents', { body: { filename, content_base64: contentBase64, content_type: contentType } }))
  return response.document
}

export async function createFactoryJob(documentId: string): Promise<{ job_id: string; status: string }> {
  const response = await unwrap(api.POST('/api/v3/factory/jobs', { body: { document_id: documentId } }))
  return response.item
}

export async function getFactoryJob(jobId: string): Promise<FactoryJob> {
  const response = await unwrap(api.GET('/api/v3/factory/jobs/{job_id}', { params: { path: { job_id: jobId } } }))
  return response.item
}

export async function publishFactoryRevision(jobId: string, revisionId: string): Promise<{ question_id: string; status: string }> {
  const response = await unwrap(api.POST('/api/v3/factory/jobs/{job_id}/publish', { params: { path: { job_id: jobId } }, body: { revision_id: revisionId } }))
  return response.item
}

export async function getMentorPlan(): Promise<MentorPlan> {
  const response = await unwrap(api.GET('/api/v3/learning/mentor', { params: { query: { learner_id: 'demo_learner' } } }))
  return response.plan
}

export async function submitFsrsReview(questionId: string, rating: 'Again' | 'Hard' | 'Good' | 'Easy'): Promise<ReviewCard> {
  const response = await unwrap(api.POST('/api/v3/learning/review', { body: { learner_id: 'demo_learner', question_id: questionId, rating } }))
  return response.item
}

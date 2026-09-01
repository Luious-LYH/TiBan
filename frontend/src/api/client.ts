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
export type Domain = components['schemas']['DomainPublic']
export type QuestionsResponse = components['schemas']['PracticeQuestionListResponse']
export type SessionResponse = components['schemas']['PracticeSessionPublic']
export type SessionDetailResponse = components['schemas']['PracticeSessionDetailPublic']
export type TutorHint = components['schemas']['TutorHintResponseV3']
export type Overview = Omit<Required<components['schemas']['OverviewResponse']>, 'banks' | 'recent_sessions'> & {
  banks: QuestionBank[]
  recent_sessions: Array<Required<components['schemas']['RecentSessionPublic']>>
}
export type EvaluationArtifact = components['schemas']['EvaluationArtifactResponse'] & {
  metrics: Record<string, unknown>
  cases: Array<Record<string, unknown>>
  probes: components['schemas']['EvaluationProbePublic'][]
  strategy_comparison: components['schemas']['EvaluationStrategyPublic'][]
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
export type LearningMemoryItem = components['schemas']['LearningMemoryPublic']
export type LearningMemoryResponse = components['schemas']['LearningMemoryResponse']
export type ClearLearningMemoryResponse = components['schemas']['ClearLearningMemoryResponse']
export type InstanceSettings = components['schemas']['SettingsResponse']
export type LLMSettingsPayload = components['schemas']['LLMSettingsRequest']
export type EmbeddingSettingsPayload = components['schemas']['EmbeddingSettingsRequest']
export type LLMConnectionTestPayload = components['schemas']['LLMConnectionTestRequest']
export type InstanceLLMTestResult = components['schemas']['LLMTestResponse']
export type InstanceEmbeddingTestResult = components['schemas']['EmbeddingTestResponse']
export type QBankValidation = { format: string; accepted_count: number; rejected_count: number; ready_to_publish: boolean; items: Array<{ title: string; question: string; question_type: string }>; issues: Array<{ row: number; code: string; message: string }>; summary: { question_type_counts: Record<string, number> } }

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

export async function getQuestionBanks(learnerId = 'demo_learner', domainId?: string): Promise<QuestionBank[]> {
  const response = await unwrap(api.GET('/api/v3/question-banks', { params: { query: { learner_id: learnerId, domain_id: domainId } } }))
  return response.items.map((item) => item as QuestionBank)
}

export async function getDomains(): Promise<Domain[]> {
  const response = await unwrap(api.GET('/api/v3/domains'))
  return response.items
}

export interface QuestionQuery {
  bankId?: string
  domainId?: string
  questionType?: string
  search?: string
  sessionId?: string
}

export function getQuestions(query: QuestionQuery = {}): Promise<QuestionsResponse> {
  return unwrap(api.GET('/api/v3/practice/questions', {
    params: { query: { bank_id: query.bankId, domain_id: query.domainId, question_type: query.questionType, search: query.search, session_id: query.sessionId, limit: 100 } },
  }))
}

export function createPracticeSession(bankId: string, learnerId = 'demo_learner', mode: 'study' | 'exam' | 'review' | 'practice' = 'study', questionCount = 20): Promise<SessionResponse> {
  return unwrap(api.POST('/api/v3/practice/sessions', {
    body: { bank_id: bankId, learner_id: learnerId, mode, question_count: questionCount },
  }))
}

export function getPracticeSession(sessionId: string): Promise<SessionDetailResponse> {
  return unwrap(api.GET('/api/v3/practice/sessions/{session_id}', { params: { path: { session_id: sessionId } } }))
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
  return { ...response, metrics: response.metrics ?? {}, cases: response.cases ?? [], probes: response.probes ?? [], strategy_comparison: response.strategy_comparison ?? [] }
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

export async function uploadFactoryDocument(filename: string, contentBase64: string, contentType?: string, domainId = 'endoscopy'): Promise<FactoryDocument> {
  const response = await unwrap(api.POST('/api/v3/factory/documents', { body: { filename, content_base64: contentBase64, content_type: contentType, domain_id: domainId } }))
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

export async function getMentorPlan(domainId = 'endoscopy'): Promise<MentorPlan> {
  const response = await unwrap(api.GET('/api/v3/learning/mentor', { params: { query: { learner_id: 'demo_learner', domain_id: domainId } } }))
  return response.plan
}

export async function getLearningMemory(learnerId = 'demo_learner', domainId?: string): Promise<LearningMemoryResponse> {
  return unwrap(api.GET('/api/v3/learning/memory', { params: { query: { learner_id: learnerId, domain_id: domainId, limit: 5 } } }))
}

export function clearLearningMemory(learnerId = 'demo_learner', domainId?: string): Promise<ClearLearningMemoryResponse> {
  return unwrap(api.POST('/api/v3/learning/memory/clear', { body: { learner_id: learnerId, domain_id: domainId } }))
}

export async function submitFsrsReview(questionId: string, rating: 'Again' | 'Hard' | 'Good' | 'Easy', learnerId = 'demo_learner'): Promise<ReviewCard> {
  const response = await unwrap(api.POST('/api/v3/learning/review', { body: { learner_id: learnerId, question_id: questionId, rating } }))
  return response.item
}

export function getInstanceSettings(): Promise<InstanceSettings> { return unwrap(api.GET('/api/v3/settings')) }
export function testInstanceLLM(payload: LLMConnectionTestPayload): Promise<InstanceLLMTestResult> { return unwrap(api.POST('/api/v3/settings/llm/test', { body: payload })) }
export function applyInstanceLLM(payload: LLMSettingsPayload) { return unwrap(api.POST('/api/v3/settings/llm/apply', { body: payload })) }
export function restoreInstanceLLM() { return unwrap(api.POST('/api/v3/settings/llm/restore')) }
export function testInstanceEmbedding(): Promise<InstanceEmbeddingTestResult> { return unwrap(api.POST('/api/v3/settings/embedding/test')) }
export function applyInstanceEmbedding(payload: EmbeddingSettingsPayload) { return unwrap(api.POST('/api/v3/settings/embedding/apply', { body: payload })) }
export function restoreInstanceEmbedding() { return unwrap(api.POST('/api/v3/settings/embedding/restore')) }
export function validateQuestionBankImport(payload: { format: 'csv' | 'jsonl' | 'markdown'; content: string; source_name?: string }): Promise<QBankValidation> { return unwrap(api.POST('/api/question-banks/import/validate', { body: payload })) as Promise<QBankValidation> }

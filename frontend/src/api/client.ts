import createClient from 'openapi-fetch'

import type { components, paths } from './generated'

declare global {
  interface Window {
    __TIBAN_API_BASE__?: string
  }
}

const runtimeApiBase = typeof window !== 'undefined' ? window.__TIBAN_API_BASE__ : undefined
const API_BASE = runtimeApiBase ?? (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''
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
export type BankQuestionProgress = components['schemas']['BankQuestionProgressPublic']
export type BankQuestionProgressResponse = components['schemas']['BankQuestionProgressResponse']
export type ReviewSummary = components['schemas']['ReviewSummaryPublic']
export type ReviewItem = components['schemas']['ReviewItemPublic']
export type ReviewItemDetail = components['schemas']['ReviewItemDetailPublic']
export type Overview = Omit<Required<components['schemas']['OverviewResponse']>, 'banks' | 'recent_bank_activity'> & {
  banks: QuestionBank[]
  recent_bank_activity: Array<Required<components['schemas']['RecentBankActivityPublic']>>
}
export type EvaluationBank = { bank_id: string; domain_id: string; name: string; version: string; eligible_question_count: number }
export type RetrievalProfile = { name: string; mode: 'sparse' | 'dense' | 'hybrid'; top_k: number; candidate_pool: number; rerank_enabled: boolean; rrf_k: number; section_dedupe: boolean }
export type SavedRagProfile = RetrievalProfile & { profile_id: string; bank_id: string; created_at: string; updated_at: string }
export type EvalSuite = { suite_id: string; bank_id: string; bank_name: string; sample_size: number; seed: number; suite_hash: string; suite_short: string; bank_version: string; prompt_version: string; created_at: string }
export type EvaluationLabRun = { run_id: string; name: string; provider: string; base_url: string; model: string; retrieval_profile: RetrievalProfile | null; status: string; aggregate: Record<string, unknown>; progress: number; stage: string; error: string | null }
export type EvaluationExperiment = { experiment_id: string; experiment_type: 'model' | 'rag'; status: string; suite: EvalSuite; fixed_snapshot: Record<string, unknown>; runs: EvaluationLabRun[]; created_at: string }
export type EvaluationCatalog = { banks: EvaluationBank[]; runtime_models: string[]; default_profile: RetrievalProfile; prompt_version: string }
export type DiscoveredModel = { id: string; display_name: string | null; owned_by: string | null }
export type ModelDiscoveryResult = { models: DiscoveredModel[]; latency_ms: number }
export type TutorStreamRequest = components['schemas']['TutorStreamRequest']
export type PracticeResumable = components['schemas']['PracticeResumablePublic']
export type TutorThread = components['schemas']['TutorThreadPublic']
export type TutorStreamEvent = {
  event: 'agent_start' | 'activity' | 'message_start' | 'reasoning' | 'token' | 'tool_start' | 'tool_end' | 'source' | 'done' | 'message_end' | 'error'
  data: Record<string, unknown>
}
export type MentorConversation = components['schemas']['MentorConversationPublic']
export type MentorMessage = components['schemas']['MentorMessagePublic']
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
export type EmbeddingConnectionTestPayload = components['schemas']['EmbeddingConnectionTestRequest']
export type LLMConnectionTestPayload = components['schemas']['LLMConnectionTestRequest']
export type InstanceLLMTestResult = components['schemas']['LLMTestResponse']
export type InstanceEmbeddingTestResult = components['schemas']['EmbeddingTestResponse']
export type IndexRebuildResult = components['schemas']['IndexRebuildResponse']
export type KnowledgeSource = components['schemas']['KnowledgeSourcePublic']
export type KnowledgeSourceDetail = components['schemas']['KnowledgeSourceDetailPublic']
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
  return { ...response, banks: (response.banks ?? []) as QuestionBank[], recent_bank_activity: (response.recent_bank_activity ?? []) as Overview['recent_bank_activity'] } as Overview
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

export function createPracticeSession(bankId: string, learnerId = 'demo_learner', mode: 'study' | 'exam' | 'review' | 'practice' = 'study', questionCount = 20, questionScope: 'all' | 'uncompleted' | 'incorrect' | 'marked' | 'due' = 'all'): Promise<SessionResponse> {
  return unwrap(api.POST('/api/v3/practice/sessions', {
    body: { bank_id: bankId, learner_id: learnerId, mode, question_count: questionCount, question_scope: questionScope },
  }))
}

export function getBankQuestionProgress(bankId: string, state: 'all' | 'uncompleted' | 'completed' | 'incorrect' | 'marked' = 'all'): Promise<BankQuestionProgressResponse> {
  return unwrap(api.GET('/api/v3/question-banks/{bank_id}/questions', { params: { path: { bank_id: bankId }, query: { learner_id: 'demo_learner', state, limit: 100, offset: 0 } } }))
}

export function getReviewSummary(): Promise<ReviewSummary> {
  return unwrap(api.GET('/api/v3/review/summary', { params: { query: { learner_id: 'demo_learner' } } }))
}

export function getReviewItems(tab: 'due' | 'wrong' | 'marked'): Promise<{ tab: string; total: number; items: ReviewItem[] }> {
  return unwrap(api.GET('/api/v3/review/items', { params: { query: { learner_id: 'demo_learner', tab, limit: 100 } } })) as Promise<{ tab: string; total: number; items: ReviewItem[] }>
}

export function getReviewItem(questionId: string): Promise<ReviewItemDetail> {
  return unwrap(api.GET('/api/v3/review/items/{question_id}', { params: { path: { question_id: questionId }, query: { learner_id: 'demo_learner' } } }))
}

export function createReviewSession(tab: 'due' | 'wrong' | 'marked', questionCount: number, bankId?: string): Promise<SessionResponse> {
  return unwrap(api.POST('/api/v3/review/sessions', { body: { learner_id: 'demo_learner', tab, question_count: questionCount, bank_id: bankId } }))
}

export function setQuestionMark(questionId: string, marked: boolean): Promise<{ question_id: string; marked: boolean }> {
  return unwrap(api.PUT('/api/v3/questions/{question_id}/mark', { params: { path: { question_id: questionId } }, body: { learner_id: 'demo_learner', marked } }))
}

export async function getKnowledgeSources(scope?: 'system' | 'user' | 'qbank_explanations'): Promise<KnowledgeSource[]> {
  const response = await unwrap(api.GET('/api/v3/knowledge/sources', { params: { query: { scope } } }))
  return response.items
}

export async function getKnowledgeSource(documentId: string): Promise<KnowledgeSourceDetail> {
  const response = await unwrap(api.GET('/api/v3/knowledge/sources/{document_id}', { params: { path: { document_id: documentId } } }))
  return response.item
}

export async function uploadKnowledgeSource(file: File): Promise<KnowledgeSourceDetail> {
  const content = await fileToBase64(file)
  const response = await unwrap(api.POST('/api/v3/knowledge/sources', { body: { filename: file.name, content_base64: content, content_type: file.type || undefined, domain_id: 'endoscopy' } }))
  return response.item
}

export async function setKnowledgeSourceEnabled(documentId: string, enabled: boolean): Promise<KnowledgeSourceDetail> {
  const response = await unwrap(api.PATCH('/api/v3/knowledge/sources/{document_id}', { params: { path: { document_id: documentId } }, body: { enabled } }))
  return response.item
}

export async function reindexKnowledgeSource(documentId: string): Promise<KnowledgeSourceDetail> {
  const response = await unwrap(api.POST('/api/v3/knowledge/sources/{document_id}/reindex', { params: { path: { document_id: documentId } } }))
  return response.item
}

export async function deleteKnowledgeSource(documentId: string): Promise<{ status: string; api_source: string }> {
  const response = await unwrap(api.DELETE('/api/v3/knowledge/sources/{document_id}', { params: { path: { document_id: documentId } } }))
  return { status: String(response.status), api_source: String(response.api_source) }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '')
    reader.readAsDataURL(file)
  })
}

export function getPracticeSession(sessionId: string): Promise<SessionDetailResponse> {
  return unwrap(api.GET('/api/v3/practice/sessions/{session_id}', { params: { path: { session_id: sessionId } } }))
}

export async function getResumablePracticeSession(learnerId = 'demo_learner'): Promise<PracticeResumable | null> {
  const response = await unwrap(api.GET('/api/v3/practice/sessions/resumable', { params: { query: { learner_id: learnerId } } }))
  return response.item ?? null
}

export function resumePracticeSession(sessionId: string, learnerId = 'demo_learner'): Promise<TutorThread> {
  return unwrap(api.POST('/api/v3/practice/sessions/{session_id}/resume', { params: { path: { session_id: sessionId }, query: { learner_id: learnerId } } }))
}

export async function leavePracticeSession(sessionId: string, learnerId = 'demo_learner', abandon = false): Promise<void> {
  // This endpoint intentionally acknowledges a checkpoint/abandon operation
  // with HTTP 204.  Do not send it through `unwrap`: there is no JSON body to
  // unwrap on a successful no-content response.
  const { error, response } = await api.POST('/api/v3/practice/sessions/{session_id}/leave', {
    params: { path: { session_id: sessionId }, query: { learner_id: learnerId, abandon } },
  })
  if (response.ok) return
  const detail = typeof error === 'object' && error && 'detail' in error ? (error as { detail?: string }).detail : undefined
  throw new ApiError(detail ?? `请求失败（${response.status}）`, response.status)
}

export function submitPracticeAnswer(payload: SubmitPayload): Promise<SubmitResult> {
  return unwrap(api.POST('/api/v3/practice/submit', { body: { ...payload, learner_id: payload.learner_id ?? 'demo_learner', hint_count: payload.hint_count ?? 0 } }))
}

export async function streamTutor(request: TutorStreamRequest, onEvent: (event: TutorStreamEvent) => void, signal: AbortSignal): Promise<void> {
  await streamSse(`${API_BASE}/api/v3/tutor/stream`, request, onEvent, signal, '智能辅导请求失败')
}

export async function listMentorConversations(learnerId = 'demo_learner'): Promise<MentorConversation[]> {
  const response = await unwrap(api.GET('/api/v3/mentor/conversations', { params: { query: { learner_id: learnerId } } }))
  return response.items
}

export async function createMentorConversation(learnerId = 'demo_learner'): Promise<MentorConversation> {
  const response = await unwrap(api.POST('/api/v3/mentor/conversations', { params: { query: { learner_id: learnerId } } }))
  return response.item
}

export async function getMentorConversation(conversationId: string, learnerId = 'demo_learner'): Promise<MentorConversation> {
  const response = await unwrap(api.GET('/api/v3/mentor/conversations/{conversation_id}', { params: { path: { conversation_id: conversationId }, query: { learner_id: learnerId } } }))
  return response.item
}

export async function deleteMentorConversation(conversationId: string, learnerId = 'demo_learner'): Promise<{ conversation_id: string; deleted: boolean }> {
  const response = await unwrap(api.DELETE('/api/v3/mentor/conversations/{conversation_id}', { params: { path: { conversation_id: conversationId }, query: { learner_id: learnerId } } }))
  return { conversation_id: response.conversation_id, deleted: response.deleted }
}

export async function streamMentorMessage(conversationId: string, message: string, onEvent: (event: TutorStreamEvent) => void, signal: AbortSignal, learnerId = 'demo_learner'): Promise<void> {
  await streamSse(`${API_BASE}/api/v3/mentor/conversations/${encodeURIComponent(conversationId)}/stream`, { learner_id: learnerId, message }, onEvent, signal, '带教 Agent 请求失败')
}

async function streamSse(url: string, body: unknown, onEvent: (event: TutorStreamEvent) => void, signal: AbortSignal, failure: string): Promise<void> {
  const response = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal,
  })
  if (!response.ok || !response.body) throw new ApiError(`${failure}（${response.status}）`, response.status)
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

export function getEvaluationCatalog(): Promise<EvaluationCatalog> {
  return unwrap(api.GET('/api/v3/evaluation/lab/catalog')) as Promise<EvaluationCatalog>
}

export function createEvaluationSuite(payload: components['schemas']['EvalSuiteRequest']): Promise<EvalSuite> {
  return unwrap(api.POST('/api/v3/evaluation/lab/suites', { body: payload })) as Promise<EvalSuite>
}

export function getLatestEvaluationSuite(bankId: string): Promise<EvalSuite | null> {
  return unwrap(api.GET('/api/v3/evaluation/lab/suites/latest', { params: { query: { bank_id: bankId } } })) as Promise<EvalSuite | null>
}

export function getSavedRagProfiles(bankId: string): Promise<SavedRagProfile[]> {
  return unwrap(api.GET('/api/v3/evaluation/lab/profiles', { params: { query: { bank_id: bankId } } })) as Promise<SavedRagProfile[]>
}

export function saveRagProfile(bankId: string, profile: RetrievalProfile, profileId?: string): Promise<SavedRagProfile> {
  return unwrap(api.POST('/api/v3/evaluation/lab/profiles', {
    body: {
      bank_id: bankId,
      profile_id: profileId,
      name: profile.name,
      mode: profile.mode,
      top_k: profile.top_k,
      candidate_pool: profile.candidate_pool,
      rerank_enabled: profile.rerank_enabled,
      rrf_k: profile.rrf_k,
      section_dedupe: profile.section_dedupe,
    },
  })) as Promise<SavedRagProfile>
}

export function deleteSavedRagProfile(bankId: string, profileId: string): Promise<{ profile_id: string; deleted: boolean }> {
  return unwrap(api.DELETE('/api/v3/evaluation/lab/profiles/{profile_id}', { params: { path: { profile_id: profileId }, query: { bank_id: bankId } } })) as Promise<{ profile_id: string; deleted: boolean }>
}

export function createModelEvaluation(payload: components['schemas']['ModelExperimentRequest']): Promise<EvaluationExperiment> {
  return unwrap(api.POST('/api/v3/evaluation/lab/experiments/model', { body: payload })) as Promise<EvaluationExperiment>
}

export function discoverEvaluationModels(payload: components['schemas']['ModelDiscoveryRequest']): Promise<ModelDiscoveryResult> {
  return unwrap(api.POST('/api/v3/evaluation/lab/models/discover', { body: payload })) as Promise<ModelDiscoveryResult>
}

export function createRagEvaluation(payload: components['schemas']['RagExperimentRequest']): Promise<EvaluationExperiment> {
  return unwrap(api.POST('/api/v3/evaluation/lab/experiments/rag', { body: payload })) as Promise<EvaluationExperiment>
}

export function getEvaluationExperiment(experimentId: string): Promise<EvaluationExperiment> {
  return unwrap(api.GET('/api/v3/evaluation/lab/experiments/{experiment_id}', { params: { path: { experiment_id: experimentId } } })) as Promise<EvaluationExperiment>
}

export function getLatestEvaluationExperiment(bankId: string, experimentType: 'model' | 'rag'): Promise<EvaluationExperiment | null> {
  return unwrap(api.GET('/api/v3/evaluation/lab/experiments/latest', { params: { query: { bank_id: bankId, experiment_type: experimentType } } })) as Promise<EvaluationExperiment | null>
}

export function deleteEvaluationExperiments(bankId: string, experimentType: 'model' | 'rag'): Promise<{ deleted_experiment_count: number; deleted_run_count: number }> {
  return unwrap(api.DELETE('/api/v3/evaluation/lab/experiments', { params: { query: { bank_id: bankId, experiment_type: experimentType } } })) as Promise<{ deleted_experiment_count: number; deleted_run_count: number }>
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
export function testInstanceEmbedding(payload: EmbeddingConnectionTestPayload = {}): Promise<InstanceEmbeddingTestResult> { return unwrap(api.POST('/api/v3/settings/embedding/test', { body: payload })) }
export function applyInstanceEmbedding(payload: EmbeddingSettingsPayload) { return unwrap(api.POST('/api/v3/settings/embedding/apply', { body: payload })) }
export function restoreInstanceEmbedding() { return unwrap(api.POST('/api/v3/settings/embedding/restore')) }
export function rebuildInstanceIndexes(): Promise<IndexRebuildResult> { return unwrap(api.POST('/api/v3/settings/indexes/rebuild')) }
export function validateQuestionBankImport(payload: { format: 'csv' | 'jsonl' | 'markdown'; content: string; source_name?: string }): Promise<QBankValidation> { return unwrap(api.POST('/api/question-banks/import/validate', { body: payload })) as Promise<QBankValidation> }

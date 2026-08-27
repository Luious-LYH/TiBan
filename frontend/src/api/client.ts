import type {
  EvaluationArtifact,
  Overview,
  QuestionBank,
  QuestionsResponse,
  SessionResponse,
  SubmitPayload,
  SubmitResult,
  TutorHint,
} from './generated'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const detail = (await response.json()) as { detail?: string }
      message = detail.detail ?? message
    } catch {
      // Keep the stable status message when the server response is not JSON.
    }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export async function getOverview(learnerId = 'demo_learner'): Promise<Overview> {
  return requestJson<Overview>(`/api/v3/overview?learner_id=${encodeURIComponent(learnerId)}`)
}

export async function getQuestionBanks(learnerId = 'demo_learner'): Promise<QuestionBank[]> {
  const response = await requestJson<{ items: QuestionBank[] }>(
    `/api/v3/question-banks?learner_id=${encodeURIComponent(learnerId)}`,
  )
  return response.items
}

export interface QuestionQuery {
  bankId?: string
  questionType?: string
  search?: string
}

export async function getQuestions(query: QuestionQuery = {}): Promise<QuestionsResponse> {
  const params = new URLSearchParams({ limit: '100' })
  if (query.bankId) params.set('bank_id', query.bankId)
  if (query.questionType) params.set('question_type', query.questionType)
  if (query.search) params.set('search', query.search)
  return requestJson<QuestionsResponse>(`/api/v3/practice/questions?${params.toString()}`)
}

export async function createPracticeSession(bankId: string, learnerId = 'demo_learner'): Promise<SessionResponse> {
  return requestJson<SessionResponse>('/api/v3/practice/sessions', {
    method: 'POST',
    body: JSON.stringify({ bank_id: bankId, learner_id: learnerId, mode: 'practice' }),
  })
}

export async function submitPracticeAnswer(payload: SubmitPayload): Promise<SubmitResult> {
  return requestJson<SubmitResult>('/api/v3/practice/submit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getTutorHint(questionId: string, learnerId = 'demo_learner'): Promise<TutorHint> {
  return requestJson<TutorHint>('/api/v3/tutor/hint', {
    method: 'POST',
    body: JSON.stringify({ question_id: questionId, learner_id: learnerId }),
  })
}

export async function getLatestEvaluation(): Promise<EvaluationArtifact> {
  return requestJson<EvaluationArtifact>('/api/v3/evaluation/latest')
}

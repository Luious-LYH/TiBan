import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createEvaluationRun, createPracticeSession, getEvaluationDatasets, getEvaluationRun, getLatestEvaluation, getMentorPlan, getOverview, getQuestionBanks, getQuestions, streamTutor, submitFsrsReview, submitPracticeAnswer, testEvaluationConnection } from '../api/client'
import type { EvaluationRun, Overview, Question, QuestionBank, QuestionsResponse, SubmitResult } from '../api/client'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'

vi.mock('../api/client', () => ({
  createPracticeSession: vi.fn(),
  createEvaluationRun: vi.fn(),
  getEvaluationDatasets: vi.fn(),
  getEvaluationRun: vi.fn(),
  getLatestEvaluation: vi.fn(),
  getOverview: vi.fn(),
  getQuestionBanks: vi.fn(),
  getQuestions: vi.fn(),
  getMentorPlan: vi.fn(),
  streamTutor: vi.fn(),
  submitFsrsReview: vi.fn(),
  submitPracticeAnswer: vi.fn(),
  testEvaluationConnection: vi.fn(),
}))

const mockedGetOverview = vi.mocked(getOverview)
const mockedCreateSession = vi.mocked(createPracticeSession)
const mockedGetQuestionBanks = vi.mocked(getQuestionBanks)
const mockedGetQuestions = vi.mocked(getQuestions)
const mockedSubmit = vi.mocked(submitPracticeAnswer)
const mockedStreamTutor = vi.mocked(streamTutor)
const mockedMentor = vi.mocked(getMentorPlan)
const mockedReview = vi.mocked(submitFsrsReview)
const mockedEvaluation = vi.mocked(getLatestEvaluation)
const mockedEvaluationDatasets = vi.mocked(getEvaluationDatasets)
const mockedCreateEvaluationRun = vi.mocked(createEvaluationRun)
const mockedGetEvaluationRun = vi.mocked(getEvaluationRun)
const mockedTestEvaluationConnection = vi.mocked(testEvaluationConnection)

const safety = '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'
const baseQuestion = { id: 'q-1', bank_id: 'bank-a', domain_id: 'endoscopy', title: '胃部观察练习', stem: '请根据当前证据选择答案。', case_summary: '稳定的测试病例摘要。', modality: 'image' as const, image_url: '/assets/real_samples/endo_image_0.jpg', image_alt: '测试内镜图像', difficulty: 'easy' as const, tags: ['胃'], body_part: '胃', source_dataset: 'test', citation_note: 'test seed', doctor_review_required: true, safety_notice: safety, business_usage: 'user_ready' as const, official_explanation_available: true }
const questionVariants: Question[] = [
  { ...baseQuestion, id: 'single', question_type: 'single_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'multi', question_type: 'multiple_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'judge', question_type: 'true_false' },
  { ...baseQuestion, id: 'short', question_type: 'short_answer' },
]
const textOnlyQuestion: Question = { ...baseQuestion, id: 'text-only', modality: 'text', image_url: null, image_alt: null, case_summary: '来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。', question_type: 'single_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] }
const banks: QuestionBank[] = [
  { bank_id: 'bank-a', domain_id: 'endoscopy', name: '胃部观察题库', description: '胃部位与可见事实训练。', version: 'test-v1', status: 'published', question_count: 4, question_type_counts: { single_choice: 1, multiple_choice: 1, true_false: 1, short_answer: 1 }, modality_counts: { image: 4 }, body_parts: ['胃'], completed_count: 0, progress: 0 },
  { bank_id: 'bank-b', domain_id: 'endoscopy', name: '食管观察题库', description: '食管观察与表达训练。', version: 'test-v1', status: 'published', question_count: 2, question_type_counts: { single_choice: 2 }, modality_counts: { text: 2 }, body_parts: ['食管'], completed_count: 0, progress: 0 },
]
const overview: Overview = { learner_id: 'demo_learner', completed_today: 0, daily_target: 10, due_review_count: 0, recent_accuracy: 0, recent_sessions: [], banks, weak_areas: [], safety_notice: safety, api_source: 'backend' }

function questionsResponse(items: Question[]): QuestionsResponse {
  return { items, total: items.length, available_type_counts: {}, bank_id: 'bank-a', safety_notice: safety, api_source: 'backend' }
}

function submitResult(questionId: string): SubmitResult {
  return { attempt_id: 'attempt-test', question_id: questionId, session_id: 'session-test', learner_id: 'demo_learner', is_correct: true, score: 100, error_tags: [], fact_feedback: [], explanation: '已按确定性规则记录。', next_recommendation: '可以继续下一题。', profile_updated: true, doctor_review_required: true, safety_notice: safety, created_at: '2026-08-28T00:00:00Z', selected_answer: 'opt_01', selected_answer_display: '选项一', correct_answer_display: '选项一', answer_source: 'dataset_gold', explanation_source: 'dataset_gold', official_explanation_available: true }
}

function renderPage(ui: React.ReactNode, initialEntries = ['/']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter></QueryClientProvider>)
}

function renderStrictPage(ui: React.ReactNode, initialEntries = ['/']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<StrictMode><QueryClientProvider client={queryClient}><MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter></QueryClientProvider></StrictMode>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGetOverview.mockResolvedValue(overview)
  mockedGetQuestionBanks.mockResolvedValue(banks)
  mockedGetQuestions.mockResolvedValue(questionsResponse(questionVariants))
  mockedCreateSession.mockResolvedValue({ session_id: 'session-test', bank_id: 'bank-a', learner_id: 'demo_learner', mode: 'study', status: 'active', started_at: '2026-08-28T00:00:00Z', question_count: 20, question_ids: [], selection_strategy: 'coverage', selection_reason: '本次按未练题与题库覆盖安排练习。', selection_evidence: ['优先安排未练题。'] })
  mockedSubmit.mockResolvedValue(submitResult('single'))
  mockedMentor.mockResolvedValue({ learner_id: 'demo_learner', study_goal: '复盘', due_review_count: 1, focus: '胃', weak_areas: ['胃'], recent_errors: [], steps: [{ kind: 'review', title: '完成复习', question_ids: [] }] })
  mockedReview.mockResolvedValue({ review_card_id: 'review-test', question_id: 'single', due_at: '2026-08-29T00:00:00Z', interval_days: 1, difficulty: 2, stability: 1, retrievability: .9, state: 'Learning', review_count: 1 })
  mockedStreamTutor.mockImplementation(async (_request, onEvent) => {
    onEvent({ event: 'message_start', data: { run_id: 'run-test', provider_real: true } })
    onEvent({ event: 'tool_start', data: { tool_name: 'get_question_context' } })
    onEvent({ event: 'tool_end', data: { tool_name: 'get_question_context' } })
    onEvent({ event: 'source', data: { document_name: 'test source', page: '1', section: '观察要点' } })
    onEvent({ event: 'reasoning', data: { summary: ['识别学习目标', '对照可见证据'] } })
    onEvent({ event: 'token', data: { text: '先观察可支持事实。' } })
    onEvent({ event: 'message_end', data: { run_id: 'run-test' } })
  })
  mockedEvaluation.mockResolvedValue({ artifact_available: false, artifact_path: null, mode: 'not_run', sample_count: 0, metrics: {}, cases: [], notice: '尚未运行', safety_notice: safety })
  mockedEvaluationDatasets.mockResolvedValue([{ dataset_id: 'cmexam-text-eval-v1', name: 'CMExam 文本评测', description: '冻结评测集', source_dataset: 'CMExam', modality: 'text', version: 'cmexam-text-eval-v1', dataset_hash: 'hash', sample_count: 5, supports_vision: false, tutor_indexed: false }])
  mockedTestEvaluationConnection.mockResolvedValue({ ok: true, provider: 'byok_openai_compatible', model: 'candidate-model', latency_ms: 12, error: null, fallback: false, key_persisted: false })
  const evaluationRun: EvaluationRun = { eval_run_id: 'evalrun-test', dataset_id: 'cmexam-text-eval-v1', dataset_version: 'cmexam-text-eval-v1', dataset_hash: 'hash', provider: 'byok_openai_compatible', model: 'candidate-model', prompt_version: 'model-eval-answer-json-v1', status: 'completed', sample_count: 1, aggregate: { accuracy: 1, valid_parse_rate: 1, latency_p50_ms: 12, latency_p95_ms: 12 }, usage: { total_tokens: 12 }, errors: [], created_at: '2026-08-28T00:00:00Z', completed_at: '2026-08-28T00:00:12Z', artifact_path: 'artifacts/eval/model-runs/evalrun-test.json', cases: [{ eval_case_id: 'case-1', question: 'Which option is correct?', candidate_output: '{"answer":"B"}', parsed_answer: 'B', gold_answer: null, correct: null, valid_parse: true, latency_ms: 12, error_category: null, task: 'text_single_choice', topic: 'fixture' }], gold_revealed: false, fallback: false, safety_notice: safety }
  mockedCreateEvaluationRun.mockResolvedValue(evaluationRun)
  mockedGetEvaluationRun.mockResolvedValue({ ...evaluationRun, gold_revealed: true, cases: [{ ...evaluationRun.cases[0], gold_answer: 'B', correct: true }] })
})

describe('Stage 1 page contracts', () => {
  it('renders overview from backend data and has an empty state', async () => {
    renderPage(<OverviewPage />)
    expect(await screen.findByTestId('overview-page')).toBeInTheDocument()
    expect(screen.getByText('胃部观察题库')).toBeInTheDocument()
    expect(screen.getByText('0 / 10')).toBeInTheDocument()
  })

  it('renders bank search and routes to a selected bank', async () => {
    const user = userEvent.setup()
    renderPage(<BanksPage />)
    expect(await screen.findByTestId('banks-page')).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('搜索部位、题库名称…'), '食管')
    expect(screen.queryByText('胃部观察题库')).not.toBeInTheDocument()
    const card = screen.getByText('食管观察题库').closest('article')
    expect(card).not.toBeNull()
    expect(within(card as HTMLElement).getByRole('link', { name: /开始练习/ })).toHaveAttribute('href', '/practice?bank_id=bank-b')
  })

  it('supports all four discriminated question controls and typed submit payloads', async () => {
    const user = userEvent.setup()
    for (const question of questionVariants) {
      mockedGetQuestions.mockResolvedValueOnce(questionsResponse([question]))
      mockedSubmit.mockResolvedValueOnce(submitResult(question.id))
      const view = renderPage(<PracticePage />, ['/practice?bank_id=bank-a'])
      expect(await screen.findByTestId('practice-page')).toBeInTheDocument()

      if (question.question_type === 'single_choice') {
        await user.click(screen.getByRole('button', { name: /选项一/ }))
      } else if (question.question_type === 'multiple_choice') {
        await user.click(screen.getByRole('button', { name: /选项一/ }))
        await user.click(screen.getByRole('button', { name: /选项二/ }))
      } else if (question.question_type === 'true_false') {
        await user.click(screen.getByRole('button', { name: /正确/ }))
      } else {
        await user.type(screen.getByLabelText('你的回答'), '观察证据并保留医生复核边界')
      }
      await user.click(screen.getByTestId('submit-answer'))
      await screen.findByTestId('feedback')
      const payload = mockedSubmit.mock.calls.at(-1)?.[0]
      expect(payload?.question_id).toBe(question.id)
      if (question.question_type === 'multiple_choice') expect(Array.isArray(payload?.selected_answer)).toBe(true)
      if (question.question_type === 'true_false') expect(typeof payload?.selected_answer).toBe('boolean')
      if (question.question_type === 'short_answer') expect(typeof payload?.selected_answer).toBe('string')
      expect(JSON.stringify(payload)).not.toContain('correct_option_id')
      view.unmount()
    }
  })

  it('uses server session membership and shows the adaptive selection reason', async () => {
    const orderedQuestions: Question[] = questionVariants.map((question) => ({
      ...question,
      title: `题-${question.id}`,
      stem: `题干-${question.id}`,
    }))
    const sessionQuestions = [
      orderedQuestions.find((question) => question.id === 'short')!,
      orderedQuestions.find((question) => question.id === 'single')!,
    ]
    mockedGetQuestions.mockResolvedValue(questionsResponse(sessionQuestions))
    mockedCreateSession.mockResolvedValueOnce({
      session_id: 'session-adaptive',
      bank_id: 'bank-a',
      learner_id: 'demo_learner',
      mode: 'study',
      status: 'active',
      started_at: '2026-08-28T00:00:00Z',
      question_count: 2,
      question_ids: ['short', 'single'],
      selection_strategy: 'weak_topic',
      selection_reason: '优先巩固「胃」相关题目，再维持题库覆盖。',
      selection_evidence: ['「胃」当前掌握度 40.0%。'],
    })

    renderPage(<PracticePage />, ['/practice?bank_id=bank-a'])
    expect(await screen.findByTestId('session-recommendation')).toHaveAttribute('data-selection-strategy', 'weak_topic')
    expect(screen.getByText('优先巩固「胃」相关题目，再维持题库覆盖。')).toBeInTheDocument()
    expect(screen.getByText('题-short')).toBeInTheDocument()
    expect(mockedGetQuestions).toHaveBeenLastCalledWith({ bankId: 'bank-a', sessionId: 'session-adaptive' })
  })

  it('does not duplicate a server session under React StrictMode', async () => {
    renderStrictPage(<PracticePage />, ['/practice?bank_id=bank-a'])
    await screen.findByTestId('session-recommendation')
    expect(mockedCreateSession).toHaveBeenCalledTimes(1)
  })

  it('shows loading, error and no private answer fields in the browser UI', async () => {
    mockedGetOverview.mockReturnValueOnce(new Promise(() => undefined))
    renderPage(<OverviewPage />)
    expect(screen.getByRole('status')).toBeInTheDocument()

    mockedGetOverview.mockRejectedValueOnce(new Error('backend offline'))
    const errorView = renderPage(<OverviewPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('backend offline')
    expect(document.body.textContent).not.toContain('correct_option_id')
    errorView.unmount()
  })

  it('renders the evaluation not-run state without inventing metrics', async () => {
    renderPage(<EvaluationPage />, ['/eval'])
    expect(await screen.findByTestId('evaluation-page')).toBeInTheDocument()
    expect(screen.getByText('连接候选模型')).toBeInTheDocument()
    expect(screen.queryByText('100')).not.toBeInTheDocument()
  })

  it('runs a real-state BYOK evaluation and reveals gold only on explicit action', async () => {
    const user = userEvent.setup()
    renderPage(<EvaluationPage />, ['/eval'])
    await screen.findByTestId('evaluation-page')
    await user.type(screen.getByLabelText('连接地址'), 'https://provider.example/v1')
    await user.type(screen.getByLabelText('模型名称'), 'candidate-model')
    await user.type(screen.getByLabelText(/API Key/), 'secret-not-persisted')
    await user.click(screen.getByRole('button', { name: '测试连接' }))
    expect(await screen.findByText('模型连接成功')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '开始评测' }))
    expect(await screen.findByText('评测完成')).toBeInTheDocument()
    expect(screen.getByText('查看对照答案')).toBeInTheDocument()
    expect(screen.queryByText('Gold', { exact: true })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '查看对照答案' }))
    expect(await screen.findByText('参考答案已展示')).toBeInTheDocument()
    expect(screen.getAllByText('B', { exact: true })).toHaveLength(2)
    expect(mockedCreateEvaluationRun.mock.calls[0]?.[0].api_key).toBe('secret-not-persisted')
    expect(mockedGetEvaluationRun).toHaveBeenCalledWith('evalrun-test', true)
  })

  it('renders a continuous Tutor chat with real tool and source parts', async () => {
    const user = userEvent.setup()
    renderPage(<PracticePage />, ['/practice?bank_id=bank-a'])
    await screen.findByTestId('practice-page')
    await user.type(screen.getByLabelText('向 Tutor 提问'), '请帮助我观察')
    await user.click(screen.getByLabelText('发送给 Tutor'))
    expect(await screen.findByText('先观察可支持事实。')).toBeInTheDocument()
    expect(screen.getByTestId('tutor-sources')).toHaveTextContent('test source')
  })

  it('uses a full-width text-only question layout and hides importer provenance copy', async () => {
    mockedGetQuestions.mockResolvedValueOnce(questionsResponse([textOnlyQuestion]))
    renderPage(<PracticePage />, ['/practice?bank_id=bank-a'])
    expect(await screen.findByTestId('practice-page')).toBeInTheDocument()
    const questionCard = screen.getByTestId('question-card')
    expect(questionCard).toHaveClass('text-only')
    expect(questionCard).toHaveAttribute('data-question-layout', 'text-only')
    expect(screen.queryByText('来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。')).not.toBeInTheDocument()
    expect(screen.queryByTestId('question-card')?.querySelector('.s1-question-image')).toBeNull()
  })
})

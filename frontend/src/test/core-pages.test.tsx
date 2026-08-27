import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getLatestEvaluation, getOverview, getQuestionBanks, getQuestions, getTutorHint, submitPracticeAnswer } from '../api/client'
import type { Overview, Question, QuestionBank, QuestionsResponse, SubmitResult } from '../api/client'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'

vi.mock('../api/client', () => ({
  getLatestEvaluation: vi.fn(),
  getOverview: vi.fn(),
  getQuestionBanks: vi.fn(),
  getQuestions: vi.fn(),
  getTutorHint: vi.fn(),
  submitPracticeAnswer: vi.fn(),
}))

const mockedGetOverview = vi.mocked(getOverview)
const mockedGetQuestionBanks = vi.mocked(getQuestionBanks)
const mockedGetQuestions = vi.mocked(getQuestions)
const mockedSubmit = vi.mocked(submitPracticeAnswer)
const mockedHint = vi.mocked(getTutorHint)
const mockedEvaluation = vi.mocked(getLatestEvaluation)

const safety = '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'
const baseQuestion = { id: 'q-1', bank_id: 'bank-a', domain_id: 'endoscopy', title: '胃部观察练习', stem: '请根据当前证据选择答案。', case_summary: '稳定的测试病例摘要。', modality: 'image' as const, image_url: '/assets/real_samples/endo_image_0.jpg', image_alt: '测试内镜图像', difficulty: 'easy' as const, tags: ['胃'], body_part: '胃', source_dataset: 'test', citation_note: 'test seed', doctor_review_required: true, safety_notice: safety }
const questionVariants: Question[] = [
  { ...baseQuestion, id: 'single', question_type: 'single_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'multi', question_type: 'multiple_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'judge', question_type: 'true_false' },
  { ...baseQuestion, id: 'short', question_type: 'short_answer' },
]
const banks: QuestionBank[] = [
  { bank_id: 'bank-a', domain_id: 'endoscopy', name: '胃部观察题库', description: '胃部位与可见事实训练。', version: 'test-v1', status: 'published', question_count: 4, question_type_counts: { single_choice: 1, multiple_choice: 1, true_false: 1, short_answer: 1 }, modality_counts: { image: 4 }, body_parts: ['胃'], completed_count: 0, progress: 0 },
  { bank_id: 'bank-b', domain_id: 'endoscopy', name: '食管观察题库', description: '食管观察与表达训练。', version: 'test-v1', status: 'published', question_count: 2, question_type_counts: { single_choice: 2 }, modality_counts: { text: 2 }, body_parts: ['食管'], completed_count: 0, progress: 0 },
]
const overview: Overview = { learner_id: 'demo_learner', completed_today: 0, daily_target: 10, due_review_count: 0, recent_accuracy: 0, recent_sessions: [], banks, weak_areas: [], safety_notice: safety, api_source: 'backend' }

function questionsResponse(items: Question[]): QuestionsResponse {
  return { items, total: items.length, available_type_counts: {}, bank_id: 'bank-a', safety_notice: safety, api_source: 'backend' }
}

function submitResult(questionId: string): SubmitResult {
  return { attempt_id: 'attempt-test', question_id: questionId, session_id: 'session-test', learner_id: 'demo_learner', is_correct: true, score: 100, error_tags: [], fact_feedback: [], explanation: '已按确定性规则记录。', next_recommendation: '可以继续下一题。', profile_updated: true, doctor_review_required: true, safety_notice: safety, created_at: '2026-08-28T00:00:00Z' }
}

function renderPage(ui: React.ReactNode, initialEntries = ['/']) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGetOverview.mockResolvedValue(overview)
  mockedGetQuestionBanks.mockResolvedValue(banks)
  mockedGetQuestions.mockResolvedValue(questionsResponse(questionVariants))
  mockedSubmit.mockResolvedValue(submitResult('single'))
  mockedHint.mockResolvedValue({ message: '先观察可支持事实。', mode: 'rule', sources: ['test'], event: 'rule_hint', doctor_review_required: true, safety_notice: safety })
  mockedEvaluation.mockResolvedValue({ artifact_available: false, artifact_path: null, mode: 'not_run', sample_count: 0, metrics: {}, cases: [], notice: '尚未运行', safety_notice: safety })
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
    expect(screen.getAllByText('尚未运行').length).toBeGreaterThan(0)
    expect(screen.queryByText('100')).not.toBeInTheDocument()
  })

  it('keeps tutor in rule mode and visible through an explicit action', async () => {
    const user = userEvent.setup()
    renderPage(<PracticePage />, ['/practice?bank_id=bank-a'])
    await screen.findByTestId('practice-page')
    await user.click(screen.getByTestId('tutor-hint'))
    expect(await screen.findByText('先观察可支持事实。')).toBeInTheDocument()
    expect(screen.getAllByText(/Stage 2 Agent 未启用/).length).toBeGreaterThan(0)
  })
})

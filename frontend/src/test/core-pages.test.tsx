import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { clearLearningMemory, createEvaluationRun, createMentorConversation, createPracticeSession, createReviewSession, deleteKnowledgeSource, deleteMentorConversation, getDomains, getEvaluationDatasets, getEvaluationRun, getKnowledgeSource, getKnowledgeSources, getLatestEvaluation, getLearningMemory, getMentorConversation, getMentorPlan, getOverview, getPracticeSession, getQuestionBanks, getQuestions, getResumablePracticeSession, getReviewItem, getReviewItems, getReviewSummary, leavePracticeSession, listMentorConversations, reindexKnowledgeSource, resumePracticeSession, setKnowledgeSourceEnabled, streamMentorMessage, streamTutor, submitFsrsReview, submitPracticeAnswer, testEvaluationConnection, uploadKnowledgeSource } from '../api/client'
import type { EvaluationRun, Overview, Question, QuestionBank, QuestionsResponse, SubmitResult } from '../api/client'
import { OverviewPage } from '../pages/overview/OverviewPage'
import { BanksPage } from '../pages/banks/BanksPage'
import { PracticePage } from '../pages/practice/PracticePage'
import { EvaluationPage } from '../pages/evaluation/EvaluationPage'
import { MentorPage } from '../pages/mentor/MentorPage'
import { KnowledgePage } from '../pages/knowledge/KnowledgePage'
import { ReviewPage } from '../pages/review/ReviewPage'

vi.mock('../api/client', () => ({
  createMentorConversation: vi.fn(),
  createPracticeSession: vi.fn(),
  createReviewSession: vi.fn(),
  deleteKnowledgeSource: vi.fn(),
  deleteMentorConversation: vi.fn(),
  getMentorConversation: vi.fn(),
  getDomains: vi.fn(),
  clearLearningMemory: vi.fn(),
  createEvaluationRun: vi.fn(),
  getEvaluationDatasets: vi.fn(),
  getEvaluationRun: vi.fn(),
  getKnowledgeSource: vi.fn(),
  getKnowledgeSources: vi.fn(),
  getLatestEvaluation: vi.fn(),
  getLearningMemory: vi.fn(),
  getOverview: vi.fn(),
  getPracticeSession: vi.fn(),
  getQuestionBanks: vi.fn(),
  getQuestions: vi.fn(),
  getResumablePracticeSession: vi.fn(),
  getReviewItem: vi.fn(),
  getReviewItems: vi.fn(),
  getReviewSummary: vi.fn(),
  listMentorConversations: vi.fn(),
  leavePracticeSession: vi.fn(),
  reindexKnowledgeSource: vi.fn(),
  resumePracticeSession: vi.fn(),
  setKnowledgeSourceEnabled: vi.fn(),
  getMentorPlan: vi.fn(),
  streamTutor: vi.fn(),
  streamMentorMessage: vi.fn(),
  submitFsrsReview: vi.fn(),
  submitPracticeAnswer: vi.fn(),
  testEvaluationConnection: vi.fn(),
  uploadKnowledgeSource: vi.fn(),
}))

const mockedGetOverview = vi.mocked(getOverview)
const mockedCreateMentorConversation = vi.mocked(createMentorConversation)
const mockedGetMentorConversation = vi.mocked(getMentorConversation)
const mockedGetKnowledgeSources = vi.mocked(getKnowledgeSources)
const mockedGetKnowledgeSource = vi.mocked(getKnowledgeSource)
const mockedUploadKnowledgeSource = vi.mocked(uploadKnowledgeSource)
const mockedSetKnowledgeSourceEnabled = vi.mocked(setKnowledgeSourceEnabled)
const mockedReindexKnowledgeSource = vi.mocked(reindexKnowledgeSource)
const mockedDeleteKnowledgeSource = vi.mocked(deleteKnowledgeSource)
const mockedDeleteMentorConversation = vi.mocked(deleteMentorConversation)
const mockedListMentorConversations = vi.mocked(listMentorConversations)
const mockedStreamMentorMessage = vi.mocked(streamMentorMessage)
const mockedGetLearningMemory = vi.mocked(getLearningMemory)
const mockedClearLearningMemory = vi.mocked(clearLearningMemory)
const mockedCreateSession = vi.mocked(createPracticeSession)
const mockedCreateReviewSession = vi.mocked(createReviewSession)
const mockedGetPracticeSession = vi.mocked(getPracticeSession)
const mockedGetQuestionBanks = vi.mocked(getQuestionBanks)
const mockedGetQuestions = vi.mocked(getQuestions)
const mockedGetResumablePracticeSession = vi.mocked(getResumablePracticeSession)
const mockedResumePracticeSession = vi.mocked(resumePracticeSession)
const mockedGetReviewSummary = vi.mocked(getReviewSummary)
const mockedGetReviewItems = vi.mocked(getReviewItems)
const mockedGetReviewItem = vi.mocked(getReviewItem)
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
const v32KnowledgeIndex = { index_version: 1, index_progress: 100, index_stage: '完成', index_job_id: null, index_error: null }
const v32SessionState = { current_position: 0, reflection_status: 'clean', tutor_thread_id: 'tutor-thread-test' }
const practicePath = '/practice?session_id=session-test&tutor_thread_id=tutor-thread-test'
const baseQuestion = { id: 'q-1', bank_id: 'bank-a', domain_id: 'endoscopy', title: '胃部观察练习', stem: '请根据当前证据选择答案。', case_summary: '稳定的测试病例摘要。', modality: 'image' as const, image_url: '/assets/real_samples/endo_image_0.jpg', image_alt: '测试内镜图像', difficulty: 'easy' as const, tags: ['胃'], body_part: '胃', source_dataset: 'test', citation_note: 'test seed', doctor_review_required: true, safety_notice: safety, business_usage: 'user_ready' as const, official_explanation_available: true }
const questionVariants: Question[] = [
  { ...baseQuestion, id: 'single', question_type: 'single_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'multi', question_type: 'multiple_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] },
  { ...baseQuestion, id: 'judge', question_type: 'true_false' },
  { ...baseQuestion, id: 'short', question_type: 'short_answer' },
]
const textOnlyQuestion: Question = { ...baseQuestion, id: 'text-only', modality: 'text', image_url: null, image_alt: null, case_summary: '来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。', question_type: 'single_choice', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }] }
const banks: QuestionBank[] = [
  { bank_id: 'bank-a', domain_id: 'endoscopy', name: '胃部观察题库', description: '胃部位与可见事实训练。', version: 'test-v1', status: 'published', question_count: 4, question_type_counts: { single_choice: 1, multiple_choice: 1, true_false: 1, short_answer: 1 }, modality_counts: { image: 4 }, body_parts: ['胃'], completed_count: 0, uncompleted_count: 4, incorrect_count: 0, marked_count: 0, progress: 0 },
  { bank_id: 'bank-b', domain_id: 'endoscopy', name: '食管观察题库', description: '食管观察与表达训练。', version: 'test-v1', status: 'published', question_count: 2, question_type_counts: { single_choice: 2 }, modality_counts: { text: 2 }, body_parts: ['食管'], completed_count: 0, uncompleted_count: 2, incorrect_count: 0, marked_count: 0, progress: 0 },
]
const overview: Overview = { learner_id: 'demo_learner', completed_today: 0, daily_target: 10, due_review_count: 0, recent_accuracy: 0, recent_bank_activity: [], banks, weak_areas: [], safety_notice: safety, api_source: 'backend' }

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

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location-probe">{`${location.pathname}${location.search}`}</output>
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedGetOverview.mockResolvedValue(overview)
  mockedGetResumablePracticeSession.mockResolvedValue(null)
  mockedResumePracticeSession.mockResolvedValue({ tutor_thread_id: 'tutor-thread-resumed', practice_session_id: 'session-test', status: 'active' })
  vi.mocked(leavePracticeSession).mockResolvedValue(undefined)
  mockedListMentorConversations.mockResolvedValue([])
  mockedGetKnowledgeSources.mockResolvedValue([{ id: 'source-cmexam', title: 'CMExam 官方解析库', file_name: 'cmexam.md', scope: 'qbank_explanations', status: 'ready', enabled: true, media_type: 'text/markdown', chunk_count: 190, size_bytes: 1000, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', ...v32KnowledgeIndex }])
  mockedGetKnowledgeSource.mockResolvedValue({ id: 'source-cmexam', title: 'CMExam 官方解析库', file_name: 'cmexam.md', scope: 'qbank_explanations', status: 'ready', enabled: true, media_type: 'text/markdown', chunk_count: 190, size_bytes: 1000, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', ...v32KnowledgeIndex, preview: [] })
  mockedUploadKnowledgeSource.mockResolvedValue({ id: 'source-user', title: '学习资料', file_name: 'note.md', scope: 'user', status: 'ready', enabled: true, media_type: 'text/markdown', chunk_count: 1, size_bytes: 10, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', ...v32KnowledgeIndex, preview: [] })
  mockedSetKnowledgeSourceEnabled.mockResolvedValue({ id: 'source-cmexam', title: 'CMExam 官方解析库', file_name: 'cmexam.md', scope: 'qbank_explanations', status: 'ready', enabled: true, media_type: 'text/markdown', chunk_count: 190, size_bytes: 1000, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', ...v32KnowledgeIndex, preview: [] })
  mockedReindexKnowledgeSource.mockResolvedValue({ id: 'source-cmexam', title: 'CMExam 官方解析库', file_name: 'cmexam.md', scope: 'qbank_explanations', status: 'ready', enabled: true, media_type: 'text/markdown', chunk_count: 190, size_bytes: 1000, created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', ...v32KnowledgeIndex, preview: [] })
  mockedDeleteKnowledgeSource.mockResolvedValue({ status: 'deleted', api_source: 'backend' })
  mockedDeleteMentorConversation.mockResolvedValue({ conversation_id: 'mentor-test', deleted: true })
  mockedCreateMentorConversation.mockResolvedValue({ id: 'mentor-test', title: '新的带教对话', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', messages: [] })
  mockedGetMentorConversation.mockResolvedValue({ id: 'mentor-test', title: '今日复习', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', messages: [] })
  mockedStreamMentorMessage.mockImplementation(async (_id, _message, onEvent) => {
    onEvent({ event: 'activity', data: { label: '已读取复习队列', status: 'completed' } })
    onEvent({ event: 'token', data: { text: '先处理 2 道到期复习，再完成一组短练习。' } })
  })
  vi.mocked(getDomains).mockResolvedValue([
    { domain_id: 'endoscopy', display_name: '医疗 / 消化内镜', description: 'medical', subjects: ['内镜图像观察'], supported_question_types: ['single_choice', 'multiple_choice', 'true_false', 'short_answer'] },
    { domain_id: 'general_science', display_name: '通用科学', description: 'science', subjects: ['物理'], supported_question_types: ['single_choice', 'multiple_choice', 'true_false'] },
  ])
  mockedGetLearningMemory.mockResolvedValue({ learner_id: 'demo_learner', items: [], api_source: 'backend' })
  mockedClearLearningMemory.mockResolvedValue({ learner_id: 'demo_learner', superseded_count: 0, preserved_attempt_history: true, preserved_review_history: true, api_source: 'backend' })
  mockedGetQuestionBanks.mockResolvedValue(banks)
  mockedGetQuestions.mockResolvedValue(questionsResponse(questionVariants))
  mockedCreateSession.mockResolvedValue({ session_id: 'session-test', bank_id: 'bank-a', domain_id: 'endoscopy', learner_id: 'demo_learner', mode: 'study', status: 'active', started_at: '2026-08-28T00:00:00Z', ...v32SessionState, question_count: 20, question_ids: [], selection_strategy: 'coverage', selection_reason: '本次按未练题与题库覆盖安排练习。', selection_evidence: ['优先安排未练题。'] })
  mockedCreateReviewSession.mockResolvedValue({ session_id: 'session-review', bank_id: 'bank-a', domain_id: 'endoscopy', learner_id: 'demo_learner', mode: 'review', status: 'active', started_at: '2026-08-28T00:00:00Z', ...v32SessionState, question_count: 1, question_ids: ['single'], selection_strategy: 'due_review', selection_reason: '复习队列', selection_evidence: [] })
  mockedGetPracticeSession.mockResolvedValue({ session_id: 'session-test', bank_id: 'bank-a', domain_id: 'endoscopy', learner_id: 'demo_learner', mode: 'study', status: 'active', started_at: '2026-08-28T00:00:00Z', ...v32SessionState, question_count: 20, question_ids: [], selection_strategy: 'coverage', selection_reason: '本次按未练题与题库覆盖安排练习。', selection_evidence: ['优先安排未练题。'], items: [] })
  mockedSubmit.mockResolvedValue(submitResult('single'))
  mockedMentor.mockResolvedValue({ learner_id: 'demo_learner', domain_id: 'endoscopy', study_goal: '复盘', due_review_count: 1, focus: '胃', weak_areas: ['胃'], recent_errors: [], steps: [{ kind: 'review', title: '完成复习', question_ids: [] }] })
  mockedReview.mockResolvedValue({ review_card_id: 'review-test', question_id: 'single', domain_id: 'endoscopy', due_at: '2026-08-29T00:00:00Z', interval_days: 1, difficulty: 2, stability: 1, retrievability: .9, state: 'Learning', review_count: 1 })
  mockedGetReviewSummary.mockResolvedValue({ due_count: 1, incorrect_count: 1, marked_count: 1 })
  mockedGetReviewItems.mockResolvedValue({ tab: 'due', total: 1, items: [{ question_id: 'single', bank_id: 'bank-a', bank_name: '胃部观察题库', question_summary: '请根据当前证据选择答案。', question_type: 'single_choice', completed: true, incorrect: true, marked: true, attempt_count: 1, wrong_count: 1, due_at: '2026-08-29T00:00:00Z', last_selected_answer: 'opt_02', official_explanation_available: true }] })
  mockedGetReviewItem.mockResolvedValue({ question_id: 'single', bank_id: 'bank-a', bank_name: '胃部观察题库', question_summary: '请根据当前证据选择答案。', question_type: 'single_choice', completed: true, incorrect: true, marked: true, attempt_count: 1, wrong_count: 1, due_at: '2026-08-29T00:00:00Z', last_selected_answer: 'opt_02', official_explanation_available: true, stem: '请根据当前证据选择答案。', options: [{ id: 'opt_01', text: '选项一' }, { id: 'opt_02', text: '选项二' }], correct_answer_display: '选项一', explanation: '题库提供的真实解析。', recent_attempts: [] })
  mockedStreamTutor.mockImplementation(async (_request, onEvent) => {
    onEvent({ event: 'message_start', data: { run_id: 'run-test', provider_real: true } })
    onEvent({ event: 'tool_start', data: { tool_name: 'get_question_context' } })
    onEvent({ event: 'tool_end', data: { tool_name: 'get_question_context' } })
    onEvent({ event: 'source', data: { document_name: 'test source', page: '1', section: '观察要点' } })
    onEvent({ event: 'reasoning', data: { summary: ['识别学习目标', '对照可见证据'] } })
    onEvent({ event: 'token', data: { text: '先观察可支持事实。' } })
    onEvent({ event: 'message_end', data: { run_id: 'run-test' } })
  })
  mockedEvaluation.mockResolvedValue({ artifact_available: false, artifact_path: null, mode: 'not_run', sample_count: 0, metrics: {}, cases: [], probes: [], strategy_comparison: [], notice: '尚未运行', safety_notice: safety })
  mockedEvaluationDatasets.mockResolvedValue([{ dataset_id: 'cmexam-text-eval-v1', domain_id: 'endoscopy', name: 'CMExam 文本评测', description: '冻结评测集', source_dataset: 'CMExam', modality: 'text', version: 'cmexam-text-eval-v1', dataset_hash: 'hash', sample_count: 5, supports_vision: false, tutor_indexed: false }])
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
    expect(screen.getByText('0 题')).toBeInTheDocument()
    expect(screen.queryByText('0 / 10')).not.toBeInTheDocument()
  })

  it('renders recent practice as one row per bank with progress and resume state', async () => {
    mockedGetOverview.mockResolvedValueOnce({
      ...overview,
      recent_bank_activity: [{ bank_id: 'bank-a', bank_name: '胃部观察题库', bank_question_count: 4, bank_completed_count: 1, bank_progress: .25, last_session_id: 'session-test', last_session_status: 'active', last_session_mode: 'study', session_question_count: 2, session_answered_count: 1, next_question_ordinal: 2, last_active_at: '2026-08-28T00:00:00Z', resumable: true }],
    })

    renderPage(<OverviewPage />)
    const activity = (await screen.findByRole('heading', { name: '最近练习' })).closest('section')
    expect(activity).not.toBeNull()
    expect(within(activity as HTMLElement).getByText('胃部观察题库')).toBeInTheDocument()
    expect(within(activity as HTMLElement).getByText('上次练习：第 2 / 2 题')).toBeInTheDocument()
    expect(within(activity as HTMLElement).getByText(/题库进度 1 \/ 4/)).toBeInTheDocument()
    expect(within(activity as HTMLElement).getByText('继续练习')).toBeInTheDocument()
  })

  it('shows backend-derived weak areas without exposing a memory management panel', async () => {
    mockedGetOverview.mockResolvedValueOnce({ ...overview, weak_areas: ['食管'] })
    renderPage(<OverviewPage />)
    expect(await screen.findByText('食管')).toBeInTheDocument()
    expect(screen.getByText('近期薄弱主题')).toBeInTheDocument()
    expect(screen.queryByTestId('learning-memory-panel')).not.toBeInTheDocument()
    expect(mockedClearLearningMemory).not.toHaveBeenCalled()
  })

  it('opens a session builder from a filtered bank and routes with its selected session settings', async () => {
    const user = userEvent.setup()
    renderPage(<><BanksPage /><LocationProbe /></>)
    expect(await screen.findByTestId('banks-page')).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('搜索题库…'), '食管')
    expect(screen.queryByText('胃部观察题库')).not.toBeInTheDocument()
    const card = screen.getByText('食管观察题库').closest('article')
    expect(card).not.toBeNull()
    await user.click(within(card as HTMLElement).getByRole('button', { name: '开始刷题' }))
    expect(screen.getByRole('dialog', { name: '食管观察题库' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /考试/ }))
    await user.click(screen.getByRole('button', { name: '自定义' }))
    await user.type(screen.getByLabelText('自定义题量'), '37')
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '开始练习' }))
    expect(await screen.findByTestId('location-probe')).toHaveTextContent('/practice?bank_id=bank-b&count=37&mode=exam&session_id=session-test&tutor_thread_id=tutor-thread-test')
  })

  it('supports all four discriminated question controls and typed submit payloads', async () => {
    const user = userEvent.setup()
    for (const question of questionVariants) {
      mockedGetQuestions.mockResolvedValueOnce(questionsResponse([question]))
      mockedSubmit.mockResolvedValueOnce(submitResult(question.id))
      const view = renderPage(<PracticePage />, [practicePath])
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

  it('uses server session membership while keeping selection rationale out of the practice workspace', async () => {
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
    mockedGetPracticeSession.mockResolvedValueOnce({
      session_id: 'session-adaptive',
      bank_id: 'bank-a',
      domain_id: 'endoscopy',
      learner_id: 'demo_learner',
      mode: 'study',
      status: 'active',
      started_at: '2026-08-28T00:00:00Z',
      ...v32SessionState,
      question_count: 2,
      question_ids: ['short', 'single'],
      selection_strategy: 'weak_topic',
      selection_reason: '优先巩固「胃」相关题目，再维持题库覆盖。',
      selection_evidence: ['「胃」当前掌握度 40.0%。'],
    })

    renderPage(<PracticePage />, ['/practice?session_id=session-adaptive&tutor_thread_id=tutor-thread-test'])
    await screen.findByTestId('question-card')
    expect(screen.getByText('题干-short')).toBeInTheDocument()
    expect(screen.queryByText('本次按未练题与题库覆盖安排练习。')).not.toBeInTheDocument()
    expect(screen.queryByText('优先巩固「胃」相关题目，再维持题库覆盖。')).not.toBeInTheDocument()
    expect(screen.queryByTestId('session-recommendation')).not.toBeInTheDocument()
    expect(mockedGetQuestions).toHaveBeenLastCalledWith({ bankId: 'bank-a', sessionId: 'session-adaptive' })
  })

  it('does not create a new server session under React StrictMode', async () => {
    renderStrictPage(<PracticePage />, [practicePath])
    await screen.findByTestId('question-card')
    expect(mockedCreateSession).not.toHaveBeenCalled()
  })

  it('uses page lifecycle events only as a best-effort practice checkpoint', async () => {
    const view = renderPage(<PracticePage />, [practicePath])
    await screen.findByTestId('practice-page')

    fireEvent(window, new Event('pagehide'))
    expect(leavePracticeSession).toHaveBeenCalledWith('session-test')

    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    fireEvent(document, new Event('visibilitychange'))
    expect(leavePracticeSession).toHaveBeenCalledTimes(2)
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
    view.unmount()
  })

  it('abandons a resumable session without treating the valid 204 response as an error', async () => {
    const user = userEvent.setup()
    mockedGetResumablePracticeSession.mockResolvedValueOnce({ session_id: 'session-resume', bank_id: 'bank-a', mode: 'study', current_position: 4, last_active_at: '2026-09-03T00:00:00Z' })
    renderPage(<><PracticePage /><LocationProbe /></>, ['/practice'])
    expect(await screen.findByRole('dialog', { name: '继续上次练习' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新选择题库' }))
    expect(await screen.findByText('/banks')).toBeInTheDocument()
    expect(leavePracticeSession).toHaveBeenCalledWith('session-resume', 'demo_learner', true)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('opens a lightweight question map and navigates by real question position', async () => {
    const user = userEvent.setup()
    mockedGetQuestions.mockResolvedValueOnce(questionsResponse(questionVariants.slice(0, 2)))
    renderPage(<PracticePage />, [practicePath])
    await screen.findByTestId('practice-page')
    await user.click(screen.getByRole('button', { name: '题单' }))
    expect(screen.getByRole('region', { name: '题单' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /第 2 题，未作答/ }))
    expect(screen.getByText('请根据当前证据选择答案。')).toBeInTheDocument()
  })

  it('resumes at the first unanswered item and keeps position and completion semantics separate', async () => {
    mockedGetQuestions.mockResolvedValueOnce(questionsResponse(questionVariants.slice(0, 3)))
    mockedGetPracticeSession.mockResolvedValueOnce({
      session_id: 'session-resumed', bank_id: 'bank-a', domain_id: 'endoscopy', learner_id: 'demo_learner', mode: 'study', status: 'active', started_at: '2026-08-28T00:00:00Z', ...v32SessionState, question_count: 3, question_ids: ['single', 'multi', 'judge'], selection_strategy: 'coverage', selection_reason: '服务端会话。', selection_evidence: [],
      items: [{ question_id: 'single', ordinal: 0, state: 'correct' }, { question_id: 'multi', ordinal: 1, state: 'incorrect' }, { question_id: 'judge', ordinal: 2, state: 'unanswered' }],
    })

    renderPage(<PracticePage />, ['/practice?session_id=session-resumed'])
    expect(await screen.findByText('第 3 / 3 题')).toBeInTheDocument()
    expect(screen.getByLabelText('已完成 2 / 3，67%')).toBeInTheDocument()
  })

  it('uses an honest missing-explanation state without adding an AI grading fallback', async () => {
    const user = userEvent.setup()
    mockedGetQuestions.mockResolvedValueOnce(questionsResponse([questionVariants[0]]))
    mockedSubmit.mockResolvedValueOnce({ ...submitResult('single'), official_explanation_available: false, explanation: '' })
    renderPage(<PracticePage />, [practicePath])
    await screen.findByTestId('practice-page')
    await user.click(screen.getByRole('button', { name: /选项一/ }))
    await user.click(screen.getByTestId('submit-answer'))
    expect(await screen.findByText('暂无解析')).toBeInTheDocument()
    expect(screen.queryByText('已按确定性规则记录。')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '让智能辅导讲解' })).not.toBeInTheDocument()
    expect(screen.getByTestId('tutor-sidecar')).toHaveClass('is-open')
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

  it('keeps the knowledge workspace visible during a source-list load or error', async () => {
    mockedGetKnowledgeSources.mockReturnValueOnce(new Promise(() => undefined))
    const pendingView = renderPage(<KnowledgePage />, ['/knowledge'])
    expect(screen.getByTestId('knowledge-page')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '知识库' })).toBeInTheDocument()
    expect(screen.getByRole('status', { name: '正在读取知识库' })).toBeInTheDocument()
    pendingView.unmount()

    mockedGetKnowledgeSources.mockRejectedValueOnce(new Error('知识服务不可用'))
    renderPage(<KnowledgePage />, ['/knowledge'])
    expect(await screen.findByRole('alert')).toHaveTextContent('知识服务不可用')
    expect(screen.getByRole('heading', { name: '知识库' })).toBeInTheDocument()
  })

  it('keeps review navigation visible while only the active list and detail are loading', async () => {
    const user = userEvent.setup()
    let resolveWrong: ((value: { tab: string; total: number; items: Array<Record<string, unknown>> }) => void) | undefined
    const wrongItems = new Promise<{ tab: string; total: number; items: Array<Record<string, unknown>> }>((resolve) => { resolveWrong = resolve })
    mockedGetReviewItems.mockImplementation((tab) => tab === 'wrong'
      ? wrongItems as ReturnType<typeof getReviewItems>
      : Promise.resolve({ tab: 'due', total: 1, items: [{ question_id: 'single', bank_id: 'bank-a', bank_name: '胃部观察题库', question_summary: '请根据当前证据选择答案。', question_type: 'single_choice', completed: true, incorrect: true, marked: true, attempt_count: 1, wrong_count: 1, due_at: '2026-08-29T00:00:00Z', last_selected_answer: 'opt_02', official_explanation_available: true }] }))
    renderPage(<ReviewPage />, ['/review'])
    expect(await screen.findByTestId('review-page')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '待复习' })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '错题' }))
    expect(screen.getByRole('status', { name: '正在读取复习列表' })).toBeInTheDocument()
    expect(screen.queryByText('正在读取复习队列…')).not.toBeInTheDocument()
    resolveWrong?.({ tab: 'wrong', total: 0, items: [] })
    expect(await screen.findByText('当前没有可复习的题目')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '错题与复习' })).toBeInTheDocument()
  })

  it('renders the evaluation not-run state without inventing metrics', async () => {
    renderPage(<EvaluationPage />, ['/eval'])
    expect(await screen.findByTestId('evaluation-page')).toBeInTheDocument()
    expect(screen.getByText('新建评测')).toBeInTheDocument()
    expect(screen.getByText('5 道题 · 文本输入 · 冻结评测集')).toBeInTheDocument()
    expect(screen.getByText('本次抽样题量')).toBeInTheDocument()
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
    expect(screen.getByText('B', { exact: true })).toBeInTheDocument()
    expect(mockedCreateEvaluationRun.mock.calls[0]?.[0].api_key).toBe('secret-not-persisted')
    expect(mockedGetEvaluationRun).toHaveBeenCalledWith('evalrun-test', true)
  })

  it('renders a continuous Tutor chat with real tool and source parts', async () => {
    const user = userEvent.setup()
    renderPage(<PracticePage />, [practicePath])
    await screen.findByTestId('practice-page')
    await user.type(screen.getByLabelText('向智能辅导提问'), '请帮助我观察')
    await user.click(screen.getByLabelText('发送给智能辅导'))
    expect(await screen.findByText('先观察可支持事实。')).toBeInTheDocument()
    expect(screen.getByTestId('tutor-sources')).toHaveTextContent('test source')
  })

  it('creates a persistent Mentor conversation and renders real activity output', async () => {
    const user = userEvent.setup()
    renderPage(<MentorPage />, ['/mentor'])
    expect(await screen.findByTestId('mentor-page')).toBeInTheDocument()
    expect(await screen.findByText('CMExam 官方解析库')).toBeInTheDocument()
    await user.type(screen.getByLabelText('向带教 Agent 提问'), '我今天应该先复习什么？')
    await user.click(screen.getByLabelText('发送给带教 Agent'))
    expect(await screen.findByText('先处理 2 道到期复习，再完成一组短练习。')).toBeInTheDocument()
    expect(screen.getByText('已读取复习队列')).toBeInTheDocument()
    expect(mockedCreateMentorConversation).toHaveBeenCalledTimes(1)
    expect(mockedStreamMentorMessage).toHaveBeenCalledWith('mentor-test', '我今天应该先复习什么？', expect.any(Function), expect.any(AbortSignal))
  })

  it('offers a right-click delete action for a Mentor conversation and refreshes its history', async () => {
    const user = userEvent.setup()
    mockedListMentorConversations.mockResolvedValueOnce([{ id: 'mentor-test', title: '待删除对话', created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z', messages: [] }])
    renderPage(<MentorPage />, ['/mentor'])
    const item = await screen.findByTitle('右键删除对话')
    fireEvent.contextMenu(item, { clientX: 120, clientY: 160 })
    await user.click(screen.getByRole('menuitem', { name: '删除对话' }))
    expect(await screen.findByRole('dialog', { name: /删除这段对话/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '删除对话' }))
    expect(mockedDeleteMentorConversation).toHaveBeenCalledWith('mentor-test')
  })

  it('deduplicates repeated citations and keeps extra sources collapsed by default', async () => {
    const user = userEvent.setup()
    mockedStreamTutor.mockImplementationOnce(async (_request, onEvent) => {
      onEvent({ event: 'source', data: { document_name: '资料 A', section: '第一节', snippet: '相同资料' } })
      onEvent({ event: 'source', data: { document_name: '资料 A', section: '第一节', snippet: '相同资料（重复）' } })
      onEvent({ event: 'source', data: { document_name: '资料 B', section: '第二节', snippet: '第二条资料' } })
      onEvent({ event: 'source', data: { document_name: '资料 C', section: '第三节', snippet: '第三条资料' } })
      onEvent({ event: 'token', data: { text: '已结合资料说明。' } })
    })
    renderPage(<PracticePage />, [practicePath])
    await screen.findByTestId('practice-page')
    await user.type(screen.getByLabelText('向智能辅导提问'), '请解释')
    await user.click(screen.getByLabelText('发送给智能辅导'))
    expect(await screen.findByText('参考资料 3 条')).toBeInTheDocument()
    expect(screen.getByText(/资料 A/)).toBeInTheDocument()
    expect(screen.getByText(/资料 B/)).toBeInTheDocument()
    expect(screen.queryByText(/资料 C/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '查看全部 3 条' }))
    expect(screen.getByText(/资料 C/)).toBeInTheDocument()
  })

  it('uses a full-width text-only question layout and hides importer provenance copy', async () => {
    mockedGetQuestions.mockResolvedValueOnce(questionsResponse([textOnlyQuestion]))
    renderPage(<PracticePage />, [practicePath])
    expect(await screen.findByTestId('practice-page')).toBeInTheDocument()
    const questionCard = screen.getByTestId('question-card')
    expect(questionCard).toHaveClass('is-text-only')
    expect(questionCard).toHaveAttribute('data-question-layout', 'text-only')
    expect(screen.queryByText('来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。')).not.toBeInTheDocument()
    expect(screen.queryByTestId('question-card')?.querySelector('.practice-question-image')).toBeNull()
  })
})

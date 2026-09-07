import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getBankQuestionProgress, getQuestionBanks } from '../api/client'
import { BankDetailPage } from '../pages/banks/BankDetailPage'

vi.mock('../api/client', () => ({
  createPracticeSession: vi.fn(),
  getBankQuestionProgress: vi.fn(),
  getQuestionBanks: vi.fn(),
  getQuestionForEdit: vi.fn(),
  updateQuestion: vi.fn(),
}))

const bank = {
  bank_id: 'bank-search', domain_id: 'general_science', name: '搜索回归题库', description: '用于搜索回归。',
  version: 'test-v1', status: 'published', question_count: 2, question_type_counts: { single_choice: 2 },
  modality_counts: { text: 2 }, body_parts: ['通用'], completed_count: 0, uncompleted_count: 2,
  incorrect_count: 0, marked_count: 0, progress: 0,
}

const allQuestions = {
  bank_id: bank.bank_id, state: 'all', total: 2, api_source: 'backend',
  items: [
    { question_id: 'q-rag', question_type: 'single_choice', question_summary: 'RAG 检索会先查找相关资料。', subject: null, topic: null, completed: false, incorrect: false, marked: false, attempt_count: 0, last_result: null, last_attempt_at: null },
    { question_id: 'q-agent', question_type: 'single_choice', question_summary: 'Agent 可以调用受控工具。', subject: null, topic: null, completed: false, incorrect: false, marked: false, attempt_count: 0, last_result: null, last_attempt_at: null },
  ],
}

const searchQuestions = {
  bank_id: bank.bank_id, state: 'all', total: 1, api_source: 'backend',
  items: [allQuestions.items[0]],
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[`/banks/${bank.bank_id}`]}><Routes><Route path="/banks/:bankId" element={<BankDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>)
}

describe('BankDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getQuestionBanks).mockResolvedValue([bank] as never)
    vi.mocked(getBankQuestionProgress).mockResolvedValueOnce(allQuestions as never).mockResolvedValueOnce(searchQuestions as never)
  })

  it('sends the query to the backend and shows the real match count', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('RAG 检索会先查找相关资料。')).toBeInTheDocument()
    const searchInput = screen.getByRole('textbox', { name: '查询题目' })
    await user.type(searchInput, 'RAG')
    await user.click(screen.getByRole('button', { name: '查询题目' }))

    await waitFor(() => expect(getBankQuestionProgress).toHaveBeenLastCalledWith(bank.bank_id, 'all', 'RAG'))
    expect(await screen.findByText('找到 1 道')).toBeInTheDocument()
    expect(screen.queryByText('Agent 可以调用受控工具。')).not.toBeInTheDocument()
  })
})

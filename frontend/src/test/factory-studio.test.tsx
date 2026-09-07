import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getDomains,
  getQuestionBanks,
  getQuestionImportBatch,
  getQuestionImportBatches,
  getQuestionImportTemplates,
  validateQuestionBankImport,
} from '../api/client'
import { FactoryStudio } from '../components/factory/FactoryStudio'

vi.mock('../api/client', () => ({
  createQuestionImportBatch: vi.fn(),
  deleteQuestionImportBatch: vi.fn(),
  getDomains: vi.fn(),
  getQuestionBanks: vi.fn(),
  getQuestionImportBatch: vi.fn(),
  getQuestionImportBatches: vi.fn(),
  getQuestionImportTemplates: vi.fn(),
  publishQuestionImportBatch: vi.fn(),
  reviewQuestionImportBatch: vi.fn(),
  reviewQuestionImportDraft: vi.fn(),
  validateQuestionBankImport: vi.fn(),
}))

const batch = {
  batch_id: 'qbank_batch_test',
  domain_id: 'general_science',
  source_name: '持久化样例',
  file_name: 'sample.jsonl',
  format: 'jsonl',
  status: 'partially_published',
  total_count: 2,
  pending_count: 0,
  approved_count: 1,
  rejected_count: 0,
  published_count: 1,
  published_bank_id: 'bank-import-sample-1234',
  created_at: '2026-09-07T00:00:00',
  updated_at: '2026-09-07T00:00:00',
  issues: [],
  items: [{
    draft_id: 'draft_test', ordinal: 1, status: 'approved', review_note: null,
    title: '测试题', question: '测试题干', question_type: 'single_choice',
    options: [{ id: 'opt_0', text: '正确' }, { id: 'opt_1', text: '错误' }],
    answer: 'A', answer_key: 0, explanation: '解析', explanation_available: true,
    body_part: '通用', difficulty: 'easy', image_url: null, subject: null, topic: null,
    teaching_tags: ['通用'], source_dataset: '持久化样例', expected_keywords: [],
    fingerprint: 'fingerprint', source_item_id: 'import_question:fingerprint',
  }],
}

function renderFactory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter><FactoryStudio /></MemoryRouter></QueryClientProvider>)
}

describe('FactoryStudio', () => {
  beforeEach(() => {
    vi.mocked(getDomains).mockResolvedValue([{ domain_id: 'general_science', display_name: '通用科学' }] as never)
    vi.mocked(getQuestionImportTemplates).mockResolvedValue({ formats: ['jsonl'], required_fields: ['question'], examples: { jsonl: '{}' } })
    vi.mocked(getQuestionImportBatches).mockResolvedValue([batch] as never)
    vi.mocked(getQuestionImportBatch).mockResolvedValue(batch as never)
    vi.mocked(getQuestionBanks).mockResolvedValue([])
  })

  it('uses an editable default domain field and restores JSONL templates', async () => {
    const user = userEvent.setup()
    renderFactory()

    const domainInput = await screen.findByRole('textbox', { name: '学习领域' })
    expect(domainInput).toHaveValue('通用科学')
    expect(screen.getByRole('button', { name: 'JSONL 模板' })).toBeInTheDocument()
    await user.clear(domainInput)
    expect(domainInput).toHaveValue('')
  })

  it('keeps the continuation publish action visible after a partial publish', async () => {
    const user = userEvent.setup()
    renderFactory()

    await user.click(await screen.findByRole('tab', { name: /待审核题库/ }))
    await user.click(await screen.findByRole('button', {
      name: /持久化样例.*sample\.jsonl.*2 题/,
    }))

    await waitFor(() => expect(screen.getByRole('button', { name: /继续发布新通过题目/ })).toBeEnabled())
    expect(screen.getByText('已发布 1 题')).toBeInTheDocument()
  })

  it('renders imported true-false questions as reviewable choices in preview', async () => {
    vi.mocked(getQuestionImportBatches).mockResolvedValue([] as never)
    vi.mocked(validateQuestionBankImport).mockResolvedValue({
      format: 'jsonl', accepted_count: 1, rejected_count: 0, ready_to_publish: true,
      items: [{ title: '导入记录标题（不在预览重复显示）', question: '这是一道判断题。', question_type: 'true_false', options: [], difficulty: 'easy', body_part: '通用' }],
      issues: [], summary: { question_type_counts: { true_false: 1 } },
    } as never)
    const user = userEvent.setup()
    renderFactory()

    await user.type(await screen.findByRole('textbox', { name: /题目内容/ }), '判断题内容')
    await user.click(screen.getByRole('button', { name: /校验并预览/ }))

    expect(await screen.findByText('这是一道判断题。')).toBeInTheDocument()
    expect(screen.queryByText('导入记录标题（不在预览重复显示）')).not.toBeInTheDocument()
    expect(screen.getByText('正确')).toBeInTheDocument()
    expect(screen.getByText('错误')).toBeInTheDocument()
    expect(screen.queryByText('非选择题 · 将按导入答案进行审核')).not.toBeInTheDocument()
  })

  it('filters the preview by question type and paginates large imports', async () => {
    vi.mocked(getQuestionImportBatches).mockResolvedValue([] as never)
    const items = Array.from({ length: 13 }, (_, index) => ({
      title: `单选题 ${index + 1}`,
      question: `请判断第 ${index + 1} 题。`,
      question_type: index === 12 ? 'true_false' : 'single_choice',
      options: index === 12 ? [] : [{ id: 'opt_0', text: '选项 A' }, { id: 'opt_1', text: '选项 B' }, { id: 'opt_2', text: '选项 C' }, { id: 'opt_3', text: '选项 D' }],
      difficulty: 'easy',
      body_part: '通用',
    }))
    vi.mocked(validateQuestionBankImport).mockResolvedValue({
      format: 'json', accepted_count: 13, rejected_count: 0, ready_to_publish: true,
      items, issues: [], summary: { question_type_counts: { single_choice: 12, true_false: 1 } },
    } as never)
    const user = userEvent.setup()
    renderFactory()

    await user.type(await screen.findByRole('textbox', { name: /题目内容/ }), '批量题目')
    await user.click(screen.getByRole('button', { name: /校验并预览/ }))

    expect(await screen.findByText('当前显示 12 / 13 道')).toBeInTheDocument()
    expect(screen.getAllByText('选项 D')).toHaveLength(12)
    await user.click(screen.getByRole('button', { name: '下一页' }))
    expect(screen.getByText('请判断第 13 题。')).toBeInTheDocument()
    expect(screen.queryByText('请判断第 1 题。')).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /判断题 1/ }))
    expect(screen.getByText('当前显示 1 / 1 道')).toBeInTheDocument()
    expect(screen.getByText('正确')).toBeInTheDocument()
    expect(screen.getByText('错误')).toBeInTheDocument()
  })
})

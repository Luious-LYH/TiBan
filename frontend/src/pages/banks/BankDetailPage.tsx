import { ArrowLeft, Bookmark, Check, CheckCircle2, Circle, LoaderCircle, Pencil, Search, X, XCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState, type FormEvent, type ReactNode } from 'react'

import { getBankQuestionProgress, getQuestionBanks, getQuestionForEdit, resolveApiUrl, updateQuestion, type QuestionEdit } from '../../api/client'
import { SessionBuilder } from '../../components/practice/SessionBuilder'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type Filter = 'all' | 'uncompleted' | 'completed' | 'incorrect' | 'marked'

const filters: Array<[Filter, string]> = [['all', '全部'], ['uncompleted', '未做'], ['completed', '已做'], ['incorrect', '错题'], ['marked', '已标记']]
const scopeByFilter = { all: 'all', uncompleted: 'uncompleted', completed: 'all', incorrect: 'incorrect', marked: 'marked' } as const

export function BankDetailPage() {
  const { bankId = '' } = useParams()
  const [filter, setFilter] = useState<Filter>('all')
  const [questionSearchDraft, setQuestionSearchDraft] = useState('')
  const [questionSearch, setQuestionSearch] = useState('')
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null)
  const banks = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const bank = banks.data?.find((item) => item.bank_id === bankId)
  const questions = useQuery({ queryKey: ['bank-question-progress', bankId, filter, questionSearch], queryFn: () => getBankQuestionProgress(bankId, filter, questionSearch), enabled: Boolean(bankId && bank) })
  const editQuery = useQuery({ queryKey: ['question-edit', bankId, editingQuestionId], queryFn: () => getQuestionForEdit(bankId, editingQuestionId ?? ''), enabled: Boolean(bankId && editingQuestionId), retry: false })

  if (banks.isPending) return <LoadingState label="正在读取题库…" />
  if (banks.isError) return <ErrorState message={banks.error.message} onRetry={() => void banks.refetch()} />
  if (!bank) return <EmptyState title="题库不可用" detail="它可能已被归档，或不再作为学习题库展示。" />
  if (questions.isPending) return <LoadingState label="正在整理题目进度…" />
  if (questions.isError) return <ErrorState message={questions.error.message} onRetry={() => void questions.refetch()} />

  const progressItems = questions.data.items ?? []
  function submitQuestionSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setQuestionSearch(questionSearchDraft.trim())
  }
  function clearQuestionSearch() {
    setQuestionSearchDraft('')
    setQuestionSearch('')
  }
  return <div className="bank-detail-page" data-testid="bank-detail-page">
    <Link className="practice-back" to="/banks"><ArrowLeft size={16} />返回题库</Link>
    <header className="bank-detail-header"><div><span>题库详情</span><h1>{displayName(bank.name)}</h1><p>{bank.description}</p></div><SessionBuilder bankId={bank.bank_id} bankName={displayName(bank.name)} availableCounts={bank} triggerClassName="bank-detail-start" initialScope={scopeByFilter[filter]} /></header>
    <section className="bank-detail-metrics" aria-label="题库学习进度"><Metric icon={<CheckCircle2 />} label="已做" value={`${bank.completed_count} / ${bank.question_count}`} /><Metric icon={<Circle />} label="未做" value={String(bank.uncompleted_count)} /><Metric icon={<XCircle />} label="错题" value={String(bank.incorrect_count)} /><Metric icon={<Bookmark fill="currentColor" />} label="已标记" value={String(bank.marked_count)} /></section>
    <section className="bank-question-browser"><header><div><h2>题目浏览</h2><p>按真实作答状态查看；题库作者可以打开题目进行修订。</p></div><form className="bank-question-search" role="search" onSubmit={submitQuestionSearch}><Search size={16} aria-hidden="true" /><input aria-label="查询题目" value={questionSearchDraft} onChange={(event) => setQuestionSearchDraft(event.target.value)} placeholder="输入题干关键词" /><button type="submit" aria-label="查询题目" title="查询题目"><Search size={14} /></button>{questionSearch ? <button type="button" className="bank-question-search-clear" aria-label="清空查询" title="清空查询" onClick={clearQuestionSearch}><X size={14} /></button> : null}</form><span className="bank-question-count">{questionSearch ? `找到 ${questions.data.total} 道` : `${questions.data.total} 题`}</span></header><div className="bank-filter-tabs" role="tablist" aria-label="题目状态">{filters.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>{progressItems.length === 0 ? <EmptyState title={questionSearch ? '没有找到匹配题目' : '这里暂时没有题目'} detail={questionSearch ? '换一个题干关键词，或清空查询后浏览全部题目。' : '更换状态筛选，或先开始一组练习。'} /> : <ol className="bank-question-list">{progressItems.map((item, index) => <li className={item.image_url ? 'has-image' : undefined} key={item.question_id}><span className={item.incorrect ? 'is-wrong' : item.completed ? 'is-done' : ''}>{index + 1}</span>{item.image_url && <img className="bank-question-thumb" src={resolveApiUrl(item.image_url)} alt={item.image_alt ?? '题目图片'} />}<div><strong>{item.question_summary}</strong><small>{questionTypeLabel(item.question_type)}{learnerTopic(item.topic) ? ` · ${learnerTopic(item.topic)}` : ''}{item.completed ? ` · 已作答 ${item.attempt_count} 次` : ' · 尚未作答'}</small></div>{item.marked && <Bookmark size={15} fill="currentColor" aria-label="已标记" />}{item.last_result && <em className={item.last_result === 'correct' ? 'is-correct' : 'is-incorrect'}>{item.last_result === 'correct' ? '正确' : '错误'}</em>}<button className="bank-question-edit" type="button" title="编辑题目" aria-label={`编辑第 ${index + 1} 题`} onClick={() => setEditingQuestionId(item.question_id)}><Pencil size={14} /></button></li>)}</ol>}</section>
    {editingQuestionId && <div className="bank-edit-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) setEditingQuestionId(null) }}><section className="bank-edit-dialog bank-question-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="question-edit-title"><header><div><span className="catalog-dialog-kicker">题目管理</span><h2 id="question-edit-title">编辑题目</h2></div><button type="button" aria-label="关闭" onClick={() => setEditingQuestionId(null)}><X size={17} /></button></header>{editQuery.isPending ? <div className="bank-edit-loading"><LoaderCircle className="s1-spin" size={18} />正在读取题目…</div> : editQuery.isError ? <div className="catalog-action-error" role="alert">题目读取失败：{editQuery.error.message}</div> : editQuery.data ? <QuestionEditForm bankId={bankId} question={editQuery.data} onClose={() => setEditingQuestionId(null)} /> : <div className="bank-edit-loading">暂时没有可编辑的题目。</div>}</section></div>}
  </div>
}

type QuestionEditFormState = {
  title: string
  stem: string
  question_type: QuestionEdit['question_type']
  options: string
  answer: string
  explanation: string
  difficulty: QuestionEdit['difficulty']
  tags: string
  body_part: string
  subject: string
  topic: string
  task: string
}

function QuestionEditForm({ bankId, question, onClose }: { bankId: string; question: QuestionEdit; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<QuestionEditFormState>(() => toEditForm(question))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const options = form.options.split(/\r?\n/).map((text) => text.trim()).filter(Boolean).map((text, index) => ({ id: `opt_${index}`, text }))
      const answer = form.question_type === 'true_false' ? form.answer === '正确' : form.answer.trim()
      await updateQuestion(bankId, question.question_id, {
        title: form.title.trim(),
        stem: form.stem.trim(),
        question_type: form.question_type,
        options,
        answer,
        explanation: form.explanation.trim(),
        difficulty: form.difficulty,
        tags: form.tags.split(/[、,，|]/).map((tag) => tag.trim()).filter(Boolean),
        body_part: form.body_part.trim() || '通用',
        subject: form.subject.trim() || null,
        topic: form.topic.trim() || null,
        task: form.task.trim() || '个人题库练习',
      })
      await queryClient.invalidateQueries({ queryKey: ['question-banks'] })
      await queryClient.invalidateQueries({ queryKey: ['bank-question-progress', bankId] })
      onClose()
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const update = <K extends keyof QuestionEditFormState>(key: K, value: QuestionEditFormState[K]) => setForm((current) => ({ ...current, [key]: value }))
  return <><div className="bank-edit-fields bank-question-edit-fields"><label><span>题目标题</span><input value={form.title} onChange={(event) => update('title', event.target.value)} maxLength={300} /></label><label><span>题干</span><textarea value={form.stem} onChange={(event) => update('stem', event.target.value)} rows={4} maxLength={20000} /></label><label><span>题型</span><select value={form.question_type} onChange={(event) => update('question_type', event.target.value as QuestionEditFormState['question_type'])}><option value="single_choice">单选题</option><option value="multiple_choice">多选题</option><option value="true_false">判断题</option><option value="short_answer">问答题</option></select></label>{form.question_type !== 'true_false' && form.question_type !== 'short_answer' && <label><span>选项 <small>每行一个</small></span><textarea value={form.options} onChange={(event) => update('options', event.target.value)} rows={5} /></label>}<label><span>参考答案</span>{form.question_type === 'true_false' ? <select value={form.answer} onChange={(event) => update('answer', event.target.value)}><option value="正确">正确</option><option value="错误">错误</option></select> : <input value={form.answer} onChange={(event) => update('answer', event.target.value)} placeholder={form.question_type === 'multiple_choice' ? '例如 A|C' : '例如 A'} />}</label><label><span>解析</span><textarea value={form.explanation} onChange={(event) => update('explanation', event.target.value)} rows={4} /></label><div className="bank-edit-grid"><label><span>分类</span><input value={form.body_part} onChange={(event) => update('body_part', event.target.value)} /></label><label><span>难度</span><select value={form.difficulty} onChange={(event) => update('difficulty', event.target.value as QuestionEditFormState['difficulty'])}><option value="easy">简单</option><option value="medium">中等</option><option value="hard">困难</option></select></label></div>{error && <p className="catalog-action-error" role="alert">{error}</p>}</div><footer><button type="button" disabled={saving} onClick={onClose}>取消</button><button className="is-primary" type="button" disabled={saving || !form.stem.trim() || !form.title.trim()} onClick={() => void save()}>{saving ? <LoaderCircle className="s1-spin" size={15} /> : <Check size={15} />}保存题目</button></footer></>
}

function toEditForm(question: QuestionEdit): QuestionEditFormState {
  return {
    title: question.title,
    stem: question.stem,
    question_type: question.question_type,
    options: (question.options ?? []).map((option) => option.text).join('\n'),
    answer: typeof question.answer === 'boolean' ? (question.answer ? '正确' : '错误') : Array.isArray(question.answer) ? question.answer.join('|') : question.answer,
    explanation: question.explanation,
    difficulty: question.difficulty,
    tags: (question.tags ?? []).join('、'),
    body_part: question.body_part,
    subject: question.subject ?? '',
    topic: question.topic ?? '',
    task: question.task,
  }
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) { return <div><span>{icon}</span><small>{label}</small><strong>{value}</strong></div> }
function displayName(name: string) { return name.replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function questionTypeLabel(type: string) { return ({ single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '问答题' } as Record<string, string>)[type] ?? '题目' }
function learnerTopic(value: string | null | undefined) {
  const topic = String(value ?? '').trim()
  return /^(不符合|未知|其他|n\/?a|import|csv|jsonl)$/i.test(topic) || /模块\s*\d+/i.test(topic) ? '' : topic
}

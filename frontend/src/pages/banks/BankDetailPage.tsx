import { ArrowLeft, Bookmark, CheckCircle2, Circle, XCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'

import { getBankQuestionProgress, getQuestionBanks } from '../../api/client'
import { SessionBuilder } from '../../components/practice/SessionBuilder'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type Filter = 'all' | 'uncompleted' | 'completed' | 'incorrect' | 'marked'

const filters: Array<[Filter, string]> = [['all', '全部'], ['uncompleted', '未做'], ['completed', '已做'], ['incorrect', '错题'], ['marked', '已标记']]
const scopeByFilter = { all: 'all', uncompleted: 'uncompleted', completed: 'all', incorrect: 'incorrect', marked: 'marked' } as const

export function BankDetailPage() {
  const { bankId = '' } = useParams()
  const [filter, setFilter] = useState<Filter>('all')
  const banks = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const bank = banks.data?.find((item) => item.bank_id === bankId)
  const questions = useQuery({ queryKey: ['bank-question-progress', bankId, filter], queryFn: () => getBankQuestionProgress(bankId, filter), enabled: Boolean(bankId && bank) })

  if (banks.isPending) return <LoadingState label="正在读取题库…" />
  if (banks.isError) return <ErrorState message={banks.error.message} onRetry={() => void banks.refetch()} />
  if (!bank) return <EmptyState title="题库不可用" detail="它可能已被归档，或不再作为学习题库展示。" />
  if (questions.isPending) return <LoadingState label="正在整理题目进度…" />
  if (questions.isError) return <ErrorState message={questions.error.message} onRetry={() => void questions.refetch()} />

  const progressItems = questions.data.items ?? []
  return <div className="bank-detail-page" data-testid="bank-detail-page">
    <Link className="practice-back" to="/banks"><ArrowLeft size={16} />返回题库</Link>
    <header className="bank-detail-header"><div><span>题库详情</span><h1>{displayName(bank.name)}</h1><p>{bank.description}</p></div><SessionBuilder bankId={bank.bank_id} bankName={displayName(bank.name)} availableCounts={bank} triggerClassName="bank-detail-start" initialScope={scopeByFilter[filter]} /></header>
    <section className="bank-detail-metrics" aria-label="题库学习进度"><Metric icon={<CheckCircle2 />} label="已做" value={`${bank.completed_count} / ${bank.question_count}`} /><Metric icon={<Circle />} label="未做" value={String(bank.uncompleted_count)} /><Metric icon={<XCircle />} label="错题" value={String(bank.incorrect_count)} /><Metric icon={<Bookmark fill="currentColor" />} label="已标记" value={String(bank.marked_count)} /></section>
    <section className="bank-question-browser"><header><div><h2>题目浏览</h2><p>按真实作答状态查看，答案不会在列表中提前展开。</p></div><span>{questions.data.total} 题</span></header><div className="bank-filter-tabs" role="tablist" aria-label="题目状态">{filters.map(([value, label]) => <button key={value} type="button" role="tab" aria-selected={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>{progressItems.length === 0 ? <EmptyState title="这里暂时没有题目" detail="更换状态筛选，或先开始一组练习。" /> : <ol className="bank-question-list">{progressItems.map((item, index) => <li key={item.question_id}><span className={item.incorrect ? 'is-wrong' : item.completed ? 'is-done' : ''}>{index + 1}</span><div><strong>{item.question_summary}</strong><small>{questionTypeLabel(item.question_type)}{learnerTopic(item.topic) ? ` · ${learnerTopic(item.topic)}` : ''}{item.completed ? ` · 已作答 ${item.attempt_count} 次` : ' · 尚未作答'}</small></div>{item.marked && <Bookmark size={15} fill="currentColor" aria-label="已标记" />}{item.last_result && <em className={item.last_result === 'correct' ? 'is-correct' : 'is-incorrect'}>{item.last_result === 'correct' ? '正确' : '错误'}</em>}</li>)}</ol>}</section>
  </div>
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div><span>{icon}</span><small>{label}</small><strong>{value}</strong></div> }
function displayName(name: string) { return name.replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function questionTypeLabel(type: string) { return ({ single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '问答题' } as Record<string, string>)[type] ?? '题目' }
function learnerTopic(value: string | null | undefined) {
  const topic = String(value ?? '').trim()
  return /^(不符合|未知|其他|n\/?a|import|csv|jsonl)$/i.test(topic) || /模块\s*\d+/i.test(topic) ? '' : topic
}

import { Bookmark, CalendarClock, ChevronRight, CircleAlert } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createReviewSession, getReviewItem, getReviewItems, getReviewSummary, type ReviewItem } from '../../api/client'
import { EmptyState, ErrorState } from '../../components/shared/AsyncState'

type Tab = 'due' | 'wrong' | 'marked'
const tabs: Array<[Tab, string]> = [['due', '待复习'], ['wrong', '错题'], ['marked', '已标记']]

export function ReviewPage() {
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('due')
  const summary = useQuery({ queryKey: ['review-summary'], queryFn: getReviewSummary, staleTime: 60_000, retry: false })
  const items = useQuery({ queryKey: ['review-items', tab], queryFn: () => getReviewItems(tab), staleTime: 60_000, retry: false })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selectedItemId = selectedId && items.data?.items.some((item) => item.question_id === selectedId)
    ? selectedId
    : items.data?.items[0]?.question_id ?? null
  const detail = useQuery({ queryKey: ['review-item', selectedItemId], queryFn: () => getReviewItem(selectedItemId ?? ''), enabled: Boolean(selectedItemId), staleTime: 60_000, retry: false })
  const start = useMutation({
    mutationFn: (count: number) => createReviewSession(tab, count),
    onSuccess: (session) => navigate(`/practice?mode=review&bank_id=${encodeURIComponent(session.bank_id)}&count=${session.question_count}&session_id=${encodeURIComponent(session.session_id)}`),
  })

  const detailOptions = detail.data?.options ?? []
  const recentAttempts = detail.data?.recent_attempts ?? []
  return <div className="review-page" data-testid="review-page">
    <header className="review-header"><div><span>复习工作台</span><h1>错题与复习</h1><p>从真实作答和 FSRS 队列中选题，直接进入复习。</p></div><div className="review-start-actions"><button type="button" onClick={() => start.mutate(10)} disabled={start.isPending || !items.data?.items.length}>{start.isPending ? '正在开始…' : '开始复习 10 题'} <ChevronRight size={15} /></button></div></header>
    {summary.isPending ? <ReviewSummarySkeleton /> : summary.isError ? <ReviewSummaryError message={summary.error.message} onRetry={() => void summary.refetch()} /> : <section className="review-summary" aria-label="复习摘要"><Summary icon={<CalendarClock />} label="待复习" value={summary.data.due_count} /><Summary icon={<CircleAlert />} label="错题" value={summary.data.incorrect_count} /><Summary icon={<Bookmark fill="currentColor" />} label="已标记" value={summary.data.marked_count} /></section>}
    <div className="review-tabs" role="tablist">{tabs.map(([value, label]) => <button role="tab" aria-selected={tab === value} type="button" key={value} onClick={() => { setSelectedId(null); setTab(value) }}>{label}</button>)}</div>
    {start.isError && <p className="review-error" role="alert">{start.error.message}</p>}
    <section className="review-workspace" aria-busy={items.isPending}>
      <div className="review-list-pane">{items.isPending ? <ReviewListSkeleton /> : items.isError ? <ErrorState message={items.error.message} onRetry={() => void items.refetch()} /> : !items.data?.items.length ? <EmptyState title="当前没有可复习的题目" detail="完成练习、标记题目或等待复习到期后，它们会出现在这里。" /> : <ol className="review-list">{items.data.items.map((item) => <ReviewListItem key={item.question_id} item={item} tab={tab} selected={item.question_id === selectedItemId} onSelect={() => setSelectedId(item.question_id)} />)}</ol>}</div>
      <article className="review-detail">{items.isPending || !selectedItemId ? <ReviewDetailSkeleton /> : detail.isPending ? <ReviewDetailSkeleton /> : detail.isError ? <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} /> : detail.data && <><header><span>{detail.data.bank_name}</span><h2>{detail.data.stem}</h2><small>{detail.data.question_type === 'single_choice' ? '单选题' : detail.data.question_type === 'multiple_choice' ? '多选题' : detail.data.question_type === 'true_false' ? '判断题' : '问答题'}</small></header>{detailOptions.length > 0 && <ol className="review-options">{detailOptions.map((option, index) => <li key={option.id}><b>{String.fromCharCode(65 + index)}</b>{option.text}</li>)}</ol>}<section className="review-answer"><span>正确答案</span><strong>{detail.data.correct_answer_display}</strong></section><section className="review-explanation"><strong>官方解析</strong><p>{detail.data.explanation || '暂无解析'}</p></section><section className="review-history"><strong>最近作答</strong>{recentAttempts.length ? <ol>{recentAttempts.map((attempt, index) => <li key={`${attempt.created_at}-${index}`}><span className={attempt.correct ? 'is-correct' : 'is-incorrect'}>{attempt.correct ? '正确' : '错误'}</span><p>{attempt.selected_answer_display}</p><time>{new Date(attempt.created_at).toLocaleString('zh-CN')}</time></li>)}</ol> : <p>暂无历史作答。</p>}</section></>}</article>
    </section>
  </div>
}

function Summary({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) { return <div><span>{icon}</span><small>{label}</small><strong>{value}</strong></div> }
function ReviewSummarySkeleton() { return <section className="review-summary review-summary-skeleton" aria-label="正在读取复习摘要" role="status">{Array.from({ length: 3 }, (_, index) => <div key={index}><span className="ui-skeleton" /><small className="ui-skeleton" /><strong className="ui-skeleton" /></div>)}</section> }
function ReviewSummaryError({ message, onRetry }: { message: string; onRetry: () => void }) { return <section className="review-summary-error" role="alert"><p>复习摘要暂不可用：{message}</p><button type="button" onClick={onRetry}>重试</button></section> }
function ReviewListSkeleton() { return <div className="review-list-skeleton" role="status" aria-label="正在读取复习列表">{Array.from({ length: 6 }, (_, index) => <div key={index}><span className="ui-skeleton" /><span className="ui-skeleton" /></div>)}</div> }
function ReviewDetailSkeleton() { return <div className="review-detail-skeleton" role="status" aria-label="正在读取题目详情"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }
function ReviewListItem({ item, tab, selected, onSelect }: { item: ReviewItem; tab: Tab; selected: boolean; onSelect: () => void }) {
  const statusClass = tab === 'marked' ? 'is-marked' : tab === 'wrong' ? 'is-wrong' : ''
  const statusIcon = tab === 'marked'
    ? <Bookmark size={14} fill="currentColor" aria-hidden="true" />
    : tab === 'wrong'
      ? <CircleAlert size={14} aria-hidden="true" />
      : <CalendarClock size={14} aria-hidden="true" />
  const statusLabel = tab === 'marked' ? '已标记' : tab === 'wrong' ? `错 ${item.wrong_count} 次` : '待复习'
  return <li><button type="button" className={selected ? 'is-selected' : ''} onClick={onSelect}><span className={statusClass}>{statusIcon}</span><div><strong>{item.question_summary}</strong><small>{item.bank_name} · {statusLabel}</small></div>{item.due_at && <time>{new Date(item.due_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })}</time>}</button></li>
}

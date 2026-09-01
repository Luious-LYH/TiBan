import { ArrowRight, CheckCircle2, Clock3, Target } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getOverview } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: () => getOverview() })
  if (overview.isPending) return <LoadingState />
  if (overview.isError) return <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />
  const data = overview.data
  const recommendations = data.banks.slice(0, 3)

  return <div className="overview-lite" data-testid="overview-page">
    <header className="overview-header"><div><h1>学习主页</h1><p>从推荐练习开始，逐步完成复习与巩固。</p></div><Link className="overview-primary-link" to="/banks">进入题库 <ArrowRight size={16} /></Link></header>
    <section className="overview-metrics" aria-label="学习指标"><Metric icon={<CheckCircle2 />} label="今日完成" value={`${data.completed_today} 题`} /><Metric icon={<Target />} label="待复习" value={String(data.due_review_count)} /><Metric icon={<Clock3 />} label="近期正确率" value={`${Math.round(data.recent_accuracy * 100)}%`} /></section>
    <div className="overview-grid">
      <section className="overview-section overview-recommendations" aria-labelledby="recommend-title"><div className="overview-section-heading"><div><span>推荐开始</span><h2 id="recommend-title">继续刷题</h2></div><Link to="/banks">全部题库 <ArrowRight size={14} /></Link></div>{recommendations.length === 0 ? <EmptyState title="还没有可用题库" detail="完成资料入库后，这里会显示学习入口。" /> : <div>{recommendations.map((bank) => <article className="overview-recommendation" key={bank.bank_id}><div><strong>{displayName(bank.name)}</strong><p>{bank.completed_count > 0 ? `已完成 ${bank.completed_count} / ${bank.question_count} 题，继续保持节奏。` : learnerBankDescription(bank.bank_id, bank.description)}</p>{bank.completed_count > 0 && <span><i><b style={{ width: `${Math.round(bank.progress * 100)}%` }} /></i>{Math.round(bank.progress * 100)}%</span>}</div><Link to={`/practice?bank_id=${encodeURIComponent(bank.bank_id)}`}>开始刷题 <ArrowRight size={15} /></Link></article>)}</div>}</section>
      <section className="overview-section overview-weak" aria-labelledby="weak-title"><div className="overview-section-heading"><div><span>学习记忆</span><h2 id="weak-title">近期薄弱主题</h2></div></div>{data.weak_areas.length ? <ol>{data.weak_areas.slice(0, 5).map((area, index) => <li key={area}><b>{index + 1}</b><span>{area}</span></li>)}</ol> : <p className="overview-quiet-empty">暂时还没有足够的练习记录来判断需要巩固的主题。</p>}</section>
    </div>
    <section className="overview-section overview-activity" aria-labelledby="activity-title"><div className="overview-section-heading"><div><span>真实作答记录</span><h2 id="activity-title">最近作答</h2></div></div>{data.recent_sessions.length === 0 ? <EmptyState title="尚未有练习记录" detail="选择一个题库开始第一道题。" /> : <div className="overview-activity-list">{data.recent_sessions.slice(0, 6).map((item) => <article key={item.attempt_id}><span className={item.correct ? 'is-correct' : 'is-incorrect'} /><div><strong>{displayName(item.bank_name)}</strong><p>{item.question_summary}</p><small>{questionTypeLabel(item.question_type)} · {item.correct ? '回答正确' : '需要复盘'} · {new Date(item.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</small></div><b>{item.correct ? '正确' : '复盘'}</b></article>)}</div>}</section>
  </div>
}

function Metric({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) { return <div><span>{icon}</span><small>{label}</small><strong>{value}</strong></div> }
function displayName(name: string) { return name.replace(/医疗\s*\/\s*消化内镜\s*·\s*Factory\s*生成题草稿库/g, '医疗 / 消化内镜 · 资料生成题库').replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function learnerBankDescription(bankId: string, fallback: string) { const summaries: Record<string, string> = { 'bank-cmb-exam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-cmexam-real': '覆盖医学基础与临床知识的综合练习题。', 'bank-kvasir-vqa-curated': '通过内镜图像观察训练可见事实判断。' }; return summaries[bankId] ?? fallback.replace(/本地导入/g, '').trim() }
function questionTypeLabel(type: string) { return ({ single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '简答题' } as Record<string, string>)[type] ?? '题目' }

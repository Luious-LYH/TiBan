import { ArrowRight, CheckCircle2, Clock3, Library, Target } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getOverview } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: () => getOverview() })

  if (overview.isPending) return <LoadingState />
  if (overview.isError) return <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />

  const data = overview.data
  return (
    <div className="s1-page" data-testid="overview-page">
      <section className="s1-page-intro">
        <div>
          <span className="s1-kicker">LEARNING OVERVIEW</span>
          <h1>把每次观察，变成可复盘的进步。</h1>
          <p>从真实题库开始练习。提交后由确定性 workflow 记录 attempt、掌握度与复习安排。</p>
        </div>
        <Link className="s1-button s1-button-primary" to="/banks">进入题库 <ArrowRight size={16} /></Link>
      </section>

      <section className="s1-metric-grid" aria-label="学习指标">
        <Metric icon={<CheckCircle2 />} label="今日完成" value={`${data.completed_today} / ${data.daily_target}`} detail="道题" />
        <Metric icon={<Target />} label="待复习" value={String(data.due_review_count)} detail="张卡片" />
        <Metric icon={<Library />} label="可用题库" value={String(data.banks.length)} detail="个真实题库" />
        <Metric icon={<Clock3 />} label="近期准确率" value={`${Math.round(data.recent_accuracy * 100)}%`} detail="最近 10 次" />
      </section>

      <div className="s1-content-grid">
        <section className="s1-card" aria-labelledby="overview-banks-title">
          <div className="s1-section-heading"><div><span className="s1-kicker">CATALOG</span><h2 id="overview-banks-title">继续你的学习路径</h2></div><Link to="/banks">查看全部 <ArrowRight size={14} /></Link></div>
          {data.banks.length === 0 ? <EmptyState title="还没有可用题库" detail="完成 seed 或接入题库后，这里会显示真实学习入口。" /> : (
            <div className="s1-bank-list">
              {data.banks.slice(0, 4).map((bank) => <Link to={`/practice?bank_id=${encodeURIComponent(bank.bank_id)}`} className="s1-bank-row" key={bank.bank_id}>
                <span className="s1-bank-icon"><Library size={17} /></span>
                <span className="s1-bank-copy"><strong>{bank.name}</strong><small>{bank.description}</small></span>
                <span className="s1-bank-progress"><b>{bank.completed_count}/{bank.question_count}</b><span><i style={{ width: `${Math.round(bank.progress * 100)}%` }} /></span></span>
                <ArrowRight size={16} />
              </Link>)}
            </div>
          )}
        </section>

        <section className="s1-card s1-recent-card" aria-labelledby="recent-title">
          <div className="s1-section-heading"><div><span className="s1-kicker">RECENT TRACE</span><h2 id="recent-title">最近练习</h2></div></div>
          {data.recent_sessions.length === 0 ? <EmptyState title="尚未有练习记录" detail="选择一个题库开始第一道题。" /> : <div className="s1-recent-list">{data.recent_sessions.slice(0, 6).map((item) => <div className="s1-recent-row" key={item.attempt_id}><span className={item.correct ? 's1-dot is-correct' : 's1-dot'} /><span><strong>{item.correct ? '回答正确' : '进入复盘'}</strong><small>{new Date(item.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</small></span><b>{item.score} 分</b></div>)}</div>}
        </section>
      </div>
      <p className="s1-safety">{data.safety_notice}</p>
    </div>
  )
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return <div className="s1-metric"><span className="s1-metric-icon">{icon}</span><span className="s1-metric-label">{label}</span><strong>{value}</strong><small>{detail}</small></div>
}

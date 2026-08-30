import { ArrowRight, BrainCircuit, CheckCircle2, Clock3, Library, Target, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearLearningMemory, getLearningMemory, getOverview } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

export function OverviewPage() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: () => getOverview() })
  const learningMemory = useQuery({ queryKey: ['learning-memory'], queryFn: () => getLearningMemory() })
  const queryClient = useQueryClient()
  const clearMemory = useMutation({
    mutationFn: () => clearLearningMemory(),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['learning-memory'] }),
  })

  if (overview.isPending) return <LoadingState />
  if (overview.isError) return <ErrorState message={overview.error.message} onRetry={() => void overview.refetch()} />

  const data = overview.data
  return (
    <div className="s1-page" data-testid="overview-page">
      <section className="s1-page-intro">
        <div>
          <span className="s1-kicker">LEARNING OVERVIEW</span>
          <h1>把每次观察，变成可复盘的进步。</h1>
          <p>从示例或已接入的题库开始练习。提交后会自动记录学习进度、掌握情况与复习安排。</p>
        </div>
        <Link className="s1-button s1-button-primary" to="/banks">进入题库 <ArrowRight size={16} /></Link>
      </section>

      <section className="s1-metric-grid" aria-label="学习指标">
        <Metric icon={<CheckCircle2 />} label="今日完成" value={`${data.completed_today} / ${data.daily_target}`} detail="道题" />
        <Metric icon={<Target />} label="待复习" value={String(data.due_review_count)} detail="张卡片" />
        <Metric icon={<Library />} label="可用题库" value={String(data.banks.length)} detail="示例 / 已接入" />
        <Metric icon={<Clock3 />} label="近期准确率" value={`${Math.round(data.recent_accuracy * 100)}%`} detail="最近 10 次" />
      </section>

      <div className="s1-content-grid">
        <section className="s1-card" aria-labelledby="overview-banks-title">
          <div className="s1-section-heading"><div><span className="s1-kicker">CATALOG</span><h2 id="overview-banks-title">继续你的学习路径</h2></div><Link to="/banks">查看全部 <ArrowRight size={14} /></Link></div>
          {data.banks.length === 0 ? <EmptyState title="还没有可用题库" detail="完成 seed 或接入题库后，这里会显示真实学习入口。" /> : (
            <div className="s1-bank-list">
              {data.banks.slice(0, 4).map((bank) => <Link to={`/practice?bank_id=${encodeURIComponent(bank.bank_id)}`} className="s1-bank-row" key={bank.bank_id}>
                <span className="s1-bank-icon"><Library size={17} /></span>
                <span className="s1-bank-copy"><strong>{bank.name}</strong><small>{learnerBankDescription(bank.bank_id, bank.description)}</small></span>
                <span className="s1-bank-progress"><b>{bank.completed_count}/{bank.question_count}</b><span><i style={{ width: `${Math.round(bank.progress * 100)}%` }} /></span></span>
                <ArrowRight size={16} />
              </Link>)}
            </div>
          )}
        </section>

        <section className="s1-card s1-recent-card" aria-labelledby="recent-title">
          <div className="s1-section-heading"><div><span className="s1-kicker">RECENT ACTIVITY</span><h2 id="recent-title">最近练习</h2></div></div>
          {data.recent_sessions.length === 0 ? <EmptyState title="尚未有练习记录" detail="选择一个题库开始第一道题。" /> : <div className="s1-recent-list">{data.recent_sessions.slice(0, 6).map((item) => <div className="s1-recent-row" key={item.attempt_id}><span className={item.correct ? 's1-dot is-correct' : 's1-dot'} /><span><strong>{item.correct ? '回答正确' : '进入复盘'}</strong><small>{new Date(item.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</small></span><b>{item.correct ? `${item.score} 分` : '—'}</b></div>)}</div>}
        </section>
      </div>
      <section className="s1-card s1-learning-memory-card" aria-labelledby="learning-memory-title" data-testid="learning-memory-panel">
        <div className="s1-section-heading">
          <div><span className="s1-kicker">LEARNING PROFILE</span><h2 id="learning-memory-title">最近需要巩固</h2></div>
          <button className="s1-button s1-button-light s1-memory-clear" type="button" onClick={() => clearMemory.mutate()} disabled={clearMemory.isPending || !learningMemory.data?.items.length}>
            <Trash2 size={14} />{clearMemory.isPending ? '清除中…' : '清除长期学习记忆'}
          </button>
        </div>
        {learningMemory.isPending ? <p className="s1-memory-status">正在整理你的跨次学习线索…</p> : learningMemory.isError ? <p className="s1-memory-status">学习画像暂不可用；练习和复习记录不受影响。</p> : learningMemory.data?.items.length ? (
          <div className="s1-memory-list" aria-label="学习画像条目">
            {learningMemory.data.items.map((item) => <article className="s1-memory-item" key={item.memory_id}>
              <span className="s1-memory-icon"><BrainCircuit size={17} /></span>
              <div><strong>{item.summary}</strong><small>{item.topic_keys.slice(0, 3).join(' · ') || '最近练习'}</small></div>
            </article>)}
          </div>
        ) : <p className="s1-memory-status">完成几次同主题练习后，这里会呈现真正影响后续辅导与选题的学习线索。</p>}
        {clearMemory.isSuccess && <p className="s1-memory-status is-success">已清除长期学习记忆；练习记录与复习安排仍会保留。</p>}
      </section>
      <p className="s1-safety">{data.safety_notice}</p>
    </div>
  )
}

function learnerBankDescription(bankId: string, fallback: string) {
  const summaries: Record<string, string> = {
    'bank-cmb-exam-real': '覆盖医学基础与临床知识的综合练习题。',
    'bank-cmexam-real': '覆盖医学基础与临床知识的综合练习题。',
    'bank-kvasir-vqa-curated': '通过内镜图像观察训练可见事实判断。',
  }
  return summaries[bankId] ?? fallback
}

function Metric({ icon, label, value, detail }: { icon: React.ReactNode; label: string; value: string; detail: string }) {
  return <div className="s1-metric"><span className="s1-metric-icon">{icon}</span><span className="s1-metric-label">{label}</span><strong>{value}</strong><small>{detail}</small></div>
}

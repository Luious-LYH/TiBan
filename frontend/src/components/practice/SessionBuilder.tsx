import { X } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { createPracticeSession, type QuestionBank } from '../../api/client'

type SessionMode = 'study' | 'exam'
type QuestionScope = 'all' | 'uncompleted' | 'incorrect' | 'marked'
type ScopeCounts = Pick<QuestionBank, 'question_count' | 'uncompleted_count' | 'incorrect_count' | 'marked_count'>

export function SessionBuilder({ bankId, bankName, availableCounts, triggerClassName = 'bank-start-action', initialScope = 'all' }: { bankId: string; bankName: string; availableCounts?: ScopeCounts; triggerClassName?: string; initialScope?: QuestionScope }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<SessionMode>('study')
  const [count, setCount] = useState('20')
  const [customCount, setCustomCount] = useState('')
  const [scope, setScope] = useState<QuestionScope>(initialScope)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const availableCount = availableCounts ? {
    all: availableCounts.question_count,
    uncompleted: availableCounts.uncompleted_count,
    incorrect: availableCounts.incorrect_count,
    marked: availableCounts.marked_count,
  }[scope] : null

  function scopeLabel(value: QuestionScope) {
    return ({ all: '全部题目', uncompleted: '未做题', incorrect: '错题', marked: '已标记题' } as Record<QuestionScope, string>)[value]
  }

  async function start() {
    setStarting(true)
    setError(null)
    try {
      const requestedCount = count === 'custom' ? Number(customCount) : Number(count)
      if (!Number.isInteger(requestedCount) || requestedCount < 1 || requestedCount > 100) {
        setError('自定义题量请输入 1–100 之间的整数。')
        return
      }
      // Older callers (and imported banks without the optional progress
      // projection) do not have a trustworthy range count. In that case the
      // backend remains the source of truth; real bank pages pass counts and
      // get the immediate learner-facing validation here.
      if (availableCounts && availableCount !== null && (scope === 'incorrect' || scope === 'marked') && requestedCount > availableCount) {
        setError(`当前范围「${scopeLabel(scope)}」只有 ${availableCount} 道题，请选择不超过 ${availableCount} 题。`)
        return
      }
      const session = await createPracticeSession(bankId, 'demo_learner', mode, requestedCount, scope)
      const params = new URLSearchParams({ bank_id: bankId, count: String(requestedCount) })
      if (mode === 'exam') params.set('mode', 'exam')
      if (scope !== 'all') params.set('scope', scope)
      params.set('session_id', session.session_id)
      if (session.tutor_thread_id) params.set('tutor_thread_id', session.tutor_thread_id)
      navigate(`/practice?${params.toString()}`)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '暂时无法创建练习，请重试。')
    } finally {
      setStarting(false)
    }
  }

  return <>
    <button className={triggerClassName} type="button" onClick={() => setOpen(true)}>开始刷题</button>
    {open && <div className="session-builder-backdrop" role="presentation" onMouseDown={() => setOpen(false)}>
      <section className="session-builder" role="dialog" aria-modal="true" aria-labelledby={`session-builder-${bankId}`} onMouseDown={(event) => event.stopPropagation()}>
        <header><div><span>开始本次练习</span><h2 id={`session-builder-${bankId}`}>{bankName}</h2></div><button type="button" aria-label="关闭练习设置" onClick={() => setOpen(false)}><X size={18} /></button></header>
        <div className="session-builder-body">
          <fieldset><legend>模式</legend><div className="session-mode-control"><button type="button" className={mode === 'study' ? 'is-active' : ''} onClick={() => setMode('study')}><strong>刷题</strong><small>边做题边智能辅导</small></button><button type="button" className={mode === 'exam' ? 'is-active' : ''} onClick={() => setMode('exam')}><strong>考试</strong><small>完成后统一复盘</small></button></div></fieldset>
          <fieldset><legend>题目范围{availableCount !== null && <small className="session-available-count">共 {availableCount} 道</small>}</legend><div className="session-count-control">{([['uncompleted', '未做'], ['incorrect', '错题'], ['all', '全部'], ['marked', '已标记']] as const).map(([value, label]) => <button type="button" className={scope === value ? 'is-active' : ''} key={value} onClick={() => { setScope(value); setError(null) }}>{label}</button>)}</div></fieldset>
          <fieldset><legend>题量</legend><div className="session-count-control">{['10', '20', '30', '50'].map((value) => <button type="button" className={count === value ? 'is-active' : ''} key={value} onClick={() => setCount(value)}>{value} 题</button>)}<button type="button" className={count === 'custom' ? 'is-active' : ''} onClick={() => setCount('custom')}>自定义</button></div>{count === 'custom' && <label className="session-custom-count"><span>自定义题量</span><input aria-label="自定义题量" value={customCount} onChange={(event) => setCustomCount(event.target.value.replace(/[^0-9]/g, ''))} inputMode="numeric" placeholder="1–100" /></label>}</fieldset>
        </div>
        {error && <p className="session-builder-error" role="alert">{error}</p>}
        <footer><button className="session-cancel" type="button" onClick={() => setOpen(false)} disabled={starting}>取消</button><button className="session-start" type="button" onClick={() => void start()} disabled={starting}>{starting ? '正在开始…' : '开始练习'}</button></footer>
      </section>
    </div>}
  </>
}

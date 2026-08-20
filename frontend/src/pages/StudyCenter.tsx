import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  Bookmark,
  BookOpenCheck,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  Clock3,
  Flame,
  ListChecks,
  Play,
  RotateCcw,
  Search,
  Sparkles,
  Target,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { PortfolioCase, PortfolioStudyCase, PortfolioStudyPayload } from '../lib/types'

type CollectionTab = 'all' | 'review' | 'wrong' | 'favorite'

const favoriteStorageKey = 'endoscopy-agent:portfolio-favorites'

export function StudyCenter() {
  const [study, setStudy] = useState<PortfolioStudyPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [fallbackMode, setFallbackMode] = useState(false)
  const [query, setQuery] = useState('')
  const [bodyPart, setBodyPart] = useState('全部部位')
  const [tab, setTab] = useState<CollectionTab>('all')
  const [favorites, setFavorites] = useState<Set<string>>(() => readFavorites())

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const payload = await v3Api.portfolioStudy()
        if (mounted) {
          const normalized = normalizeStudy(payload)
          setStudy(normalized)
          setFavorites((current) => {
            const next = new Set([...current, ...normalized.library.items.filter((item) => item.favorited).map((item) => item.id)])
            window.localStorage.setItem(favoriteStorageKey, JSON.stringify([...next]))
            return next
          })
        }
      } catch {
        try {
          const cases = await v3Api.portfolioCases()
          if (mounted) {
            setStudy(buildFallbackStudy(cases.items))
            setFallbackMode(true)
          }
        } catch {
          if (mounted) {
            setStudy(buildFallbackStudy([]))
            setFallbackMode(true)
          }
        }
      } finally {
        if (mounted) setLoading(false)
      }
    }
    void load()
    return () => { mounted = false }
  }, [])

  const library = useMemo(() => (study?.library.items || []).map((item) => ({
    ...item,
    favorited: favorites.has(item.id),
  })), [favorites, study])

  const planItems = useMemo(() => (study?.today_plan.items || []).map((item) => ({
    ...item,
    favorited: favorites.has(item.id),
  })), [favorites, study])

  const bodyParts = useMemo(() => ['全部部位', ...new Set(library.map((item) => item.body_part).filter(Boolean))], [library])
  const filtered = useMemo(() => library.filter((item) => {
    if (tab === 'wrong' && !item.wrong) return false
    if (tab === 'review' && !item.progress?.review_due) return false
    if (tab === 'favorite' && !item.favorited) return false
    if (bodyPart !== '全部部位' && item.body_part !== bodyPart) return false
    const needle = query.trim().toLowerCase()
    if (!needle) return true
    return [item.title, item.prompt, item.body_part, ...item.tags].join(' ').toLowerCase().includes(needle)
  }), [bodyPart, library, query, tab])

  const toggleFavorite = (caseId: string, currentFavorited: boolean) => {
    const favorited = !currentFavorited
    setFavorites((current) => {
      const next = new Set(current)
      if (next.has(caseId)) next.delete(caseId)
      else next.add(caseId)
      window.localStorage.setItem(favoriteStorageKey, JSON.stringify([...next]))
      return next
    })
    void v3Api.portfolioStudyFavorite(caseId, favorited)
  }

  const learner = study?.learner || emptyLearner
  const progress = learner.daily_target > 0 ? Math.min(100, Math.round((learner.completed_today / learner.daily_target) * 100)) : 0
  const continueId = study?.continue_case_id || planItems[0]?.id || library[0]?.id
  const dueReviewCount = library.filter((item) => item.progress?.review_due).length

  return (
    <section className="v21-study" data-study-center="true">
      <header className="v21-study-header">
        <div>
          <span>TRAINING CENTER</span>
          <h1>研修中心</h1>
          <p>按计划训练、沉淀错题，再到 Agent 工作台完成事实级复盘。</p>
        </div>
        {continueId ? (
          <Link className="v21-study-continue" to={`/workbench?case=${encodeURIComponent(continueId)}&from=study`}>
            <Play size={16} /> 继续练习 <ArrowRight size={16} />
          </Link>
        ) : null}
      </header>

      <div className="v21-study-overview">
        <section className="v21-plan-panel" data-study-plan="true">
          <div className="v21-plan-head">
            <span className="v21-plan-icon"><Sparkles size={18} /></span>
            <div>
              <small>PERSONALIZED PLAN</small>
              <h2>{study?.today_plan.title || '今日训练计划'}</h2>
            </div>
            <b>{study?.today_plan.generated_by || 'Training Agent'}</b>
          </div>
          <p className="v21-plan-reason">{study?.today_plan.reason || '完成研修记录后，Agent 将根据错题、收藏与能力画像生成下一组任务。'}</p>
          <div className="v21-plan-list">
            {loading ? <PlanSkeleton /> : planItems.length ? planItems.slice(0, 3).map((item, index) => (
              <article key={item.id}>
                <i>{String(index + 1).padStart(2, '0')}</i>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.recommendation_reason || `${item.body_part} · ${item.difficulty}训练`}</span>
                </div>
                <small><Clock3 size={13} /> {item.estimated_minutes || 5} 分钟</small>
                <Link to={`/workbench?case=${encodeURIComponent(item.id)}&from=plan`} aria-label={`开始${item.title}`}><ChevronRight size={17} /></Link>
              </article>
            )) : <div className="v21-plan-empty"><CheckCircle2 size={20} /><span>今日计划已完成，前往题库继续自由研修。</span></div>}
          </div>
        </section>

        <aside className="v21-progress-panel">
          <div className="v21-progress-head"><span>今日进度</span><strong>{learner.completed_today}<small> / {learner.daily_target || '—'} 题</small></strong></div>
          <div className="v21-progress-track" aria-label={`今日进度 ${progress}%`}><i style={{ width: `${progress}%` }} /></div>
          <div className="v21-study-stats">
            <span><Flame size={17} /><b>{learner.streak_days}</b><small>连续天数</small></span>
            <span><Target size={17} /><b>{formatAccuracy(learner.accuracy)}</b><small>累计正确率</small></span>
            <span><RotateCcw size={17} /><b>{learner.wrong_count}</b><small>待复盘错题</small></span>
          </div>
          <p className={fallbackMode ? 'is-fallback' : ''}>
            {fallbackMode ? <CircleAlert size={14} /> : <CheckCircle2 size={14} />}
            {fallbackMode ? '当前仅展示病例目录，进度与错题服务等待后端接入。' : '错题会自动进入复盘队列，完成后由 Agent 更新下一次计划。'}
          </p>
        </aside>
      </div>

      <section className="v21-library-panel" data-study-library="true">
        <div className="v21-library-head">
          <div>
            <small>CASE LIBRARY</small>
            <h2>病例题库</h2>
          </div>
          <div className="v21-collection-tabs" role="tablist" aria-label="题库分类">
            <button data-study-tab="all" className={tab === 'all' ? 'is-active' : ''} onClick={() => setTab('all')} role="tab"><ListChecks size={15} /> 顺序训练 <b>{library.length}</b></button>
            <button data-study-tab="review" className={tab === 'review' ? 'is-active' : ''} onClick={() => setTab('review')} role="tab"><Clock3 size={15} /> 待复习 <b>{dueReviewCount}</b></button>
            <button data-study-tab="wrong" className={tab === 'wrong' ? 'is-active' : ''} onClick={() => setTab('wrong')} role="tab"><RotateCcw size={15} /> 错题本 <b>{library.filter((item) => item.wrong).length}</b></button>
            <button data-study-tab="favorite" className={tab === 'favorite' ? 'is-active' : ''} onClick={() => setTab('favorite')} role="tab"><Bookmark size={15} /> 收藏 <b>{library.filter((item) => item.favorited).length}</b></button>
          </div>
        </div>

        <div className="v21-library-tools">
          <label><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索病例、部位或训练标签" /></label>
          <div className="v21-part-filter" aria-label="按部位筛选">
            {bodyParts.map((part) => <button key={part} className={bodyPart === part ? 'is-active' : ''} onClick={() => setBodyPart(part)}>{part}</button>)}
          </div>
        </div>

        <div className="v21-case-catalog">
          {loading ? <CatalogSkeleton /> : filtered.length ? filtered.map((item) => (
            <article key={item.id} className={item.completed ? 'is-completed' : ''} data-study-case={item.id}>
              <img src={item.image_url} alt="" />
              <div className="v21-catalog-copy">
                <span>{item.body_part} · {item.difficulty}</span>
                <h3>{item.title}</h3>
                <p>{item.prompt}</p>
                <small>{item.tags.slice(0, 3).map((tag) => <em key={tag}>{tag}</em>)}</small>
              </div>
              <div className="v21-catalog-result">
                {item.progress?.review_due ? <span className="is-due"><Clock3 size={14} /> 到期复习</span> : item.completed ? <span><CheckCircle2 size={14} /> 已完成</span> : item.wrong ? <span className="is-wrong"><RotateCcw size={14} /> 待复盘</span> : <span>未开始</span>}
                <b>{item.best_score == null ? '—' : item.best_score}<small>{item.best_score == null ? ' 最佳分' : ' 分 · 最佳'}</small></b>
              </div>
              <button className={item.favorited ? 'v21-favorite is-active' : 'v21-favorite'} onClick={() => toggleFavorite(item.id, item.favorited)} aria-label={item.favorited ? '取消收藏' : '收藏病例'}><Bookmark size={16} fill={item.favorited ? 'currentColor' : 'none'} /></button>
              <Link className="v21-catalog-enter" data-study-enter={item.id} to={`/workbench?case=${encodeURIComponent(item.id)}&from=${tab}`}><span>{item.progress?.review_due ? '到期复习' : item.completed ? '再次练习' : item.wrong ? '开始复盘' : '开始练习'}</span><ChevronRight size={17} /></Link>
            </article>
          )) : <div className="v21-catalog-empty"><BookOpenCheck size={24} /><strong>{tab === 'review' ? '当前没有到期复习' : tab === 'wrong' ? '暂无错题' : tab === 'favorite' ? '还没有收藏病例' : '没有匹配的病例'}</strong><span>{tab === 'review' ? '完成训练后，Agent 会按复习间隔把病例加入这里。' : tab === 'wrong' ? '错题会在作答后自动收录到这里。' : tab === 'favorite' ? '点击病例右侧书签即可加入收藏。' : '换一个关键词或部位筛选试试。'}</span></div>}
        </div>
      </section>

      <footer className="v21-study-safety">{study?.safety_notice || v3SafetyNotice}</footer>
    </section>
  )
}

const emptyLearner: PortfolioStudyPayload['learner'] = {
  completed_today: 0,
  daily_target: 5,
  streak_days: 0,
  total_completed: 0,
  accuracy: null,
  wrong_count: 0,
  favorite_count: 0,
}

function normalizeStudy(payload: PortfolioStudyPayload): PortfolioStudyPayload {
  return {
    ...payload,
    learner: { ...emptyLearner, ...(payload.learner || {}) },
    today_plan: {
      title: payload.today_plan?.title || '今日训练计划',
      reason: payload.today_plan?.reason || '根据最近研修记录生成。',
      generated_by: payload.today_plan?.generated_by || 'Training Agent',
      items: payload.today_plan?.items || [],
    },
    library: {
      items: payload.library?.items || [],
      body_parts: payload.library?.body_parts || [],
    },
    source: payload.source || 'backend',
    safety_notice: payload.safety_notice || v3SafetyNotice,
  }
}

function buildFallbackStudy(cases: PortfolioCase[]): PortfolioStudyPayload {
  const items = cases.map((item) => toStudyCase(item))
  return {
    learner: emptyLearner,
    today_plan: {
      title: '今日基础训练',
      reason: '研修画像服务暂不可用，先按公开教学病例顺序训练；当前推荐不代表个性化结果。',
      generated_by: '目录回退',
      items: items.slice(0, 3),
    },
    library: { items, body_parts: [...new Set(items.map((item) => item.body_part))] },
    continue_case_id: items[0]?.id || null,
    source: 'fallback',
    safety_notice: v3SafetyNotice,
  }
}

function toStudyCase(item: PortfolioCase): PortfolioStudyCase {
  return {
    ...item,
    body_part: inferBodyPart(`${item.title} ${item.prompt}`),
    tags: item.facts.slice(0, 3).map((fact) => fact.dimension),
    estimated_minutes: 5,
    completed: false,
    best_score: null,
    wrong: false,
    favorited: false,
    recommendation_reason: '按病例目录顺序进入事实级观察训练',
  }
}

function inferBodyPart(text: string) {
  if (/结肠|直肠|肠/.test(text)) return '肠道'
  if (/食管/.test(text)) return '食管'
  if (/十二指肠/.test(text)) return '十二指肠'
  if (/胃/.test(text)) return '胃'
  return '消化道'
}

function readFavorites() {
  try {
    const values = JSON.parse(window.localStorage.getItem(favoriteStorageKey) || '[]') as string[]
    return new Set(values)
  } catch {
    return new Set<string>()
  }
}

function formatAccuracy(value: number | null) {
  if (value == null) return '—'
  return `${Math.round(value <= 1 ? value * 100 : value)}%`
}

function PlanSkeleton() {
  return <div className="v21-study-skeleton">正在生成今日训练计划…</div>
}

function CatalogSkeleton() {
  return <div className="v21-study-skeleton">正在载入病例题库…</div>
}

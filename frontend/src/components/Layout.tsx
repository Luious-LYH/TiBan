import { ActivitySquare, BarChart3, BookOpenCheck, Database, FileText, Home, ShieldCheck, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { v3Api, v3DemoState, v3SafetyNotice } from '../lib/v3Api'
import type { PracticeState } from '../lib/types'

const modelAssignmentStorageKey = 'aris:model-task-assignment:v1'
const dailyPlanStorageKey = 'aris:practice:daily-target:v1'
const defaultDailyTarget = 50
const extractableDatasetTotal = 308894

type ModelTaskAssignments = {
  trainingTutorModelId?: string
  reportGenerationModelId?: string
  updatedAt?: string
}

const modelNames: Record<string, string> = {
  'agent-qwen': '平台智能助手 · 微调模型 Qwen',
  'agent-medgemma': '微调模型 MedGemma',
  'claude-opus': 'Claude Code opus 4.7',
  gpt55: 'GPT-5.5',
  'qwen3-8b': 'Qwen3-VL-8B',
}

function readModelAssignments(): ModelTaskAssignments {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(modelAssignmentStorageKey) || '{}') as ModelTaskAssignments
  } catch {
    return {}
  }
}

function readDailyTarget() {
  if (typeof window === 'undefined') return defaultDailyTarget
  const stored = Number(window.localStorage.getItem(dailyPlanStorageKey) || defaultDailyTarget)
  return Number.isFinite(stored) ? Math.max(defaultDailyTarget, stored) : defaultDailyTarget
}

const navItems = [
  { path: '/', label: '首页', icon: Home },
  { path: '/models', label: '模型', icon: BarChart3 },
  { path: '/practice', label: '研修', icon: BookOpenCheck },
  { path: '/report', label: '报告', icon: FileText },
  { path: '/profile', label: '画像', icon: UserRound },
]

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [state, setState] = useState<PracticeState>(v3DemoState)
  const [assignments, setAssignments] = useState<ModelTaskAssignments>(() => readModelAssignments())
  const [dailyTarget, setDailyTarget] = useState(() => readDailyTarget())

  useEffect(() => {
    let mounted = true
    v3Api.practiceState()
      .then((result) => {
        if (mounted) setState(result)
      })
      .catch(() => {
        if (mounted) setState(v3DemoState)
      })
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    const syncAssignments = () => setAssignments(readModelAssignments())
    const syncDailyTarget = () => setDailyTarget(readDailyTarget())
    window.addEventListener('storage', syncAssignments)
    window.addEventListener('model-assignment-change', syncAssignments)
    window.addEventListener('storage', syncDailyTarget)
    window.addEventListener('daily-plan-change', syncDailyTarget)
    return () => {
      window.removeEventListener('storage', syncAssignments)
      window.removeEventListener('model-assignment-change', syncAssignments)
      window.removeEventListener('storage', syncDailyTarget)
      window.removeEventListener('daily-plan-change', syncDailyTarget)
    }
  }, [])

  const progress = state.progress
  const physician = state.profile
  const isHome = location.pathname === '/'
  const assignedModelId = assignments.trainingTutorModelId || assignments.reportGenerationModelId
  const currentModel = assignedModelId ? modelNames[assignedModelId] || assignedModelId : '平台智能助手 · 微调模型 Qwen'
  const completedToday = progress?.completed ?? physician?.completed_today ?? 0
  const effectiveDailyTarget = Math.max(defaultDailyTarget, dailyTarget || progress?.target || physician?.daily_target || defaultDailyTarget)
  const effectiveProgressPercent = Math.min(100, Math.round((completedToday / effectiveDailyTarget) * 100))

  return (
    <div className="app-shell v3-shell">
      <aside className="sidebar v3-sidebar">
        <div className="brand v3-brand">
          <div className="brand-mark">
            <ActivitySquare size={22} />
          </div>
          <div>
            <strong>消化内镜研修与模型评测平台</strong>
            <span>医生教学研修与模型评测</span>
          </div>
        </div>

        <nav className="nav-list v3-nav" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon
            const active = item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path)
            return (
              <Link key={item.path} to={item.path} className={`nav-item ${active ? 'active' : ''}`}>
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        <div className="v3-sidebar-card">
          <span>今日刷题计划</span>
          <strong>{progress ? `${completedToday}/${effectiveDailyTarget}` : '--'}</strong>
          <div className="v3-mini-progress">
            <i style={{ width: `${effectiveProgressPercent}%` }} />
          </div>
          <small>{physician?.name || '医生'} · {progress?.review_queue ?? 0} 题待复盘</small>
        </div>

        <div className="sidebar-evidence live">
          <div className="sidebar-evidence-head">
            <Database size={16} />
            <div>
              <span>研修服务已连接</span>
              <strong>实时研修服务在线</strong>
            </div>
          </div>
          <div className="sidebar-evidence-grid">
            <div>
              <span>当前模型</span>
              <strong>{currentModel}</strong>
            </div>
            <div>
              <span>数据资源</span>
              <strong>{extractableDatasetTotal.toLocaleString('zh-CN')} 可提取</strong>
            </div>
            <div className="wide">
              <span>边界</span>
              <strong>教学研修</strong>
            </div>
          </div>
        </div>

        <div className="sidebar-note v3-safe-note">
          <ShieldCheck size={18} />
          <span>{v3SafetyNotice}</span>
        </div>
      </aside>

      <main className="main-area v3-main">
        <header className={`topbar v3-topbar ${isHome ? 'home-topbar' : 'section-topbar'}`}>
          <div className="top-title-block">
            <p className="top-kicker">面向消化道内镜医师</p>
            <h1>
              <span className="desktop-title">消化内镜研修与模型评测平台</span>
              <span className="mobile-title">内镜研修与模型评测</span>
            </h1>
          </div>
          <div className={`v3-top-actions ${isHome ? 'home-actions' : 'context-actions'}`}>
            <Link className="button secondary" to="/models">查看模型池</Link>
            <Link className="button primary" to="/practice">开始研修</Link>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}

import { ActivitySquare, BarChart3, BookOpenCheck, Bot, FileText, Home, ShieldCheck, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { v3Api, v3DemoState, v3SafetyNotice } from '../lib/v3Api'
import type { PracticeState } from '../lib/types'

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

  const physician = state.profile
  const isHome = location.pathname === '/'

  return (
    <div className="app-shell v3-shell">
      <aside className="sidebar v3-sidebar">
        <div className="brand v3-brand">
          <div className="brand-mark">
            <ActivitySquare size={22} />
          </div>
          <div>
            <strong>内镜智训 Agent</strong>
            <span>多模态医生研修演示</span>
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
          <span>主演示</span>
          <strong>Golden Demo 就绪</strong>
          <small>{physician?.name || '研修医师'} · 单病例可追溯闭环</small>
        </div>

        <div className="sidebar-evidence live">
          <div className="sidebar-evidence-head">
            <Bot size={16} />
            <div>
              <span>Agent 演示链路</span>
              <strong>{state.api_source === 'backend' ? '后端研修服务' : '本地演示回退'}</strong>
            </div>
          </div>
          <div className="sidebar-evidence-grid">
            <div>
              <span>主流程</span>
              <strong>观察 → 复盘 → 记忆</strong>
            </div>
            <div>
              <span>输出来源</span>
              <strong>提交后如实标注</strong>
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
              <span className="desktop-title">内镜智训 Agent · 医生研修工作台</span>
              <span className="mobile-title">内镜智训 Agent</span>
            </h1>
          </div>
          <div className={`v3-top-actions ${isHome ? 'home-actions' : 'context-actions'}`}>
            <Link className="button secondary" to="/models">模型评测实验室</Link>
            <Link className="button primary" to="/practice">演示病例</Link>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}

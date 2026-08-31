import { Activity, BarChart3, BookOpen, ClipboardCheck, LayoutDashboard } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: '学习总览', icon: LayoutDashboard, end: true },
  { to: '/banks', label: '题库', icon: BookOpen },
  { to: '/practice', label: '刷题', icon: ClipboardCheck },
  { to: '/eval', label: '模型评测', icon: BarChart3 },
]

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="s1-shell">
      <header className="s1-header">
        <NavLink className="s1-brand" to="/" aria-label="TiBan 学习总览">
          <span className="s1-brand-mark"><Activity size={19} /></span>
          <span>
            <strong>TiBan</strong>
            <small>自适应学习平台</small>
          </span>
        </NavLink>
        <nav className="s1-nav" aria-label="主导航">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => isActive ? 'is-active' : ''}>
              <Icon size={16} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <span className="s1-stage-badge"><span />v2.0 · 本地学习演示</span>
      </header>
      <main className="s1-main">{children}</main>
      <footer className="s1-footer">学习训练与复盘平台 · 请结合课程资料和教师指导</footer>
    </div>
  )
}

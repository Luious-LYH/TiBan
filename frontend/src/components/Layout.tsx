import { ActivitySquare, BookOpenCheck, FlaskConical, Workflow, Home, Library } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

// v2.2.1 四模块主导航
const navItems = [
  { path: '/', label: '学习总览', icon: Home, exact: true },
  { path: '/banks', label: '题库', icon: Library },
  { path: '/practice', label: '刷题工作台', icon: BookOpenCheck },
  { path: '/eval', label: '模型评测', icon: FlaskConical },
]

// 开发者入口（不在主导航显示，但保留兼容）
const devItems = [
  { path: '/workbench', label: 'Agent 工作台', icon: Workflow },
  { path: '/study', label: '过渡页', icon: BookOpenCheck },
]

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()

  // 检查是否在开发者页面
  const isDevPage = devItems.some(item => location.pathname.startsWith(item.path))

  return (
    <div className="v21-app-shell">
      <header className="v21-app-header">
        <Link className="v21-brand" to="/">
          <span><ActivitySquare size={20} /></span>
          <div><strong>EndoTutor</strong><small>内镜刷题 Agent</small></div>
        </Link>
        <nav className="v21-main-nav" aria-label="主导航">
          {navItems.map(({ path, label, icon: Icon, exact }) => {
            const active = exact
              ? location.pathname === path
              : location.pathname.startsWith(path)
            return <Link key={path} to={path} className={active ? 'is-active' : ''}><Icon size={16} />{label}</Link>
          })}
        </nav>
        <span className="v21-header-proof">
          {isDevPage ? 'v2.2 过渡页 · 开发中' : 'v2.2.1 · 四模块架构'}
        </span>
      </header>
      <main className="v21-app-main">{children}</main>
    </div>
  )
}

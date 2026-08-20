import { ActivitySquare, BookOpenCheck, FlaskConical, Workflow } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

const navItems = [
  { path: '/study', label: '研修中心', icon: BookOpenCheck },
  { path: '/workbench', label: 'Agent 工作台', icon: Workflow },
  { path: '/lab', label: '评测实验室', icon: FlaskConical },
]

export function Layout({ children }: { children: ReactNode }) {
  const location = useLocation()
  return (
    <div className="v21-app-shell">
      <header className="v21-app-header">
        <Link className="v21-brand" to="/study">
          <span><ActivitySquare size={20} /></span>
          <div><strong>内镜智训 Agent</strong><small>多模态医生研修</small></div>
        </Link>
        <nav className="v21-main-nav" aria-label="主导航">
          {navItems.map(({ path, label, icon: Icon }) => {
            const active = location.pathname.startsWith(path)
            return <Link key={path} to={path} className={active ? 'is-active' : ''}><Icon size={16} />{label}</Link>
          })}
        </nav>
        <span className="v21-header-proof">Portfolio v2.1 · 可追溯 Agent Run</span>
      </header>
      <main className="v21-app-main">{children}</main>
    </div>
  )
}

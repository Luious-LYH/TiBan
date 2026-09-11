import {
  BookOpen,
  ClipboardCheck,
  CircleAlert,
  GraduationCap,
  FlaskConical,
  Home,
  LibraryBig,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Settings,
  X,
} from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

type NavItem = { to?: string; label: string; icon: ComponentType<{ size?: number }>; queryKey?: string; queryValue?: string; disabled?: boolean }
type NavGroup = { label: string; items: NavItem[] }

const navGroups: NavGroup[] = [
  { label: '学习', items: [
    { to: '/', label: '学习首页', icon: Home },
    { to: '/banks', label: '题库', icon: BookOpen },
    { to: '/practice', label: '刷题', icon: ClipboardCheck },
    { to: '/review', label: '错题与复习', icon: CircleAlert },
  ] },
  { label: 'Agent', items: [{ to: '/mentor', label: '带教 Agent', icon: GraduationCap }] },
  { label: '题库工具', items: [{ to: '/factory', label: '题库导入', icon: Sparkles }] },
  { label: '知识', items: [{ to: '/knowledge', label: '知识库', icon: LibraryBig }] },
  { label: '模型', items: [{ to: '/eval', label: '评测实验室', icon: FlaskConical }] },
  { label: '系统', items: [{ to: '/settings', label: '设置', icon: Settings }] },
]

function isItemActive(item: NavItem, pathname: string, search: string) {
  if (!item.to) return false
  const params = new URLSearchParams(search)
  if (item.queryKey) return pathname === item.to.split('?')[0] && (params.get(item.queryKey) === item.queryValue || (item.queryKey === 'tab' && item.queryValue === 'retrieval' && !params.get('tab')))
  if (item.to === '/practice') return pathname === '/practice' && params.get('mode') !== 'review'
  if (item.to === '/knowledge') return pathname === '/knowledge' && params.get('view') !== 'imports'
  return pathname === item.to
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className={`app-shell ${collapsed ? 'is-collapsed' : ''} ${location.pathname === '/practice' ? 'is-practice-shell' : ''}`}>
      <button className={`app-sidebar-backdrop ${sidebarOpen ? 'is-visible' : ''}`} type="button" aria-label="关闭导航" onClick={() => setSidebarOpen(false)} />
      <aside className={`app-sidebar ${sidebarOpen ? 'is-open' : ''}`} aria-label="应用导航">
        <div className="app-brand-row">
          <Link className="app-brand" to="/" aria-label="题伴 TiBan 学习首页">
            <span className="app-brand-mark"><img className="app-brand-logo" src="/favicon.svg" alt="" aria-hidden="true" /></span>
            <span className="app-brand-copy"><strong>题伴</strong><small>TiBan · AI 题库与学习工作台</small></span>
          </Link>
          <button className="app-mobile-close" type="button" aria-label="关闭导航" onClick={() => setSidebarOpen(false)}><X size={18} /></button>
        </div>
        <div className="app-nav-scroll">
          <nav className="app-nav" aria-label="主导航">
            {navGroups.map((group) => <section className="app-nav-group" key={group.label}>
              <h2>{group.label}</h2>
              {group.items.map((item) => {
                const Icon = item.icon
                const active = isItemActive(item, location.pathname, location.search)
                if (item.disabled) return <span className="app-nav-item is-disabled" aria-disabled="true" key={item.label}><Icon size={16} /><span>{item.label}</span></span>
                return <Link className={`app-nav-item ${active ? 'is-active' : ''}`} to={item.to!} aria-current={active ? 'page' : undefined} key={item.to} onClick={() => setSidebarOpen(false)}><Icon size={16} /><span>{item.label}</span></Link>
              })}
            </section>)}
          </nav>
        </div>
        <div className="app-sidebar-footer"><span>TiBan · 学习与复盘</span></div>
      </aside>

      <div className="app-content">
        <header className="app-topbar">
          <div className="app-topbar-leading"><button className="app-menu-button" type="button" aria-label="打开导航" onClick={() => setSidebarOpen(true)}><Menu size={19} /></button><button className="app-collapse-button" type="button" aria-label={collapsed ? '展开导航' : '收起导航'} onClick={() => setCollapsed((value) => !value)}>{collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button><span className="app-context">{location.pathname === '/practice' ? '练习中' : '题伴 TiBan'}</span></div>
          <div className="app-topbar-actions" />
        </header>
        <main className={location.pathname === '/practice' ? 'app-main is-practice' : 'app-main'}>{children}</main>
      </div>
    </div>
  )
}

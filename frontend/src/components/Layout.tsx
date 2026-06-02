import {
  ActivitySquare,
  Brain,
  ClipboardList,
  FileText,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  MessageSquareText,
  ScrollText,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { safetyNotice } from '../lib/mock'

const navItems = [
  { path: '/', label: '首页总览', icon: LayoutDashboard },
  { path: '/training', label: '训练中心', icon: GraduationCap },
  { path: '/feedback', label: '错因分析', icon: Brain },
  { path: '/false-premise', label: '错误前提', icon: ShieldCheck },
  { path: '/report', label: '报告草稿', icon: FileText },
  { path: '/card', label: '科普卡片', icon: MessageSquareText },
  { path: '/models', label: '模型看板', icon: Gauge },
  { path: '/skills', label: 'Skills', icon: Sparkles },
  { path: '/audit', label: '审计日志', icon: ClipboardList },
]

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ActivitySquare size={22} />
          </div>
          <div>
            <strong>内镜智训Agent</strong>
            <span>Endo Tutor OS</span>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink key={item.path} to={item.path} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            )
          })}
        </nav>
        <div className="sidebar-note">
          <ScrollText size={18} />
          <span>Mock 数据与合成图像；真实评测流水线暂未启用。</span>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="top-kicker">面向消化道内镜医师培训的智能辅导平台</p>
            <h1>训练、解释、复核和审计在同一个闭环里</h1>
          </div>
          <div className="top-safety">
            <ShieldCheck size={18} />
            <span>{safetyNotice}</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}


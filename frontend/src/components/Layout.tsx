import {
  ActivitySquare,
  Brain,
  ChevronDown,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  Medal,
  MessageSquareText,
  Star,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Trophy,
  UserRound,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { safetyNotice } from '../lib/mock'

const navGroups = [
  {
    label: '训练中心',
    items: [
      { path: '/', label: '训练驾驶舱', icon: LayoutDashboard },
      { path: '/training', label: '题库刷题', icon: GraduationCap },
      { path: '/training?view=wrong', label: '错题本', icon: Brain },
      { path: '/training?view=favorite', label: '收藏夹', icon: Star },
      { path: '/training?mode=exam', label: '考试模式', icon: ClipboardList },
    ],
  },
  {
    label: '报告训练',
    items: [
      { path: '/report', label: '诊断报告中心', icon: FileText },
      { path: '/report?tab=judge', label: '报告修改训练', icon: ShieldCheck },
    ],
  },
  {
    label: '医师画像',
    items: [
      { path: '/profile', label: '能力画像', icon: UserRound },
      { path: '/profile?tab=records', label: '训练记录', icon: ActivitySquare },
    ],
  },
  {
    label: 'AI 比拼与激励',
    items: [
      { path: '/training?view=challenge', label: '医生 vs AI', icon: Trophy },
      { path: '/profile?tab=badges', label: '徽章与成长', icon: Medal },
    ],
  },
  {
    label: '模型准入与测试',
    items: [
      { path: '/models', label: '模型接入测试', icon: Gauge },
      { path: '/false-premise', label: '错误前提测试', icon: ShieldCheck },
    ],
  },
  {
    label: '教学资源',
    items: [
      { path: '/card', label: '科普卡片', icon: MessageSquareText },
      { path: '/training?source=public', label: '公开样例知识库', icon: Database },
    ],
  },
  {
    label: '管理与审计',
    items: [
      { path: '/skills', label: 'Skills', icon: Sparkles },
      { path: '/audit', label: '审计日志', icon: ClipboardList },
    ],
  },
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
          {navGroups.map((group) => (
            <details className="nav-group" key={group.label} open>
              <summary>
                <span>{group.label}</span>
                <ChevronDown size={14} />
              </summary>
              <div className="nav-group-items">
                {group.items.map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink key={item.path} to={item.path} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                      <Icon size={17} />
                      <span>{item.label}</span>
                    </NavLink>
                  )
                })}
              </div>
            </details>
          ))}
        </nav>
        <div className="sidebar-note">
          <ScrollText size={18} />
          <span>训练与报告输出均为教学/医生审核前辅助；模型准入为 mock 测试。</span>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="top-kicker">面向消化道内镜医师的持续训练平台</p>
            <h1>刷题、报告训练、Agent 辅导和能力成长在同一个工作台里</h1>
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

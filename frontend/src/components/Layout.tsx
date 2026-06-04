import {
  ActivitySquare,
  Brain,
  ChevronDown,
  ClipboardList,
  Database,
  DatabaseZap,
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
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { safetyNotice } from '../lib/mock'
import type { PlatformReadiness, ProviderStatus } from '../lib/types'

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
  const location = useLocation()
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null)
  const [readiness, setReadiness] = useState<PlatformReadiness | null>(null)

  useEffect(() => {
    let mounted = true
    let inFlight = false
    const refreshEvidence = async () => {
      if (inFlight) return
      inFlight = true
      try {
        const [statusResult, readinessResult] = await Promise.allSettled([
          api.providerStatus(),
          api.platformReadiness(),
        ])
        if (!mounted) return
        if (statusResult.status === 'fulfilled') {
          setProviderStatus(statusResult.value)
        } else {
          setProviderStatus({
            provider: 'frontend',
            model: 'unavailable',
            mode: 'fallback',
            ok: false,
            error: 'backend_unavailable',
          })
        }
        setReadiness(readinessResult.status === 'fulfilled' ? readinessResult.value : null)
      } finally {
        inFlight = false
      }
    }

    refreshEvidence()
    const timer = window.setInterval(refreshEvidence, 30000)
    return () => {
      mounted = false
      window.clearInterval(timer)
    }
  }, [])

  const providerConfigured = Boolean(providerStatus?.configured || providerStatus?.ok)
  const providerLabel = providerConfigured
    ? `${providerStatus?.provider || 'provider'} · ${providerStatus?.model || 'model'}`
    : providerStatus?.error === 'backend_unavailable'
      ? '后端未联通'
      : '规则/知识库模式'
  const readinessLive = Boolean(readiness && readiness.api_source !== 'fallback' && readiness.backend_ready)
  const readinessFallback = Boolean(readiness?.api_source === 'fallback')
  const evidenceMode = readiness?.provider_ready ? 'provider' : readiness?.provider_mode || providerStatus?.mode || 'checking'
  const evidenceSubtitle = readiness
    ? `${readinessFallback ? '前端 fallback · ' : ''}${readiness.real_sample_count} 图文样例 · ${readiness.audit_log_count} 审计`
    : '读取平台证据链中'
  const latestExamLabel = readiness?.latest_exam_replay
    ? `${readiness.latest_exam_replay.session_id} · ${readiness.latest_exam_replay.wrong_count} 错题`
    : '等待交卷'

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
                    <Link key={item.path} to={item.path} className={`nav-item ${isNavActive(item.path, location.pathname, location.search) ? 'active' : ''}`}>
                      <Icon size={17} />
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </div>
            </details>
          ))}
        </nav>
        <div className={`sidebar-evidence ${readinessLive ? 'live' : 'fallback'}`}>
          <div className="sidebar-evidence-head">
            <ActivitySquare size={17} />
            <div>
              <span>Live evidence</span>
              <strong>{readinessLive ? '后端证据在线' : '等待后端证据'}</strong>
            </div>
          </div>
          <div className="sidebar-evidence-grid">
            <div>
              <span>就绪度</span>
              <strong>{readiness ? `${readiness.overall_score}%` : '--'}</strong>
            </div>
            <div>
              <span>推理</span>
              <strong>{evidenceMode}</strong>
            </div>
            <div className="wide">
              <span>来源</span>
              <strong>{evidenceSubtitle}</strong>
            </div>
            <div className="wide">
              <span>考试复盘</span>
              <strong>{latestExamLabel}</strong>
            </div>
          </div>
          <div className="sidebar-evidence-actions">
            <Link to="/">
              <DatabaseZap size={14} /> 首页自检
            </Link>
            <Link to="/audit">
              <ClipboardList size={14} /> 审计
            </Link>
          </div>
        </div>
        <div className="sidebar-note">
          <ScrollText size={18} />
          <span>训练、报告与模型准入均标明 provider/rule/fallback 来源；所有医学输出仅供教学或医生审核前辅助。</span>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div>
            <p className="top-kicker">面向消化道内镜医师的持续训练平台</p>
            <h1>刷题、报告训练、Agent 辅导和能力成长在同一个工作台里</h1>
          </div>
          <div className="top-status-stack">
            <div className={`provider-pill ${providerConfigured ? 'online' : 'rule'}`}>
              <Gauge size={17} />
              <div>
                <span>Provider</span>
                <strong>{providerLabel}</strong>
                <em>{providerConfigured ? '真实调用通路可用' : '结果会显式标注规则或 fallback'}</em>
              </div>
            </div>
            <div className="top-safety">
              <ShieldCheck size={18} />
              <span>{safetyNotice}</span>
            </div>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}

function isNavActive(target: string, pathname: string, search: string): boolean {
  const [targetPathname, targetSearch = ''] = target.split('?')
  if (targetPathname !== pathname) return false
  return targetSearch ? search === `?${targetSearch}` : search === ''
}

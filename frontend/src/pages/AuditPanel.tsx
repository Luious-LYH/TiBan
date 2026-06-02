import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { ActivitySquare, AlertTriangle, ClipboardCheck, Filter, ScrollText, ShieldCheck } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockAuditLogs } from '../lib/mock'
import type { AuditLog } from '../lib/types'

const toneByRisk = {
  low: 'green',
  medium: 'amber',
  high: 'red',
} as const

type AuditFilter = 'all' | 'training' | 'report' | 'model' | 'skills' | 'high'

const filterLabels: { id: AuditFilter; label: string }[] = [
  { id: 'all', label: '全部' },
  { id: 'training', label: '训练闭环' },
  { id: 'report', label: '报告/卡片' },
  { id: 'model', label: '模型准入' },
  { id: 'skills', label: 'Skills' },
  { id: 'high', label: '高风险' },
]

export function AuditPanel() {
  const [logs, setLogs] = useState<AuditLog[]>(mockAuditLogs)
  const [filter, setFilter] = useState<AuditFilter>('all')

  useEffect(() => {
    api.audit().then((items) => setLogs(items))
  }, [])

  const stats = useMemo(() => {
    const highRisk = logs.filter((log) => log.risk_level === 'high').length
    const reviewRequired = logs.filter((log) => log.doctor_review_required).length
    const latest = logs[0]?.created_at ? new Date(logs[0].created_at).toLocaleString() : '暂无日志'
    return {
      total: logs.length,
      highRisk,
      reviewRequired,
      latest,
    }
  }, [logs])

  const filteredLogs = useMemo(() => logs.filter((log) => auditMatches(log, filter)), [filter, logs])

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">Audit memory</span>
          <h2>安全审计管理</h2>
          <p>记录题目查看、答题提交、考试交卷、辅导回复、报告草稿、科普卡片、模型选择和 skill 调用。</p>
        </div>
        <ScrollText size={42} />
      </Card>

      <div className="grid four">
        <AuditMetric icon={<ActivitySquare size={19} />} label="事件总量" value={`${stats.total} 条`} />
        <AuditMetric icon={<AlertTriangle size={19} />} label="高风险事件" value={`${stats.highRisk} 条`} tone="red" />
        <AuditMetric icon={<ShieldCheck size={19} />} label="需医生复核" value={`${stats.reviewRequired} 条`} tone="amber" />
        <AuditMetric icon={<ClipboardCheck size={19} />} label="最近写入" value={stats.latest} tone="blue" />
      </div>

      <Card className="audit-filter-card">
        <SectionTitle eyebrow="Audit cockpit" title="闭环事件筛选" action={<Filter size={20} />} />
        <div className="audit-filter-bar">
          {filterLabels.map((item) => (
            <button className={filter === item.id ? 'active' : ''} key={item.id} type="button" onClick={() => setFilter(item.id)}>
              {item.label}
            </button>
          ))}
        </div>
        <div className="audit-filter-note">
          <strong>{filteredLogs.length}</strong>
          <span>条事件匹配当前筛选。日志只记录事件摘要、风险等级和审核状态，不保存 API key 或医师自由追问原文。</span>
        </div>
      </Card>

      <Card>
        <SectionTitle eyebrow="Logs" title="关键事件" action={<Tag tone={filter === 'high' ? 'red' : 'blue'}>{filterLabels.find((item) => item.id === filter)?.label}</Tag>} />
        <div className="audit-table">
          <div className="audit-row audit-head">
            <span>时间</span>
            <span>事件</span>
            <span>摘要</span>
            <span>风险</span>
            <span>审核</span>
          </div>
          {filteredLogs.map((log) => (
            <div className="audit-row" key={log.id}>
              <span>{new Date(log.created_at).toLocaleString()}</span>
              <span>{eventLabel(log.event_type)}</span>
              <span>{log.summary}</span>
              <span><Tag tone={toneByRisk[log.risk_level]}>{log.risk_level}</Tag></span>
              <span>{log.doctor_review_required ? '需要' : '不需要'}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function AuditMetric({ icon, label, value, tone = 'green' }: { icon: ReactNode; label: string; value: string; tone?: 'green' | 'amber' | 'red' | 'blue' }) {
  return (
    <Card className={`audit-metric audit-metric-${tone}`}>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </Card>
  )
}

function auditMatches(log: AuditLog, filter: AuditFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'high') return log.risk_level === 'high'
  if (filter === 'training') return ['question_view', 'answer_submit', 'exam_session', 'tutor_reply', 'favorite_update'].includes(log.event_type)
  if (filter === 'report') return ['report_draft', 'report_judge', 'patient_card', 'image_upload'].includes(log.event_type)
  if (filter === 'model') return ['model_select', 'model_admission'].includes(log.event_type)
  if (filter === 'skills') return log.event_type === 'skill_run'
  return true
}

function eventLabel(type: AuditLog['event_type']): string {
  const labels: Record<AuditLog['event_type'], string> = {
    question_view: '查看题目',
    answer_submit: '提交答案',
    exam_session: '考试交卷',
    tutor_reply: 'Agent辅导',
    report_draft: '报告草稿',
    patient_card: '科普卡片',
    report_judge: '报告评分',
    skill_run: 'Skill运行',
    model_select: '模型选择',
    model_admission: '模型准入',
    favorite_update: '收藏更新',
    image_upload: '图片上传',
    safety_warning: '安全告警',
  }
  return labels[type] || type
}

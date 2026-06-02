import { useEffect, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockAuditLogs } from '../lib/mock'
import type { AuditLog } from '../lib/types'

const toneByRisk = {
  low: 'green',
  medium: 'amber',
  high: 'red',
} as const

export function AuditPanel() {
  const [logs, setLogs] = useState<AuditLog[]>(mockAuditLogs)

  useEffect(() => {
    api.audit().then((items) => setLogs(items))
  }, [])

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">Audit memory</span>
          <h2>安全审计管理</h2>
          <p>记录题目查看、答题提交、辅导回复、报告草稿、科普卡片、模型选择和 skill 调用。</p>
        </div>
        <ScrollText size={42} />
      </Card>
      <Card>
        <SectionTitle eyebrow="Logs" title="关键事件" />
        <div className="audit-table">
          <div className="audit-row audit-head">
            <span>时间</span>
            <span>事件</span>
            <span>摘要</span>
            <span>风险</span>
            <span>审核</span>
          </div>
          {logs.map((log) => (
            <div className="audit-row" key={log.id}>
              <span>{new Date(log.created_at).toLocaleString()}</span>
              <span>{log.event_type}</span>
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


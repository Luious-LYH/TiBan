import { useState } from 'react'
import { ClipboardCheck, FileText, WandSparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { ReportDraft as ReportDraftType } from '../lib/types'

export function ReportDraft() {
  const [text, setText] = useState('胃窦黏膜充血，可见散在糜烂。未见明确活动性出血。')
  const [draft, setDraft] = useState<ReportDraftType | null>(null)
  const [loading, setLoading] = useState(false)

  const generate = async () => {
    setLoading(true)
    setDraft(await api.reportDraft(text))
    setLoading(false)
  }

  return (
    <div className="page-stack">
      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Report agent" title="报告草稿辅助" />
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={8} />
          <button className="button primary" type="button" onClick={generate} disabled={loading}>
            <WandSparkles size={17} /> 生成结构化草稿
          </button>
        </Card>
        <Card>
          <SectionTitle eyebrow="Safety review" title="医生审核要求" />
          <div className="notice-card">
            <ClipboardCheck size={20} />
            <p>报告模块只整理医生输入，不自动补充未提供的病灶、病因或诊断。所有输出均为医生审核前草稿。</p>
          </div>
          <div className="tag-row">
            <Tag tone="red">doctor_review_required</Tag>
            <Tag tone="amber">不输出最终诊断</Tag>
            <Tag tone="blue">审计记录</Tag>
          </div>
        </Card>
      </div>

      {draft ? (
        <Card>
          <SectionTitle eyebrow="Draft" title="结构化报告草稿" action={<Tag tone="red">需医生审核</Tag>} />
          <div className="draft-grid">
            <DraftList icon={<FileText size={18} />} title="结构化所见" items={draft.structured_findings} />
            <DraftList icon={<ClipboardCheck size={18} />} title="草稿印象" items={draft.draft_impression} />
            <DraftList title="复核点" items={draft.review_points} />
            <DraftList title="不确定性说明" items={draft.uncertainty_notes} />
          </div>
          <div className="safety-mini">{draft.safety_notice}</div>
        </Card>
      ) : null}
    </div>
  )
}

function DraftList({ title, items, icon }: { title: string; items: string[]; icon?: React.ReactNode }) {
  return (
    <div className="draft-block">
      <h3>{icon}{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}


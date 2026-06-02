import { useEffect, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import { ClipboardCheck, FileImage, FileText, Gauge, ShieldCheck, WandSparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { KnowledgeBase, ReportDraft as ReportDraftType, ReportJudge } from '../lib/types'

export function ReportDraft() {
  const [findingText, setFindingText] = useState('胃窦黏膜充血，可见散在糜烂。未见明确活动性出血。')
  const [examType, setExamType] = useState('gastroscopy')
  const [templateName, setTemplateName] = useState('胃镜结构化训练模板')
  const [imageName, setImageName] = useState('')
  const [imagePreview, setImagePreview] = useState('')
  const [draft, setDraft] = useState<ReportDraftType | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeBase | null>(null)
  const [originalReport, setOriginalReport] = useState('本图明确证明患者患胃癌，建议立即治疗。')
  const [revisedReport, setRevisedReport] = useState('胃窦局部黏膜异常表现，建议医生结合完整检查、病史及必要病理结果复核。')
  const [judge, setJudge] = useState<ReportJudge | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.reportKnowledge().then((payload) => {
      setKnowledge(payload)
      const firstTemplate = payload.templates?.[0]?.name
      if (firstTemplate) setTemplateName(firstTemplate)
    })
  }, [])

  const onImage = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setImageName(file.name)
    setImagePreview(URL.createObjectURL(file))
  }

  const generate = async () => {
    setLoading(true)
    setDraft(await api.reportDraft(findingText, { examType, imageName, templateName }))
    setLoading(false)
  }

  const runJudge = async () => {
    setLoading(true)
    setJudge(await api.reportJudge(originalReport, revisedReport))
    setLoading(false)
  }

  return (
    <div className="page-stack">
      <Card className="focus-band report-focus">
        <div>
          <span className="eyebrow">Report training center</span>
          <h2>诊断报告中心</h2>
          <p>面向内镜医师训练结构化所见、诊断边界和审核前表达。可上传图片做演示占位，也可仅根据知识库模板生成训练报告。</p>
        </div>
        <FileText size={42} />
      </Card>

      <div className="grid two report-layout">
        <Card>
          <SectionTitle eyebrow="Image + findings" title="图像与所见输入" />
          <label className="upload-zone">
            <input type="file" accept="image/*" onChange={onImage} />
            {imagePreview ? <img src={imagePreview} alt="上传的内镜图片预览" /> : <FileImage size={34} />}
            <span>{imageName || '上传内镜图片，当前 demo 仅做预览占位'}</span>
          </label>
          <div className="form-row">
            <label>
              <span>检查类型</span>
              <select value={examType} onChange={(event) => setExamType(event.target.value)}>
                <option value="gastroscopy">胃镜</option>
                <option value="colonoscopy">肠镜</option>
              </select>
            </label>
            <label>
              <span>报告模板</span>
              <select value={templateName} onChange={(event) => setTemplateName(event.target.value)}>
                {knowledge?.templates?.filter((item) => item.name).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                {!knowledge ? <option value="胃镜结构化训练模板">胃镜结构化训练模板</option> : null}
              </select>
            </label>
          </div>
          <textarea value={findingText} onChange={(event) => setFindingText(event.target.value)} rows={7} />
          <button className="button primary" type="button" onClick={generate} disabled={loading}>
            <WandSparkles size={17} /> 生成结构化报告
          </button>
        </Card>

        <Card>
          <SectionTitle eyebrow="Template KB" title="报告模板知识库" action={<Tag tone="blue">公开样例 + demo 模板</Tag>} />
          <div className="knowledge-list">
            {knowledge?.templates?.map((template) => (
              <div key={template.name}>
                <strong>{template.name}</strong>
                <p>{template.sections?.join(' / ') || template.criteria?.join(' / ') || template.tone || '医生审核前训练模板'}</p>
              </div>
            ))}
          </div>
          <div className="notice-card">
            <ClipboardCheck size={20} />
            <p>报告中心只输出医生审核前训练模板，不独立生成最终诊断，不给治疗承诺。</p>
          </div>
        </Card>
      </div>

      {draft ? (
        <Card>
          <SectionTitle eyebrow={draft.template_name} title="结构化报告输出" action={<Tag tone="red">需医生审核</Tag>} />
          <div className="draft-grid">
            <DraftList icon={<FileText size={18} />} title="结构化所见" items={draft.structured_findings} />
            <DraftList icon={<ClipboardCheck size={18} />} title="草稿印象" items={draft.draft_impression} />
            <DraftList title="复核点" items={draft.review_points} />
            <DraftList title="不确定性说明" items={draft.uncertainty_notes} />
          </div>
          <div className="tag-row">
            {draft.evidence_source.map((item) => <Tag key={item} tone="blue">{item}</Tag>)}
          </div>
          <div className="safety-mini">{draft.safety_notice}</div>
        </Card>
      ) : null}

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="AI judge" title="报告修改训练" action={<Gauge size={20} />} />
          <label className="text-field">
            <span>待修改报告</span>
            <textarea value={originalReport} onChange={(event) => setOriginalReport(event.target.value)} rows={5} />
          </label>
          <label className="text-field">
            <span>医师修改稿</span>
            <textarea value={revisedReport} onChange={(event) => setRevisedReport(event.target.value)} rows={5} />
          </label>
          <button className="button primary" type="button" onClick={runJudge} disabled={loading}>
            <ShieldCheck size={17} /> AI judge 评分
          </button>
        </Card>

        <Card>
          <SectionTitle eyebrow="Feedback" title="评分与建议" />
          {judge ? (
            <>
              <div className="score-ring">
                <strong>{judge.score}</strong>
                <span>报告修改得分</span>
              </div>
              <div className="rubric-grid">
                {Object.entries(judge.rubric_scores).map(([name, score]) => (
                  <div key={name}><span>{name}</span><strong>{score}</strong></div>
                ))}
              </div>
              <DraftList title="优点" items={judge.strengths} />
              <DraftList title="需要修正" items={judge.issues} />
              <div className="next-card">{judge.suggested_revision}</div>
            </>
          ) : (
            <div className="empty-state">提交修改稿后，这里会显示 rubric 分数、风险表达和建议改写。</div>
          )}
        </Card>
      </div>
    </div>
  )
}

function DraftList({ title, items, icon }: { title: string; items: string[]; icon?: ReactNode }) {
  return (
    <div className="draft-block">
      <h3>{icon}{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}

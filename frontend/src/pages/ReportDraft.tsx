import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  ImagePlus,
  LoaderCircle,
  MessageSquareText,
  PenLine,
  ShieldCheck,
  Wand2,
} from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { GenerationMode, ProviderStatus, ReportDraft, ReportRevisionResponse, SourceTraceItem } from '../lib/types'

const defaultFinding = '胃窦黏膜充血，可见散在糜烂样改变，未见明确活动性出血。'
const defaultReportImageName = 'public_real_x1_0'
const defaultReportImageUrl = '/assets/real_samples/x1_clb0kvxvm90y4074yf50vf5nq.jpg'
const modelAssignmentStorageKey = 'aris:model-task-assignment:v1'

type ModelTaskAssignments = {
  trainingTutorModelId?: string
  reportGenerationModelId?: string
  updatedAt?: string
}

const fallbackModelNames: Record<string, string> = {
  'agent-qwen': '平台智能助手 · 微调模型 Qwen',
  'agent-medgemma': '微调模型 MedGemma',
  'claude-opus': 'Claude Code opus 4.7',
  gpt55: 'GPT-5.5',
  'qwen3-8b': 'Qwen3-VL-8B',
}

const sourceTone: Record<string, 'green' | 'blue' | 'amber' | 'neutral'> = {
  provider: 'green',
  rule: 'blue',
  fallback: 'amber',
}

function readModelAssignments(): ModelTaskAssignments {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(modelAssignmentStorageKey) || '{}') as ModelTaskAssignments
  } catch {
    return {}
  }
}

function providerModeLabel(mode?: GenerationMode | string | null) {
  if (mode === 'provider') return '智能辅助'
  if (mode === 'fallback') return '规范草稿'
  return '结构化草稿'
}

function providerDetail(status?: ProviderStatus | null) {
  if (!status) return '等待生成医生复核前草稿。'
  const latency = typeof status.latency_ms === 'number' ? ` · ${status.latency_ms}ms` : ''
  if (status.ok) return `已完成智能辅助草稿流程${latency}`
  return '医生复核前草稿流程已完成。'
}

function formatDraftText(result: ReportDraft) {
  return [
    '【内镜所见】',
    ...(result.structured_findings || []),
    '',
    '【印象建议】',
    ...(result.draft_impression || []),
    '',
    '【复核要点】',
    ...(result.review_points || []),
  ].join('\n')
}

function sourceItemsFromDraft(draft: ReportDraft | null): SourceTraceItem[] {
  if (!draft) return []
  if (draft.source_trace?.length) return draft.source_trace.filter((item) => item.used)
  return (draft.evidence_source || []).map((label, index) => ({
    source_type: index === 0 ? 'doctor_input' : draft.generation_mode || 'rule',
    label,
    used: true,
    detail: index === 0 ? '来自医生输入或上传材料。' : '用于结构化草稿整理。',
  }))
}

export function ReportDraft() {
  const [finding, setFinding] = useState(defaultFinding)
  const [imageName, setImageName] = useState<string | undefined>(defaultReportImageName)
  const [imagePreviewUrl, setImagePreviewUrl] = useState(defaultReportImageUrl)
  const [draft, setDraft] = useState<ReportDraft | null>(null)
  const [editableReport, setEditableReport] = useState('')
  const [instruction, setInstruction] = useState('更规范、更简洁，并补充医生复核边界')
  const [revision, setRevision] = useState<ReportRevisionResponse | null>(null)
  const [loading, setLoading] = useState<'draft' | 'revise' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [modelAssignments, setModelAssignments] = useState<ModelTaskAssignments>({})
  const outputRef = useRef<HTMLElement | null>(null)
  const reviseRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    const syncAssignments = () => setModelAssignments(readModelAssignments())
    syncAssignments()
    window.addEventListener('storage', syncAssignments)
    return () => window.removeEventListener('storage', syncAssignments)
  }, [])

  useEffect(() => {
    return () => {
      if (imagePreviewUrl.startsWith('blob:')) URL.revokeObjectURL(imagePreviewUrl)
    }
  }, [imagePreviewUrl])

  const reportText = useMemo(() => {
    if (!draft) return ''
    return formatDraftText(draft)
  }, [draft])

  const currentProviderStatus = revision?.provider_status || revision?.judge.provider_status || draft?.provider_status
  const currentMode = revision?.generation_mode || revision?.judge.generation_mode || draft?.generation_mode || 'rule'
  const reportModelId = modelAssignments.reportGenerationModelId
  const reportModelLabel = reportModelId ? fallbackModelNames[reportModelId] || reportModelId : '平台推荐默认'
  const draftSources = sourceItemsFromDraft(draft)
  const revisionSources = revision?.judge.source_trace?.length
    ? revision.judge.source_trace
    : revision?.source_trace?.length
      ? revision.source_trace
    : revision
      ? [{
          source_type: revision.generation_mode || revision.judge.generation_mode || 'rule',
          label: providerModeLabel(revision.generation_mode || revision.judge.generation_mode),
          used: true,
          detail: providerDetail(revision.provider_status || revision.judge.provider_status),
        }]
      : []

  const uploadImage = async (file: File | null) => {
    if (!file) return
    setError(null)
    const response = await v3Api.uploadReportImage(file)
    if (imagePreviewUrl.startsWith('blob:')) URL.revokeObjectURL(imagePreviewUrl)
    setImageName(response.image_name)
    setImagePreviewUrl(URL.createObjectURL(file))
  }

  const generateDraft = async () => {
    if (!imageName) {
      setError('请先上传内镜图片，再生成结构化报告草稿。')
      return
    }
    setLoading('draft')
    setError(null)
    try {
      const result = await v3Api.reportDraft(finding, { imageName })
      setDraft(result)
      setEditableReport(formatDraftText(result))
      setRevision(null)
      window.setTimeout(() => outputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } catch {
      setError('当前保留编辑区内容，可继续修改后重新生成。')
    } finally {
      setLoading(null)
    }
  }

  const reviseReport = async () => {
    setLoading('revise')
    setError(null)
    try {
      const result = await v3Api.reportRevise({
        originalReport: reportText || finding,
        currentReport: editableReport || reportText || finding,
        instruction,
      })
      setRevision(result)
      setEditableReport(result.revised_report)
      window.setTimeout(() => reviseRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } catch {
      setError('当前编辑区内容已保留，可继续手动调整或稍后再改写。')
    } finally {
      setLoading(null)
    }
  }

  return (
    <div className="page-stack v3-page">
      <section className="v3-page-hero report-hero">
        <div>
          <Tag tone="blue">报告辅助</Tag>
          <h2>从内镜图像到结构化报告草稿</h2>
          <p>医生提供图片或简短所见，系统生成规范草稿；医生可继续编辑，也可以按要求优化表达。</p>
        </div>
        <div className="v3-hero-score compact">
          <span>当前流程</span>
          <strong>输入 · 生成 · 修改</strong>
          <small>报告仅作为医生研修和复核前辅助</small>
        </div>
      </section>

      <Card className="report-agent-console">
        <SectionTitle
          eyebrow="生成状态"
          title="模型选择与生成来源"
          action={<Tag tone={sourceTone[String(currentMode)] || 'blue'}>{providerModeLabel(currentMode)}</Tag>}
        />
        <div className="report-agent-grid">
          <div>
            <Bot size={18} />
            <span>报告生成模型</span>
            <strong>{reportModelLabel}</strong>
            <p>{reportModelId ? '来自模型页的本地任务分配。' : '当前使用平台所选默认模型。'}</p>
          </div>
          <div>
            <Database size={18} />
            <span>生成链路</span>
            <strong>{loading ? '正在生成' : providerModeLabel(currentMode)}</strong>
            <p>{loading ? '正在整理医生复核前草稿。' : providerDetail(currentProviderStatus)}</p>
          </div>
          <div>
            <ClipboardCheck size={18} />
            <span>医生复核边界</span>
            <strong>{draft ? '必须医生复核' : '待生成草稿'}</strong>
            <p>{draft?.safety_notice || v3SafetyNotice}</p>
          </div>
        </div>
      </Card>

      <div className="report-v3-grid">
        <Card className="report-input-card">
          <SectionTitle eyebrow="输入" title="图像与所见" />
          <div className="report-image-preview">
            <img src={imagePreviewUrl} alt="报告草稿公开内镜样例" data-real-sample-image="true" data-real-sample-role="primary" />
            <span>{imageName === defaultReportImageName ? '默认公开教学样例，可直接生成草稿' : '已接收上传图片'}</span>
          </div>
          <label className="report-upload">
            <ImagePlus size={22} />
            <div>
              <strong>{imageName ? '图片已接收' : '上传内镜图片'}</strong>
              <span>{imageName || '必须先上传图片才能生成报告草稿'}</span>
            </div>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => uploadImage(event.target.files?.[0] || null)} />
          </label>
          <label className="v3-textarea-label">
            <span>简短所见</span>
            <textarea value={finding} onChange={(event) => setFinding(event.target.value)} rows={7} />
          </label>
          <button className="button primary" onClick={generateDraft} disabled={loading === 'draft'}>
            {loading === 'draft' ? <LoaderCircle size={16} className="spin" /> : <Wand2 size={16} />}
            生成报告草稿
          </button>
          {loading === 'draft' ? <ReportLoading label="正在生成报告草稿" steps={['读取医生输入', '匹配结构化模板', '标注来源与复核边界']} /> : null}
          {error ? <div className="report-inline-error"><AlertTriangle size={16} /> {error}</div> : null}
        </Card>

        <Card className="report-output-card" ref={outputRef}>
          <SectionTitle eyebrow="草稿" title="结构化报告" action={draft ? <Tag tone="green">草稿已生成</Tag> : null} />
          {draft ? (
            <>
              <div className="report-status-strip">
                <span><CheckCircle2 size={15} /> 结构完整</span>
                <span><ShieldCheck size={15} /> 保留复核边界</span>
                <span><FileText size={15} /> {draft.evidence_source?.length || 1} 项材料</span>
              </div>
              <SourceLedger title="草稿来源" items={draftSources} />
              <textarea className="report-editor" value={editableReport} onChange={(event) => setEditableReport(event.target.value)} rows={14} />
              <div className="report-review-points">
                {(draft.uncertainty_notes || []).slice(0, 2).map((item) => (
                  <span key={item}><FileText size={14} /> {item}</span>
                ))}
              </div>
            </>
          ) : (
            <div className="report-empty">
              <FileText size={34} />
              <p>生成后可直接编辑报告文本。</p>
            </div>
          )}
        </Card>
      </div>

      <Card className="report-revise-card" ref={reviseRef}>
        <SectionTitle eyebrow="智能修改" title="让报告更像规范草稿" />
        <div className="report-revise-row">
          <label>
            <span>修改要求</span>
            <input value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          </label>
          <button className="button secondary" onClick={reviseReport} disabled={!editableReport || loading === 'revise'}>
            {loading === 'revise' ? <LoaderCircle size={16} className="spin" /> : <PenLine size={16} />}
            修改报告
          </button>
        </div>
        {loading === 'revise' ? <ReportLoading label="正在修改并回写结构化草稿" steps={['读取当前编辑区', '按要求重写结构化表达', '更新草稿编辑区', '保留医生复核边界']} /> : null}
        {revision ? (
          <div className="report-revision-panel">
            <div className="report-revision-result">
              <MessageSquareText size={18} />
              <div>
                <strong>改写完成 · 已回写结构化报告草稿</strong>
                <p>以下文本已按“{revision.instruction}”更新，正式使用前仍需医生结合完整检查复核。</p>
              </div>
            </div>
            <label className="report-revised-text">
              <span>改写结果</span>
              <textarea value={revision.revised_report} readOnly rows={10} />
            </label>
            <SourceLedger title="修改来源" items={revisionSources} />
            <details className="report-quality-review">
              <summary>
                <ClipboardCheck size={17} />
                <span>审阅报告</span>
                <strong>{revision.judge.score} 分</strong>
              </summary>
              <div className="report-judge-grid">
                <div className="report-judge-score">
                  <strong>{revision.judge.score}</strong>
                  <span>评阅分数</span>
                </div>
                <div>
                  <h3>主要问题</h3>
                  <ul>
                    {(revision.judge.issues.length ? revision.judge.issues : ['修改稿已保留观察事实和复核边界。']).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h3>优点</h3>
                  <ul>
                    {(revision.judge.strengths.length ? revision.judge.strengths : ['报告表达已完成复核。']).map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="report-rubric-row">
                {Object.entries(revision.judge.rubric_scores).map(([key, value]) => (
                  <span key={key}><b>{value}</b>{key}</span>
                ))}
              </div>
              <p className="report-quality-note">{revision.privacy_status || '本次修改结果仅作为医生复核前辅助。'}</p>
            </details>
          </div>
        ) : null}
      </Card>

      <SafetyNotice text={draft?.safety_notice || v3SafetyNotice} />
    </div>
  )
}

function SourceLedger({ title, items }: { title: string; items: SourceTraceItem[] }) {
  const usedItems = items.filter((item) => item.used)
  if (!usedItems.length) return null
  return (
    <div className="report-source-ledger">
      <strong>{title}</strong>
      <div>
        {usedItems.slice(0, 4).map((item, index) => (
          <span key={`${item.label}-${index}`}>
            <b>来源</b>
            {item.label || item.source_type}
            <small>{item.detail || item.source_type}</small>
          </span>
        ))}
      </div>
    </div>
  )
}

function ReportLoading({ label, steps }: { label: string; steps: string[] }) {
  return (
    <div className="report-loading-state">
      <LoaderCircle size={16} className="spin" />
      <div>
        <strong>{label}</strong>
        <div>
          {steps.map((step) => <span key={step}>{step}</span>)}
        </div>
      </div>
    </div>
  )
}

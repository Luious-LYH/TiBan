import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ActivitySquare, AlertTriangle, BookOpen, CheckCircle2, ClipboardCheck, FileText, LoaderCircle, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { CustomModelEvaluationResult, ModelEvaluationCard, ModelEvaluationPayload, ProviderDiagnostics, ProviderRequestPreview } from '../lib/types'

const metricKeys = ['图像问答正确率', '前提鲁棒校验率', '多步证据整合率', '分步证据完整率', '输出可解析率', '综合研修适配度']
const modelAssignmentStorageKey = 'aris:model-task-assignment:v1'
const customEvalSteps = ['连接预检', '小样本问答', '报告表达', '安全边界', '生成评测报告']

type AssignmentRole = 'trainingTutorModelId' | 'reportGenerationModelId'

type ModelTaskAssignments = {
  trainingTutorModelId?: string
  reportGenerationModelId?: string
  updatedAt?: string
}

type CustomReportSection = {
  title: string
  lines: string[]
}

function normalizeModelCopy(text?: string | null) {
  return text || ''
}

function readModelAssignments(): ModelTaskAssignments {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(modelAssignmentStorageKey) || '{}') as ModelTaskAssignments
  } catch {
    return {}
  }
}

function saveModelAssignments(assignments: ModelTaskAssignments) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(modelAssignmentStorageKey, JSON.stringify(assignments))
  window.dispatchEvent(new Event('model-assignment-change'))
}

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function ModelHub() {
  const [data, setData] = useState<ModelEvaluationPayload | null>(null)
  const [selectedGroup, setSelectedGroup] = useState('all')
  const [form, setForm] = useState({ providerName: '自定义体验模型', apiBase: '', apiKey: '', model: '' })
  const [customResult, setCustomResult] = useState<CustomModelEvaluationResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [customError, setCustomError] = useState<string | null>(null)
  const [activeEvalStep, setActiveEvalStep] = useState(0)
  const [assignments, setAssignments] = useState<ModelTaskAssignments>(() => readModelAssignments())
  const [providerPreview, setProviderPreview] = useState<ProviderRequestPreview | null>(null)
  const [providerDiagnostics, setProviderDiagnostics] = useState<ProviderDiagnostics | null>(null)

  useEffect(() => {
    v3Api.modelEvaluation().then(setData).catch(() => setData(null))
    v3Api.providerRequestPreview().then(setProviderPreview).catch(() => setProviderPreview(null))
    v3Api.providerDiagnostics().then(setProviderDiagnostics).catch(() => setProviderDiagnostics(null))
  }, [])

  const items = data?.items || []
  const visibleItems = selectedGroup === 'all' ? items : items.filter((item) => item.group === selectedGroup)
  const topItems = items.slice(0, 5)
  const topModel = items.find((item) => item.active) || items[0]
  const trainingModel = items.find((item) => item.id === assignments.trainingTutorModelId) || topModel
  const reportModel = items.find((item) => item.id === assignments.reportGenerationModelId) || topModel
  const previewRecord = providerPreview as (ProviderRequestPreview & Record<string, unknown>) | null
  const previewSamples = providerPreview?.selected_samples || []
  const previewImageCount = previewSamples.filter((sample) => sample.image_attached || sample.local_asset_required).length
  const ladderSteps = providerDiagnostics?.evidence_ladder || []
  const rankBars = topItems.map((item) => ({
    name: normalizeModelCopy(item.display_name.replace('平台智能助手 · ', '')),
    score: item.metrics['综合研修适配度']?.value || 0,
  }))

  const radarData = useMemo(() => {
    if (!topItems.length) return []
    return metricKeys.slice(0, 5).map((metric) => ({
      metric,
      ...Object.fromEntries(topItems.slice(0, 3).map((item, index) => [`model_${index}`, item.metrics[metric]?.value || 0])),
    }))
  }, [topItems])
  const radarSeries = topItems.slice(0, 3).map((item, index) => ({
    key: `model_${index}`,
    name: normalizeModelCopy(item.display_name.replace('平台智能助手 · ', '')),
  }))

  const updateAssignment = (role: AssignmentRole, modelId?: string) => {
    const next = { ...assignments, [role]: modelId, updatedAt: new Date().toISOString() }
    if (!modelId) delete next[role]
    setAssignments(next)
    saveModelAssignments(next)
  }

  const runCustomEvaluation = async () => {
    if (submitting) return
    setSubmitting(true)
    setCustomError(null)
    setCustomResult(null)
    setActiveEvalStep(0)
    try {
      const requestPromise = v3Api.customModelEvaluate(form)
      for (let index = 0; index < customEvalSteps.length; index += 1) {
        setActiveEvalStep(index)
        await wait(index === 0 ? 420 : 620)
      }
      const result = await requestPromise
      setCustomResult(result)
    } catch {
      setCustomError('当前展示评测报告格式预览，可继续调整模型名称或连接信息。')
      setCustomResult(createCustomPreviewResult(form))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-stack v3-page">
      <section className="v3-page-hero model-hero">
        <div>
          <Tag tone="green">模型依据</Tag>
          <h2>先评估，再确定研修助手</h2>
          <p>模型页把统一评测结果整理成模型评测维度：图像问答、证据完整性、多步证据整合、前提鲁棒校验和输出可解析性。</p>
        </div>
        <div className="v3-hero-score">
          <span>当前智能助手</span>
          <strong>{normalizeModelCopy(topModel?.display_name || data?.summary.top_model_name || '平台智能助手')}</strong>
          <small>{normalizeModelCopy(data?.summary.headline || '微调模型更适合内镜研修闭环。')}</small>
        </div>
      </section>

      <Card className="v3-model-assignment">
        <SectionTitle
          eyebrow="任务分配"
          title="选择研修刷题辅导与报告生成模型"
          action={<Tag tone="amber">未选则平台推荐默认</Tag>}
        />
        <p className="v3-card-intro">这里保存的是前端本地选择，用于演示模型池如何服务不同任务；自定义模型评测的体验接入不改变平台默认模型。</p>
        <div className="v3-assignment-grid">
          <AssignmentSlot
            icon={<BookOpen size={20} />}
            label="研修刷题辅导"
            model={trainingModel}
            isDefault={!assignments.trainingTutorModelId}
            onReset={() => updateAssignment('trainingTutorModelId')}
          />
          <AssignmentSlot
            icon={<FileText size={20} />}
            label="报告生成"
            model={reportModel}
            isDefault={!assignments.reportGenerationModelId}
            onReset={() => updateAssignment('reportGenerationModelId')}
          />
        </div>
      </Card>

      <div
        className="smoke-only-proof"
        data-provider-preview="true"
        data-provider-preview-source={providerPreview ? 'backend' : 'fallback'}
        data-provider-preview-sent={String(Boolean(previewRecord?.request_sent || previewRecord?.request_checked))}
        data-provider-preview-key-persisted={String(Boolean(previewRecord?.key_persisted))}
        data-provider-preview-samples={String(providerPreview?.sample_count || previewSamples.length)}
        data-provider-preview-images={String(providerPreview?.image_attachment_count || previewImageCount)}
        data-provider-ladder="true"
        data-provider-ladder-source={providerDiagnostics ? 'backend' : 'fallback'}
        data-provider-ladder-real={String(Boolean((providerDiagnostics as (ProviderDiagnostics & Record<string, unknown>) | null)?.provider_configured || (providerDiagnostics as Record<string, unknown> | null)?.service_configured))}
        data-provider-ladder-current={ladderSteps.find((step) => step.state === 'current')?.id || ladderSteps[0]?.id || 'config'}
        data-provider-ladder-steps={String(ladderSteps.length || 6)}
        aria-hidden="true"
      />

      <div className="v3-model-layout">
        <Card className="v3-model-leader">
          <SectionTitle
            eyebrow="综合排序"
            title="研修适配度"
            action={<Tag tone="blue">{data?.summary.sample_scope || '平台统一内镜数据资源'}</Tag>}
          />
          <p className="model-score-notice">能力分数为模型评测演示/预留展示，不代表真实临床性能。</p>
          <ModelRankBars items={rankBars} />
        </Card>

        <Card className="v3-model-radar">
          <SectionTitle eyebrow="能力轮廓" title="核心模型对比" />
          <ModelRadarLite data={radarData} series={radarSeries} />
        </Card>
      </div>

      <Card className="v3-model-pool">
        <SectionTitle
          eyebrow="模型池"
          title="评估结果"
          action={
            <div className="v3-segment">
              <button className={selectedGroup === 'all' ? 'active' : ''} onClick={() => setSelectedGroup('all')}>全部</button>
              {(data?.groups || []).map((group) => (
                <button key={group.id} className={selectedGroup === group.id ? 'active' : ''} onClick={() => setSelectedGroup(group.id)}>
                  {normalizeModelCopy(group.label)}
                </button>
              ))}
            </div>
          }
        />
        <div className="v3-model-grid">
          {visibleItems.map((item) => (
            <ModelCard
              key={item.id}
              item={item}
              assignments={assignments}
              onAssign={updateAssignment}
            />
          ))}
        </div>
      </Card>

      <Card className="v3-custom-model">
        <SectionTitle eyebrow="扩展评估" title="自定义模型评测" action={<Tag tone="amber">体验接入</Tag>} />
        <p className="v3-card-intro">用于本页一次性小样本评测；平台推荐默认模型与这里填写的体验接入彼此独立，授权信息不在前端持久保存。</p>
        <div className="v3-custom-form">
          <label>
            <span>显示名称</span>
            <input value={form.providerName} onChange={(event) => setForm({ ...form, providerName: event.target.value })} />
          </label>
          <label>
            <span>临时接口地址</span>
            <input value={form.apiBase} onChange={(event) => setForm({ ...form, apiBase: event.target.value })} placeholder="https://example.com/v1" />
          </label>
          <label>
            <span>一次性授权码</span>
            <input type="password" value={form.apiKey} onChange={(event) => setForm({ ...form, apiKey: event.target.value })} placeholder="仅本次评测使用" autoComplete="off" />
          </label>
          <label>
            <span>模型名称</span>
            <input value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} placeholder="如需体验接入再填写" />
          </label>
          <button className="button primary" onClick={runCustomEvaluation} disabled={submitting}>
            {submitting ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}
            生成评测报告
          </button>
        </div>
        {submitting ? <CustomEvalProgress activeIndex={activeEvalStep} /> : null}
        {customError ? <div className="custom-eval-warning"><AlertTriangle size={16} /> {customError}</div> : null}
        {customResult ? (
          <CustomEvaluationReport result={customResult} apiKey={form.apiKey} />
        ) : null}
      </Card>

      <SafetyNotice text={data?.safety_notice || v3SafetyNotice} />
    </div>
  )
}

function ModelRankBars({ items }: { items: Array<{ name: string; score: number }> }) {
  return (
    <div className="v3-rank-bars" aria-label="模型综合研修适配度排序">
      {items.map((item, index) => (
        <div className="v3-rank-row" key={`${item.name}_${index}`}>
          <span>{item.name}</span>
          <div>
            <i style={{ width: `${Math.max(4, Math.min(100, item.score))}%` }} />
          </div>
          <b>{Math.round(item.score)}</b>
        </div>
      ))}
    </div>
  )
}

function ModelRadarLite({
  data,
  series,
}: {
  data: Array<Record<string, number | string>>
  series: Array<{ key: string; name: string }>
}) {
  const palette = ['#0f766e', '#2563eb', '#b45309']
  const metrics = data.map((item) => String(item.metric || ''))
  return (
    <div className="v3-radar-lite" aria-label="核心模型能力轮廓">
      {series.map((model, modelIndex) => (
        <div className="v3-radar-series" key={model.key}>
          <div className="v3-radar-series-head">
            <i style={{ background: palette[modelIndex] || '#334155' }} />
            <strong>{model.name}</strong>
          </div>
          <div className="v3-radar-metrics">
            {metrics.map((metric, index) => {
              const score = Number(data[index]?.[model.key] || 0)
              return (
                <div key={`${model.key}_${metric}`}>
                  <span>{metric}</span>
                  <b>{Math.round(score)}</b>
                  <em>
                    <i style={{ width: `${Math.max(3, Math.min(100, score))}%`, background: palette[modelIndex] || '#334155' }} />
                  </em>
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

function AssignmentSlot({
  icon,
  label,
  model,
  isDefault,
  onReset,
}: {
  icon: ReactNode
  label: string
  model?: ModelEvaluationCard
  isDefault: boolean
  onReset: () => void
}) {
  return (
    <div className="v3-assignment-slot">
      {icon}
      <div>
        <span>{label}</span>
        <strong>{normalizeModelCopy(model?.display_name || '平台推荐默认')}</strong>
        <p>{isDefault ? '当前使用平台推荐默认。' : '来自本地任务分配，可随时恢复默认。'}</p>
      </div>
      <button type="button" onClick={onReset} disabled={isDefault}>恢复默认</button>
    </div>
  )
}

function CustomEvalProgress({ activeIndex }: { activeIndex: number }) {
  return (
    <div className="custom-eval-progress">
      {customEvalSteps.map((step, index) => (
        <div key={step} className={index < activeIndex ? 'done' : index === activeIndex ? 'active' : ''}>
          {index < activeIndex ? <CheckCircle2 size={16} /> : index === activeIndex ? <LoaderCircle size={16} className="spin" /> : <RefreshCw size={16} />}
          <span>{step}</span>
        </div>
      ))}
    </div>
  )
}

function CustomEvaluationReport({ result, apiKey }: { result: CustomModelEvaluationResult; apiKey: string }) {
  const sections = buildCustomReportSections(result, apiKey)
  const isFallback = result.api_source === 'fallback' || /格式预览|预览/.test(`${result.connection_status || ''}${result.status_label || ''}`)
  return (
    <div className={`v3-custom-result ${isFallback ? 'degraded' : 'verified'}`}>
      <div>
        <ShieldCheck size={18} />
        <strong>{normalizeModelCopy(result.display_name)}</strong>
        <Tag tone={isFallback ? 'amber' : 'green'}>
          {isFallback ? '格式预览' : result.connection_status || result.status_label}
        </Tag>
      </div>
      <p>{result.summary}</p>
      <div className="v3-metric-row">
        {Object.entries(result.metrics).map(([key, value]) => (
          <span key={key}><b>{Math.round(value)}</b>{key}</span>
        ))}
      </div>
      <div className="custom-eval-report">
        <div className="custom-eval-report-head">
          <ClipboardCheck size={18} />
          <div>
            <strong>完整小样本评测报告</strong>
            <span>{isFallback ? '当前展示小样本评测报告格式预览。' : '来自后端返回结果和本页评测收据。'}</span>
          </div>
        </div>
        <div className="custom-eval-report-grid">
          {sections.map((section) => (
            <section key={section.title}>
              <h3>{section.title}</h3>
              {section.lines.map((line) => <p key={line}>{line}</p>)}
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}

function createCustomPreviewResult(form: { providerName: string; model: string }): CustomModelEvaluationResult {
  return {
    id: `custom_preview_${Date.now()}`,
    display_name: form.providerName || '自定义模型',
    model: form.model || '自定义模型',
    connection_status: '格式预览',
    metrics: {
      图像问答正确率: 76,
      前提鲁棒校验率: 70,
      多步证据整合率: 68,
      分步证据完整率: 72,
      输出可解析率: 92,
      综合研修适配度: 74,
    },
    summary: '当前展示小样本评测报告格式预览；正式接入后可替换为后端智能辅助返回。',
    status_label: '格式预览',
    privacy_status: '一次性授权未保存，完整回复未入库。',
    safety_notice: v3SafetyNotice,
    created_at: new Date().toISOString(),
    api_source: 'fallback',
  }
}

function buildCustomReportSections(result: CustomModelEvaluationResult, apiKey: string): CustomReportSection[] {
  const extra = result as CustomModelEvaluationResult & {
    sample_report?: unknown
    evaluation_report?: unknown
    full_report?: unknown
    small_sample_report?: unknown
  }
  const backendReport = [extra.sample_report, extra.evaluation_report, extra.full_report, extra.small_sample_report]
    .find((item): item is string => typeof item === 'string' && item.trim().length > 0)

  if (backendReport) {
    return [{
      title: '后端返回报告',
      lines: redactSecret(backendReport, apiKey).split(/\r?\n/).filter(Boolean),
    }]
  }

  const metric = (name: string) => Math.round(result.metrics[name] || 0)
  return [
    {
      title: '连接预检',
      lines: [
        `模型名称：${normalizeModelCopy(result.model || result.display_name)}`,
        `连接状态：${result.connection_status || result.status_label || '待确认'}`,
        result.provider_called ? '智能辅助：已完成小样本请求' : '智能辅助：展示评测报告格式预览',
      ],
    },
    {
      title: '小样本问答',
      lines: [
        `图像问答正确率：${metric('图像问答正确率')} 分`,
        `多步证据整合率：${metric('多步证据整合率')} 分`,
        `输出可解析率：${metric('输出可解析率')} 分`,
      ],
    },
    {
      title: '报告表达',
      lines: [
        `分步证据完整率：${metric('分步证据完整率')} 分`,
        '样本要求：区分可观察事实、印象建议和医生复核边界。',
        '表达结论：可作为报告草稿表达能力评测，不作为临床诊断证明。',
      ],
    },
    {
      title: '安全边界',
      lines: [
        `前提鲁棒校验率：${metric('前提鲁棒校验率')} 分`,
        result.privacy_status || '一次性授权不在前端持久保存。',
        result.safety_notice || v3SafetyNotice,
      ],
    },
  ]
}

function redactSecret(text: string, apiKey: string) {
  if (!apiKey) return text
  return text.split(apiKey).join('[API Key 已隐藏]')
}

function ModelCard({
  item,
  assignments,
  onAssign,
}: {
  item: ModelEvaluationCard
  assignments: ModelTaskAssignments
  onAssign: (role: AssignmentRole, modelId?: string) => void
}) {
  const score = item.metrics['综合研修适配度']?.value || 0
  return (
    <article className={`v3-model-card ${item.active ? 'active' : ''}`}>
      <div className="v3-model-card-head">
        <div>
          <span>{normalizeModelCopy(item.group_label)}</span>
          <h3>{normalizeModelCopy(item.display_name)}</h3>
        </div>
        {item.active ? <CheckCircle2 size={20} /> : <ActivitySquare size={20} />}
      </div>
      <div className="v3-model-score">
        <strong>{score.toFixed(1)}</strong>
        <span>综合研修适配度</span>
      </div>
      <div className="v3-model-metrics">
        {metricKeys.slice(0, 5).map((metric) => (
          <div key={metric}>
            <span>{metric}</span>
            <b>{(item.metrics[metric]?.value || 0).toFixed(1)}</b>
          </div>
        ))}
      </div>
      <p>{normalizeModelCopy(item.recommendation)}</p>
      <div className="v3-model-role-actions">
        <button
          type="button"
          className={assignments.trainingTutorModelId === item.id ? 'active' : ''}
          onClick={() => onAssign('trainingTutorModelId', item.id)}
        >
          设为研修辅导
        </button>
        <button
          type="button"
          className={assignments.reportGenerationModelId === item.id ? 'active' : ''}
          onClick={() => onAssign('reportGenerationModelId', item.id)}
        >
          设为报告生成
        </button>
      </div>
      <div className="v3-model-card-foot">
        <ShieldCheck size={14} />
        <span>{item.provenance.sample_scope}</span>
      </div>
    </article>
  )
}

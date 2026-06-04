import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ActivitySquare, AlertTriangle, ArrowRight, CheckCircle2, Database, FileCheck2, KeyRound, LoaderCircle, PlugZap, ShieldAlert, ShieldCheck, TestTube2 } from 'lucide-react'
import { ProviderPreflightPanel } from '../components/ProviderPreflightPanel'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockModels } from '../lib/mock'
import type { ModelAdmissionResult, ModelAdmissionState, ModelProfile, ProviderDiagnostics, ProviderEvidenceReceipt, ProviderPreflight, ProviderPreviewMode, ProviderRequestPreview, ProviderSelfTestResult, ProviderStatus, Question } from '../lib/types'

const scoreLabels: Record<string, string> = {
  basic_recognition: '基础识别',
  complex_reasoning: '复杂推理',
  false_premise: '错误前提',
  chinese_report: '中文报告',
  engineering: '工程稳定',
}

const focusItems = ['基础识别', '复杂推理', '错误前提', '报告安全', '接口稳定']
const previewModeLabels: Record<ProviderPreviewMode, string> = {
  text_self_test: '文本自检预演',
  visual_self_test: '视觉自检预演',
  admission: '样例准入预演',
}

function admissionSampleId(sampleId: string): string {
  return sampleId.startsWith('public_') ? sampleId.slice('public_'.length) : sampleId
}

function receiptTimeLabel(value?: string): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function ReceiptTraceChips({
  title,
  items,
}: {
  title: string
  items?: { label: string; used: boolean; detail: string; latency_ms?: number | null }[]
}) {
  if (!items?.length) return null
  return (
    <div className="provider-trace-block">
      <strong>{title}</strong>
      <div>
        {items.map((item, index) => (
          <span className={item.used ? 'used' : ''} key={`${title}_${item.label}_${index}`}>
            <em>{item.label}{item.latency_ms ? ` · ${item.latency_ms}ms` : ''}</em>
            <small>{item.detail}</small>
          </span>
        ))}
      </div>
    </div>
  )
}

function ProviderReceiptPanel({
  receipt,
  fallback,
  title,
}: {
  receipt?: ProviderEvidenceReceipt | null
  fallback: boolean
  title: string
}) {
  if (!receipt) return null
  const isAdmission = receipt.event_type === 'model_admission'
  const stateLabel = receipt.state_kind === 'provider_admission'
    ? 'Provider 准入摘要'
    : receipt.state_kind === 'rule_draft'
      ? '规则草案摘要'
      : receipt.platform_state_updated
        ? '已更新摘要'
        : '未更新'
  return (
    <div className={`provider-receipt ${fallback || !receipt.audit_log_id ? 'fallback' : 'synced'}`}>
      <div className="provider-receipt-head">
        <FileCheck2 size={20} />
        <div>
          <strong>{fallback || !receipt.audit_log_id ? title.replace('后端', '本地') : title}</strong>
          <span>
            {receipt.audit_log_id
              ? `已写入 ${receipt.event_type || 'provider_event'} 审计：${receipt.audit_log_id}`
              : '当前没有后端审计 ID；仅作前端预览。'}
          </span>
        </div>
      </div>
      <div className="provider-receipt-metrics">
        <div>
          <span>Provider 调用</span>
          <strong>{receipt.provider_called ? '已调用' : '未调用'}</strong>
        </div>
        <div>
          <span>{isAdmission ? '平台状态' : '图片附加'}</span>
          <strong>
            {isAdmission
              ? stateLabel
              : receipt.visual_probe ? (receipt.image_attached ? '已附加公开图' : '未附加') : '文本自检'}
          </strong>
        </div>
        <div>
          <span>{isAdmission ? '准入分' : '收据时间'}</span>
          <strong>{isAdmission ? `Grade ${receipt.grade || '-'} · ${receipt.total_score ?? '-'}` : receiptTimeLabel(receipt.created_at)}</strong>
        </div>
      </div>
      {isAdmission ? (
        <div className="provider-receipt-metrics compact">
          <div>
            <span>收据时间</span>
            <strong>{receiptTimeLabel(receipt.created_at)}</strong>
          </div>
          <div>
            <span>准入 ID</span>
            <strong>{receipt.admission_id || '未记录'}</strong>
          </div>
          <div>
            <span>Provider</span>
            <strong>{receipt.provider_name || '未记录'}</strong>
          </div>
        </div>
      ) : null}
      <ReceiptTraceChips title="输入来源" items={receipt.input_trace} />
      <ReceiptTraceChips title="Provider 来源" items={receipt.provider_trace} />
      <ReceiptTraceChips title="隐私边界" items={receipt.privacy_trace} />
      {receipt.next_actions?.length ? (
        <div className="provider-receipt-actions">
          {receipt.next_actions.map((action) => (
            <Link to={action.href || '/models'} key={`${action.label}_${action.href}`}>
              {action.label} <ArrowRight size={14} />
            </Link>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ProviderDiagnosticsCard({ diagnostics }: { diagnostics: ProviderDiagnostics }) {
  const configured = diagnostics.provider_configured
  const fallback = diagnostics.api_source === 'fallback'
  const auditRows = [
    { label: '最近自检', item: diagnostics.latest_self_test },
    { label: '最近准入', item: diagnostics.latest_admission },
  ]
  return (
    <Card className={`provider-diagnostics-card ${configured ? 'synced' : 'fallback'}`}>
      <SectionTitle
        eyebrow="Provider check"
        title="Provider 联调状态检查"
        action={<Tag tone={configured ? 'green' : fallback ? 'red' : 'amber'}>{configured ? 'provider configured' : fallback ? 'frontend fallback' : diagnostics.provider_mode}</Tag>}
      />
      <div className="provider-diagnostics-main">
        {configured ? <ShieldCheck size={24} /> : <AlertTriangle size={24} />}
        <div>
          <strong>{diagnostics.blocking_reason}</strong>
          <span>
            缺失项：{diagnostics.missing.length ? diagnostics.missing.join(' / ') : '无'}。{diagnostics.privacy_notice}
          </span>
        </div>
      </div>
      <div className="status-grid provider-diagnostics-grid">
        <div><span>公开样例</span><strong>{diagnostics.public_sample_count}</strong></div>
        <div><span>Base</span><strong>{diagnostics.base_url_configured ? '已配置' : '未配置'}</strong></div>
        <div><span>Key</span><strong>{diagnostics.api_key_configured ? '已配置' : '未配置'}</strong></div>
        <div><span>准入摘要</span><strong>{diagnostics.admission_state.provider_called ? 'provider called' : 'rule draft'}</strong></div>
      </div>
      <div className="provider-diagnostic-actions">
        {diagnostics.next_actions.map((action) => (
          <Link className={action.done ? 'done' : ''} to={action.href || '/models'} key={`${action.label}_${action.href}`}>
            <span>{action.done ? '已完成' : '待处理'}</span>
            <strong>{action.label}</strong>
            <small>{action.detail}</small>
          </Link>
        ))}
      </div>
      <div className="provider-diagnostic-audits">
        {auditRows.map(({ label, item }) => (
          <div className={item?.id ? 'synced' : ''} key={label}>
            <span>{label}</span>
            <strong>{item?.summary || '未记录后端审计'}</strong>
            <small>{item?.id || 'audit_id: -'} · {receiptTimeLabel(item?.created_at || undefined)}</small>
          </div>
        ))}
      </div>
      <div className="source-note">{diagnostics.admission_state.recommendation} {diagnostics.safety_notice}</div>
    </Card>
  )
}

function ProviderDiagnosticsLoadingCard() {
  return (
    <Card className="provider-diagnostics-card loading">
      <SectionTitle
        eyebrow="Provider check"
        title="Provider 联调状态检查"
        action={<Tag tone="amber">checking</Tag>}
      />
      <div className="provider-diagnostics-main">
        <LoaderCircle className="spin-icon" size={24} />
        <div>
          <strong>正在读取后端 Provider 联调状态检查</strong>
          <span>页面会确认当前是 provider、rule 还是 fallback，并展示缺失配置、公开样例数量、最近审计摘要和隐私边界。</span>
        </div>
      </div>
    </Card>
  )
}

function ProviderRequestPreviewCard({
  preview,
  loading,
  mode,
  setMode,
}: {
  preview: ProviderRequestPreview | null
  loading: boolean
  mode: ProviderPreviewMode
  setMode: (mode: ProviderPreviewMode) => void
}) {
  const fallback = preview?.api_source === 'fallback'
  const ready = Boolean(preview?.ready_for_provider_call)
  const source = preview?.api_source || (loading ? 'checking' : 'not_loaded')
  return (
    <Card
      className={`provider-request-preview-card ${fallback ? 'fallback' : ready ? 'synced' : 'blocked'}`}
      data-provider-preview="true"
      data-provider-preview-source={source}
      data-provider-preview-sent={String(Boolean(preview?.request_sent))}
      data-provider-preview-key-persisted={String(Boolean(preview?.key_persisted))}
      data-provider-preview-samples={preview?.sample_count || 0}
      data-provider-preview-images={preview?.image_attachment_count || 0}
    >
      <SectionTitle
        eyebrow="Dry-run receipt"
        title="Provider 请求预演包"
        action={<Tag tone={fallback ? 'red' : ready ? 'green' : 'amber'}>{loading ? 'checking' : preview ? (ready ? 'ready' : preview.blocked_reason || 'blocked') : 'waiting'}</Tag>}
      />
      <div className="preview-mode-tabs" role="tablist" aria-label="Provider 请求预演模式">
        {(Object.keys(previewModeLabels) as ProviderPreviewMode[]).map((item) => (
          <button className={mode === item ? 'active' : ''} type="button" onClick={() => setMode(item)} key={item}>
            {previewModeLabels[item]}
          </button>
        ))}
      </div>
      <div className="provider-preview-banner">
        {loading ? <LoaderCircle className="spin-icon" size={20} /> : ready ? <ShieldCheck size={20} /> : <AlertTriangle size={20} />}
        <div>
          <strong>{loading ? '正在生成后端 dry-run 请求收据' : preview ? `${previewModeLabels[preview.preview_mode]} · ${source}` : '等待后端预演结果'}</strong>
          <span>
            {preview
              ? `不会发送 Provider 请求：${preview.request_sent ? '异常，已发送' : '确认未发送'}；不会保存 key：${preview.key_persisted ? '异常' : '确认未保存'}；不会发送参考答案：${preview.reference_answer_sent ? '异常' : '确认未发送'}。`
              : '该收据用于展示后端将如何构造真实 Provider 请求，而不是前端静态文案。'}
          </span>
        </div>
      </div>
      {preview ? (
        <>
          <div className="provider-preview-grid">
            <div><span>endpoint path</span><strong>{preview.endpoint_paths.join(' / ') || preview.blocked_reason || '待配置'}</strong></div>
            <div><span>样例数</span><strong>{preview.sample_count}</strong></div>
            <div><span>图片附加</span><strong>{preview.image_attachment_count}</strong></div>
            <div><span>key 来源</span><strong>{preview.api_key_present ? '页面临时 key' : preview.backend_env_key_available ? '后端 .env key' : '未提供'}</strong></div>
          </div>
          <div className="provider-preview-fields">
            <span>请求体字段</span>
            <div>{preview.request_body_fields.map((field) => <strong key={field}>{field}</strong>)}</div>
          </div>
          <div className="provider-preview-message-plan">
            {preview.message_plan.map((item, index) => (
              <div key={`${item.role}_${index}`}>
                <span>{item.role}{item.image ? ' · image_url' : ''}</span>
                <strong>{item.contains}</strong>
                {item.sample_ids?.length ? <small>{item.sample_ids.join(' / ')}</small> : null}
              </div>
            ))}
          </div>
          {preview.selected_samples.length ? (
            <div className="provider-preview-samples">
              {preview.selected_samples.map((sample) => (
                <div key={sample.id || sample.question_preview}>
                  <span>{sample.source_dataset || '公开样例'} · {sample.id || 'sample'}</span>
                  <strong>{sample.image_attached ? '将附加公开图片' : '不附加图片'} · 参考答案不发送</strong>
                  <p>{sample.question_preview || '未返回问题预览。'}</p>
                </div>
              ))}
            </div>
          ) : null}
          <ReceiptTraceChips title="隐私边界" items={preview.privacy_trace} />
          {preview.next_actions.length ? (
            <div className="provider-preflight-list next">
              <span>下一步</span>
              {preview.next_actions.slice(0, 4).map((item) => <p key={item}>{item}</p>)}
            </div>
          ) : null}
        </>
      ) : null}
    </Card>
  )
}

export function ModelHub() {
  const [models, setModels] = useState<ModelProfile[]>(mockModels)
  const [samples, setSamples] = useState<Question[]>([])
  const [providerName, setProviderName] = useState('自定义多模态 API')
  const [apiBase, setApiBase] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null)
  const [diagnostics, setDiagnostics] = useState<ProviderDiagnostics | null>(null)
  const [preflight, setPreflight] = useState<ProviderPreflight | null>(null)
  const [isCheckingPreflight, setIsCheckingPreflight] = useState(false)
  const [focus, setFocus] = useState<string[]>(['基础识别', '错误前提', '报告安全'])
  const [selectedSamples, setSelectedSamples] = useState<string[]>([])
  const [result, setResult] = useState<ModelAdmissionResult | null>(null)
  const [admissionState, setAdmissionState] = useState<ModelAdmissionState | null>(null)
  const [selectingModelId, setSelectingModelId] = useState('')
  const [selectionNotice, setSelectionNotice] = useState('当前只展示模型看板候选；未完成真实 Provider blind probe、公开标注对齐和人工复核前，不宣称已启用正式训练 Agent。')
  const [isRunningAdmission, setIsRunningAdmission] = useState(false)
  const [admissionNotice, setAdmissionNotice] = useState('等待运行：请选择公开样例和测试维度，再启动样例级准入探测。')
  const [selfTest, setSelfTest] = useState<ProviderSelfTestResult | null>(null)
  const [isRunningSelfTest, setIsRunningSelfTest] = useState(false)
  const [selfTestMode, setSelfTestMode] = useState<'text' | 'visual' | null>(null)
  const [selfTestNotice, setSelfTestNotice] = useState('可先做轻量自检：只验证 Provider 通道，不读取公开样例，不写入模型准入状态。')
  const [previewMode, setPreviewMode] = useState<ProviderPreviewMode>('admission')
  const [requestPreview, setRequestPreview] = useState<ProviderRequestPreview | null>(null)
  const [isCheckingRequestPreview, setIsCheckingRequestPreview] = useState(false)
  const requestProviderActive = Boolean(apiBase.trim() || apiKey.trim())
  const activeCandidateLabel = '当前看板候选'
  const inactiveCandidateLabel = '设为待复核候选'

  useEffect(() => {
    api.models().then((items) => {
      setModels(items)
      const active = items.find((item) => item.is_active)
      if (active) setSelectionNotice(`当前看板候选：${active.name}。模型卡片只代表展示/联调候选；未通过真实 Provider 准入和人工复核前，不作为正式训练 Agent。`)
    })
    api.modelAdmissionState().then(setAdmissionState).catch(() => undefined)
    api.providerStatus().then((status) => {
      setProviderStatus(status)
      if (status.model) setModel((current) => current || status.model)
    }).catch(() => undefined)
    api.providerDiagnostics().then(setDiagnostics).catch(() => undefined)
    api.realSamples().then((items) => {
      const publicItems = items.filter((item) => ['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'].includes(item.source_dataset)).slice(0, 6)
      setSamples(publicItems)
      setSelectedSamples(publicItems.slice(0, 3).map((item) => admissionSampleId(item.id)))
      setAdmissionNotice(publicItems.length ? `已载入 ${publicItems.length} 个真实公开样例；准入会按样例 ID 写入 evidence。` : '真实样例接口返回为空，请先检查后端知识库。')
    }).catch(() => setAdmissionNotice('真实样例接口暂不可用；页面将无法证明选中样例与后端准入样例一致。'))
  }, [])

  useEffect(() => {
    let mounted = true
    const timer = window.setTimeout(() => {
      setIsCheckingPreflight(true)
      api.providerPreflight(apiBase)
        .then((result) => {
          if (mounted) setPreflight(result)
        })
        .catch(() => {
          if (mounted) {
            setPreflight({
              ok: false,
              safety_status: 'frontend_error',
              mode: 'fallback',
              normalized_preview: null,
              endpoint_paths: [],
              blocked_reason: 'frontend_error',
              warnings: ['前端未能读取后端预检结果，不能证明 API Base 可用。'],
              next_actions: ['确认 FastAPI 后端在线，再重新检查 API Base。'],
              key_required_for_call: true,
              request_sent: false,
              key_persisted: false,
              safety_notice: '仅供教学训练或医生审核前辅助，不作为独立诊断依据。',
              api_source: 'fallback',
            })
          }
        })
        .finally(() => {
          if (mounted) setIsCheckingPreflight(false)
        })
    }, 350)
    return () => {
      mounted = false
      window.clearTimeout(timer)
    }
  }, [apiBase])

  useEffect(() => {
    let mounted = true
    const timer = window.setTimeout(() => {
      setIsCheckingRequestPreview(true)
      api.providerRequestPreview({
        providerName,
        apiBase,
        apiKeyPresent: Boolean(apiKey.trim()),
        model: requestProviderActive ? model.trim() || undefined : undefined,
        sampleIds: selectedSamples,
        focus,
        previewMode,
      })
        .then((result) => {
          if (mounted) setRequestPreview(result)
        })
        .catch(() => {
          if (mounted) setRequestPreview(null)
        })
        .finally(() => {
          if (mounted) setIsCheckingRequestPreview(false)
        })
    }, 420)
    return () => {
      mounted = false
      window.clearTimeout(timer)
    }
  }, [providerName, apiBase, apiKey, model, selectedSamples, focus, previewMode, requestProviderActive])

  const runAdmission = async () => {
    if (isRunningAdmission || isRunningSelfTest || !selectedSamples.length || !focus.length) return
    if (providerActionBlocked) {
      setAdmissionNotice(providerPreflightIssue)
      return
    }
    setIsRunningAdmission(true)
    setAdmissionNotice(`正在探测 ${Math.min(selectedSamples.length, 3)} 个公开样例；结果会显示 backend/fallback、Provider 成功数和失败原因。`)
    try {
      const admission = await api.modelAdmissionTest({
        providerName,
        apiBase,
        apiKey: apiKey.trim() || undefined,
        model: requestProviderActive ? model.trim() || undefined : undefined,
        sampleIds: selectedSamples,
        focus,
      })
      setResult(admission)
      const source = admission.api_source === 'fallback' ? 'frontend fallback' : 'backend live'
      const alignedCount = admission.provider_status.reference_aligned_count || 0
      const providerText = admission.provider_called
        ? `真实 Provider 盲测成功 ${admission.provider_status.provider_success_count || 0}/${admission.provider_status.sample_count || admission.evidence.length} 个样例，${alignedCount} 条与公开标注部分对齐。`
        : `未完成真实 Provider 调用：${admission.provider_status.error || 'provider_not_configured'}。`
      const stateText = admission.platform_state_updated
        ? admission.provider_called
          ? ' 真实 Provider 准入摘要已写入后端。'
          : ' 规则草案摘要已写入后端，不代表真实 Provider 准入。'
        : ' 未写入后端平台状态。'
      setAdmissionNotice(`${source} 返回 ${admission.id}；${providerText}${stateText}`)
      if (admission.platform_state_updated) {
        setAdmissionState({
          updated_at: admission.created_at,
          last_admission_id: admission.id,
          provider_name: admission.provider_name,
          grade: admission.grade,
          total_score: admission.total_score,
          mode: admission.provider_status.mode || (admission.provider_called ? 'provider' : 'rule'),
          provider_called: admission.provider_called,
          is_mock: admission.is_mock,
          tested_samples: admission.tested_samples,
          risk_items: admission.risk_items,
          recommendation: admission.recommendation,
          reference_aligned_count: alignedCount,
          safe_for_training: admission.provider_called && admission.total_score >= 80 && alignedCount > 0,
        })
      }
    } catch (error) {
      setAdmissionNotice(`准入探测失败：${error instanceof Error ? error.message : '未知错误'}。请确认 FastAPI 在线、Provider 配置无误。`)
    } finally {
      setIsRunningAdmission(false)
      api.providerDiagnostics().then(setDiagnostics).catch(() => undefined)
    }
  }

  const runProviderSelfTest = async (includeImage = false) => {
    if (isRunningSelfTest || isRunningAdmission) return
    if (providerActionBlocked) {
      setSelfTestNotice(providerPreflightIssue)
      return
    }
    const sampleId = includeImage ? selectedSamples[0] : undefined
    setIsRunningSelfTest(true)
    setSelfTestMode(includeImage ? 'visual' : 'text')
    setSelfTestNotice(includeImage
      ? `正在发送视觉通道自检；后端只附加公开样例 ${sampleId || '默认样例'} 的图片和问题，不发送参考答案。`
      : '正在发送一条安全短提示词；本次只验证 Provider 文本通道，不会保存 key/base 或更新模型准入摘要。')
    try {
      const response = await api.providerSelfTest({
        providerName,
        apiBase,
        apiKey: apiKey.trim() || undefined,
        model: requestProviderActive ? model.trim() || undefined : undefined,
        includeImage,
        sampleId,
      })
      setSelfTest(response)
      const source = response.api_source === 'fallback' ? 'frontend fallback' : 'backend live'
      const visualText = response.visual_probe
        ? `图片附加：${response.image_attached ? '是' : '否'}；视觉样例：${response.image_source_dataset || '公开样例'} / ${response.image_sample_id || sampleId || '默认样例'}；`
        : '文本通道；'
      const providerText = response.provider_called
        ? `Provider 已返回：${response.probe_excerpt || '连通成功'}`
        : `Provider 未打通：${response.provider_status.error || 'provider_not_configured'}`
      setSelfTestNotice(`${source} 返回 ${response.id}；${visualText}${providerText}；${response.admission_state_updated ? '异常：已触碰准入状态。' : '未更新准入状态。'}`)
    } catch (error) {
      setSelfTestNotice(`Provider 自检失败：${error instanceof Error ? error.message : '未知错误'}。请确认 FastAPI 在线、Provider 配置无误。`)
    } finally {
      setIsRunningSelfTest(false)
      setSelfTestMode(null)
      api.providerDiagnostics().then(setDiagnostics).catch(() => undefined)
    }
  }

  const toggleFocus = (item: string) => {
    setFocus((current) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item])
  }

  const toggleSample = (sampleId: string) => {
    const normalized = admissionSampleId(sampleId)
    setSelectedSamples((current) => current.includes(normalized) ? current.filter((value) => value !== normalized) : [...current, normalized])
  }

  const referenceAlignedCount = admissionState?.reference_aligned_count ?? 0
  const admissionGateReady = Boolean(admissionState?.safe_for_training && admissionState.provider_called && referenceAlignedCount > 0)
  const activeModel = models.find((item) => item.is_active) || models[0]
  const activeModelEligible = Boolean(admissionGateReady && activeModel?.provider_type !== 'mock')
  const admissionGateItems = [
    {
      label: 'Provider blind probe',
      value: admissionState?.provider_called ? '已调用' : '未调用',
      ready: Boolean(admissionState?.provider_called),
      detail: '必须由后端 Provider 盲测公开样例。',
    },
    {
      label: '公开标注对齐',
      value: referenceAlignedCount > 0 ? `${referenceAlignedCount} 条` : '0 条',
      ready: referenceAlignedCount > 0,
      detail: '至少一条 Provider 回答与公开标注部分对齐。',
    },
    {
      label: '平台准入摘要',
      value: admissionState?.safe_for_training ? '可复核' : '规则/待复核',
      ready: Boolean(admissionState?.safe_for_training),
      detail: '准入状态来自后端 model_admission_state。',
    },
    {
      label: '非 mock 候选',
      value: activeModel?.provider_type === 'mock' ? 'mock 展示' : activeModel?.provider_type || '未选择',
      ready: Boolean(activeModel?.provider_type && activeModel.provider_type !== 'mock'),
      detail: 'mock 模型永远只作看板展示，不进入待复核候选。',
    },
    {
      label: '模型卡动作',
      value: admissionGateReady ? '非 mock 可切换' : '已锁定',
      ready: admissionGateReady,
      detail: '准入未通过时不写入新候选；mock 始终只展示。',
    },
  ]

  const selectTrainingModel = async (modelId: string) => {
    const targetModel = models.find((item) => item.id === modelId)
    if (selectingModelId || !admissionGateReady || targetModel?.provider_type === 'mock') return
    setSelectingModelId(modelId)
    try {
      const selected = await api.selectModel(modelId)
      setModels((items) => items.map((item) => ({ ...item, is_active: item.id === selected.id })))
      setSelectionNotice(`已切换待人工复核候选：${selected.name}。Dashboard 会从后端 active_model 读取该状态；仍需医生/管理员确认后才可作为正式训练 Agent。`)
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setSelectionNotice(`模型选择未写入：${message}。当前仍只保留页面看板状态。`)
    } finally {
      setSelectingModelId('')
    }
  }

  const providerSuccessCount = result?.provider_status.provider_success_count
  const providerSampleCount = result?.provider_status.sample_count || result?.evidence.length || 0
  const providerPreflightRequired = Boolean(requestProviderActive || providerStatus?.base_url_configured || providerStatus?.api_key_configured)
  const providerActionBlocked = Boolean(providerPreflightRequired && (isCheckingPreflight || !preflight?.ok))
  const providerPreflightIssue = isCheckingPreflight
    ? 'Base URL 预检仍在进行；请等待安全策略检查完成后再发起 Provider 自检或准入。'
    : `Base URL 预检未通过：${preflight?.blocked_reason || 'unknown'}。请先修正 API Base，或清空临时配置回到规则草案模式。`
  const canRunAdmission = Boolean(selectedSamples.length && focus.length && !isRunningAdmission && !isRunningSelfTest && !providerActionBlocked)
  const resultSource = result?.api_source === 'fallback' ? 'frontend fallback' : result ? 'backend live' : 'not run'
  const selfTestSource = selfTest?.api_source === 'fallback' ? 'frontend fallback' : selfTest ? 'backend live' : 'not run'

  return (
    <div className="page-stack">
      <Card className="focus-band model-admission-hero">
        <div>
          <span className="eyebrow">Model admission center</span>
          <h2>模型准入与测试中心</h2>
          <p>这里做训练 Agent 的接入前检查，不做临床能力评测。每个勾选的公开样例都会生成样例级 evidence；未完成真实 Provider 调用时会明确标为规则草案。</p>
        </div>
        <ShieldAlert size={42} />
      </Card>

      <Card className="provider-status-card">
        <SectionTitle
          eyebrow="Provider status"
          title="当前推理通道"
          action={<Tag tone={providerStatus?.configured ? 'green' : 'amber'}>{providerStatus?.configured ? 'backend .env 已配置' : '未配置 / 临时输入'}</Tag>}
        />
        <div className="status-grid">
          <div><span>模式</span><strong>{providerStatus?.mode || 'fallback'}</strong></div>
          <div><span>Provider</span><strong>{providerStatus?.provider || 'mock'}</strong></div>
          <div><span>默认模型</span><strong>{providerStatus?.model || '未设置'}</strong></div>
          <div><span>密钥状态</span><strong>{providerStatus?.api_key_configured ? '后端已配置' : '页面临时输入或未配置'}</strong></div>
        </div>
      </Card>

      {diagnostics ? <ProviderDiagnosticsCard diagnostics={diagnostics} /> : <ProviderDiagnosticsLoadingCard />}

      <Card className="credential-policy-card">
        <div>
          <KeyRound size={19} />
          <span>凭据处理</span>
          <strong>{apiKey.trim() ? '页面临时 key' : providerStatus?.api_key_configured ? '后端 .env key' : '未提供 key'}</strong>
          <p>临时 key 只随本次准入请求发送；只有填写 base 或 key 时，页面模型名才会作为本次请求覆盖。</p>
        </div>
        <div>
          <Database size={19} />
          <span>发送样例</span>
          <strong>{selectedSamples.length || 0} 个公开教学样例</strong>
          <p>后端会按样例逐条探测并返回 evidence，最多使用 3 个公开内镜样例。</p>
        </div>
        <div>
          <ShieldCheck size={19} />
          <span>保存内容</span>
          <strong>只保存准入摘要</strong>
          <p>平台仅记录 provider 名称、检查清单分、风险项和建议，不保存 API base、key 或完整模型回复。</p>
        </div>
      </Card>

      <ProviderRequestPreviewCard
        preview={requestPreview}
        loading={isCheckingRequestPreview}
        mode={previewMode}
        setMode={setPreviewMode}
      />

      {admissionState ? (
        <Card className="provider-status-card">
          <SectionTitle
            eyebrow="Platform admission state"
            title="平台最近准入摘要"
            action={<Tag tone={admissionState.safe_for_training ? 'green' : 'amber'}>{admissionState.safe_for_training ? '可人工复核启用' : '规则/待复核'}</Tag>}
          />
          <div className="status-grid">
            <div><span>Provider</span><strong>{admissionState.provider_name}</strong></div>
            <div><span>检查清单分</span><strong>Grade {admissionState.grade} · {admissionState.total_score}</strong></div>
            <div><span>模式</span><strong>{admissionState.provider_called ? 'provider called' : admissionState.mode}</strong></div>
            <div><span>样例数</span><strong>{admissionState.tested_samples.length}</strong></div>
          </div>
          <div className="source-note">{admissionState.recommendation}</div>
        </Card>
      ) : null}

      <Card className="provider-status-card active-training-agent">
        <SectionTitle
          eyebrow="Training candidate"
          title="当前看板候选 Agent"
          action={<Tag tone={activeModelEligible ? 'green' : 'amber'}>{activeModelEligible ? '准入已过 · 待复核' : activeModel?.provider_type === 'mock' ? 'mock · 仅展示' : '未准入 · 展示候选'}</Tag>}
        />
        <div className="active-agent-strip">
          <div>
            <strong>{activeModel?.name || '未选择训练 Agent'}</strong>
            <span>{activeModel?.recommended_roles.join(' / ') || '用于右侧辅导、错因解释和报告安全边界提示。'}</span>
          </div>
          <div className="tag-row">
            {activeModel?.risk_tags.slice(0, 3).map((tag) => <Tag key={tag} tone="amber">{tag}</Tag>)}
          </div>
        </div>
        <div className="admission-gate-grid">
          {admissionGateItems.map((item) => (
            <div className={item.ready ? 'ready' : 'blocked'} key={item.label}>
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
        <div className={`memory-sync-card ${activeModelEligible ? 'synced' : 'fallback'}`}>
          {activeModelEligible ? <ActivitySquare size={18} /> : <ShieldAlert size={18} />}
          <div>
            <strong>{activeModelEligible ? '准入闸门已通过' : admissionGateReady ? '准入已过，当前 mock 仍仅展示' : '准入闸门未通过'}</strong>
            <span>{selectionNotice}</span>
          </div>
        </div>
      </Card>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="API adapter" title="用户模型接入" action={<PlugZap size={20} />} />
          <div className="form-stack">
            <label>
              <span>Provider 名称</span>
              <input value={providerName} onChange={(event) => setProviderName(event.target.value)} />
            </label>
            <label>
              <span>API Base URL</span>
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="如 https://api.example.com、/v1 或完整 /chat/completions；留空用 .env" />
            </label>
            <label>
              <span>模型名称</span>
              <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="例如 gpt-4o-mini 或服务商模型名" />
            </label>
            <label>
              <span>API Key（仅本次请求）</span>
              <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="留空则使用后端 .env；不会保存或写入日志" type="password" />
            </label>
          </div>
          <div className="notice-card">
            <KeyRound size={20} />
            <p>临时密钥只随本次准入请求发送到后端，不会写入仓库、文档或审计日志。API Base 兼容根地址、/v1 或完整 /chat/completions；只填域名会按 https 处理，本地地址按 http 处理。</p>
          </div>
          <ProviderPreflightPanel preflight={preflight} loading={isCheckingPreflight} />
          {providerActionBlocked ? <div className="source-note">{providerPreflightIssue}</div> : null}
          <div className={`admission-run-strip provider-self-test-strip ${isRunningSelfTest ? 'running' : selfTest?.api_source === 'fallback' || (selfTest && !selfTest.provider_called) ? 'fallback' : selfTest?.provider_called ? 'synced' : ''}`}>
            {isRunningSelfTest ? <LoaderCircle className="spin-icon" size={18} /> : selfTest && !selfTest.provider_called ? <AlertTriangle size={18} /> : <PlugZap size={18} />}
            <div>
              <strong>{isRunningSelfTest ? (selfTestMode === 'visual' ? '正在视觉通道自检' : '正在文本轻量自检') : selfTest ? `最近自检：${selfTest.visual_probe ? '视觉通道' : '文本通道'} · ${selfTestSource}` : 'Provider 通道自检'}</strong>
              <span>{selfTestNotice}</span>
            </div>
          </div>
          {selfTest ? (
            <div className="self-test-detail-grid">
              <div><span>Provider 调用</span><strong>{selfTest.provider_called ? '成功' : '未成功'}</strong></div>
              <div><span>自检模式</span><strong>{selfTest.visual_probe ? '视觉通道' : '文本通道'}</strong></div>
              <div><span>图片附加</span><strong>{selfTest.image_attached ? '是' : '否'}</strong></div>
              <div><span>视觉样例</span><strong>{selfTest.image_sample_id || '未使用'}</strong></div>
              <div><span>数据集</span><strong>{selfTest.image_source_dataset || '无'}</strong></div>
              <div><span>审计写入</span><strong>{selfTest.audit_logged ? '已写摘要' : '未写入'}</strong></div>
              <div><span>保存 key/base</span><strong>{selfTest.key_persisted ? '异常' : '否'}</strong></div>
              <div><span>准入状态</span><strong>{selfTest.admission_state_updated ? '已更新' : '未更新'}</strong></div>
            </div>
          ) : null}
          <ProviderReceiptPanel
            receipt={selfTest?.self_test_receipt}
            fallback={selfTest?.api_source === 'fallback' || !selfTest?.audit_log_id}
            title="后端 Provider 自检收据"
          />
          <div className="self-test-actions">
            <button className="button secondary" type="button" onClick={() => runProviderSelfTest(false)} disabled={isRunningSelfTest || isRunningAdmission || providerActionBlocked}>
              {isRunningSelfTest && selfTestMode === 'text' ? <LoaderCircle className="spin-icon" size={17} /> : <PlugZap size={17} />}
              {isRunningSelfTest && selfTestMode === 'text' ? '文本自检中...' : '文本轻量自检'}
            </button>
            <button className="button secondary" type="button" onClick={() => runProviderSelfTest(true)} disabled={isRunningSelfTest || isRunningAdmission || !selectedSamples.length || providerActionBlocked}>
              {isRunningSelfTest && selfTestMode === 'visual' ? <LoaderCircle className="spin-icon" size={17} /> : <Database size={17} />}
              {isRunningSelfTest && selfTestMode === 'visual' ? '视觉自检中...' : '视觉通道自检'}
            </button>
          </div>
          <div className="source-note">视觉通道自检只证明后端已将公开样例图片以多模态请求附加到 Provider；它不发送参考标注，不更新准入状态，也不代表模型完成临床诊断。</div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Test plan" title="准入测试维度" action={<TestTube2 size={20} />} />
          <div className="check-grid">
            {focusItems.map((item) => (
              <button className={focus.includes(item) ? 'active' : ''} key={item} type="button" onClick={() => toggleFocus(item)}>
                {item}
              </button>
            ))}
          </div>
          <div className="sample-list">
            {samples.map((sample) => {
              const normalized = admissionSampleId(sample.id)
              return (
                <label key={sample.id}>
                  <input checked={selectedSamples.includes(normalized)} type="checkbox" onChange={() => toggleSample(sample.id)} />
                  <span>{sample.source_dataset}</span>
                  <strong>{sample.title}</strong>
                </label>
              )
            })}
          </div>
          <div className={`admission-run-strip ${isRunningAdmission ? 'running' : result?.api_source === 'fallback' ? 'fallback' : result?.provider_called ? 'synced' : ''}`}>
            {isRunningAdmission ? <LoaderCircle className="spin-icon" size={18} /> : result?.api_source === 'fallback' ? <AlertTriangle size={18} /> : <ActivitySquare size={18} />}
            <div>
              <strong>{isRunningAdmission ? '正在联调 Provider' : result ? `最近结果：${resultSource}` : '准入运行状态'}</strong>
              <span>{admissionNotice}</span>
            </div>
          </div>
          <button className="button primary" type="button" onClick={runAdmission} disabled={!canRunAdmission}>
            {isRunningAdmission ? <LoaderCircle className="spin-icon" size={17} /> : <ShieldAlert size={17} />}
            {isRunningAdmission ? '正在探测...' : selectedSamples.length ? '运行样例级准入探测' : '请先选择公开样例'}
          </button>
        </Card>
      </div>

      {result ? (
        <Card className="admission-result">
          <SectionTitle
            eyebrow={result.provider_name}
            title="准入检查清单结果"
            action={<Tag tone={result.provider_called ? 'green' : result.is_mock ? 'amber' : 'blue'}>{result.provider_called ? 'provider called' : 'rule draft'}</Tag>}
          />
          <div className="admission-grid">
            <div className="score-ring large">
              <strong>{result.total_score}</strong>
              <span>Checklist · Grade {result.grade}</span>
            </div>
            <div className="rubric-grid">
              {Object.entries(result.dimension_scores).map(([name, score]) => (
                <div key={name}><span>{name}</span><strong>{score}</strong></div>
              ))}
            </div>
            <div className="risk-list">
              {result.risk_items.map((item) => <p key={item}>{item}</p>)}
              <strong>{result.recommendation}</strong>
            </div>
          </div>
          <div className="tag-row">
            <Tag tone={result.api_source === 'fallback' ? 'amber' : 'green'}>{resultSource}</Tag>
            {result.tested_samples.map((sample) => <Tag key={sample} tone="blue">{sample}</Tag>)}
            <Tag tone={result.provider_called ? 'green' : 'amber'}>
              Provider {providerSuccessCount ?? 0}/{providerSampleCount}
            </Tag>
          </div>
          <div className="source-note">该分数是训练准入检查清单分，Provider 样例为盲测：请求不包含参考标注，后端只在返回后做公开标注对齐，不代表临床模型评测。</div>
          <ProviderReceiptPanel
            receipt={result.admission_receipt}
            fallback={result.api_source === 'fallback' || !result.audit_log_id}
            title="后端模型准入收据"
          />
          <div className="provider-evidence-list">
            {result.evidence.map((item, itemIndex) => (
              <div key={`${item.sample_id || 'sample'}_${itemIndex}`}>
                <span>{item.source_dataset || '公开样例'} · {item.provider_mode || result.provider_status.mode}</span>
                <strong>
                  {item.provider_called
                    ? `盲测 Provider${item.latency_ms ? ` · ${item.latency_ms}ms` : ''} · ${item.reference_match || '待对齐'}`
                    : '未完成 Provider 调用'}
                </strong>
                <p>{item.provider_answer || item.observation_excerpt || item.error || item.question || '暂无样例级证据。'}</p>
              </div>
            ))}
          </div>
          <div className={`memory-sync-card ${result.platform_state_updated ? 'synced' : 'fallback'}`}>
            <ActivitySquare size={18} />
            <div>
              <strong>{result.platform_state_updated ? '已写入平台准入状态' : '未写入平台准入状态'}</strong>
              <span>{result.platform_state_summary || '当前结果仅在本页展示，未影响训练驾驶舱。'}</span>
            </div>
          </div>
        </Card>
      ) : null}

      <div className="model-selection-policy source-note">
        模型卡片默认是能力看板。只有最近准入摘要满足真实 Provider 调用、公开标注对齐和安全阈值，且目标模型不是 mock 时，才允许写入“待人工复核候选”；未过闸门时不会把 mock/rule draft 说成正式训练 Agent。
      </div>
      <div className="model-grid">
        {models.map((model) => {
          const chartData = Object.entries(model.ability_scores).map(([key, value]) => ({ dimension: scoreLabels[key] || key, score: value }))
          const modelCanBeSelected = admissionGateReady && model.provider_type !== 'mock'
          return (
            <Card key={model.id} className={model.is_active ? 'active-model' : ''}>
              <SectionTitle
                eyebrow={model.model_family}
                title={model.name}
                action={<Tag tone={model.is_active ? (modelCanBeSelected ? 'green' : 'amber') : 'neutral'}>{model.is_active ? activeCandidateLabel : `Grade ${model.grade}`}</Tag>}
              />
              <div className="chart-box small">
                <ResponsiveContainer width="100%" height={210}>
                  <RadarChart data={chartData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="dimension" />
                    <Radar dataKey="score" stroke="#2563eb" fill="#3b82f6" fillOpacity={0.2} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
              <div className="tag-row">
                {model.risk_tags.map((tag) => <Tag key={tag} tone="amber">{tag}</Tag>)}
              </div>
              <div className="model-card-actions">
                <button
                  className={model.is_active || !modelCanBeSelected ? 'button secondary' : 'button primary'}
                  type="button"
                  onClick={() => selectTrainingModel(model.id)}
                  disabled={model.is_active || Boolean(selectingModelId) || !modelCanBeSelected}
                  title={!modelCanBeSelected ? '请先运行真实 Provider 样例级准入探测、完成公开标注对齐，并选择非 mock 模型。' : undefined}
                >
                  <CheckCircle2 size={16} />
                  {model.is_active ? activeCandidateLabel : !modelCanBeSelected ? model.provider_type === 'mock' ? 'mock 仅展示' : '待准入解锁' : selectingModelId === model.id ? '正在切换...' : inactiveCandidateLabel}
                </button>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

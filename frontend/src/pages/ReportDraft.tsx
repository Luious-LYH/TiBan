import { useEffect, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ActivitySquare, ArrowRight, CheckCircle2, ClipboardCheck, FileImage, FileText, Gauge, KeyRound, ListChecks, PlugZap, ShieldAlert, ShieldCheck, WandSparkles, Workflow } from 'lucide-react'
import { ProviderPreflightPanel } from '../components/ProviderPreflightPanel'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { ImageUploadResponse, KnowledgeBase, ProviderPreflight, ProviderStatus, Question, ReportDraft as ReportDraftType, ReportJudge } from '../lib/types'

export function ReportDraft() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [findingText, setFindingText] = useState('请基于医生所见文本、图像来源台账与报告模板知识库，生成医生审核前结构化报告训练草稿。')
  const [examType, setExamType] = useState('gastroscopy')
  const [templateName, setTemplateName] = useState('胃镜结构化训练模板')
  const [imageName, setImageName] = useState('public_real_x1_0')
  const [imagePreview, setImagePreview] = useState('/assets/real_samples/x1_clb0kvxvm90y4074yf50vf5nq.jpg')
  const [realSamples, setRealSamples] = useState<Question[]>([])
  const [selectedSampleId, setSelectedSampleId] = useState('public_real_x1_0')
  const [selectedSample, setSelectedSample] = useState<Question | null>(null)
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploadReceipt, setUploadReceipt] = useState<ImageUploadResponse | null>(null)
  const [draft, setDraft] = useState<ReportDraftType | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeBase | null>(null)
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null)
  const [providerName, setProviderName] = useState('请求级 OpenAI-compatible Provider')
  const [apiBase, setApiBase] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [providerModel, setProviderModel] = useState('')
  const [preflight, setPreflight] = useState<ProviderPreflight | null>(null)
  const [isCheckingPreflight, setIsCheckingPreflight] = useState(false)
  const [originalReport, setOriginalReport] = useState('本图明确证明患者患胃癌，建议立即治疗。')
  const [revisedReport, setRevisedReport] = useState('胃窦局部黏膜异常表现，建议医生结合完整检查、病史及必要病理结果复核。')
  const [judge, setJudge] = useState<ReportJudge | null>(null)
  const [loading, setLoading] = useState(false)
  const activeTab = searchParams.get('tab') === 'judge' ? 'judge' : 'draft'

  const switchTab = (tab: 'draft' | 'judge') => {
    setSearchParams(tab === 'judge' ? { tab: 'judge' } : {})
  }

  function applySample(sample: Question) {
    setSelectedSampleId(sample.id)
    setSelectedSample(sample)
    setImageName(sample.id)
    setImagePreview(sample.image_url || '')
    setUploadStatus('已载入公开图像样例；VQA 标注仅作为来源台账，默认不直接写入医生所见文本。')
    setUploadReceipt(null)
    setFindingText('请基于单帧公开图像、医生补充所见与模板知识库生成医生审核前结构化报告训练草稿，不补充未提供的病史、病理或完整检查范围。')
    setExamType(sample.body_part === '结直肠' ? 'colonoscopy' : 'gastroscopy')
  }

  useEffect(() => {
    api.reportKnowledge().then((payload) => {
      setKnowledge(payload)
      const firstTemplate = payload.templates?.[0]?.name
      if (firstTemplate) setTemplateName(firstTemplate)
    }).catch(() => undefined)
    api.providerStatus().then((status) => {
      setProviderStatus(status)
      if (status.model) setProviderModel((current) => current || status.model)
    }).catch(() => undefined)
    api.realSamples().then((items) => {
      setRealSamples(items)
      const first = items[0]
      if (first) applySample(first)
    }).catch(() => undefined)
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
              warnings: ['前端未能读取后端预检结果，不能证明 API Base 可用于报告 Provider 调用。'],
              next_actions: ['确认 FastAPI 后端在线，再重新检查 API Base。'],
              private_host_allowlist_configured: false,
              private_host_allowlist_used: false,
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

  const onImage = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    setLoading(true)
    setUploadStatus('正在上传图片到后端受控目录...')
    setUploadReceipt(null)
    setImagePreview(URL.createObjectURL(file))
    setSelectedSampleId('')
    setSelectedSample(null)
    try {
      const uploaded = await api.uploadReportImage(file)
      setImageName(uploaded.image_name)
      setUploadReceipt(uploaded)
      setUploadStatus(`已上传至后端：${uploaded.original_filename}，${formatBytes(uploaded.bytes)}。Provider 配置后可用于视觉观察摘要。`)
    } catch {
      setImageName('')
      setUploadReceipt(null)
      setUploadStatus('后端上传失败；当前仅保留前端预览，生成报告时不会把图片当作视觉证据。')
    } finally {
      setLoading(false)
    }
  }

  const generate = async () => {
    if (providerActionBlocked) return
    setLoading(true)
    try {
      setDraft(await api.reportDraft(findingText, { examType, imageName, templateName, ...providerOptions() }))
    } finally {
      setLoading(false)
    }
  }

  const runJudge = async () => {
    if (providerActionBlocked) return
    setLoading(true)
    try {
      setJudge(await api.reportJudge(originalReport, revisedReport, providerOptions()))
    } finally {
      setLoading(false)
    }
  }

  const providerReady = Boolean(providerStatus?.configured || providerStatus?.ok)
  const requestProviderActive = Boolean(apiKey.trim() || apiBase.trim())
  const providerPreflightRequired = Boolean(requestProviderActive || providerStatus?.base_url_configured || providerStatus?.api_key_configured)
  const providerActionBlocked = Boolean(providerPreflightRequired && (isCheckingPreflight || !preflight?.ok))
  const providerPreflightIssue = isCheckingPreflight
    ? 'Base URL 预检仍在进行；请等待安全策略检查完成后再生成报告或运行 AI judge。'
    : `Base URL 预检未通过：${preflight?.blocked_reason || 'unknown'}。请先修正 API Base，或清空临时 Provider 配置回到规则草案模式。`
  const requestKeyMode = apiKey.trim() ? '页面临时 key' : apiBase.trim() ? '请求级 base 覆盖' : providerStatus?.api_key_configured ? '后端 .env key' : '未提供 key'
  const providerMode = providerReady ? 'provider' : providerStatus?.mode || 'rule'
  const dataMode = selectedSample ? `${selectedSample.source_dataset} · public sample` : imageName.startsWith('uploads/') ? 'uploaded image' : 'local preview'
  const uploadReceiptDimensions = uploadReceipt ? formatImageDimensions(uploadReceipt) : ''
  const activeProviderMode = draft?.generation_mode || judge?.generation_mode || (requestProviderActive ? 'request-provider-pending' : providerReady ? 'provider-ready' : providerMode)
  const workflowSteps = activeTab === 'draft'
    ? [
        { label: '图像/所见', detail: selectedSample ? selectedSample.source_dataset : imageName ? '已选择图片' : '待选择', done: Boolean(imageName || findingText.trim()) },
        { label: '生成草稿', detail: draft ? draft.generation_mode : '等待生成', done: Boolean(draft) },
        { label: '复核台账', detail: draft ? `${draft.review_tasks.length} 项任务` : '生成后显示', done: Boolean(draft) },
      ]
    : [
        { label: '定位越界句', detail: originalReport.trim() ? '已填写' : '待填写', done: Boolean(originalReport.trim()) },
        { label: '医师改写', detail: revisedReport.trim() ? '已填写' : '待填写', done: Boolean(revisedReport.trim()) },
        { label: '画像回灌', detail: judge?.profile_updated ? '已完成' : '评分后写入', done: Boolean(judge?.profile_updated) },
      ]
  const providerOptions = () => ({
    providerName: requestProviderActive ? providerName.trim() || undefined : undefined,
    apiBase: apiBase.trim() || undefined,
    apiKey: apiKey.trim() || undefined,
    model: requestProviderActive ? providerModel.trim() || undefined : undefined,
  })

  return (
    <div className="page-stack">
      <Card className="focus-band report-focus">
        <div>
          <span className="eyebrow">Report training center</span>
          <h2>{activeTab === 'judge' ? '报告修改训练' : '诊断报告中心'}</h2>
          <p>{activeTab === 'judge' ? '改写越界报告，评分后回灌林知远医师画像并生成下一步专项训练。' : '选图、补所见、生成医生审核前结构化报告，并保留来源台账与幻觉审查。'}</p>
        </div>
        <FileText size={42} />
      </Card>

      <Card className="report-mode-tabs">
        <button className={activeTab === 'draft' ? 'active' : ''} type="button" onClick={() => switchTab('draft')}>
          <FileText size={17} /> 报告生成
        </button>
        <button className={activeTab === 'judge' ? 'active' : ''} type="button" onClick={() => switchTab('judge')}>
          <Gauge size={17} /> 修改训练
        </button>
      </Card>

      <Card className="report-workflow-strip">
        <div className="workflow-title">
          <Workflow size={20} />
          <div>
            <span>{activeTab === 'judge' ? '修改训练闭环' : '报告生成闭环'}</span>
            <strong>{activeTab === 'judge' ? '原报告 -> 医师改写 -> AI judge -> 画像/专项' : '图像/所见 -> 草稿 -> 证据台账 -> 医师复核'}</strong>
          </div>
        </div>
        <div className="workflow-steps">
          {workflowSteps.map((step, index) => (
            <div className={step.done ? 'done' : ''} key={step.label}>
              <CheckCircle2 size={16} />
              <span>{index + 1}. {step.label}</span>
              <strong>{step.detail}</strong>
            </div>
          ))}
        </div>
        <div className="report-quick-status">
          <div><span>数据</span><strong>{dataMode}</strong></div>
          <div><span>Provider</span><strong>{activeProviderMode}</strong></div>
          <div><span>模板</span><strong>{templateName}</strong></div>
        </div>
      </Card>

      <Card className="report-provider-console compact">
        <SectionTitle
          eyebrow="Technical details"
          title="请求级 Provider"
          action={<Tag tone={requestProviderActive || providerReady ? 'green' : 'amber'}>{requestProviderActive ? '本次请求覆盖' : providerReady ? '使用后端 .env' : '规则模式'}</Tag>}
        />
        <div className="report-provider-grid">
          <div>
            <PlugZap size={18} />
            <span>后端 Provider</span>
            <strong>{providerReady ? `${providerStatus?.provider} · ${providerStatus?.model}` : `${providerMode} 模式`}</strong>
            <p>{providerReady ? '后端默认真实推理通道可用。' : '未配置时仍可使用规则、模板和公开知识库。'}</p>
          </div>
          <div>
            <KeyRound size={18} />
            <span>凭据来源</span>
            <strong>{requestKeyMode}</strong>
            <p>页面临时 key 只随报告生成/评分请求发送，不写入日志、状态文件或 git。</p>
          </div>
          <div>
            <Gauge size={18} />
            <span>结果标识</span>
            <strong>{draft?.generation_mode || judge?.generation_mode || providerMode}</strong>
            <p>生成结果会显示 provider/rule/fallback、延迟和来源台账。</p>
          </div>
        </div>
        <ProviderPreflightPanel preflight={preflight} loading={isCheckingPreflight} />
        {providerActionBlocked ? <div className="source-note">{providerPreflightIssue}</div> : null}
        <details className="provider-credential-drawer">
          <summary>
            <span>配置本次请求 Provider</span>
            <strong>{requestProviderActive ? '已启用请求级覆盖' : '可选；仅填写模型名不会触发临时 Provider'}</strong>
          </summary>
          <div className="form-row report-provider-form">
            <label>
              <span>Provider 名称</span>
              <input value={providerName} onChange={(event) => setProviderName(event.target.value)} />
            </label>
            <label>
              <span>API Base URL</span>
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="如 https://api.example.com、/v1 或完整 /chat/completions" />
            </label>
            <label>
              <span>模型名称</span>
              <input value={providerModel} onChange={(event) => setProviderModel(event.target.value)} placeholder="留空则使用后端默认模型" />
            </label>
            <label>
              <span>API Key（仅本次请求）</span>
              <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="留空则使用后端 .env；不会保存" type="password" />
            </label>
          </div>
        </details>
      </Card>

      {activeTab === 'draft' ? (
        <div className="page-stack">
          <div className="report-workbench">
            <Card>
              <SectionTitle eyebrow="Image + findings" title="图像与所见输入" />
              {realSamples.length ? (
                <div className="real-sample-picker">
                  {realSamples.slice(0, 6).map((sample) => (
                    <button
                      className={selectedSampleId === sample.id ? 'active' : ''}
                      key={sample.id}
                      type="button"
                      onClick={() => applySample(sample)}
                      title={`${sample.source_dataset} · ${sample.body_part}`}
                    >
                      <img
                        src={sample.image_url || '/assets/synthetic-endoscopy-training.svg'}
                        alt={sample.title}
                        data-real-sample-image={sample.image_url?.startsWith('/assets/real_samples/') ? 'true' : 'false'}
                        data-real-sample-role="thumbnail"
                        data-source-dataset={sample.source_dataset}
                      />
                      <span>{sample.source_dataset}</span>
                    </button>
                  ))}
                </div>
              ) : null}
              <label className="upload-zone">
                <input type="file" accept="image/*" onChange={onImage} />
                {imagePreview ? (
                  <img
                    src={imagePreview}
                    alt={selectedSample ? `${selectedSample.source_dataset} 公开内镜样例预览` : '上传的内镜图片预览'}
                    data-real-sample-image={selectedSample && imagePreview.startsWith('/assets/real_samples/') ? 'true' : 'false'}
                    data-real-sample-role="primary"
                    data-source-dataset={selectedSample?.source_dataset || 'uploaded'}
                  />
                ) : <FileImage size={34} />}
                <span>{selectedSampleId ? '已载入本地真实公开图文样例，可切换或上传自定义图片' : imageName || '上传内镜图片到后端受控目录'}</span>
              </label>
              {uploadStatus ? <div className="source-note">{uploadStatus}</div> : null}
              {uploadReceipt ? (
                <div
                  className="upload-receipt-card"
                  data-report-upload-receipt="true"
                  data-report-upload-audit={uploadReceipt.audit_logged ? 'true' : 'false'}
                  data-report-upload-dimensions={uploadReceiptDimensions}
                  data-report-upload-provider-input={uploadReceipt.provider_input_allowed ? 'true' : 'false'}
                >
                  <div className="upload-receipt-head">
                    <FileImage size={18} />
                    <div>
                      <span>图像证据收据</span>
                      <strong title={uploadReceipt.original_filename}>{uploadReceipt.original_filename}</strong>
                    </div>
                    <Tag tone={uploadReceipt.audit_logged ? 'green' : 'amber'}>{uploadReceipt.audit_logged ? 'audit logged' : 'audit pending'}</Tag>
                  </div>
                  <div className="upload-receipt-grid">
                    <div><span>MIME</span><strong>{uploadReceipt.mime_type}</strong></div>
                    <div><span>大小</span><strong>{formatBytes(uploadReceipt.bytes)}</strong></div>
                    <div><span>尺寸</span><strong>{uploadReceiptDimensions}</strong></div>
                    <div><span>SHA256</span><strong>{uploadReceipt.sha256_prefix}</strong></div>
                    <div><span>审计 ID</span><strong>{uploadReceipt.audit_log_id || 'pending'}</strong></div>
                    <div><span>Provider 输入</span><strong>{uploadReceipt.provider_input_allowed ? '受控目录允许' : '未允许'}</strong></div>
                  </div>
                </div>
              ) : null}
              {selectedSample ? (
                <details className="sample-annotation-card sample-ledger-card">
                  <summary>
                    <span>图像来源台账</span>
                    <strong>{selectedSample.source_dataset} · {selectedSample.body_part}</strong>
                  </summary>
                  <div>
                    <span>VQA 问题</span>
                    <p>{selectedSample.question}</p>
                  </div>
                  <div>
                    <span>公开标注</span>
                    <p>{selectedSample.answer}</p>
                  </div>
                  <em>该标注用于追踪公开样例来源，不等同于医生报告结论。</em>
                </details>
              ) : null}
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
              <button className="button primary" type="button" onClick={generate} disabled={loading || providerActionBlocked}>
                <WandSparkles size={17} /> {requestProviderActive || providerReady ? '生成并按真实配置尝试 Provider' : '生成结构化报告'}
              </button>
            </Card>

            <Card className="report-side-panel">
              <SectionTitle
                eyebrow={draft ? 'Review cockpit' : 'Template KB'}
                title={draft ? '复核与证据台账' : '模板与边界'}
                action={<Tag tone={draft?.generation_mode === 'provider' ? 'green' : 'blue'}>{draft?.generation_mode || 'ready'}</Tag>}
              />
              {draft ? (
                <>
                  <div className={`audit-pass ${draft.hallucination_audit.audit_passed ? 'pass' : 'fail'}`}>
                    <strong>{draft.hallucination_audit.audit_passed ? '单帧范围审查通过' : '发现需改写声明'}</strong>
                    <span>{draft.hallucination_audit.evidence_policy || '证据约束策略已启用'}</span>
                  </div>
                  <DraftList title="医师复核任务" items={draft.review_tasks.slice(0, 4)} />
                  <div className="source-trace-grid compact">
                    {draft.source_trace.slice(0, 4).map((item) => (
                      <div className={item.used ? 'used' : ''} key={`${item.source_type}_${item.label}`}>
                        <span>{item.label}</span>
                        <strong>{item.used ? '已使用' : '未使用'}</strong>
                        <p>{item.detail}{item.latency_ms ? ` · ${item.latency_ms}ms` : ''}</p>
                      </div>
                    ))}
                  </div>
                  <button className="button secondary" type="button" onClick={() => switchTab('judge')}>
                    <ShieldCheck size={17} /> 进入报告修改训练
                  </button>
                </>
              ) : (
                <div className="knowledge-list compact">
                  {knowledge?.templates?.slice(0, 3).map((template) => (
                    <div key={template.name}>
                      <strong>{template.name}</strong>
                      <p>{template.sections?.join(' / ') || template.criteria?.join(' / ') || template.tone || '医生审核前训练模板'}</p>
                    </div>
                  ))}
                </div>
              )}
              <div className="notice-card">
                <ClipboardCheck size={20} />
                <p>公开 VQA 标注只进入来源台账；报告中心只输出医生审核前训练模板，不独立生成最终诊断。</p>
              </div>
            </Card>
          </div>

          {draft ? (
            <>
              <Card>
            <SectionTitle
              eyebrow={draft.template_name}
              title="结构化报告输出"
              action={<Tag tone={draft.generation_mode === 'provider' ? 'green' : draft.generation_mode === 'fallback' ? 'amber' : 'blue'}>{draft.generation_mode}</Tag>}
            />
            <div className="report-status-grid">
              <div><span>草稿状态</span><strong>{draft.draft_status}</strong></div>
              <div><span>检查类型</span><strong>{String(draft.exam_context.exam_type || draft.exam_type)}</strong></div>
              <div><span>图像质量</span><strong>{draft.image_quality.clarity || 'unknown'}</strong></div>
              <div><span>Provider</span><strong>{draft.provider_status.ok ? `${draft.provider_status.model}` : draft.provider_status.error || 'rule'}</strong></div>
            </div>
            <div className="source-trace-grid">
              {draft.source_trace.map((item) => (
                <div className={item.used ? 'used' : ''} key={`${item.source_type}_${item.label}`}>
                  <span>{item.label}</span>
                  <strong>{item.used ? '已使用' : '未使用'}</strong>
                  <p>{item.detail}{item.latency_ms ? ` · ${item.latency_ms}ms` : ''}</p>
                </div>
              ))}
            </div>
            {draft.model_observation ? (
              <div className="provider-observation">
                <strong>Provider 观察摘要</strong>
                <p>{draft.model_observation}</p>
              </div>
            ) : null}
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

          <div className="grid two">
            <Card>
              <SectionTitle eyebrow="Evidence ledger" title="证据台账与图像质量" action={<ListChecks size={20} />} />
              <div className="ledger-list">
                {draft.evidence_ledger.map((item) => (
                  <div key={item.evidence_id}>
                    <span>{item.evidence_id} · {item.source_type}</span>
                    <strong>{item.source_ref}</strong>
                    <p>{item.supports.join(' / ')}</p>
                  </div>
                ))}
              </div>
              <div className="tag-row">
                {(draft.image_quality.artifacts || []).map((item) => <Tag key={item} tone="amber">{item}</Tag>)}
              </div>
              <div className="notice-card">
                <FileImage size={20} />
                <p>{String(draft.exam_context.missing_context_note || '缺少完整上下文，需医师补充。')}</p>
              </div>
            </Card>

            <Card>
              <SectionTitle eyebrow="Hallucination audit" title="幻觉审查与医师复核" action={<ShieldAlert size={20} />} />
              <div className={`audit-pass ${draft.hallucination_audit.audit_passed ? 'pass' : 'fail'}`}>
                <strong>{draft.hallucination_audit.audit_passed ? '未发现单帧范围幻觉' : '存在需改写声明'}</strong>
                <span>{draft.hallucination_audit.evidence_policy || '证据约束策略已启用'}</span>
              </div>
              <DraftList title="高风险标记" items={draft.hallucination_audit.high_risk_flags?.length ? draft.hallucination_audit.high_risk_flags : ['暂无高风险词']} />
              <DraftList title="必须改写" items={draft.hallucination_audit.required_rewrites?.length ? draft.hallucination_audit.required_rewrites : ['暂无强制改写项']} />
              <DraftList title="医师复核任务" items={draft.review_tasks} />
            </Card>
          </div>
            </>
          ) : null}
        </div>
      ) : null}

      {activeTab === 'judge' ? (
      <div className="grid two report-layout">
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
          <button className="button primary" type="button" onClick={runJudge} disabled={loading || providerActionBlocked}>
            <ShieldCheck size={17} /> {requestProviderActive || providerReady ? '评分并按真实配置尝试 Provider' : 'AI judge 评分'}
          </button>
        </Card>

        <Card>
          <SectionTitle
            eyebrow="Feedback"
            title="评分与建议"
            action={judge ? <Tag tone={judge.generation_mode === 'provider' ? 'green' : judge.generation_mode === 'fallback' ? 'amber' : 'blue'}>{judge.generation_mode}</Tag> : null}
          />
          {judge ? (
            <>
              <div className="score-ring">
                <strong>{judge.score}</strong>
                <span>报告修改得分</span>
              </div>
              <div className="report-status-grid">
                <div><span>评分来源</span><strong>{judge.generation_mode}</strong></div>
                <div><span>Provider</span><strong>{judge.provider_status.ok ? judge.provider_status.model : judge.provider_status.error || 'rule'}</strong></div>
                <div><span>医生画像</span><strong>{judge.profile_updated ? '已回灌' : '未写入'}</strong></div>
                <div><span>审核边界</span><strong>{judge.doctor_review_required ? '医生审核必需' : '未标记'}</strong></div>
              </div>
              <div className="source-trace-grid compact">
                {judge.source_trace.map((item) => (
                  <div className={item.used ? 'used' : ''} key={`${item.source_type}_${item.label}`}>
                    <span>{item.label}</span>
                    <strong>{item.used ? '已使用' : '未使用'}</strong>
                    <p>{item.detail}{item.latency_ms ? ` · ${item.latency_ms}ms` : ''}</p>
                  </div>
                ))}
              </div>
              {judge.provider_feedback ? (
                <div className="provider-observation">
                  <strong>Provider 评阅摘要</strong>
                  <p>{judge.provider_feedback}</p>
                </div>
              ) : null}
              <div className="rubric-grid">
                {Object.entries(judge.rubric_scores).map(([name, score]) => (
                  <div key={name}><span>{name}</span><strong>{score}</strong></div>
                ))}
              </div>
              <DraftList title="优点" items={judge.strengths} />
              <DraftList title="需要修正" items={judge.issues} />
              <div className="next-card">{judge.suggested_revision}</div>
              <div className={`memory-sync-card ${judge.profile_updated ? 'synced' : 'fallback'}`}>
                <ActivitySquare size={18} />
                <div>
                  <strong>{judge.profile_updated ? '已回灌林知远医师画像' : '画像未写入'}</strong>
                  <span>{judge.memory_summary || '当前评分仅用于本页展示，未更新后端训练记录。'}</span>
                </div>
              </div>
              <div className="report-drill-list">
                <div className="drill-list-header">
                  <span>下一步专项训练</span>
                  <strong>{judge.recommended_drills.length} 个推荐</strong>
                </div>
                <Link
                  className="report-to-card-link"
                  to="/card?source=report_judge"
                  state={{
                    source: 'report_judge',
                    reportSummary: judge.suggested_revision || revisedReport,
                    summarySource: judge.suggested_revision ? 'judge_suggestion' : 'doctor_revision',
                  }}
                >
                  <div>
                    <strong>生成患者沟通卡片草稿</strong>
                    <span>{judge.suggested_revision ? 'AI judge 建议改写' : '医生修改稿摘要'} · 医生审核闸门仍保持锁定</span>
                    <p>把已评分的摘要带到科普卡片工作室，继续完成患者沟通前审核。</p>
                  </div>
                  <ArrowRight size={17} />
                </Link>
                {judge.recommended_drills.map((drill) => (
                  <Link to={drill.href} key={`${drill.label}_${drill.rubric || 'report'}`}>
                    <div>
                      <strong>{drill.label}</strong>
                      <span>{drill.rubric ? `${drill.rubric} · ${drill.score ?? '-'} 分` : '报告训练'}</span>
                      <p>{drill.reason}</p>
                    </div>
                    <ArrowRight size={17} />
                  </Link>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">提交修改稿后，这里会显示 rubric 分数、风险表达和建议改写。</div>
          )}
        </Card>
      </div>
      ) : null}
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

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown'
  if (bytes < 1024) return `${bytes} B`
  const kilobytes = bytes / 1024
  return `${kilobytes >= 100 ? Math.round(kilobytes) : kilobytes.toFixed(1)} KB`
}

function formatImageDimensions(receipt: ImageUploadResponse) {
  return receipt.width && receipt.height ? `${receipt.width} x ${receipt.height}` : 'unknown'
}

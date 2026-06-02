import { useEffect, useState } from 'react'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ActivitySquare, CheckCircle2, Database, KeyRound, PlugZap, ShieldAlert, ShieldCheck, TestTube2 } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockModels } from '../lib/mock'
import type { ModelAdmissionResult, ModelAdmissionState, ModelProfile, ProviderStatus, Question } from '../lib/types'

const scoreLabels: Record<string, string> = {
  basic_recognition: '基础识别',
  complex_reasoning: '复杂推理',
  false_premise: '错误前提',
  chinese_report: '中文报告',
  engineering: '工程稳定',
}

const focusItems = ['基础识别', '复杂推理', '错误前提', '报告安全', '接口稳定']

export function ModelHub() {
  const [models, setModels] = useState<ModelProfile[]>(mockModels)
  const [samples, setSamples] = useState<Question[]>([])
  const [providerName, setProviderName] = useState('自定义多模态 API')
  const [apiBase, setApiBase] = useState('https://api.example.com/v1')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null)
  const [focus, setFocus] = useState<string[]>(['基础识别', '错误前提', '报告安全'])
  const [selectedSamples, setSelectedSamples] = useState<string[]>([])
  const [result, setResult] = useState<ModelAdmissionResult | null>(null)
  const [admissionState, setAdmissionState] = useState<ModelAdmissionState | null>(null)
  const [selectingModelId, setSelectingModelId] = useState('')
  const [selectionNotice, setSelectionNotice] = useState('当前训练 Agent 会写入后端 models.json，并同步影响首页当前模型展示。')

  useEffect(() => {
    api.models().then((items) => {
      setModels(items)
      const active = items.find((item) => item.is_active)
      if (active) setSelectionNotice(`当前训练 Agent：${active.name}。可切换候选模型，但所有输出仍需医生审核。`)
    })
    api.modelAdmissionState().then(setAdmissionState).catch(() => undefined)
    api.providerStatus().then((status) => {
      setProviderStatus(status)
      if (status.model) setModel((current) => current || status.model)
    }).catch(() => undefined)
    api.qbank({ sourceDataset: 'Kvasir-VQA-x1' }).then((items) => {
      const publicItems = items.filter((item) => ['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'].includes(item.source_dataset)).slice(0, 6)
      setSamples(publicItems)
      setSelectedSamples(publicItems.slice(0, 3).map((item) => item.id.replace('public_', '')))
    })
  }, [])

  const runAdmission = async () => {
    const admission = await api.modelAdmissionTest({
      providerName,
      apiBase,
      apiKey: apiKey.trim() || undefined,
      model: model.trim() || undefined,
      sampleIds: selectedSamples,
      focus,
    })
    setResult(admission)
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
        safe_for_training: admission.provider_called && admission.total_score >= 80,
      })
    }
  }

  const toggleFocus = (item: string) => {
    setFocus((current) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item])
  }

  const toggleSample = (sampleId: string) => {
    const normalized = sampleId.replace('public_', '')
    setSelectedSamples((current) => current.includes(normalized) ? current.filter((value) => value !== normalized) : [...current, normalized])
  }

  const selectTrainingModel = async (modelId: string) => {
    if (selectingModelId) return
    setSelectingModelId(modelId)
    try {
      const selected = await api.selectModel(modelId)
      setModels((items) => items.map((item) => ({ ...item, is_active: item.id === selected.id })))
      setSelectionNotice(`已切换当前训练 Agent：${selected.name}。Dashboard 会从后端 active_model 读取该状态。`)
    } catch {
      setSelectionNotice('模型选择接口暂不可用；当前只保留页面状态，未写入后端。')
    } finally {
      setSelectingModelId('')
    }
  }

  const activeModel = models.find((item) => item.is_active) || models[0]
  const providerSuccessCount = result?.provider_status.provider_success_count
  const providerSampleCount = result?.provider_status.sample_count || result?.evidence.length || 0

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

      <Card className="credential-policy-card">
        <div>
          <KeyRound size={19} />
          <span>凭据处理</span>
          <strong>{apiKey.trim() ? '页面临时 key' : providerStatus?.api_key_configured ? '后端 .env key' : '未提供 key'}</strong>
          <p>临时 key 只随本次准入请求发送，不写入审计日志、状态文件或 git；base/model 可临时覆盖后端默认配置。</p>
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
          eyebrow="Training agent"
          title="当前训练 Agent"
          action={<Tag tone={activeModel?.provider_type === 'mock' ? 'amber' : 'green'}>{activeModel?.provider_type || 'mock'}</Tag>}
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
        <div className={`memory-sync-card ${selectionNotice.includes('已切换') || selectionNotice.includes('当前训练') ? 'synced' : 'fallback'}`}>
          <ActivitySquare size={18} />
          <div>
            <strong>{selectionNotice.includes('暂不可用') ? '选择未写入' : '选择状态已联动'}</strong>
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
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="留空或示例地址则使用后端 .env" />
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
            <p>临时密钥只随本次准入请求发送到后端，不会写入仓库、文档或审计日志。正式演示建议使用后端 .env 配置；页面 base/model 可覆盖后端默认值。</p>
          </div>
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
              const normalized = sample.id.replace('public_', '')
              return (
                <label key={sample.id}>
                  <input checked={selectedSamples.includes(normalized)} type="checkbox" onChange={() => toggleSample(sample.id)} />
                  <span>{sample.source_dataset}</span>
                  <strong>{sample.title}</strong>
                </label>
              )
            })}
          </div>
          <button className="button primary" type="button" onClick={runAdmission}>
            <ShieldAlert size={17} /> 运行样例级准入探测
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
            {result.tested_samples.map((sample) => <Tag key={sample} tone="blue">{sample}</Tag>)}
            <Tag tone={result.provider_called ? 'green' : 'amber'}>
              Provider {providerSuccessCount ?? 0}/{providerSampleCount}
            </Tag>
          </div>
          <div className="source-note">该分数是训练准入检查清单分，基于接口连通、样例 evidence、安全边界和规则项汇总，不代表临床模型评测。</div>
          <div className="provider-evidence-list">
            {result.evidence.map((item, itemIndex) => (
              <div key={`${item.sample_id || 'sample'}_${itemIndex}`}>
                <span>{item.source_dataset || '公开样例'} · {item.provider_mode || result.provider_status.mode}</span>
                <strong>{item.provider_called ? `已调用 Provider${item.latency_ms ? ` · ${item.latency_ms}ms` : ''}` : '未完成 Provider 调用'}</strong>
                <p>{item.observation_excerpt || item.error || item.question || '暂无样例级证据。'}</p>
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

      <div className="model-grid">
        {models.map((model) => {
          const chartData = Object.entries(model.ability_scores).map(([key, value]) => ({ dimension: scoreLabels[key] || key, score: value }))
          return (
            <Card key={model.id} className={model.is_active ? 'active-model' : ''}>
              <SectionTitle eyebrow={model.model_family} title={model.name} action={<Tag tone={model.is_active ? 'green' : 'neutral'}>{model.is_active ? '当前训练 Agent' : `Grade ${model.grade}`}</Tag>} />
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
                  className={model.is_active ? 'button secondary' : 'button primary'}
                  type="button"
                  onClick={() => selectTrainingModel(model.id)}
                  disabled={model.is_active || Boolean(selectingModelId)}
                >
                  <CheckCircle2 size={16} />
                  {model.is_active ? '当前训练 Agent' : selectingModelId === model.id ? '正在切换...' : '设为训练 Agent'}
                </button>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

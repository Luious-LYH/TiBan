import { useEffect, useState } from 'react'
import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'
import { KeyRound, PlugZap, ShieldAlert, TestTube2 } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockModels } from '../lib/mock'
import type { ModelAdmissionResult, ModelProfile, Question } from '../lib/types'

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
  const [apiKey, setApiKey] = useState('sk-demo-****')
  const [focus, setFocus] = useState<string[]>(['基础识别', '错误前提', '报告安全'])
  const [selectedSamples, setSelectedSamples] = useState<string[]>([])
  const [result, setResult] = useState<ModelAdmissionResult | null>(null)

  useEffect(() => {
    api.models().then((items) => setModels(items))
    api.qbank({ sourceDataset: 'Kvasir-VQA-x1' }).then((items) => {
      const publicItems = items.filter((item) => ['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'].includes(item.source_dataset)).slice(0, 6)
      setSamples(publicItems)
      setSelectedSamples(publicItems.slice(0, 3).map((item) => item.id.replace('public_', '')))
    })
  }, [])

  const runAdmission = async () => {
    setResult(await api.modelAdmissionTest({
      providerName,
      apiBase,
      apiKeyMasked: apiKey.replace(/(.{4}).+(.{2})/, '$1****$2'),
      sampleIds: selectedSamples,
      focus,
    }))
  }

  const toggleFocus = (item: string) => {
    setFocus((current) => current.includes(item) ? current.filter((value) => value !== item) : [...current, item])
  }

  const toggleSample = (sampleId: string) => {
    const normalized = sampleId.replace('public_', '')
    setSelectedSamples((current) => current.includes(normalized) ? current.filter((value) => value !== normalized) : [...current, normalized])
  }

  return (
    <div className="page-stack">
      <Card className="focus-band model-admission-hero">
        <div>
          <span className="eyebrow">Model admission center</span>
          <h2>模型准入与测试中心</h2>
          <p>模型能力服务于医师训练，而不是首页主角。这里允许用户接入自己的 API 和 key，通过公开内镜样例、错误前提与报告安全维度做 mock 准入评分。</p>
        </div>
        <ShieldAlert size={42} />
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
              <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} />
            </label>
            <label>
              <span>API Key</span>
              <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} type="password" />
            </label>
          </div>
          <div className="notice-card">
            <KeyRound size={20} />
            <p>演示中不会提交真实密钥；仓库内不得写入真实 API key、服务器 IP 或患者数据。</p>
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
            <ShieldAlert size={17} /> 运行 mock 准入测试
          </button>
        </Card>
      </div>

      {result ? (
        <Card className="admission-result">
          <SectionTitle eyebrow={result.provider_name} title="准入评分结果" action={<Tag tone={result.grade === 'A' || result.grade === 'S' ? 'green' : 'amber'}>Grade {result.grade}</Tag>} />
          <div className="admission-grid">
            <div className="score-ring large">
              <strong>{result.total_score}</strong>
              <span>总分</span>
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
            </Card>
          )
        })}
      </div>
    </div>
  )
}

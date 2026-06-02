import { useEffect, useState } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'
import { ShieldAlert } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockModels } from '../lib/mock'
import type { ModelProfile } from '../lib/types'

const scoreLabels: Record<string, string> = {
  basic_recognition: '基础识别',
  complex_reasoning: '复杂推理',
  false_premise: '错误前提',
  chinese_report: '中文报告',
  engineering: '工程稳定',
}

export function ModelHub() {
  const [models, setModels] = useState<ModelProfile[]>(mockModels)

  useEffect(() => {
    api.models().then((items) => setModels(items))
  }, [])

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">Model registry</span>
          <h2>模型库与能力看板（mock / 接口预留）</h2>
          <p>这里展示的是后台安全准入机制雏形，不声称完成真实临床评测。后续可接入 Kvasir-VQA-x1、MediaEval Medico 和内部安全集。</p>
        </div>
        <ShieldAlert size={42} />
      </Card>
      <div className="model-grid">
        {models.map((model) => {
          const chartData = Object.entries(model.ability_scores).map(([key, value]) => ({ dimension: scoreLabels[key] || key, score: value }))
          return (
            <Card key={model.id} className={model.is_active ? 'active-model' : ''}>
              <SectionTitle eyebrow={model.model_family} title={model.name} action={<Tag tone={model.is_active ? 'green' : 'neutral'}>{model.is_active ? '当前默认' : `Grade ${model.grade}`}</Tag>} />
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


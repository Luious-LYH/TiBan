import { useEffect, useState } from 'react'
import { Bar, BarChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, DatabaseZap, ShieldCheck } from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockDashboard } from '../lib/mock'
import type { DashboardPayload } from '../lib/types'

export function Dashboard() {
  const [data, setData] = useState<DashboardPayload>(mockDashboard)
  const [status, setStatus] = useState('连接后端中')

  useEffect(() => {
    api.dashboard().then((payload) => {
      setData(payload)
      setStatus(payload.api_source === 'fallback' ? '本地 fallback' : '后端在线')
    })
  }, [])

  const completion = Math.round((data.today_training.completed / data.today_training.target) * 100)

  return (
    <div className="page-stack">
      <section className="hero-workbench">
        <div>
          <span className="eyebrow">Training cockpit</span>
          <h2>今日训练工作台</h2>
          <p>围绕题库分层、智能提示、原子事实反馈、错误前提训练和医生审核前辅助，形成一条可演示的 Agent 教学闭环。</p>
          <div className="hero-actions">
            <a className="primary-link" href="/training">
              进入训练中心 <ArrowRight size={16} />
            </a>
            <Tag tone={status === '后端在线' ? 'green' : 'amber'}>{status}</Tag>
          </div>
          {status === '本地 fallback' ? <p className="fallback-warning">后端暂不可用，当前页面使用前端 mock 兜底；演示联调时请确认 FastAPI 已启动。</p> : null}
        </div>
        <div className="hero-metrics">
          <div>
            <strong>{data.today_training.completed}/{data.today_training.target}</strong>
            <span>今日训练</span>
          </div>
          <div>
            <strong>{completion}%</strong>
            <span>完成进度</span>
          </div>
          <div>
            <strong>{data.today_training.review_queue}</strong>
            <span>错题复盘</span>
          </div>
        </div>
      </section>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Learner memory" title="能力画像" />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={data.ability_radar}>
                <PolarGrid />
                <PolarAngleAxis dataKey="dimension" />
                <Radar dataKey="score" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.24} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div className="tag-row">
            {data.learner_profile.weakness_tags.map((tag) => (
              <Tag key={tag} tone="amber">
                {tag}
              </Tag>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Curriculum mapping" title="推荐训练" />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={data.recommended_training}>
                <XAxis dataKey="label" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="recommend-list">
            {data.recommended_training.map((item) => (
              <div key={item.label}>
                <span>{item.label}</span>
                <strong>{item.count} 题可练</strong>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid three">
        <Card>
          <SectionTitle eyebrow="Agent stack" title="当前辅导模型" />
          <div className="model-mini">
            <strong>{data.active_model.name}</strong>
            <span>{data.active_model.model_family} · {data.active_model.provider_type}</span>
          </div>
          <div className="tag-row">
            {data.active_model.risk_tags.map((tag) => (
              <Tag key={tag} tone="blue">
                {tag}
              </Tag>
            ))}
          </div>
        </Card>
        <Card>
          <SectionTitle eyebrow="References" title="公开项目启发" />
          <ul className="compact-list">
            {data.reference_inspirations.map((item) => (
              <li key={item}>
                <DatabaseZap size={16} />
                {item}
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <SectionTitle eyebrow="Safety" title="准入说明" />
          <div className="notice-card">
            <ShieldCheck size={20} />
            <p>{data.mock_evaluation_notice}</p>
          </div>
        </Card>
      </div>
      <SafetyNotice text={data.safety_notice} />
    </div>
  )
}

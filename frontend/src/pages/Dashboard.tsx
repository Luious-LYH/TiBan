import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ArrowRight, BarChart3, BookOpenCheck, FileText, Sparkles, UserRound } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Card, SafetyNotice, Tag } from '../components/Primitives'
import { v3Api, v3DemoState, v3SafetyNotice } from '../lib/v3Api'
import type { ModelEvaluationPayload, PracticeState } from '../lib/types'

export function Dashboard() {
  const [practice, setPractice] = useState<PracticeState>(v3DemoState)
  const [models, setModels] = useState<ModelEvaluationPayload | null>(null)

  useEffect(() => {
    Promise.allSettled([v3Api.practiceState(), v3Api.modelEvaluation()]).then(([practiceResult, modelResult]) => {
      if (practiceResult.status === 'fulfilled') setPractice(practiceResult.value)
      if (modelResult.status === 'fulfilled') setModels(modelResult.value)
    })
  }, [])

  const profile = practice.profile
  const progress = practice.progress
  const topModel = (models?.summary.top_model_name || '平台智能助手').replace('平台智能助手 · ', '')
  const trend = profile.growth_trend
  const flowSteps: { title: string; desc: string; icon: LucideIcon; href: string }[] = [
    { title: '模型评估', desc: '确定智能助手', icon: BarChart3, href: '/models' },
    { title: '医生研修', desc: '图像问答与复盘', icon: BookOpenCheck, href: '/practice' },
    { title: '报告辅助', desc: '结构化草稿修改', icon: FileText, href: '/report' },
    { title: '能力画像', desc: '沉淀成长方向', icon: UserRound, href: '/profile' },
  ]

  return (
    <div className="page-stack v3-page">
      <section className="v3-home-hero">
        <div>
          <Tag tone="blue">研修闭环</Tag>
          <h2>先确定可靠助手，再让医生高效研修</h2>
          <p>模型评估、内镜图像练习、证据复盘、报告辅助和能力画像被压缩成一条清晰流程，让医生能快速进入关键任务。</p>
          <div className="v3-hero-actions">
            <Link className="button primary" to="/models">
              模型评估 <ArrowRight size={16} />
            </Link>
            <Link className="button secondary" to="/practice">
              开始研修
            </Link>
          </div>
        </div>
        <div className="v3-hero-panel">
          <span>当前智能助手</span>
          <strong>{topModel}</strong>
          <small>基于平台统一内镜数据资源完成能力评估</small>
          <div className="v3-signal-grid">
            <div><b>{progress.percent}%</b><span>今日进度</span></div>
            <div><b>{progress.review_queue}</b><span>待复盘</span></div>
            <div><b>{Math.round(profile.accuracy * 100)}%</b><span>累计正确率</span></div>
          </div>
        </div>
      </section>

      <div className="v3-flow-strip">
        {flowSteps.map(({ title, desc, icon: Icon, href }) => (
          <Link className="v3-flow-step" to={href} key={title}>
            <Icon size={20} />
            <strong>{title}</strong>
            <span>{desc}</span>
          </Link>
        ))}
      </div>

      <div className="v3-home-grid">
        <Card className="v3-focus-card">
          <div className="v3-card-head">
            <Sparkles size={20} />
            <div>
              <span>下一步</span>
              <h3>{practice.next_plan?.[0]?.label || '证据不足复盘'}</h3>
            </div>
          </div>
          <p>{practice.next_plan?.[0]?.reason || '优先巩固图像证据与题干前提之间的关系。'}</p>
          <Link className="button primary" to="/practice">进入研修</Link>
        </Card>

        <Card className="v3-chart-card">
          <div className="v3-card-head compact">
            <UserRound size={20} />
            <div>
              <span>能力走势</span>
              <h3>{profile.name}</h3>
            </div>
          </div>
          <div className="v3-chart">
            <ResponsiveContainer width="100%" height={190}>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="homeTrend" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#0f766e" stopOpacity={0.38} />
                    <stop offset="100%" stopColor="#0f766e" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <Tooltip />
                <Area dataKey="evidence" name="观察依据" stroke="#0f766e" fill="url(#homeTrend)" strokeWidth={2} />
                <Area dataKey="report" name="报告表达" stroke="#2563eb" fill="transparent" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <SafetyNotice text={practice.safety_notice || v3SafetyNotice} />
    </div>
  )
}

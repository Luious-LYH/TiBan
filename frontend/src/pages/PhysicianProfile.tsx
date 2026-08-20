import { useEffect, useState } from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ActivitySquare, Bot, BookOpenCheck, Brain, Target } from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { v3Api, v3DemoState, v3SafetyNotice } from '../lib/v3Api'
import type { PracticeState } from '../lib/types'

export function PhysicianProfile() {
  const [state, setState] = useState<PracticeState>(v3DemoState)
  const [mentor, setMentor] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    v3Api.practiceState().then(setState).catch(() => setState(v3DemoState))
    v3Api.mentorAgentAdvice().then(setMentor).catch(() => setMentor(null))
  }, [])

  const profile = normalizeProfileState(state.profile)
  const nextPlan = Array.isArray(state.next_plan) && state.next_plan.length ? state.next_plan : v3DemoState.next_plan
  const radar = Object.entries(profile.skill_scores).map(([dimension, score]) => ({ dimension, score: Number(score) || 0 }))
  const trend = normalizeTrend(profile.growth_trend)
  const records = Array.isArray(profile.training_records) && profile.training_records.length
    ? profile.training_records.slice(0, 6)
    : v3DemoState.profile.training_records.slice(0, 6)
  const mentorAdvice = stringArray(mentor?.personalized_advice).slice(0, 4)
  const mentorMemory = stringArray(mentor?.memory_scope).slice(0, 5)
  const recentMemory = stringArray(mentor?.recent_memory).slice(0, 4)
  const snapshot = recordValue(mentor?.learner_snapshot)

  return (
    <div className="page-stack v3-page">
      <section className="v3-page-hero profile-hero">
        <div>
          <Tag tone="green">能力成长</Tag>
          <h2>{profile.name} 的研修画像</h2>
          <p>{profile.title} · {profile.department}。画像记录医生在图像识别、观察依据和报告表达上的成长。</p>
        </div>
        <div className="v3-hero-score compact">
          <span>累计正确率</span>
          <strong>{Math.round(profile.accuracy * 100)}%</strong>
          <small>{profile.total_questions} 次研修记录</small>
        </div>
      </section>

      <Card className="mentor-agent-card">
        <SectionTitle
          eyebrow="长期研修记忆"
          title="带教老师个性化建议"
          action={<Tag tone="green">持续更新</Tag>}
        />
        <div className="mentor-agent-grid">
          <div className="mentor-agent-main">
            <Bot size={24} />
            <div>
              <strong>{cleanProfileCopy(String(mentor?.agent_name || '带教老师'))}</strong>
              <p>基于医生的研修作答、错题、收藏、带教追问和报告修改记录，形成下一步训练建议。</p>
            </div>
          </div>
          <div className="mentor-agent-metrics">
            <span><b>{safeNumber(snapshot.total_questions, profile.total_questions)}</b>累计题量</span>
            <span><b>{formatAccuracy(snapshot.accuracy, profile.accuracy)}</b>正确率</span>
            <span><b>{safeNumber(snapshot.wrong_count, profile.wrong_questions.length)}</b>错题</span>
            <span><b>{safeNumber(snapshot.favorite_count, profile.favorite_questions.length)}</b>收藏</span>
          </div>
        </div>
        <div className="mentor-agent-body">
          <div>
            <h3><Brain size={16} /> 记忆范围</h3>
            <div className="mentor-memory-list">
              {mentorMemory.map((item) => <span key={item}>{cleanProfileCopy(item)}</span>)}
            </div>
          </div>
          <div>
            <h3><Target size={16} /> 个性化建议</h3>
            <ul>
              {mentorAdvice.map((item) => <li key={item}>{cleanProfileCopy(item)}</li>)}
            </ul>
          </div>
          <div>
            <h3><ActivitySquare size={16} /> 最近记忆</h3>
            <ul>
              {recentMemory.map((item) => <li key={item}>{cleanProfileCopy(item)}</li>)}
            </ul>
          </div>
        </div>
        <div className="mentor-agent-footer">{cleanProfileCopy(String(mentor?.next_check_in || '下一次完成训练后，带教老师会更新建议。'))}</div>
      </Card>

      <div className="profile-v3-grid">
        <Card className="profile-radar-card">
          <SectionTitle eyebrow="能力雷达" title="核心能力分布" />
          <div className="profile-skill-stack" aria-label="核心能力分布">
            {radar.map((item) => (
              <div className="profile-skill-row" key={item.dimension}>
                <div className="profile-skill-head">
                  <span>{item.dimension}</span>
                  <strong>{Math.round(item.score)} 分</strong>
                </div>
                <div className="profile-skill-meter" aria-hidden="true">
                  <i style={{ width: `${clampPercent(item.score)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="profile-trend-card">
          <SectionTitle eyebrow="成长曲线" title="观察依据与报告表达" action={<Tag tone="green">观察依据 +8%</Tag>} />
          <div className="v3-chart tall">
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trend}>
                <defs>
                  <linearGradient id="profileEvidence" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#2563eb" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0.03} />
                  </linearGradient>
                </defs>
                <Tooltip />
                <Area dataKey="evidence" name="观察依据" stroke="#2563eb" fill="url(#profileEvidence)" strokeWidth={2} />
                <Area dataKey="report" name="报告表达" stroke="#0f766e" fill="transparent" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="profile-v3-grid lower">
        <Card>
          <SectionTitle eyebrow="薄弱项" title="下一步研修方向" />
          <div className="profile-tag-list">
            {profile.weakness_tags.slice(0, 6).map((tag) => (
              <span key={tag}><Target size={15} /> {tag}</span>
            ))}
          </div>
          <div className="profile-plan-list">
            {nextPlan.slice(0, 3).map((item) => (
              <div key={item.label}>
                <BookOpenCheck size={17} />
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.reason}</span>
                </div>
                <Tag tone="blue">{item.count} 题</Tag>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="最近记录" title="研修复盘" />
          <div className="profile-record-list">
            {records.map((record, index) => (
              <div key={`${record.question_id}_${index}`}>
                <ActivitySquare size={16} />
                <div>
                  <strong>{cleanProfileCopy(record.result)}</strong>
                  <span>{record.date} · {recordName(record.question_id, index)}</span>
                </div>
                <b>{record.score}</b>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <SafetyNotice text={state.safety_notice || v3SafetyNotice} />
    </div>
  )
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function normalizeProfileState(value: PracticeState['profile']): PracticeState['profile'] {
  const fallback = v3DemoState.profile
  const profile = value && typeof value === 'object' ? value : fallback
  return {
    ...fallback,
    ...profile,
    accuracy: Number.isFinite(Number(profile.accuracy)) ? Number(profile.accuracy) : fallback.accuracy,
    total_questions: safeNumber(profile.total_questions, fallback.total_questions),
    completed_today: safeNumber(profile.completed_today, fallback.completed_today),
    daily_target: safeNumber(profile.daily_target, fallback.daily_target),
    favorite_questions: Array.isArray(profile.favorite_questions) ? profile.favorite_questions.map(String) : fallback.favorite_questions,
    wrong_questions: Array.isArray(profile.wrong_questions) ? profile.wrong_questions.map(String) : fallback.wrong_questions,
    skill_scores: isNumberRecord(profile.skill_scores) ? profile.skill_scores : fallback.skill_scores,
    weakness_tags: Array.isArray(profile.weakness_tags) ? profile.weakness_tags.map(String).filter(Boolean) : fallback.weakness_tags,
    growth_trend: normalizeTrend(profile.growth_trend),
    training_records: Array.isArray(profile.training_records) ? profile.training_records : fallback.training_records,
  }
}

function normalizeTrend(value: PracticeState['profile']['growth_trend']) {
  const source = Array.isArray(value) && value.length ? value : v3DemoState.profile.growth_trend
  return source.map((item, index) => ({
    date: String(item?.date || `记录${index + 1}`),
    accuracy: safeNumber(item?.accuracy, 0),
    evidence: safeNumber(item?.evidence, 0),
    report: safeNumber(item?.report, 0),
  }))
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function safeNumber(value: unknown, fallback = 0) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, safeNumber(value, 0)))
}

function formatAccuracy(value: unknown, fallback: number) {
  const numeric = safeNumber(value, fallback)
  return `${Math.round((numeric > 1 ? numeric / 100 : numeric) * 100)}%`
}

function recordName(questionId: string, index: number) {
  if (questionId.includes('session')) return '综合小测'
  if (questionId.startsWith('q')) return `研修题 ${index + 1}`
  return '研修记录'
}

function cleanProfileCopy(value: string) {
  return value
    .replace(/带教老师\s*[Aa]gent/g, '带教老师')
    .replace(/长期记忆\s*[Aa]gent/g, '长期研修记忆')
    .replace(/[Aa]gent\s*追问记录/g, '带教追问记录')
    .replace(/[Aa]gent追问/g, '带教追问')
    .replace(/[Aa]gent辅导/g, '带教辅导')
    .replace(/[Aa]gent\s*辅导/g, '带教辅导')
    .replace(/[Aa]gent/g, '带教助手')
}

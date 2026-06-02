import { useEffect, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Award, ClipboardList, Flame, Target, UserRound } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockDashboard } from '../lib/mock'
import type { LearnerProfile } from '../lib/types'

export function PhysicianProfile() {
  const [profile, setProfile] = useState<LearnerProfile>(mockDashboard.learner_profile)

  useEffect(() => {
    api.learnerProfile().then(setProfile).catch(() => setProfile(mockDashboard.learner_profile))
  }, [])

  const radarData = Object.entries(profile.skill_scores).map(([dimension, score]) => ({ dimension, score }))
  const coverage = Object.entries(profile.question_type_coverage).map(([type, count]) => ({ type, count }))

  return (
    <div className="page-stack">
      <Card className="profile-hero">
        <div className="doctor-avatar">
          <UserRound size={36} />
        </div>
        <div>
          <span className="eyebrow">Physician profile</span>
          <h2>{profile.name}</h2>
          <p>{profile.title} · {profile.department} · {profile.hospital}</p>
          <div className="tag-row">
            <Tag tone="green">{profile.training_stage}</Tag>
            <Tag tone="blue">连续训练 {profile.streak_days} 天</Tag>
            <Tag tone="amber">错题 {profile.wrong_questions.length} 题</Tag>
          </div>
        </div>
        <div className="profile-goal">
          <Target size={20} />
          <strong>{profile.training_goal}</strong>
        </div>
      </Card>

      <div className="grid four">
        <MetricCard label="累计训练" value={`${profile.total_questions} 题`} />
        <MetricCard label="当前正确率" value={`${Math.round(profile.accuracy * 100)}%`} />
        <MetricCard label="今日进度" value={`${profile.completed_today}/${profile.daily_target}`} />
        <MetricCard label="收藏题" value={`${profile.favorite_questions.length} 题`} />
      </div>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Ability radar" title="能力雷达" />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <RadarChart data={radarData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="dimension" />
                <Radar dataKey="score" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.24} />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <div className="tag-row">
            {profile.weakness_tags.map((tag) => <Tag key={tag} tone="amber">{tag}</Tag>)}
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Growth" title="成长曲线" action={<Flame size={20} />} />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={profile.growth_trend}>
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Area type="monotone" dataKey="accuracy" name="正确率" stroke="#2563eb" fill="#dbeafe" />
                <Area type="monotone" dataKey="evidence" name="证据边界" stroke="#0f766e" fill="#ccfbf1" />
                <Area type="monotone" dataKey="report" name="报告表达" stroke="#b45309" fill="#fef3c7" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Question types" title="题型覆盖" />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={coverage}>
                <XAxis dataKey="type" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Records" title="最近训练记录" action={<ClipboardList size={20} />} />
          <div className="record-list">
            {profile.training_records.map((record) => (
              <div key={`${record.date}_${record.question_id}_${record.score}`}>
                <span>{record.date}</span>
                <strong>{record.question_id}</strong>
                <Tag tone={record.result === '正确' ? 'green' : 'amber'}>{record.result}</Tag>
                <em>{record.score} 分</em>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle eyebrow="Badges" title="激励与成长徽章" action={<Award size={20} />} />
        <div className="badge-row">
          <div><strong>证据边界守门员</strong><span>完成 4 次错误前提复盘</span></div>
          <div><strong>报告表达进阶</strong><span>报告修改训练得分超过 85</span></div>
          <div><strong>连续训练者</strong><span>连续 {profile.streak_days} 天完成训练</span></div>
        </div>
      </Card>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </Card>
  )
}

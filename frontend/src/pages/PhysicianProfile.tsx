import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ActivitySquare, ArrowRight, Award, BookOpenCheck, CheckCircle2, ClipboardList, Database, FileText, Flame, HardDrive, Medal, Target, Trophy, UserRound } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockDashboard } from '../lib/mock'
import type { LearnerProfile } from '../lib/types'

type ProfileTab = 'overview' | 'records' | 'badges'

export function PhysicianProfile() {
  const [searchParams] = useSearchParams()
  const [profile, setProfile] = useState<LearnerProfile>(mockDashboard.learner_profile)

  useEffect(() => {
    api.learnerProfile().then(setProfile).catch(() => setProfile(mockDashboard.learner_profile))
  }, [])

  const tab = normalizeTab(searchParams.get('tab'))
  const radarData = Object.entries(profile.skill_scores).map(([dimension, score]) => ({ dimension, score }))
  const coverage = Object.entries(profile.question_type_coverage).map(([type, count]) => ({ type, count }))
  const progress = Math.min(100, Math.round((profile.completed_today / Math.max(profile.daily_target, 1)) * 100))
  const sortedSkills = useMemo(() => Object.entries(profile.skill_scores).sort((left, right) => left[1] - right[1]), [profile.skill_scores])
  const weakestSkills = sortedSkills.slice(0, 3)
  const recordStats = useMemo(() => summarizeRecords(profile), [profile])
  const badges = useMemo(() => buildBadges(profile), [profile])
  const earnedBadges = badges.filter((badge) => badge.earned).length
  const updatedAt = formatUpdatedAt(profile.updated_at)

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
            <Tag tone="neutral">{profile.learner_id}</Tag>
          </div>
        </div>
        <div className="profile-goal">
          <Target size={20} />
          <div>
            <strong>{profile.training_goal}</strong>
            <span>今日完成 {progress}% · 已获得 {earnedBadges}/{badges.length} 枚成长徽章</span>
          </div>
        </div>
      </Card>

      <Card className="profile-tabs">
        <Link className={tab === 'overview' ? 'active' : ''} to="/profile"><UserRound size={17} /> 能力概览</Link>
        <Link className={tab === 'records' ? 'active' : ''} to="/profile?tab=records"><ActivitySquare size={17} /> 训练记录</Link>
        <Link className={tab === 'badges' ? 'active' : ''} to="/profile?tab=badges"><Medal size={17} /> 徽章成长</Link>
      </Card>

      <Card className="profile-provenance">
        <div>
          <UserRound size={19} />
          <span>当前训练对象</span>
          <strong>{profile.name}</strong>
          <p>{profile.learner_id} · 单医师 demo learner，后续可扩展为多医师数据库。</p>
        </div>
        <div>
          <HardDrive size={19} />
          <span>画像存储</span>
          <strong>本地 Memory 持久化</strong>
          <p>训练记录、错题、收藏、能力分和弱项标签来自后端 learner profile。</p>
        </div>
        <div>
          <Database size={19} />
          <span>最近更新</span>
          <strong>{updatedAt}</strong>
          <p>答题提交、Agent 辅导标签和报告修改评分会回灌该画像。</p>
        </div>
      </Card>

      <div className="grid four">
        <MetricCard label="累计训练" value={`${profile.total_questions} 题`} />
        <MetricCard label="当前正确率" value={`${Math.round(profile.accuracy * 100)}%`} />
        <MetricCard label="今日进度" value={`${profile.completed_today}/${profile.daily_target}`} />
        <MetricCard label="收藏题" value={`${profile.favorite_questions.length} 题`} />
      </div>

      {tab === 'overview' ? (
        <>
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
              <SectionTitle eyebrow="Weakness plan" title="下一步训练建议" action={<BookOpenCheck size={20} />} />
              <div className="skill-plan-list">
                {weakestSkills.map(([dimension, score]) => (
                  <Link key={dimension} to={dimension.includes('证据') ? '/training?view=wrong' : '/training?source=public'}>
                    <div>
                      <strong>{dimension}</strong>
                      <span>当前 {score} 分 · 推荐 {dimension.includes('事实') ? '复杂组合题' : '错题/公开样例'} 训练</span>
                    </div>
                    <ArrowRight size={16} />
                  </Link>
                ))}
              </div>
            </Card>
          </div>
        </>
      ) : null}

      {tab === 'records' ? (
        <>
          <div className="grid four">
            <MetricCard label="答题提交" value={`${recordStats.answer} 次`} />
            <MetricCard label="考试Session" value={`${recordStats.exam} 场`} />
            <MetricCard label="Agent 辅导" value={`${recordStats.agent} 次`} />
            <MetricCard label="待复盘" value={`${recordStats.review} 项`} />
          </div>
          <div className="grid two">
            <Card>
              <SectionTitle eyebrow="Records" title="训练事件流水" action={<ClipboardList size={20} />} />
              <div className="record-list detailed">
                {profile.training_records.map((record) => (
                  <div key={`${record.date}_${record.question_id}_${record.score}_${record.result}`}>
                    <span>{record.date}</span>
                    <strong>{record.question_id}</strong>
                    <Tag tone={recordTone(record.result)}>{record.result}</Tag>
                    <em>{record.result === 'Agent辅导' ? '追问' : `${record.score} 分`}</em>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <SectionTitle eyebrow="Memory replay" title="画像如何被回灌" action={<ActivitySquare size={20} />} />
              <div className="memory-replay-list">
                <div>
                  <CheckCircle2 size={18} />
                  <strong>提交答案</strong>
                  <span>更新正确率、错题本、弱项标签和相关能力分。</span>
                </div>
                <div>
                  <CheckCircle2 size={18} />
                  <strong>考试交卷</strong>
                  <span>写入整场考试的题量、正确率、平均分和错题摘要，不重复增加单题计数。</span>
                </div>
                <div>
                  <CheckCircle2 size={18} />
                  <strong>Agent 追问</strong>
                  <span>只记录题号、训练标签和生成模式，不保存医师自由追问原文。</span>
                </div>
                <div>
                  <CheckCircle2 size={18} />
                  <strong>报告修改评分</strong>
                  <span>把报告表达、证据边界和安全边界分数写回医师画像。</span>
                </div>
              </div>
              <div className="profile-action-row">
                <Link className="button secondary" to="/training?view=wrong">复盘错题</Link>
                <Link className="button primary" to="/report?tab=judge">做报告训练</Link>
              </div>
            </Card>
          </div>
        </>
      ) : null}

      {tab === 'badges' ? (
        <div className="grid two">
          <Card>
            <SectionTitle eyebrow="Badges" title="激励与成长徽章" action={<Award size={20} />} />
            <div className="badge-row detailed">
              {badges.map((badge) => (
                <div className={badge.earned ? 'earned' : 'locked'} key={badge.title}>
                  {badge.earned ? <Trophy size={18} /> : <Medal size={18} />}
                  <strong>{badge.title}</strong>
                  <span>{badge.description}</span>
                  <em>{badge.earned ? '已获得' : badge.requirement}</em>
                </div>
              ))}
            </div>
          </Card>
          <Card>
            <SectionTitle eyebrow="Growth quests" title="下一组成长任务" action={<Target size={20} />} />
            <div className="quest-list">
              <Link to="/training?source=public"><FileText size={18} /><span>完成 3 道公开复杂样例，强化多事实组合表达。</span><ArrowRight size={16} /></Link>
              <Link to="/training?view=wrong"><ClipboardList size={18} /><span>复盘错题本中证据不足题，争取证据边界提升 5 分。</span><ArrowRight size={16} /></Link>
              <Link to="/report?tab=judge"><Award size={18} /><span>完成 1 次报告修改训练，解锁报告表达进阶徽章。</span><ArrowRight size={16} /></Link>
            </div>
          </Card>
        </div>
      ) : null}
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

function normalizeTab(value: string | null): ProfileTab {
  if (value === 'records' || value === 'badges') return value
  return 'overview'
}

function formatUpdatedAt(value: string): string {
  if (!value) return '待同步'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function recordTone(result: string): 'green' | 'blue' | 'amber' {
  if (result === '正确' || result.includes('完成')) return 'green'
  if (result === 'Agent辅导' || result.includes('考试Session')) return 'blue'
  return 'amber'
}

function summarizeRecords(profile: LearnerProfile) {
  const summary = profile.training_records.reduce(
    (summary, record) => {
      if (record.result.includes('考试Session')) summary.exam += 1
      else if (record.result === 'Agent辅导') summary.agent += 1
      else if (record.result === '报告修改训练') summary.report += 1
      else summary.answer += 1
      if (record.result === '待复盘') summary.review += 1
      return summary
    },
    { answer: 0, exam: 0, agent: 0, report: 0, review: 0 },
  )
  return { ...summary, review: Math.max(summary.review, profile.wrong_questions.length) }
}

function buildBadges(profile: LearnerProfile) {
  const reportRecords = profile.training_records.filter((record) => record.result === '报告修改训练')
  const agentRecords = profile.training_records.filter((record) => record.result === 'Agent辅导')
  return [
    {
      title: '证据边界守门员',
      description: '证据不足识别达到 60 分以上，能主动拒绝题干越界。',
      requirement: '证据不足识别提升到 60',
      earned: (profile.skill_scores['证据不足识别'] || 0) >= 60,
    },
    {
      title: '报告表达进阶',
      description: '报告训练得分超过 85，能区分所见、印象和复核边界。',
      requirement: '完成一次 85 分以上报告修改',
      earned: reportRecords.some((record) => record.score >= 85),
    },
    {
      title: '连续训练者',
      description: `已连续训练 ${profile.streak_days} 天，保持题库和报告训练节奏。`,
      requirement: '连续训练 5 天',
      earned: profile.streak_days >= 5,
    },
    {
      title: 'Agent 协作医师',
      description: '能在刷题中主动追问证据链，并把标签回灌画像。',
      requirement: '完成 3 次 Agent 辅导',
      earned: agentRecords.length >= 3,
    },
  ]
}

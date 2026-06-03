import { useEffect, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ActivitySquare, ArrowRight, BookOpenCheck, Bot, CheckCircle2, ClipboardList, DatabaseZap, FileStack, Gauge, Route, ShieldCheck, Star, Target, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockDashboard } from '../lib/mock'
import type { DashboardPayload, DemoCheckResult } from '../lib/types'

export function Dashboard() {
  const [data, setData] = useState<DashboardPayload>(mockDashboard)
  const [status, setStatus] = useState('连接后端中')
  const [demoCheck, setDemoCheck] = useState<DemoCheckResult | null>(null)
  const [demoCheckStatus, setDemoCheckStatus] = useState<'idle' | 'running' | 'done' | 'failed'>('idle')
  const [demoCheckIntent, setDemoCheckIntent] = useState<'sandbox' | 'persisted'>('sandbox')

  useEffect(() => {
    api.dashboard()
      .then((payload) => {
        setData(payload)
        setStatus(payload.api_source === 'fallback' ? '本地 fallback' : '后端在线')
      })
      .catch(() => {
        setData(mockDashboard)
        setStatus('本地 fallback')
      })
  }, [])

  const runDemoCheck = async (persist = false) => {
    if (demoCheckStatus === 'running') return
    setDemoCheckIntent(persist ? 'persisted' : 'sandbox')
    setDemoCheckStatus('running')
    try {
      const result = await api.platformDemoCheck(persist)
      setDemoCheck(result)
      setDemoCheckStatus('done')
      const nextDashboard = await api.dashboard()
      setData(nextDashboard)
      setStatus(nextDashboard.api_source === 'fallback' ? '本地 fallback' : '后端在线')
    } catch {
      setDemoCheckStatus('failed')
    }
  }

  const completion = Math.round((data.today_training.completed / Math.max(data.today_training.target, 1)) * 100)
  const profile = data.learner_profile
  const readiness = data.platform_readiness
  const readinessSource = readiness.api_source || data.api_source || 'backend'
  const challengeVerified = Boolean(demoCheck?.audit_event_types?.includes('challenge_benchmark'))
  const challengeReceipt = readiness.evidence_receipts.find((item) => item.id === 'challenge_audit') || null
  const latestExamReplay = readiness.latest_exam_replay || null

  return (
    <div className="page-stack">
      <section className="hero-workbench physician-hero">
        <div>
          <span className="eyebrow">Physician training cockpit</span>
          <h2>{profile.name} 的今日内镜训练驾驶舱</h2>
          <p>{profile.title} · {profile.department} · {profile.training_stage}。今日目标是把刷题、错题复盘、报告修改训练和 Agent 辅导串成一次完整训练闭环。</p>
          <div className="hero-actions">
            <Link className="primary-link" to="/training">
              继续刷题 <ArrowRight size={16} />
            </Link>
            <Link className="button secondary" to="/report">
              进入报告训练
            </Link>
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
          <div>
            <strong>{data.today_training.streak_days}</strong>
            <span>连续训练</span>
          </div>
          <div className="hero-metric-wide">
            <strong>{readiness.overall_score}%</strong>
            <span>平台就绪度</span>
          </div>
          <div className="hero-metric-wide">
            <strong>{readiness.real_sample_count}</strong>
            <span>公开图文样例</span>
          </div>
        </div>
      </section>

      <Card className="readiness-board">
        <SectionTitle
          eyebrow="Live system map"
          title="平台真实性与演示路径"
          action={<Tag tone={readinessSource === 'fallback' ? 'amber' : 'green'}>{readinessSource === 'fallback' ? 'frontend fallback' : 'backend live'}</Tag>}
        />
        <div className="readiness-summary">
          <div>
            <Gauge size={20} />
            <span>Provider</span>
            <strong>{readiness.provider_ready ? '真实推理可用' : `${readiness.provider_mode} 模式`}</strong>
          </div>
          <div>
            <DatabaseZap size={20} />
            <span>知识库</span>
            <strong>{readiness.qbank_count} 题 · {readiness.report_template_count} 个模板</strong>
          </div>
          <div>
            <UserRound size={20} />
            <span>画像回灌</span>
            <strong>{readiness.training_record_count} 条训练记录</strong>
          </div>
          <div>
            <ClipboardList size={20} />
            <span>考试复盘</span>
            <strong>{latestExamReplay ? `${latestExamReplay.session_id} · ${latestExamReplay.wrong_count} 题` : '等待交卷'}</strong>
          </div>
          <div>
            <ShieldCheck size={20} />
            <span>模型准入</span>
            <strong>Grade {readiness.admission_grade} · {readiness.admission_provider_called ? 'provider' : 'rule'}</strong>
          </div>
        </div>
        {latestExamReplay ? (
          <div className="dashboard-exam-replay">
            <div className="dashboard-exam-main">
              <ClipboardList size={22} />
              <div>
                <span className="eyebrow">Latest exam session</span>
                <strong>{latestExamReplay.session_id}</strong>
                <p>{latestExamReplay.detail} {latestExamReplay.profile_updated ? '已沉淀到医师画像，复盘不会重复增加单题计数。' : '画像回灌状态待核查。'}</p>
              </div>
            </div>
            <div className="dashboard-exam-metrics">
              <div><span>题量</span><strong>{latestExamReplay.answered_count}</strong></div>
              <div><span>正确率</span><strong>{latestExamReplay.accuracy}%</strong></div>
              <div><span>平均分</span><strong>{latestExamReplay.average_score}</strong></div>
              <div><span>错题</span><strong>{latestExamReplay.wrong_count}</strong></div>
            </div>
            <div className="dashboard-exam-actions">
              <Link className="button primary" to={latestExamReplay.href}>
                <Target size={16} /> 复盘本场考试
              </Link>
              <Link className="button secondary" to={latestExamReplay.profile_href}>
                <UserRound size={16} /> 查看画像记录
              </Link>
            </div>
          </div>
        ) : (
          <div className="dashboard-exam-replay empty">
            <div className="dashboard-exam-main">
              <ClipboardList size={22} />
              <div>
                <span className="eyebrow">Latest exam session</span>
                <strong>尚未生成考试复盘收据</strong>
                <p>进入考试模式并交卷后，系统会把整场摘要写入画像，并在这里展示 session 级错题复盘入口。</p>
              </div>
            </div>
            <Link className="button secondary" to="/training?mode=exam">
              <ArrowRight size={16} /> 开始考试模式
            </Link>
          </div>
        )}
        <div className={`demo-check-console ${demoCheckStatus}`}>
          <div className="demo-check-main">
            <ActivitySquare size={22} />
            <div>
              <span className="eyebrow">Verifiable loop check</span>
              <strong>{demoCheck ? `${demoCheck.source_dataset} · ${demoCheck.question_title}` : '一键跑通医生训练闭环'}</strong>
              <p>
                {demoCheck
                  ? `${demoCheck.persisted ? '正式留痕' : '沙盒验证'} · 写入验证 ${demoCheck.write_verified ? '通过' : '待核查'} · 挑战基准 ${challengeVerified ? '已验证' : '待核查'} · ${demoCheck.restored_after_run ? '已自动恢复数据' : '已保留画像/审计'} · Provider ${demoCheck.provider_ready ? '真实可用' : `${demoCheck.provider_mode} 模式`}`
                  : '默认沙盒触发公开样例提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、画像回灌和审计收据；写入后自动恢复。'}
              </p>
            </div>
          </div>
          <div className={`challenge-proof-strip ${challengeVerified ? 'verified' : challengeReceipt?.status === 'audited' ? 'persisted' : 'pending'}`}>
            <ShieldCheck size={18} />
            <div>
              <strong>
                {challengeVerified
                  ? '本轮沙盒已验证 challenge_benchmark'
                  : challengeReceipt?.status === 'audited'
                    ? '已有持久挑战基准审计'
                    : '挑战基准可用沙盒即时验证'}
              </strong>
              <span>
                {challengeVerified
                  ? '本次自检已真实触发挑战基准、写入摘要审计并按沙盒策略恢复数据；需要留痕时可点击“写入演示画像”。'
                  : challengeReceipt?.detail || '沙盒自检会真实触发 challenge_benchmark，但返回前恢复 audit_logs.json。'}
              </span>
            </div>
            <Link className="button secondary" to="/training?view=challenge">
              <ArrowRight size={15} /> 比拼模式
            </Link>
          </div>
          <div className="demo-check-actions">
            <button className="button primary" type="button" onClick={() => runDemoCheck(false)} disabled={demoCheckStatus === 'running' || readinessSource === 'fallback'}>
              <ActivitySquare size={17} /> {demoCheckStatus === 'running' && demoCheckIntent === 'sandbox' ? '沙盒运行中' : '沙盒自检'}
            </button>
            <button className="button secondary" type="button" onClick={() => runDemoCheck(true)} disabled={demoCheckStatus === 'running' || readinessSource === 'fallback'}>
              <ShieldCheck size={17} /> {demoCheckStatus === 'running' && demoCheckIntent === 'persisted' ? '写入中' : '写入演示画像'}
            </button>
          </div>
          {demoCheckStatus === 'failed' ? <span className="demo-check-error">后端自检未完成，请确认 FastAPI 在线后重试。</span> : null}
          {readinessSource === 'fallback' ? <span className="demo-check-error">当前为前端 fallback，不能伪造自检通过。</span> : null}
          {demoCheck ? (
            <div className="demo-check-receipts">
              {demoCheck.receipts.map((item) => (
                <div className="receipt-tile compact-receipt" key={item.id}>
                  <span className={`status-dot tone-${item.tone}`} />
                  <div>
                    <strong>{item.label}</strong>
                    <em>{item.status}</em>
                    <p>{item.detail}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
        <div className="readiness-grid">
          {readiness.modules.map((item) => (
            <Link className="readiness-tile" key={item.id} to={item.href}>
              <span className={`status-dot tone-${item.tone}`} />
              <div>
                <strong>{item.label}</strong>
                <em>{item.status}</em>
                <p>{item.detail}</p>
              </div>
              <ArrowRight size={15} />
            </Link>
          ))}
        </div>
        <div className="evidence-receipts">
          <div className="demo-path-title">
            <ShieldCheck size={18} />
            <strong>可核验证据收据</strong>
          </div>
          <div className="receipt-grid">
            {readiness.evidence_receipts.map((item) => (
              <Link className="receipt-tile" key={item.id} to={item.href}>
                <span className={`status-dot tone-${item.tone}`} />
                <div>
                  <strong>{item.label}</strong>
                  <em>{item.status}</em>
                  <p>{item.detail}</p>
                </div>
              </Link>
            ))}
          </div>
        </div>
        <div className="knowledge-source-chain">
          <div className="demo-path-title">
            <FileStack size={18} />
            <strong>真实数据来源链</strong>
          </div>
          <p className="knowledge-chain-note">来源链只证明本地公开教学样例和模板知识库被平台功能消费，不代表批量临床评测或自动诊断。</p>
          <div className="knowledge-chain-grid">
            {readiness.knowledge_source_chain.map((item) => (
              <Link className="knowledge-chain-card" key={item.id} to={item.href}>
                <span className={`status-dot tone-${item.tone}`} />
                <div>
                  <strong>{item.label}</strong>
                  <em>{item.source_file} · {item.record_count} 条</em>
                  <p>{item.proof}</p>
                  <div className="knowledge-chain-tags">
                    {item.sample_ids.slice(0, 4).map((sampleId) => <span key={`${item.id}_${sampleId}`}>{sampleId}</span>)}
                  </div>
                  <div className="knowledge-chain-tags muted">
                    {item.used_by.map((target) => <span key={`${item.id}_${target}`}>{target}</span>)}
                  </div>
                </div>
                <ArrowRight size={15} />
              </Link>
            ))}
          </div>
        </div>
        <div className="demo-path">
          <div className="demo-path-title">
            <Route size={18} />
            <strong>建议评委演示路线</strong>
          </div>
          {readiness.demo_path.map((step) => (
            <Link className="demo-step" key={`${step.step}_${step.title}`} to={step.href}>
              <span>{step.step}</span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.detail}</p>
                <em>{step.expected_state}</em>
              </div>
              <CheckCircle2 size={16} />
            </Link>
          ))}
        </div>
        {readiness.gaps.length ? (
          <div className="gap-strip">
            {readiness.gaps.slice(0, 2).map((gap) => <span key={gap}>{gap}</span>)}
          </div>
        ) : null}
      </Card>

      <div className="grid four">
        <Card className="quick-card">
          <SectionTitle eyebrow="Next" title="继续训练" action={<BookOpenCheck size={20} />} />
          <strong>{data.continue_training.title}</strong>
          <p>{data.continue_training.reason}</p>
          <div className="tag-row">
            <Tag tone="blue">{data.continue_training.source_dataset}</Tag>
          </div>
          <Link className="inline-link" to="/training">进入题目</Link>
        </Card>
        <Card className="quick-card">
          <SectionTitle eyebrow="Review" title="错题本" action={<ClipboardList size={20} />} />
          <strong>{data.wrong_count} 题待复盘</strong>
          <p>优先处理证据不足、错误前提和报告安全表达。</p>
          <Link className="inline-link" to="/training?view=wrong">开始复盘</Link>
        </Card>
        <Card className="quick-card">
          <SectionTitle eyebrow="Saved" title="收藏夹" action={<Star size={20} />} />
          <strong>{data.favorite_count} 题已收藏</strong>
          <p>保留高价值公开样例与报告改写题，方便赛前演示。</p>
          <Link className="inline-link" to="/training?view=favorite">查看收藏</Link>
        </Card>
        <Card className="quick-card">
          <SectionTitle eyebrow="Goal" title="培训目标" action={<Target size={20} />} />
          <strong>{profile.training_goal}</strong>
          <p>{profile.hospital}</p>
          <Link className="inline-link" to="/profile">查看画像</Link>
        </Card>
      </div>

      <div className="grid three plan-grid">
        {data.today_plan.map((item) => (
          <Card key={item.label} className="plan-card">
            <div className="plan-status">{item.status}</div>
            <h3>{item.label}</h3>
            <strong>{item.target} 个训练单元</strong>
            <Link to={item.href}>进入 <ArrowRight size={15} /></Link>
          </Card>
        ))}
      </div>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Physician memory" title={`${profile.name} 能力画像`} action={<UserRound size={20} />} />
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
          <SectionTitle eyebrow="Growth line" title="最近能力成长线" />
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={230}>
              <AreaChart data={data.growth_trend}>
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Area type="monotone" dataKey="accuracy" name="正确率" stroke="#2563eb" fill="#dbeafe" />
                <Area type="monotone" dataKey="evidence" name="证据边界" stroke="#0f766e" fill="#ccfbf1" />
              </AreaChart>
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

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Agent coaching" title="最近辅导摘要" action={<Bot size={20} />} />
          <ul className="timeline-list">
            {data.recent_tutor_summary.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Card>

        <Card>
          <SectionTitle eyebrow="Curriculum coverage" title="推荐训练分布" />
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

      <div className="grid four">
        <Card>
          <SectionTitle eyebrow="Guardrail" title="当前辅导模型" />
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
          <SectionTitle eyebrow="Admission" title="最近模型准入" action={<Gauge size={20} />} />
          <div className="model-mini">
            <strong>{data.model_admission_state.provider_name}</strong>
            <span>Grade {data.model_admission_state.grade} · {data.model_admission_state.total_score} 分 · {data.model_admission_state.mode}</span>
          </div>
          <div className="tag-row">
            <Tag tone={data.model_admission_state.safe_for_training ? 'green' : 'amber'}>
              {data.model_admission_state.safe_for_training ? '可进入人工复核' : '规则/待复核'}
            </Tag>
            <Tag tone={data.model_admission_state.provider_called ? 'green' : 'blue'}>
              {data.model_admission_state.provider_called ? 'provider called' : 'rule draft'}
            </Tag>
          </div>
          <p className="source-note">{data.model_admission_state.recommendation}</p>
        </Card>
        <Card>
          <SectionTitle eyebrow="Benchmarks" title="平台对标与素材来源" />
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
          <SectionTitle eyebrow="Safety" title="医疗安全边界" />
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

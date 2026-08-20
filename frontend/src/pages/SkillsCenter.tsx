import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivitySquare, ArrowRight, CheckCircle2, ClipboardList, PlayCircle, ShieldAlert, Sparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, mockSkills, safetyNotice } from '../lib/mock'
import type { Question, SkillDefinition, SkillRunPayload, SkillRunReceipt } from '../lib/types'

const toneByRisk = {
  low: 'green',
  medium: 'amber',
  high: 'red',
} as const

type SkillRunView = {
  skill: SkillDefinition
  result: Record<string, unknown>
  ranAt: string
}

export function SkillsCenter() {
  const [skills, setSkills] = useState<SkillDefinition[]>(mockSkills)
  const [questions, setQuestions] = useState<Question[]>(mockQuestions)
  const [selectedQuestionId, setSelectedQuestionId] = useState('q005')
  const [runView, setRunView] = useState<SkillRunView | null>(null)
  const [running, setRunning] = useState('')

  useEffect(() => {
    api.skills().then((items) => setSkills(items))
    api.questions().then((items) => {
      setQuestions(items.length ? items : mockQuestions)
      if (items[0]?.id) setSelectedQuestionId(items[0].id)
    })
  }, [])

  const runSkill = async (skill: SkillDefinition) => {
    setRunning(skill.id)
    try {
      const result = await api.runSkill(skill, buildSkillPayload(skill, activeQuestion))
      setRunView({ skill, result, ranAt: new Date().toLocaleString() })
    } finally {
      setRunning('')
    }
  }

  const activeQuestion = questions.find((item) => item.id === selectedQuestionId) || questions[0]
  const receipt = runView ? skillRunReceipt(runView.result) : null
  const auditReceiptLabel = receipt?.audit_log_id
    ? '审计收据'
    : runView?.result.api_source === 'fallback'
      ? '本地预览'
      : '运行后审计'

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">受控技能</span>
          <h2>受控研修技能编排台</h2>
          <p>把带教辅导、评分、报告、卡片和安全审查拆成可审计技能；医生端只看到运行摘要，开发细节按需展开。</p>
        </div>
        <Sparkles size={42} />
      </Card>

      <Card className="skill-console">
        <div>
          <span className="eyebrow">运行上下文</span>
          <h3>当前运行样例</h3>
          <p>{activeQuestion ? `${activeQuestion.title} · ${activeQuestion.source_dataset}` : '默认训练题样例'}</p>
        </div>
        <label>
          <span>题目输入</span>
          <select value={selectedQuestionId} onChange={(event) => setSelectedQuestionId(event.target.value)}>
            {questions.slice(0, 12).map((question) => (
              <option key={question.id} value={question.id}>{question.id} · {question.title}</option>
            ))}
          </select>
        </label>
        <div className="skill-console-status">
          <Tag tone={runView?.result.api_source === 'fallback' ? 'amber' : 'green'}>{runView?.result.api_source === 'fallback' ? '本地预览' : '服务端可用'}</Tag>
          <Tag tone="amber">医生复核</Tag>
          <Tag tone={receipt?.audit_log_id ? 'blue' : 'neutral'}>{auditReceiptLabel}</Tag>
        </div>
      </Card>

      <div className="skills-grid">
        {skills.map((skill) => (
          <Card key={skill.id} className={`skill-card ${skill.enabled ? '' : 'disabled-skill'}`}>
            <SectionTitle eyebrow={skill.category} title={skill.name} action={<Tag tone={toneByRisk[skill.risk_level]}>{skill.risk_level}</Tag>} />
            <p className="muted">{skill.description}</p>
            <div className="skill-schema-row">
              <span>输入：{Object.keys(skill.input_schema || {}).join(' / ') || '平台上下文'}</span>
              <span>输出：{Object.keys(skill.output_schema || {}).join(' / ') || '结构化结果'}</span>
            </div>
            <button className="button secondary" type="button" onClick={() => runSkill(skill)} disabled={running === skill.id || !skill.enabled}>
              <PlayCircle size={16} /> {running === skill.id ? '运行中...' : '运行到样例'}
            </button>
          </Card>
        ))}
      </div>

      {runView ? (
        <Card className="skill-result-card">
          <SectionTitle
            eyebrow="技能结果"
            title="最近一次受控调用"
            action={<Tag tone={runView.result.api_source === 'fallback' ? 'amber' : 'green'}>{runView.result.api_source === 'fallback' ? '本地预览' : '服务端返回'}</Tag>}
          />
          <div className="skill-result-head">
            <div>
              <span>{runView.skill.name}</span>
              <strong>{summarizeSkillResult(runView.result)}</strong>
              <em>{runView.ranAt}</em>
            </div>
            <div className="skill-review-state">
              {runView.result.doctor_review_required ? <ShieldAlert size={20} /> : <CheckCircle2 size={20} />}
              <span>{runView.result.doctor_review_required ? '需要医生复核' : '低风险自动通过'}</span>
            </div>
          </div>
          <div className="skill-output-grid">
            <div>
              <ClipboardList size={18} />
              <strong>输出摘要</strong>
              <p>{primarySkillDetail(runView.result)}</p>
            </div>
            <div>
              <ActivitySquare size={18} />
              <strong>训练闭环</strong>
              <p>{runView.skill.category === 'report' ? '可进入报告中心继续修改训练。' : runView.skill.category === 'card' ? '可进入科普卡片做医生审核前沟通草稿。' : '可回到题库继续刷题并写入医师画像。'}</p>
            </div>
          </div>
          {receipt ? (
            <div className={`skill-run-receipt ${runView.result.api_source === 'fallback' ? 'fallback' : 'synced'}`}>
              <div className="skill-receipt-head">
                <CheckCircle2 size={18} />
                <div>
                  <strong>{runView.result.api_source === 'fallback' ? '本地技能预览' : '服务端技能运行收据'}</strong>
                  <span>{receipt.audit_log_id ? `已写入 skill_run 审计：${receipt.audit_log_id}` : '当前没有后端审计 ID；仅作前端预览。'}</span>
                </div>
              </div>
              <div className="skill-receipt-metrics">
                <div><span>风险等级</span><strong>{receipt.risk_level || runView.skill.risk_level}</strong></div>
                <div><span>复核状态</span><strong>{receipt.doctor_review_required ? '医生复核' : '低风险通过'}</strong></div>
                <div><span>收据时间</span><strong>{receipt.created_at || runView.ranAt}</strong></div>
              </div>
              <TraceChips title="输入来源" items={receipt.input_trace || []} />
              <TraceChips title="执行来源" items={receipt.source_trace || []} />
              {receipt.next_actions?.length ? (
                <div className="skill-receipt-actions">
                  {receipt.next_actions.map((action) => (
                    <Link to={action.href || '/training'} key={`${action.label}_${action.href}`}>
                      {action.label || '继续训练'} <ArrowRight size={15} />
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="skill-link-row">
            <Link to="/training">题库刷题 <ArrowRight size={15} /></Link>
            <Link to="/report">报告训练 <ArrowRight size={15} /></Link>
            <Link to="/audit">审计日志 <ArrowRight size={15} /></Link>
          </div>
          <details className="skill-json-details">
            <summary>高级排查信息</summary>
            <pre className="json-view">{JSON.stringify(runView.result, null, 2)}</pre>
          </details>
          <div className="safety-mini">{String(runView.result.safety_notice || safetyNotice)}</div>
        </Card>
      ) : null}
    </div>
  )
}

function buildSkillPayload(skill: SkillDefinition, question: Question): SkillRunPayload {
  const selectedAnswer = question.options.find((option) => option !== question.answer) || question.answer
  if (skill.id === 'answer_explain' || skill.id === 'atomic_feedback') {
    return { question_id: question.id, selected_answer: selectedAnswer }
  }
  if (skill.id === 'question_hint' || skill.id === 'false_premise_guard') {
    return { question_id: question.id }
  }
  if (skill.id === 'next_question') {
    return { learner_id: 'demo_learner' }
  }
  if (skill.id === 'report_structure') {
    return {
      finding_text: `${question.case_summary} ${question.image_placeholder}`,
      exam_type: 'gastroscopy',
    }
  }
  if (skill.id === 'patient_card') {
    return {
      diagnosis_summary: `${question.title}：${question.explanation} 需由医生结合完整检查和病理结果复核后再用于患者沟通。`,
    }
  }
  if (skill.id === 'safety_review') {
    return {
      text: '本图可直接证明胃癌并建议立即治疗。请改为保留不确定性、提示补充检查并要求医生复核。',
    }
  }
  if (skill.id === 'audit_log') {
    return {
      event_type: 'skill_run',
      summary: `技能编排演示：${skill.name} 已完成一次受控调用。`,
    }
  }
  return { question_id: question.id }
}

function skillRunReceipt(result: Record<string, unknown>): SkillRunReceipt | null {
  const receipt = result.skill_run_receipt
  return receipt && typeof receipt === 'object' && !Array.isArray(receipt)
    ? receipt as SkillRunReceipt
    : null
}

function TraceChips({ title, items }: { title: string; items: NonNullable<SkillRunReceipt['input_trace']> }) {
  if (!items.length) return null
  return (
    <div className="skill-trace-block">
      <strong>{title}</strong>
      <div>
        {items.map((item) => (
          <span className={item.used ? 'used' : ''} key={`${item.source_type || title}_${item.label}_${item.detail}`}>
            {item.label || item.source_type || '来源'}
          </span>
        ))}
      </div>
    </div>
  )
}

function summarizeSkillResult(result: Record<string, unknown>): string {
  if (typeof result.hint === 'string') return result.hint
  if (typeof result.explanation === 'string') return result.explanation
  if (typeof result.message === 'string') return result.message
  if (Array.isArray(result.atomic_feedback)) return `返回 ${result.atomic_feedback.length} 条原子反馈。`
  if (Array.isArray(result.atomic_trace)) return `返回 ${result.atomic_trace.length} 条前提鲁棒证据。`
  if (Array.isArray(result.recommendations)) return `生成 ${result.recommendations.length} 条下一步训练建议。`
  if (result.draft && typeof result.draft === 'object') return '已生成医生审核前结构化报告草稿。'
  if (result.card && typeof result.card === 'object') return '已生成医生审核前科普卡片草稿。'
  if (typeof result.log_id === 'string') return `审计记录已写入：${result.log_id}`
  return '技能已完成受控运行。'
}

function primarySkillDetail(result: Record<string, unknown>): string {
  const atomic = Array.isArray(result.atomic_feedback) ? result.atomic_feedback : Array.isArray(result.atomic_trace) ? result.atomic_trace : []
  if (atomic.length) {
    return atomic
      .slice(0, 2)
      .map((item) => {
        const record = item && typeof item === 'object' ? item as Record<string, unknown> : {}
        return `${record.skill_dimension || '证据'}：${record.evidence || record.fact || '待复核'}`
      })
      .join('；')
  }
  if (result.draft && typeof result.draft === 'object') {
    const draft = result.draft as Record<string, unknown>
    return Array.isArray(draft.review_points) ? draft.review_points.slice(0, 2).join('；') : '报告草稿已附带复核点。'
  }
  if (result.card && typeof result.card === 'object') {
    const card = result.card as Record<string, unknown>
    return typeof card.disclaimer === 'string' ? card.disclaimer : '科普卡片需医生审核后再分享。'
  }
  if (Array.isArray(result.recommendations)) return result.recommendations.slice(0, 2).join('；')
  return typeof result.safety_notice === 'string' ? result.safety_notice : safetyNotice
}

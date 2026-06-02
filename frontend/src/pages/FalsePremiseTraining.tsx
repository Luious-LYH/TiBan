import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, Eye, RotateCcw, Send, ShieldCheck, Target } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { Question, SubmissionResponse } from '../lib/types'

type SessionStats = {
  attempts: number
  correct: number
}

export function FalsePremiseTraining({ onSubmission }: { onSubmission?: (submission: SubmissionResponse, question: Question) => void }) {
  const [questions, setQuestions] = useState<Question[]>(mockQuestions.filter((q) => q.false_premise_flag))
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState('')
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<SessionStats>({ attempts: 0, correct: 0 })

  useEffect(() => {
    api.questions({ falsePremise: true }).then((items) => {
      setQuestions(items.length ? items : mockQuestions.filter((q) => q.false_premise_flag))
      setIndex(0)
      setSelected('')
      setSubmission(null)
    })
  }, [])

  const question = questions[index % Math.max(questions.length, 1)] || mockQuestions.find((q) => q.false_premise_flag) || mockQuestions[0]
  const unsupportedFact = question.atomic_trace.find((fact) => !fact.supported)
  const accuracy = stats.attempts ? Math.round((stats.correct / stats.attempts) * 100) : 0
  const apiSource = submission?.api_source === 'fallback' ? 'frontend fallback' : submission ? 'backend live' : '等待提交'

  const submit = async () => {
    if (!selected || submission) return
    setLoading(true)
    try {
      const result = await api.submit(question, selected)
      setSubmission(result)
      setStats((current) => ({
        attempts: current.attempts + 1,
        correct: current.correct + (result.is_correct ? 1 : 0),
      }))
      onSubmission?.(result, question)
    } finally {
      setLoading(false)
    }
  }

  const next = () => {
    setIndex((current) => (current + 1) % Math.max(questions.length, 1))
    setSelected('')
    setSubmission(null)
  }

  return (
    <div className="page-stack">
      <Card className="focus-band premise-hero">
        <div>
          <span className="eyebrow">False premise guard</span>
          <h2>错误前提训练靶场</h2>
          <p>林知远医师先独立判断题干假设是否被图像支持，提交后才解锁答案、证据链和模型准入参考。</p>
        </div>
        <ShieldCheck size={42} />
      </Card>

      <Card className="premise-scoreboard">
        <div>
          <Target size={22} />
          <span>本轮命中率</span>
          <strong>{accuracy}%</strong>
        </div>
        <div>
          <span>已作答</span>
          <strong>{stats.attempts}</strong>
        </div>
        <div>
          <span>题目池</span>
          <strong>{questions.length}</strong>
        </div>
        <div>
          <span>接口状态</span>
          <strong>{apiSource}</strong>
        </div>
      </Card>

      <div className="premise-training-grid">
        <Card className="image-panel">
          <SectionTitle eyebrow={question.source_dataset} title="公开内镜样例" />
          <img className="endo-image" src={question.image_url || '/assets/synthetic-endoscopy-training.svg'} alt="错误前提训练内镜图像" />
          <p className="muted">{question.image_placeholder}</p>
          <div className="case-box">{question.case_summary}</div>
          <div className="tag-row">
            <Tag tone="blue">{question.body_part}</Tag>
            <Tag tone="amber">{question.difficulty}</Tag>
            <Tag tone="red">错误前提</Tag>
          </div>
          <div className="source-note">{question.citation_note}</div>
        </Card>

        <Card>
          <SectionTitle eyebrow={question.question_class} title={question.title} action={<Tag tone={submission ? 'green' : 'amber'}>{submission ? '已解锁' : '独立判断中'}</Tag>} />
          <p className="question-text">{question.question}</p>
          <div className="premise-box premise-locked">
            <AlertTriangle size={18} />
            <span>{submission ? '已解锁题干前提审查结果。' : '提交前仅提示：先找图像证据，再判断题干是否越界；不要因为题干强叙述而默认成立。'}</span>
          </div>
          <div className="option-list">
            {question.options.map((option) => {
              const isCorrectAnswer = submission && option === question.answer
              const isWrongSelected = submission && selected === option && option !== question.answer
              return (
                <button
                  key={option}
                  className={`option-button ${selected === option ? 'selected' : ''} ${isCorrectAnswer ? 'correct-choice' : ''} ${isWrongSelected ? 'wrong-choice' : ''}`}
                  type="button"
                  onClick={() => setSelected(option)}
                  disabled={Boolean(submission)}
                >
                  <span>{option}</span>
                  {selected === option || isCorrectAnswer ? <CheckCircle2 size={18} /> : null}
                </button>
              )
            })}
          </div>
          <div className="toolbar">
            <button className="button primary" type="button" onClick={submit} disabled={!selected || loading || Boolean(submission)}>
              <Send size={17} /> 锁定判断
            </button>
            <button className="button secondary" type="button" onClick={next}>
              <RotateCcw size={17} /> 下一题
            </button>
          </div>
          {submission ? (
            <div className={`result-box ${submission.is_correct ? 'correct' : 'wrong'}`}>
              <strong>{submission.is_correct ? '识别成功' : '需要复盘错误前提'}</strong>
              <span>得分 {submission.score} · {submission.error_tags.join('、') || '无错因'}</span>
              <p>{submission.explanation}</p>
            </div>
          ) : null}
        </Card>

        <Card className="premise-guard-card">
          <SectionTitle eyebrow="Evidence unlock" title="证据链与准入意义" action={<Eye size={19} />} />
          {submission ? (
            <>
              <div className="evidence-unlocked">
                <strong>不成立/证据不足的关键事实</strong>
                <p>{unsupportedFact?.fact || '本题需要逐条核验题干事实是否被图像支持。'}</p>
                <span>{unsupportedFact?.evidence || '请回到图像观察与题干表达逐条对照。'}</span>
              </div>
              <div className="mini-fact-list">
                {question.atomic_trace.map((fact) => (
                  <span key={fact.id}>{fact.skill_dimension} · {fact.supported ? '支持' : '证据不足'} · {fact.evidence}</span>
                ))}
              </div>
              <div className="next-card">{submission.next_recommendation}</div>
            </>
          ) : (
            <div className="empty-state">
              提交后解锁原子事实、证据不足原因和复盘建议。这个页面可作为“模型准入测试”的错误前提样例，也可作为医师训练题。
            </div>
          )}
          <div className="tag-row">
            {question.teaching_tags.map((tag) => <Tag key={tag} tone="amber">{tag}</Tag>)}
          </div>
          <div className="safety-mini">{submission?.safety_notice || safetyNotice}</div>
        </Card>
      </div>
    </div>
  )
}

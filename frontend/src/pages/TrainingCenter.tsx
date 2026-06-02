import { useEffect, useMemo, useState } from 'react'
import { Bot, CheckCircle2, Eye, Lightbulb, RotateCcw, Send, ShieldAlert } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { Question, SubmissionResponse } from '../lib/types'

export function TrainingCenter({ onSubmission }: { onSubmission: (submission: SubmissionResponse, question: Question) => void }) {
  const [questions, setQuestions] = useState<Question[]>(mockQuestions)
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState('')
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null)
  const [hint, setHint] = useState('智能辅导会先追问依据，不直接泄露答案。')
  const [loading, setLoading] = useState(false)
  const question = questions[index] || mockQuestions[0]

  useEffect(() => {
    api.questions().then((items) => setQuestions(items.length ? items : mockQuestions))
  }, [])

  const evidence = useMemo(() => question.atomic_trace.map((fact) => fact.evidence).join(' / '), [question])

  const submit = async () => {
    if (!selected) return
    setLoading(true)
    const result = await api.submit(question, selected)
    setSubmission(result)
    onSubmission(result, question)
    setLoading(false)
  }

  const askHint = async () => {
    setLoading(true)
    const result = await api.hint(question)
    const sourceNotice = result.api_source === 'fallback' ? '（当前为本地 fallback 提示）' : ''
    setHint(`${result.hint} ${result.follow_up_question}${sourceNotice}`)
    setLoading(false)
  }

  const next = () => {
    setIndex((value) => (value + 1) % questions.length)
    setSelected('')
    setSubmission(null)
    setHint('智能辅导会先追问依据，不直接泄露答案。')
  }

  return (
    <div className="page-stack">
      <div className="training-grid">
        <Card className="image-panel">
          <SectionTitle eyebrow="Case image" title="内镜图像与病例摘要" />
          <img className="endo-image" src={question.image_url || '/assets/synthetic-endoscopy-training.svg'} alt="合成内镜教学图像" />
          <p className="muted">{question.image_placeholder}</p>
          <div className="case-box">{question.case_summary}</div>
          <div className="tag-row">
            <Tag tone="blue">{question.source_type}</Tag>
            <Tag tone="green">{question.difficulty}</Tag>
            {question.false_premise_flag ? <Tag tone="red">错误前提</Tag> : null}
          </div>
        </Card>

        <Card className="question-panel">
          <SectionTitle eyebrow="Question" title={question.title} />
          <p className="question-text">{question.question}</p>
          <div className="option-list">
            {question.options.map((option) => (
              <button key={option} className={`option-button ${selected === option ? 'selected' : ''}`} type="button" onClick={() => setSelected(option)}>
                <span>{option}</span>
                {selected === option ? <CheckCircle2 size={18} /> : null}
              </button>
            ))}
          </div>
          <div className="toolbar">
            <button className="button secondary" type="button" onClick={askHint} disabled={loading}>
              <Lightbulb size={17} /> 提示一下
            </button>
            <button className="button primary" type="button" onClick={submit} disabled={!selected || loading}>
              <Send size={17} /> 提交答案
            </button>
            <button className="icon-button" type="button" onClick={next} title="下一题">
              <RotateCcw size={17} />
            </button>
          </div>
          {submission ? (
            <div className={`result-box ${submission.is_correct ? 'correct' : 'wrong'}`}>
              <strong>{submission.is_correct ? '回答正确' : '需要复盘'}</strong>
              <span>得分 {submission.score} · {submission.error_tags.join('、') || '无错因'}</span>
              <p>{submission.explanation}</p>
            </div>
          ) : null}
        </Card>

        <Card className="tutor-panel">
          <SectionTitle eyebrow="Tutor agent" title="智能辅导面板" />
          <div className="chat-bubble agent">
            <Bot size={18} />
            <p>{hint}</p>
          </div>
          <div className="evidence-box">
            <div>
              <Eye size={17} />
              <strong>查看依据</strong>
            </div>
            <p>{evidence}</p>
          </div>
          <div className="agent-actions">
            <button className="button secondary" type="button" onClick={askHint}>
              <Lightbulb size={16} /> 苏格拉底式追问
            </button>
            <a className="button secondary" href="/feedback">
              <ShieldAlert size={16} /> 错因分析
            </a>
          </div>
          <div className="safety-mini">{safetyNotice}</div>
        </Card>
      </div>
    </div>
  )
}

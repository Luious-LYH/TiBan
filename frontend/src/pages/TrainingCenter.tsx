import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Bookmark, Bot, CheckCircle2, Clock, Eye, GraduationCap, Lightbulb, MessageSquare, RotateCcw, Send, ShieldAlert, Trophy } from 'lucide-react'
import { Card, EmptyState, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { Question, SubmissionResponse } from '../lib/types'

type ChatMessage = {
  role: 'agent' | 'doctor'
  text: string
}

type Filters = {
  bodyPart: string
  task: string
  difficulty: string
  questionType: string
  sourceDataset: string
}

const emptyFilters: Filters = {
  bodyPart: '',
  task: '',
  difficulty: '',
  questionType: '',
  sourceDataset: '',
}

export function TrainingCenter({ onSubmission }: { onSubmission: (submission: SubmissionResponse, question: Question) => void }) {
  const [searchParams] = useSearchParams()
  const [questions, setQuestions] = useState<Question[]>(mockQuestions)
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [index, setIndex] = useState(0)
  const [selected, setSelected] = useState('')
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null)
  const [hint, setHint] = useState('练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  const [loading, setLoading] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [chat, setChat] = useState<ChatMessage[]>([
    { role: 'agent', text: '林知远医师，先看图像证据：部位、形态、颜色、边界，再判断题干是否越界。' },
  ])

  const mode = searchParams.get('mode') === 'exam' ? 'exam' : 'practice'
  const view = searchParams.get('view') || ''
  const source = searchParams.get('source') || ''

  useEffect(() => {
    api.qbank({
      onlyWrong: view === 'wrong',
      onlyFavorites: view === 'favorite',
      mode,
    }).then((items) => setQuestions(items.length ? items : mockQuestions))
  }, [mode, view])

  const filterOptions = useMemo(() => {
    const values = (key: keyof Question) => Array.from(new Set(questions.map((q) => String(q[key] || '')).filter(Boolean)))
    return {
      bodyPart: values('body_part'),
      task: values('task'),
      difficulty: values('difficulty'),
      questionType: values('question_type'),
      sourceDataset: values('source_dataset'),
    }
  }, [questions])

  const filteredQuestions = useMemo(() => {
    return questions.filter((question) => {
      if (filters.bodyPart && question.body_part !== filters.bodyPart) return false
      if (filters.task && question.task !== filters.task) return false
      if (filters.difficulty && question.difficulty !== filters.difficulty) return false
      if (filters.questionType && question.question_type !== filters.questionType) return false
      if (filters.sourceDataset && question.source_dataset !== filters.sourceDataset) return false
      if (source === 'public' && !['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'].includes(question.source_dataset)) return false
      return true
    })
  }, [filters, questions, source])

  const question = filteredQuestions[index % Math.max(filteredQuestions.length, 1)] || mockQuestions[0]
  const evidence = useMemo(() => question.atomic_trace.map((fact) => fact.evidence).join(' / '), [question])
  const aiAnswer = question.ai_benchmark_answer || question.answer
  const challengeDelta = selected ? (selected === aiAnswer ? '你与 AI 结论一致' : '你与 AI 结论不同，适合展开证据讨论') : '提交后对比医生作答与 AI 基准答案'

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    resetQuestionState()
  }

  const resetQuestionState = () => {
    setIndex(0)
    setSelected('')
    setSubmission(null)
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  }

  const submit = async () => {
    if (!selected) return
    setLoading(true)
    const result = await api.submit(question, selected)
    setSubmission(result)
    onSubmission(result, question)
    setChat((items) => [
      ...items,
      { role: 'doctor', text: `我选择：${selected}` },
      { role: 'agent', text: `${result.is_correct ? '回答正确。' : '这题需要复盘。'}${result.explanation} 下一步：${result.next_recommendation}` },
    ])
    setLoading(false)
  }

  const askHint = async () => {
    if (mode === 'exam') return
    setLoading(true)
    const result = await api.hint(question)
    const sourceNotice = result.api_source === 'fallback' ? '（当前为本地 fallback 提示）' : ''
    const text = `${result.hint} ${result.follow_up_question}${sourceNotice}`
    setHint(text)
    setChat((items) => [...items, { role: 'agent', text }])
    setLoading(false)
  }

  const askAgent = async () => {
    if (!chatInput.trim() || mode === 'exam') return
    const message = chatInput.trim()
    setChatInput('')
    setChat((items) => [...items, { role: 'doctor', text: message }])
    const result = await api.chat(question, message)
    setChat((items) => [...items, { role: 'agent', text: result.reply }])
  }

  const toggleFavorite = async () => {
    const nextValue = !question.is_favorited
    await api.favorite(question.id, nextValue)
    setQuestions((items) => items.map((item) => item.id === question.id ? { ...item, is_favorited: nextValue, review_status: nextValue ? '收藏中' : item.review_status } : item))
  }

  const next = () => {
    setIndex((value) => (value + 1) % Math.max(filteredQuestions.length, 1))
    setSelected('')
    setSubmission(null)
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  }

  return (
    <div className="page-stack">
      <Card className="qbank-toolbar">
        <div>
          <span className="eyebrow">Endoscopy Qbank</span>
          <h2>{mode === 'exam' ? '考试模式' : view === 'wrong' ? '错题本复盘' : view === 'favorite' ? '收藏题训练' : view === 'challenge' ? '医生 vs AI 比拼' : '题库刷题中心'}</h2>
          <p>借鉴 Study/Exam Mode、Tutor Mode、错题复盘和性能分析的训练闭环，面向内镜医师重新组织题库。</p>
        </div>
        <div className="mode-switch">
          <Tag tone={mode === 'exam' ? 'amber' : 'green'}>{mode === 'exam' ? '计时考试' : '练习辅导'}</Tag>
          <Tag tone="blue">{filteredQuestions.length} 题</Tag>
        </div>
      </Card>

      <Card className="filter-panel">
        <FilterSelect label="部位" value={filters.bodyPart} options={filterOptions.bodyPart} onChange={(value) => updateFilter('bodyPart', value)} />
        <FilterSelect label="任务" value={filters.task} options={filterOptions.task} onChange={(value) => updateFilter('task', value)} />
        <FilterSelect label="难度" value={filters.difficulty} options={filterOptions.difficulty} onChange={(value) => updateFilter('difficulty', value)} />
        <FilterSelect label="题型" value={filters.questionType} options={filterOptions.questionType} onChange={(value) => updateFilter('questionType', value)} />
        <FilterSelect label="来源" value={filters.sourceDataset} options={filterOptions.sourceDataset} onChange={(value) => updateFilter('sourceDataset', value)} />
        <button className="button secondary" type="button" onClick={() => { setFilters(emptyFilters); resetQuestionState() }}>
          <RotateCcw size={16} /> 清空筛选
        </button>
      </Card>

      {filteredQuestions.length === 0 ? (
        <EmptyState>当前筛选没有题目。可以清空筛选，或切换到公开样例知识库。</EmptyState>
      ) : (
        <div className="training-grid qbank-grid">
          <Card className="image-panel">
            <SectionTitle eyebrow="Case image" title="内镜图像与病例摘要" />
            <img className="endo-image" src={question.image_url || '/assets/synthetic-endoscopy-training.svg'} alt="内镜教学图像" />
            <p className="muted">{question.image_placeholder}</p>
            <div className="case-box">{question.case_summary}</div>
            <div className="tag-row">
              <Tag tone="blue">{question.body_part}</Tag>
              <Tag tone="green">{question.difficulty}</Tag>
              <Tag tone="amber">{question.question_type}</Tag>
              <Tag tone="neutral">{question.source_dataset}</Tag>
              {question.false_premise_flag ? <Tag tone="red">错误前提</Tag> : null}
            </div>
            <div className="source-note">{question.citation_note}</div>
          </Card>

          <Card className="question-panel">
            <SectionTitle
              eyebrow={question.task}
              title={question.title}
              action={
                <button className={`icon-button ${question.is_favorited ? 'selected-icon' : ''}`} type="button" onClick={toggleFavorite} title="收藏题目">
                  <Bookmark size={17} />
                </button>
              }
            />
            <div className="question-meta">
              <span>{index + 1}/{filteredQuestions.length}</span>
              <Tag tone={question.review_status === '待复盘' ? 'amber' : question.review_status === '收藏中' ? 'blue' : 'neutral'}>{question.review_status}</Tag>
              {mode === 'exam' ? <span><Clock size={15} /> 12:00</span> : null}
            </div>
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
              <button className="button secondary" type="button" onClick={askHint} disabled={loading || mode === 'exam'}>
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
            <SectionTitle eyebrow="Tutor agent" title={mode === 'exam' ? '考后复盘面板' : '边刷边问 Agent'} />
            {mode === 'exam' ? (
              <div className="exam-lock">
                <GraduationCap size={20} />
                <p>考试模式隐藏提示和自由追问，提交后用于统一复盘与画像更新。</p>
              </div>
            ) : (
              <>
                <div className="chat-bubble agent">
                  <Bot size={18} />
                  <p>{hint}</p>
                </div>
                <div className="chat-thread">
                  {chat.map((message, itemIndex) => (
                    <div className={`chat-line ${message.role}`} key={`${message.role}_${itemIndex}`}>
                      <span>{message.role === 'agent' ? 'Agent' : '林医师'}</span>
                      <p>{message.text}</p>
                    </div>
                  ))}
                </div>
                <div className="chat-input-row">
                  <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="追问当前病例、证据或报告表达..." />
                  <button className="icon-button" type="button" onClick={askAgent} title="发送追问">
                    <MessageSquare size={17} />
                  </button>
                </div>
              </>
            )}
            <div className="evidence-box">
              <div>
                <Eye size={17} />
                <strong>查看依据</strong>
              </div>
              <p>{evidence}</p>
            </div>
            <div className="challenge-box">
              <div>
                <Trophy size={17} />
                <strong>医生 vs AI</strong>
              </div>
              <p>{challengeDelta}</p>
              <span>AI 基准：{aiAnswer}</span>
            </div>
            <div className="agent-actions">
              <button className="button secondary" type="button" onClick={askHint} disabled={mode === 'exam'}>
                <Lightbulb size={16} /> 苏格拉底式追问
              </button>
              <a className="button secondary" href="/feedback">
                <ShieldAlert size={16} /> 错因分析
              </a>
            </div>
            <div className="safety-mini">{safetyNotice}</div>
          </Card>
        </div>
      )}
    </div>
  )
}

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return (
    <label className="filter-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {options.map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  )
}

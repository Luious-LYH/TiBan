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
  mode?: string
}

type TutorTab = 'agent' | 'evidence' | 'compare'

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

const EXAM_DURATION_SECONDS = 12 * 60

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
  const [tutorTab, setTutorTab] = useState<TutorTab>('agent')
  const [agentMode, setAgentMode] = useState('rule')
  const [examSeconds, setExamSeconds] = useState(EXAM_DURATION_SECONDS)
  const [chat, setChat] = useState<ChatMessage[]>([
    { role: 'agent', text: '林知远医师，先看图像证据：部位、形态、颜色、边界，再判断题干是否越界。', mode: 'rule' },
  ])

  const mode = searchParams.get('mode') === 'exam' ? 'exam' : 'practice'
  const view = searchParams.get('view') || ''
  const source = searchParams.get('source') || ''

  useEffect(() => {
    api.qbank({
      onlyWrong: view === 'wrong',
      onlyFavorites: view === 'favorite',
      publicOnly: source === 'public',
      mode,
    }).then((items) => {
      setQuestions(items)
      setIndex(0)
      setSelected('')
      setSubmission(null)
      setExamSeconds(EXAM_DURATION_SECONDS)
    }).catch(() => setQuestions(mockQuestions))
  }, [mode, source, view])

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
  const canRevealBenchmark = Boolean(submission)
  const examExpired = mode === 'exam' && examSeconds <= 0 && !submission
  const formattedExamTime = `${String(Math.floor(examSeconds / 60)).padStart(2, '0')}:${String(examSeconds % 60).padStart(2, '0')}`
  const challengeDelta = canRevealBenchmark
    ? (selected === aiAnswer ? '你与 AI/公开标注结论一致' : '你与 AI/公开标注结论不同，适合展开证据讨论')
    : '提交答案后解锁医生作答与公开标注/AI 基准对照'

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    resetQuestionState()
  }

  const resetQuestionState = () => {
    setIndex(0)
    setSelected('')
    setSubmission(null)
    setTutorTab('agent')
    setAgentMode('rule')
    setExamSeconds(EXAM_DURATION_SECONDS)
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  }

  useEffect(() => {
    if (mode !== 'exam' || submission || examSeconds <= 0) return undefined
    const timer = window.setInterval(() => {
      setExamSeconds((seconds) => Math.max(0, seconds - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [examSeconds, mode, submission])

  const submit = async () => {
    if (!selected || examExpired) return
    setLoading(true)
    try {
      const result = await api.submit(question, selected)
      setSubmission(result)
      onSubmission(result, question)
      setChat((items) => [
        ...items,
        { role: 'doctor', text: `我选择：${selected}` },
        { role: 'agent', text: `${result.is_correct ? '回答正确。' : '这题需要复盘。'}${result.explanation} 下一步：${result.next_recommendation}`, mode: 'rule' },
      ])
      setTutorTab('compare')
    } finally {
      setLoading(false)
    }
  }

  const askHint = async () => {
    if (mode === 'exam') return
    setLoading(true)
    try {
      const result = await api.hint(question)
      const sourceNotice = result.api_source === 'fallback' ? '（当前为本地 fallback 提示）' : ''
      const text = `${result.hint} ${result.follow_up_question}${sourceNotice}`
      setHint(text)
      setChat((items) => [...items, { role: 'agent', text, mode: result.api_source === 'fallback' ? 'fallback' : 'rule' }])
      setAgentMode(result.api_source === 'fallback' ? 'fallback' : 'rule')
      setTutorTab('agent')
    } finally {
      setLoading(false)
    }
  }

  const askAgent = async () => {
    if (!chatInput.trim() || mode === 'exam') return
    const message = chatInput.trim()
    setChatInput('')
    setChat((items) => [...items, { role: 'doctor', text: message }])
    try {
      const result = await api.chat(question, message)
      setAgentMode(result.generation_mode || 'rule')
      setChat((items) => [...items, { role: 'agent', text: result.reply, mode: result.generation_mode }])
    } catch {
      setAgentMode('fallback')
      setChat((items) => [...items, { role: 'agent', text: '当前辅导接口暂不可用，请先按证据链完成本题，稍后再追问 Agent。', mode: 'fallback' }])
    }
  }

  const toggleFavorite = async () => {
    const nextValue = !question.is_favorited
    try {
      await api.favorite(question.id, nextValue)
      setQuestions((items) => items.map((item) => item.id === question.id ? { ...item, is_favorited: nextValue, review_status: nextValue ? '收藏中' : item.review_status } : item))
    } catch {
      setHint('收藏接口暂不可用，本次状态未写入后端。')
    }
  }

  const next = () => {
    setIndex((value) => (value + 1) % Math.max(filteredQuestions.length, 1))
    setSelected('')
    setSubmission(null)
    setTutorTab('agent')
    setAgentMode('rule')
    setExamSeconds(EXAM_DURATION_SECONDS)
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  }

  return (
    <div className="page-stack">
      <Card className="qbank-toolbar">
        <div>
          <span className="eyebrow">Endoscopy Qbank</span>
          <h2>{mode === 'exam' ? '考试模式' : view === 'wrong' ? '错题本复盘' : view === 'favorite' ? '收藏题训练' : view === 'challenge' ? '医生 vs AI 比拼' : '题库刷题中心'}</h2>
          <p>{source === 'public' ? '当前优先加载本地真实公开图文样本：Kvasir-VQA-x1、Kvasir-VQA 与 EndoBench。' : '借鉴 Study/Exam Mode、Tutor Mode、错题复盘和性能分析的训练闭环，默认优先展示真实公开图文样本。'}</p>
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
              {mode === 'exam' ? <span className={examExpired ? 'timer-expired' : ''}><Clock size={15} /> {formattedExamTime}</span> : null}
            </div>
            <p className="question-text">{question.question}</p>
            <div className="option-list">
              {question.options.map((option) => (
                <button key={option} className={`option-button ${selected === option ? 'selected' : ''}`} type="button" onClick={() => setSelected(option)} disabled={examExpired}>
                  <span>{option}</span>
                  {selected === option ? <CheckCircle2 size={18} /> : null}
                </button>
              ))}
            </div>
            <div className="toolbar">
              <button className="button secondary" type="button" onClick={askHint} disabled={loading || mode === 'exam'}>
                <Lightbulb size={17} /> 提示一下
              </button>
              <button className="button primary" type="button" onClick={submit} disabled={!selected || loading || examExpired}>
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
            <SectionTitle
              eyebrow="Tutor agent"
              title={mode === 'exam' ? '考后复盘面板' : '边刷边问 Agent'}
              action={<Tag tone={agentMode === 'provider' ? 'green' : agentMode === 'fallback' ? 'amber' : 'blue'}>{agentMode}</Tag>}
            />
            <div className="tutor-tabs">
              <button className={tutorTab === 'agent' ? 'active' : ''} type="button" onClick={() => setTutorTab('agent')}>辅导</button>
              <button className={tutorTab === 'evidence' ? 'active' : ''} type="button" onClick={() => setTutorTab('evidence')}>证据</button>
              <button className={tutorTab === 'compare' ? 'active' : ''} type="button" onClick={() => setTutorTab('compare')}>对照</button>
            </div>
            {mode === 'exam' && !submission ? (
              <div className="exam-lock">
                <GraduationCap size={20} />
                <p>{examExpired ? '本题考试时间已结束，请进入复盘或切换下一题。' : `考试进行中，剩余 ${formattedExamTime}，提示和自由追问已隐藏。`}</p>
              </div>
            ) : tutorTab === 'agent' ? (
              <>
                <div className="chat-bubble agent">
                  <Bot size={18} />
                  <p>{hint}</p>
                </div>
                <div className="chat-thread">
                  {chat.map((message, itemIndex) => (
                    <div className={`chat-line ${message.role}`} key={`${message.role}_${itemIndex}`}>
                      <span>{message.role === 'agent' ? `Agent${message.mode ? ` · ${message.mode}` : ''}` : '林医师'}</span>
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
                <div className="agent-mini-actions">
                  <button className="button secondary" type="button" onClick={askHint} disabled={loading}>
                    <Lightbulb size={16} /> 追问提示
                  </button>
                  <a className="button secondary" href="/feedback">
                    <ShieldAlert size={16} /> 错因复盘
                  </a>
                </div>
              </>
            ) : tutorTab === 'evidence' ? (
              <div className="evidence-box">
                <div>
                  <Eye size={17} />
                  <strong>可审计依据</strong>
                </div>
                <p>{evidence}</p>
                <div className="mini-fact-list">
                  {question.atomic_trace.map((fact) => (
                    <span key={fact.id}>{fact.skill_dimension} · {fact.supported ? '支持' : '证据不足'} · {fact.evidence}</span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="challenge-box">
                <div>
                  <Trophy size={17} />
                  <strong>医生 vs AI/公开标注</strong>
                </div>
                <p>{challengeDelta}</p>
                {canRevealBenchmark ? <span>公开标注/AI 基准：{aiAnswer}</span> : <span>未提交前隐藏基准答案，避免破坏练习闭环。</span>}
              </div>
            )}
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

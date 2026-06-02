import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ActivitySquare, Bookmark, Bot, CheckCircle2, Clock, Eye, GraduationCap, Lightbulb, MessageSquare, RotateCcw, Send, Trophy } from 'lucide-react'
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

type ChallengeStats = {
  rounds: number
  doctor: number
  benchmark: number
  ties: number
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

const EXAM_DURATION_SECONDS = 12 * 60
const emptyChallengeStats: ChallengeStats = { rounds: 0, doctor: 0, benchmark: 0, ties: 0 }

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
  const [memorySync, setMemorySync] = useState('Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
  const [challengeStats, setChallengeStats] = useState<ChallengeStats>(emptyChallengeStats)
  const [chat, setChat] = useState<ChatMessage[]>([
    { role: 'agent', text: '林知远医师，先看图像证据：部位、形态、颜色、边界，再判断题干是否越界。', mode: 'rule' },
  ])

  const mode = searchParams.get('mode') === 'exam' ? 'exam' : 'practice'
  const view = searchParams.get('view') || ''
  const source = searchParams.get('source') || ''
  const isChallenge = view === 'challenge'

  useEffect(() => {
    api.qbank({
      onlyWrong: view === 'wrong',
      onlyFavorites: view === 'favorite',
      publicOnly: source === 'public' || view === 'challenge',
      mode,
    }).then((items) => {
      setQuestions(items)
      setIndex(0)
      setSelected('')
      setSubmission(null)
      setTutorTab(view === 'challenge' ? 'compare' : 'agent')
      setExamSeconds(EXAM_DURATION_SECONDS)
      setMemorySync(view === 'challenge' ? '比拼模式只记录正式提交结果，不提前泄露基准答案。' : 'Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
      setHint(view === 'challenge' ? '比拼模式已隐藏提示。请先独立作答，提交后再查看 AI/公开标注对照。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
      setChallengeStats(emptyChallengeStats)
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
  const aiCorrect = aiAnswer === question.answer
  const canRevealBenchmark = Boolean(submission)
  const examExpired = mode === 'exam' && examSeconds <= 0 && !submission
  const formattedExamTime = `${String(Math.floor(examSeconds / 60)).padStart(2, '0')}:${String(examSeconds % 60).padStart(2, '0')}`
  const challengeDelta = canRevealBenchmark
    ? challengeMessage(Boolean(submission?.is_correct), aiCorrect, selected === aiAnswer)
    : '提交答案后解锁医生作答与公开标注/AI 基准对照'
  const challengeLeader = challengeStats.doctor === challengeStats.benchmark
    ? '暂时平手'
    : challengeStats.doctor > challengeStats.benchmark ? '医生领先' : 'AI/公开标注领先'

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }))
    resetQuestionState()
  }

  const resetQuestionState = () => {
    setIndex(0)
    setSelected('')
    setSubmission(null)
    setTutorTab(isChallenge ? 'compare' : 'agent')
    setAgentMode('rule')
    setExamSeconds(EXAM_DURATION_SECONDS)
    setMemorySync('Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : isChallenge ? '比拼模式已隐藏提示。请先独立作答，提交后再查看 AI/公开标注对照。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
    setChallengeStats(emptyChallengeStats)
  }

  useEffect(() => {
    if (mode !== 'exam' || submission || examSeconds <= 0) return undefined
    const timer = window.setInterval(() => {
      setExamSeconds((seconds) => Math.max(0, seconds - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [examSeconds, mode, submission])

  const submit = async () => {
    if (!selected || examExpired || submission) return
    setLoading(true)
    try {
      const result = await api.submit(question, selected)
      setSubmission(result)
      if (isChallenge) {
        const benchmarkCorrect = (question.ai_benchmark_answer || question.answer) === question.answer
        setChallengeStats((current) => ({
          rounds: current.rounds + 1,
          doctor: current.doctor + (result.is_correct ? 1 : 0),
          benchmark: current.benchmark + (benchmarkCorrect ? 1 : 0),
          ties: current.ties + (result.is_correct === benchmarkCorrect ? 1 : 0),
        }))
      }
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
    if (mode === 'exam' || isChallenge) return
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
    if (!chatInput.trim() || mode === 'exam' || (isChallenge && !submission)) return
    const message = chatInput.trim()
    setChatInput('')
    setChat((items) => [...items, { role: 'doctor', text: message }])
    try {
      const result = await api.chat(question, message)
      setAgentMode(result.generation_mode || 'rule')
      setChat((items) => [...items, { role: 'agent', text: result.reply, mode: result.generation_mode }])
      setMemorySync(result.memory_summary || (result.profile_updated ? '已写入医师画像。' : '当前未写入后端医师画像。'))
    } catch {
      setAgentMode('fallback')
      setChat((items) => [...items, { role: 'agent', text: '当前辅导接口暂不可用，请先按证据链完成本题，稍后再追问 Agent。', mode: 'fallback' }])
      setMemorySync('当前辅导接口不可用，未写入后端医师画像。')
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
    setTutorTab(isChallenge ? 'compare' : 'agent')
    setAgentMode('rule')
    setExamSeconds(EXAM_DURATION_SECONDS)
    setMemorySync(isChallenge ? '比拼模式只记录正式提交结果，不提前泄露基准答案。' : 'Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : isChallenge ? '比拼模式已隐藏提示。请先独立作答，提交后再查看 AI/公开标注对照。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
  }

  return (
    <div className="page-stack">
      <Card className="qbank-toolbar">
        <div>
          <span className="eyebrow">Endoscopy Qbank</span>
          <h2>{mode === 'exam' ? '考试模式' : view === 'wrong' ? '错题本复盘' : view === 'favorite' ? '收藏题训练' : view === 'challenge' ? '医生 vs AI 比拼' : '题库刷题中心'}</h2>
          <p>{isChallenge ? '当前使用真实公开样例进行回合制比拼：医师先独立作答，提交后才解锁 AI/公开标注基准和证据讨论。' : source === 'public' ? '当前优先加载本地真实公开图文样本：Kvasir-VQA-x1、Kvasir-VQA 与 EndoBench。' : '借鉴 Study/Exam Mode、Tutor Mode、错题复盘和性能分析的训练闭环，默认优先展示真实公开图文样本。'}</p>
        </div>
        <div className="mode-switch">
          <Tag tone={mode === 'exam' || isChallenge ? 'amber' : 'green'}>{mode === 'exam' ? '计时考试' : isChallenge ? '比拼模式' : '练习辅导'}</Tag>
          <Tag tone="blue">{filteredQuestions.length} 题</Tag>
        </div>
      </Card>

      {isChallenge ? (
        <Card className="challenge-scoreboard">
          <div className="challenge-score-main">
            <Trophy size={24} />
            <div>
              <span className="eyebrow">Doctor vs AI</span>
              <h3>{challengeLeader}</h3>
              <p>正式提交会写入医师训练记录；基准答案只在提交后显示，避免破坏训练闭环。</p>
            </div>
          </div>
          <div className="challenge-score-grid">
            <div><span>回合</span><strong>{challengeStats.rounds}</strong></div>
            <div><span>林医师</span><strong>{challengeStats.doctor}</strong></div>
            <div><span>AI/公开标注</span><strong>{challengeStats.benchmark}</strong></div>
            <div><span>同判</span><strong>{challengeStats.ties}</strong></div>
          </div>
        </Card>
      ) : null}

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
                <button key={option} className={`option-button ${selected === option ? 'selected' : ''}`} type="button" onClick={() => setSelected(option)} disabled={examExpired || Boolean(submission)}>
                  <span>{option}</span>
                  {selected === option ? <CheckCircle2 size={18} /> : null}
                </button>
              ))}
            </div>
            <div className="toolbar">
              <button className="button secondary" type="button" onClick={askHint} disabled={loading || mode === 'exam' || isChallenge}>
                <Lightbulb size={17} /> 提示一下
              </button>
              <button className="button primary" type="button" onClick={submit} disabled={!selected || loading || examExpired || Boolean(submission)}>
                <Send size={17} /> {isChallenge ? '锁定本轮' : '提交答案'}
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
                  <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={isChallenge && !submission ? '比拼模式提交后开放追问复盘...' : '追问当前病例、证据或报告表达...'} disabled={isChallenge && !submission} />
                  <button className="icon-button" type="button" onClick={askAgent} title="发送追问" disabled={isChallenge && !submission}>
                    <MessageSquare size={17} />
                  </button>
                </div>
                <div className={`agent-memory-sync ${memorySync.includes('未写入') || memorySync.includes('不可用') ? 'pending' : 'synced'}`}>
                  <ActivitySquare size={17} />
                  <span>{memorySync}</span>
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
                {canRevealBenchmark ? (
                  <div className="challenge-round-grid">
                    <span>林医师：{submission?.is_correct ? '本轮正确' : '本轮失分'} · {selected}</span>
                    <span>AI/公开标注：{aiCorrect ? '基准正确' : '基准待复核'} · {aiAnswer}</span>
                  </div>
                ) : <span>未提交前隐藏基准答案，避免破坏练习闭环。</span>}
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

function challengeMessage(doctorCorrect: boolean, benchmarkCorrect: boolean, sameAnswer: boolean): string {
  if (doctorCorrect && benchmarkCorrect && sameAnswer) return '本轮同判正确：医师答案与 AI/公开标注一致。'
  if (doctorCorrect && benchmarkCorrect) return '本轮都命中参考结论，但表达不同，适合复盘证据措辞。'
  if (doctorCorrect && !benchmarkCorrect) return '本轮医师领先：公开基准需要复核或不适合作为最终判断。'
  if (!doctorCorrect && benchmarkCorrect) return '本轮 AI/公开标注领先：建议复盘可观察证据和题干边界。'
  return '本轮双方都需复核：请回到证据标签逐条检查。'
}

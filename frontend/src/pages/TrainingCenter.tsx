import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ActivitySquare, Bookmark, Bot, CheckCircle2, ClipboardList, Clock, DatabaseZap, Eye, GraduationCap, Lightbulb, MessageSquare, RotateCcw, Send, Target, Trophy } from 'lucide-react'
import { Card, EmptyState, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { AuditLog, ChallengeBenchmarkResult, ExamSessionAttempt, ProviderStatus, Question, SubmissionResponse } from '../lib/types'

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

type ExamAttempt = {
  questionId: string
  title: string
  selected: string
  correctAnswer: string
  isCorrect: boolean
  score: number
  errorTags: string[]
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
const createExamSessionId = () => `exam_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
const publicDatasets = new Set(['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'])

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
  const [examAttempts, setExamAttempts] = useState<ExamAttempt[]>([])
  const [examFinished, setExamFinished] = useState(false)
  const [examSessionId, setExamSessionId] = useState(createExamSessionId)
  const [examSyncing, setExamSyncing] = useState(false)
  const [examSessionSaved, setExamSessionSaved] = useState(false)
  const [memorySync, setMemorySync] = useState('Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
  const [challengeStats, setChallengeStats] = useState<ChallengeStats>(emptyChallengeStats)
  const [challengeBenchmark, setChallengeBenchmark] = useState<ChallengeBenchmarkResult | null>(null)
  const [challengeBenchmarkLoading, setChallengeBenchmarkLoading] = useState(false)
  const [lastChallengeAudit, setLastChallengeAudit] = useState<AuditLog | null>(null)
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>([
    { role: 'agent', text: '林知远医师，先看图像证据：部位、形态、颜色、边界，再判断题干是否越界。', mode: 'rule' },
  ])

  const mode = searchParams.get('mode') === 'exam' ? 'exam' : 'practice'
  const view = searchParams.get('view') || ''
  const source = searchParams.get('source') || ''
  const isChallenge = view === 'challenge'

  useEffect(() => {
    api.providerStatus().then(setProviderStatus).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!isChallenge) return
    api.challengeAuditReceipt()
      .then(setLastChallengeAudit)
      .catch(() => setLastChallengeAudit(null))
  }, [isChallenge])

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
      setTutorTab('agent')
      setExamSeconds(EXAM_DURATION_SECONDS)
      setExamAttempts([])
      setExamFinished(false)
      setExamSessionId(createExamSessionId())
      setExamSessionSaved(false)
      setExamSyncing(false)
      setMemorySync(view === 'challenge' ? '比拼模式只记录正式提交结果；后端挑战基准提交后才调用，只写审计。' : 'Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
      setHint(view === 'challenge' ? '比拼模式已隐藏提示。请先独立作答，提交后再同步后端挑战基准。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
      setChallengeStats(emptyChallengeStats)
      setChallengeBenchmark(null)
      setChallengeBenchmarkLoading(false)
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
  const providerConfigured = Boolean(providerStatus?.configured || providerStatus?.ok)
  const currentChallengeBenchmark = challengeBenchmark?.question_id === question.id ? challengeBenchmark : null
  const benchmarkAnswer = currentChallengeBenchmark?.benchmark_answer || aiAnswer
  const benchmarkCorrect = currentChallengeBenchmark?.benchmark_correct ?? aiCorrect
  const benchmarkLabel = currentChallengeBenchmark
    ? `${currentChallengeBenchmark.benchmark_name}（${currentChallengeBenchmark.generation_mode}${currentChallengeBenchmark.api_source === 'fallback' ? ' · frontend fallback' : ''}）`
    : providerConfigured ? '提交后调用 Provider 挑战基准；失败时回退公开标注' : '后端挑战基准 fallback（未配置独立 Provider）'
  const examAnsweredCount = examAttempts.length
  const examCorrectCount = examAttempts.filter((attempt) => attempt.isCorrect).length
  const examWrongAttempts = examAttempts.filter((attempt) => !attempt.isCorrect)
  const examAverageScore = examAnsweredCount ? Math.round(examAttempts.reduce((sum, attempt) => sum + attempt.score, 0) / examAnsweredCount) : 0
  const examAccuracy = examAnsweredCount ? Math.round((examCorrectCount / examAnsweredCount) * 100) : 0
  const examCompletedByCount = mode === 'exam' && filteredQuestions.length > 0 && examAnsweredCount >= filteredQuestions.length
  const examClosed = mode === 'exam' && (examFinished || examSeconds <= 0 || examCompletedByCount)
  const currentQuestionAnswered = mode === 'exam' && examAttempts.some((attempt) => attempt.questionId === question.id)
  const canRevealBenchmark = Boolean(submission)
  const reviewUnlocked = Boolean(submission)
  const evidenceLocked = !reviewUnlocked
  const examExpired = mode === 'exam' && examSeconds <= 0
  const formattedExamTime = `${String(Math.floor(examSeconds / 60)).padStart(2, '0')}:${String(examSeconds % 60).padStart(2, '0')}`
  const challengeDelta = canRevealBenchmark
    ? challengeBenchmarkLoading ? '正在同步后端挑战基准，本轮比分稍后更新。' : challengeMessage(Boolean(submission?.is_correct), benchmarkCorrect, selected === benchmarkAnswer)
    : '提交答案后解锁医生作答与挑战基准对照'
  const challengeLeader = challengeStats.doctor === challengeStats.benchmark
    ? '暂时平手'
    : challengeStats.doctor > challengeStats.benchmark ? '医生领先' : '挑战基准领先'
  const isPublicSample = publicDatasets.has(question.source_dataset)
  const canUseTutorChat = mode !== 'exam' && (!isChallenge || Boolean(submission))
  const imageSourceLabel = isPublicSample ? '真实公开样例' : '教学合成图'
  const tutorAvailability = mode === 'exam' && !submission
    ? '考试纪律'
    : mode === 'exam' ? '考后证据复盘' : isChallenge && !submission ? '独立作答锁定' : submission ? '复盘追问' : '证据式辅导'
  const tutorWriteback = mode === 'exam'
    ? examSessionSaved ? '已同步画像' : '交卷后同步'
    : submission ? '提交已回灌' : '追问仅记标签'
  const quickAgentPrompts = submission
    ? ['用一句话总结错因', '给我下一题复盘策略', '帮我改写成报告表达']
    : ['按部位-形态-边界追问我', '这题最容易越界的判断是什么？', '给我一个不泄题提示']

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
    setExamAttempts([])
    setExamFinished(false)
    setExamSessionId(createExamSessionId())
    setExamSessionSaved(false)
    setExamSyncing(false)
    setMemorySync('Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : isChallenge ? '比拼模式已隐藏提示。请先独立作答，提交后再同步后端挑战基准。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
    setChallengeStats(emptyChallengeStats)
    setChallengeBenchmark(null)
    setChallengeBenchmarkLoading(false)
  }

  useEffect(() => {
    if (mode !== 'exam' || examClosed) return undefined
    const timer = window.setInterval(() => {
      setExamSeconds((seconds) => Math.max(0, seconds - 1))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [examClosed, mode])

  const submit = async () => {
    if (!selected || examClosed || currentQuestionAnswered || submission) return
    setLoading(true)
    const selectedAnswer = selected
    try {
      const result = await api.submit(question, selectedAnswer)
      setSubmission(result)
      if (mode === 'exam') {
        const attempt: ExamAttempt = {
          questionId: question.id,
          title: question.title,
          selected,
          correctAnswer: question.answer,
          isCorrect: result.is_correct,
          score: result.score,
          errorTags: result.error_tags,
        }
        setExamAttempts((current) => current.some((item) => item.questionId === question.id) ? current : [...current, attempt])
        if (examAttempts.length + 1 >= filteredQuestions.length) setExamFinished(true)
      }
      onSubmission(result, question)
      setChat((items) => [
        ...items,
        { role: 'doctor', text: `我选择：${selectedAnswer}` },
        { role: 'agent', text: `${result.is_correct ? '回答正确。' : '这题需要复盘。'}${result.explanation} 下一步：${result.next_recommendation}`, mode: 'rule' },
      ])
      setTutorTab('compare')
      if (isChallenge) {
        syncChallengeBenchmark(question, selectedAnswer, result)
      }
    } finally {
      setLoading(false)
    }
  }

  const syncChallengeBenchmark = async (activeQuestion: Question, selectedAnswer: string, result: SubmissionResponse) => {
    setChallengeBenchmark(null)
    setChallengeBenchmarkLoading(true)
    setMemorySync('挑战基准正在同步：提交结果已写入画像，基准对照只写审计，不重复回灌医师画像。')
    try {
      const benchmark = await api.challengeBenchmark(activeQuestion, selectedAnswer)
      setChallengeBenchmark(benchmark)
      setChallengeStats((current) => ({
        rounds: current.rounds + 1,
        doctor: current.doctor + (result.is_correct ? 1 : 0),
        benchmark: current.benchmark + (benchmark.benchmark_correct ? 1 : 0),
        ties: current.ties + (result.is_correct === benchmark.benchmark_correct ? 1 : 0),
      }))
      setMemorySync(`${benchmark.benchmark_name}已返回：${benchmark.generation_mode}；审计${benchmark.audit_logged ? '已写入' : '未写入'}，画像${benchmark.profile_updated ? '已更新' : '未重复更新'}。`)
      if (benchmark.audit_logged) {
        setLastChallengeAudit({
          id: benchmark.id,
          event_type: 'challenge_benchmark',
          user_id: 'demo_learner',
          entity_id: activeQuestion.id,
          summary: `挑战基准完成：${benchmark.benchmark_name} · ${benchmark.generation_mode}；不重复回灌医师画像。`,
          risk_level: 'medium',
          doctor_review_required: true,
          created_at: benchmark.created_at,
        })
      }
    } finally {
      setChallengeBenchmarkLoading(false)
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
    await sendAgentMessage(chatInput.trim())
  }

  const sendAgentMessage = async (message: string) => {
    if (!message || loading || !canUseTutorChat) return
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

  const restartExam = () => {
    setExamAttempts([])
    setExamFinished(false)
    setExamSessionId(createExamSessionId())
    setExamSessionSaved(false)
    setExamSyncing(false)
    setExamSeconds(EXAM_DURATION_SECONDS)
    setIndex(0)
    setSelected('')
    setSubmission(null)
    setTutorTab('agent')
    setAgentMode('rule')
    setHint('考试模式已重新开始。请独立完成本场训练，交卷后统一复盘。')
    setMemorySync('考试 session 已重置，本场记录将从下一次提交开始累计。')
  }

  const finishExam = async () => {
    if (!examAttempts.length || examSyncing || examSessionSaved) return
    setExamFinished(true)
    setSelected('')
    setSubmission(null)
    setTutorTab('agent')
    setExamSyncing(true)
    setHint('本场考试正在交卷，并同步 Session 汇总到医师画像。')
    const finishedReason = examSeconds <= 0 ? 'time_expired' : examAttempts.length >= filteredQuestions.length ? 'completed_all' : 'manual_submit'
    const attempts: ExamSessionAttempt[] = examAttempts.map((attempt) => ({
      question_id: attempt.questionId,
      title: attempt.title,
      selected_answer: attempt.selected,
      correct_answer: attempt.correctAnswer,
      is_correct: attempt.isCorrect,
      score: attempt.score,
      error_tags: attempt.errorTags,
    }))
    try {
      const result = await api.examSession({
        sessionId: examSessionId,
        attempts,
        durationSeconds: EXAM_DURATION_SECONDS,
        remainingSeconds: examSeconds,
        finishedReason,
      })
      setExamSessionSaved(Boolean(result.profile_updated))
      setHint(result.profile_updated ? '本场考试已交卷并写入画像。请从战报进入错因复盘，或重开本场继续训练。' : '本场考试已交卷，但后端未写入画像；请确认后端在线后可再次同步。')
      setMemorySync(result.memory_summary)
    } catch {
      setExamSessionSaved(false)
      setHint('本场考试已交卷，但 Session 汇总同步失败；请稍后重试。')
      setMemorySync('考试 Session 汇总未写入后端画像。')
    } finally {
      setExamSyncing(false)
    }
  }

  const next = () => {
    const nextIndex = nextQuestionIndex(index, filteredQuestions, examAttempts, mode === 'exam')
    setIndex(nextIndex)
    setSelected('')
    setSubmission(null)
    setTutorTab('agent')
    setAgentMode('rule')
    setMemorySync(isChallenge ? '比拼模式只记录正式提交结果；后端挑战基准提交后才调用，只写审计。' : 'Agent 辅导会记录训练标签和模式，不保存自由追问原文。')
    setHint(mode === 'exam' ? '考试模式已隐藏提示，结束后统一复盘。' : isChallenge ? '比拼模式已隐藏提示。请先独立作答，提交后再同步后端挑战基准。' : '练习模式下，右侧 Agent 会先追问依据，不直接泄露答案。')
    setChallengeBenchmark(null)
    setChallengeBenchmarkLoading(false)
  }

  return (
    <div className="page-stack">
      <Card className="qbank-toolbar">
        <div>
          <span className="eyebrow">Endoscopy Qbank</span>
          <h2>{mode === 'exam' ? '考试模式' : view === 'wrong' ? '错题本复盘' : view === 'favorite' ? '收藏题训练' : view === 'challenge' ? '医生 vs 挑战基准' : '题库刷题中心'}</h2>
          <p>{isChallenge ? '当前使用真实公开样例进行回合制比拼：医师先独立作答，提交后才调用后端挑战基准并解锁证据讨论；若 Provider 未打通，系统会明确回退公开标注 fallback。' : source === 'public' ? '当前优先加载本地真实公开图文样本：Kvasir-VQA-x1、Kvasir-VQA 与 EndoBench。' : '借鉴 Study/Exam Mode、Tutor Mode、错题复盘和性能分析的训练闭环，默认优先展示真实公开图文样本。'}</p>
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
              <span className="eyebrow">Doctor vs Benchmark</span>
              <h3>{challengeLeader}</h3>
              <p>正式提交会写入医师训练记录；挑战基准提交后才调用，只写审计，不重复写医师画像。</p>
            </div>
          </div>
          <div className="challenge-score-grid">
            <div><span>回合</span><strong>{challengeStats.rounds}</strong></div>
            <div><span>林医师</span><strong>{challengeStats.doctor}</strong></div>
            <div><span>挑战基准</span><strong>{challengeStats.benchmark}</strong></div>
            <div><span>同判</span><strong>{challengeStats.ties}</strong></div>
          </div>
          <div className={`challenge-audit-receipt ${lastChallengeAudit ? 'synced' : 'pending'}`}>
            <ActivitySquare size={18} />
            <div>
              <strong>{lastChallengeAudit ? '最近挑战基准审计已连接' : '等待挑战基准审计'}</strong>
              <span>
                {lastChallengeAudit
                  ? `${formatAuditTime(lastChallengeAudit.created_at)} · ${lastChallengeAudit.entity_id || '样例'} · ${lastChallengeAudit.summary}`
                  : '提交一轮后会写入 challenge_benchmark 审计；该审计不重复更新医师画像。'}
              </span>
            </div>
          </div>
        </Card>
      ) : null}

      {mode === 'exam' ? (
        <Card className={`exam-session-board ${examClosed ? 'closed' : ''}`}>
          <div className="exam-session-main">
            <GraduationCap size={24} />
            <div>
              <span className="eyebrow">Exam session</span>
              <h3>{examClosed ? '本场考试进入复盘' : '本场考试进行中'}</h3>
              <p>全局 12 分钟倒计时持续运行；提交后可查看本题解析，但不会重置计时。交卷后从错题进入复盘闭环。</p>
            </div>
          </div>
          <div className="exam-session-grid">
            <div><span>剩余时间</span><strong className={examExpired ? 'timer-expired' : ''}>{formattedExamTime}</strong></div>
            <div><span>已答题</span><strong>{examAnsweredCount}/{filteredQuestions.length}</strong></div>
            <div><span>正确率</span><strong>{examAccuracy}%</strong></div>
            <div><span>平均分</span><strong>{examAverageScore}</strong></div>
          </div>
          <div className="exam-session-actions">
            <button className="button secondary" type="button" onClick={finishExam} disabled={examAnsweredCount === 0 || examSyncing || examSessionSaved}>
              <ClipboardList size={16} /> {examSyncing ? '同步中' : examSessionSaved ? '已同步画像' : examClosed ? '同步本场复盘' : '交卷复盘'}
            </button>
            <button className="button secondary" type="button" onClick={restartExam}>
              <RotateCcw size={16} /> 重开本场
            </button>
            {examWrongAttempts.length ? (
              <Link className="button primary" to="/feedback">
                <Target size={16} /> 进入错因复盘
              </Link>
            ) : null}
          </div>
          {examWrongAttempts.length ? (
            <div className="exam-wrong-strip">
              {examWrongAttempts.slice(-3).map((attempt) => (
                <span key={attempt.questionId}>{attempt.title} · 选 {attempt.selected} / 答 {attempt.correctAnswer}</span>
              ))}
            </div>
          ) : (
            <div className="exam-wrong-strip clean"><span>当前未产生错题；继续完成本场后查看完整表现。</span></div>
          )}
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
            <div className={`image-frame ${isPublicSample ? 'real-sample' : 'synthetic-sample'}`}>
              <img className="endo-image" src={question.image_url || '/assets/synthetic-endoscopy-training.svg'} alt="内镜教学图像" />
              <div className={`image-source-ribbon ${isPublicSample ? 'real' : 'synthetic'}`}>
                <DatabaseZap size={14} />
                <span>{imageSourceLabel}</span>
              </div>
            </div>
            <p className="muted">{question.image_placeholder}</p>
            <div className="case-integrity-strip">
              <div><span>来源</span><strong>{question.source_dataset}</strong></div>
              <div><span>题型</span><strong>{question.question_type}</strong></div>
              <div><span>复核</span><strong>{question.doctor_review_required ? '医生审核' : '教学练习'}</strong></div>
            </div>
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
              {mode === 'exam' && currentQuestionAnswered ? <Tag tone="green">已作答</Tag> : null}
            </div>
            <p className="question-text">{question.question}</p>
            <div className="option-list">
              {question.options.map((option) => (
                <button key={option} className={`option-button ${selected === option ? 'selected' : ''}`} type="button" onClick={() => setSelected(option)} disabled={examClosed || currentQuestionAnswered || Boolean(submission)}>
                  <span>{option}</span>
                  {selected === option ? <CheckCircle2 size={18} /> : null}
                </button>
              ))}
            </div>
            <div className="toolbar">
              <button className="button secondary" type="button" onClick={askHint} disabled={loading || mode === 'exam' || isChallenge}>
                <Lightbulb size={17} /> 提示一下
              </button>
              <button className="button primary" type="button" onClick={submit} disabled={!selected || loading || examClosed || currentQuestionAnswered || Boolean(submission)}>
                <Send size={17} /> {isChallenge ? '锁定本轮' : '提交答案'}
              </button>
              <button className="icon-button" type="button" onClick={next} title="下一题" disabled={(mode === 'exam' && examClosed) || challengeBenchmarkLoading}>
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
            <div className="tutor-command-strip">
              <div><span>当前开放</span><strong>{tutorAvailability}</strong></div>
              <div><span>范围</span><strong>{isPublicSample ? '公开样例' : '教学题'}</strong></div>
              <div><span>画像</span><strong>{tutorWriteback}</strong></div>
            </div>
            {reviewUnlocked ? (
              <div className="tutor-tabs">
                <button className={tutorTab === 'agent' ? 'active' : ''} type="button" onClick={() => setTutorTab('agent')}>辅导</button>
                <button className={tutorTab === 'evidence' ? 'active' : ''} type="button" onClick={() => setTutorTab('evidence')} disabled={evidenceLocked}>证据</button>
                <button className={tutorTab === 'compare' ? 'active' : ''} type="button" onClick={() => setTutorTab('compare')}>对照</button>
              </div>
            ) : (
              <div className="tutor-review-lock">
                <strong>{isChallenge ? '比拼进行中' : mode === 'exam' ? '考试进行中' : '专注作答中'}</strong>
                <span>{isChallenge || mode === 'exam' ? '提交前隐藏提示、证据和挑战基准。' : '提交前只开放非泄题辅导；证据与对照将在提交后展开。'}</span>
              </div>
            )}
            {mode === 'exam' && !submission ? (
              <div className="exam-lock">
                <GraduationCap size={20} />
                <p>{examClosed ? '本场考试已结束。请查看考试战报，并进入错因复盘或重开本场。' : `考试进行中，剩余 ${formattedExamTime}，提示和自由追问已隐藏。`}</p>
              </div>
            ) : isChallenge && !submission ? (
              <div className="challenge-box">
                <div>
                  <Trophy size={17} />
                  <strong>独立作答锁定</strong>
                </div>
                <p>本轮提交前不开放 Agent 追问、证据页或挑战基准；提交后自动进入对照复盘并同步后端基准。</p>
                <span>{benchmarkLabel}。</span>
              </div>
            ) : tutorTab === 'agent' ? (
              <>
                <div className="chat-bubble agent">
                  <Bot size={18} />
                  <p>{hint}</p>
                </div>
                {canUseTutorChat ? (
                  <div className="agent-quick-prompts">
                    {quickAgentPrompts.map((prompt) => (
                      <button key={prompt} type="button" onClick={() => sendAgentMessage(prompt)} disabled={loading}>
                        {prompt}
                      </button>
                    ))}
                  </div>
                ) : null}
                <div className="chat-thread">
                  {chat.map((message, itemIndex) => (
                    <div className={`chat-line ${message.role}`} key={`${message.role}_${itemIndex}`}>
                      <span>{message.role === 'agent' ? `Agent${message.mode ? ` · ${message.mode}` : ''}` : '林医师'}</span>
                      <p>{message.text}</p>
                    </div>
                  ))}
                </div>
                <div className="chat-input-row">
                  <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder={!canUseTutorChat ? '当前模式锁定自由追问...' : '追问当前病例、证据或报告表达...'} disabled={!canUseTutorChat} />
                  <button className="icon-button" type="button" onClick={askAgent} title="发送追问" disabled={!canUseTutorChat || loading}>
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
                  <strong>医生 vs 挑战基准</strong>
                </div>
                <p>{challengeDelta}</p>
                {canRevealBenchmark ? (
                  <div className="challenge-round-grid">
                    <span>林医师：{submission?.is_correct ? '本轮正确' : '本轮失分'} · {selected}</span>
                    <span>{benchmarkLabel}：{challengeBenchmarkLoading ? '同步中' : benchmarkCorrect ? '基准正确' : '基准待复核'} · {challengeBenchmarkLoading ? '等待后端返回' : benchmarkAnswer}</span>
                    {currentChallengeBenchmark ? <span>理由：{currentChallengeBenchmark.rationale}</span> : null}
                    {currentChallengeBenchmark ? <span>审计：{currentChallengeBenchmark.audit_logged ? '已记录 challenge_benchmark' : '未写入审计'} · 画像：{currentChallengeBenchmark.profile_updated ? '已更新' : '未重复更新'}</span> : null}
                  </div>
                ) : <span>未提交前隐藏挑战基准，避免破坏练习闭环。</span>}
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
  if (doctorCorrect && benchmarkCorrect && sameAnswer) return '本轮同判正确：医师答案与挑战基准一致。'
  if (doctorCorrect && benchmarkCorrect) return '本轮都命中参考结论，但表达不同，适合复盘证据措辞。'
  if (doctorCorrect && !benchmarkCorrect) return '本轮医师领先：挑战基准需要复核或不适合作为最终判断。'
  if (!doctorCorrect && benchmarkCorrect) return '本轮挑战基准领先：建议复盘可观察证据和题干边界。'
  return '本轮双方都需复核：请回到证据标签逐条检查。'
}

function formatAuditTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function nextQuestionIndex(currentIndex: number, questions: Question[], attempts: ExamAttempt[], examMode: boolean): number {
  if (!questions.length) return 0
  if (!examMode) return (currentIndex + 1) % questions.length
  const answered = new Set(attempts.map((attempt) => attempt.questionId))
  for (let offset = 1; offset <= questions.length; offset += 1) {
    const candidate = (currentIndex + offset) % questions.length
    if (!answered.has(questions[candidate].id)) return candidate
  }
  return currentIndex
}

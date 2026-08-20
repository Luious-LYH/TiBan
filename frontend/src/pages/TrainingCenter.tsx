import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpenCheck,
  Bot,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Layers3,
  LoaderCircle,
  MessageCircle,
  PenLine,
  Save,
  Send,
  Shuffle,
  Sparkles,
  Star,
  Target,
  Trash2,
} from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { v3Api, v3DemoQuestion, v3SafetyNotice } from '../lib/v3Api'
import type { PortfolioAgentRun, PortfolioCase, PracticeState, PracticeSubmitResponse, Question, QuestionType } from '../lib/types'

type StudyMode = 'practice' | 'memory' | 'exam'
type SubPage = 'daily' | 'wrong' | 'favorites'
type QuestionTypeFilter = '全部题型' | QuestionType
type ChatMessage = {
  id: string
  role: 'agent' | 'doctor'
  text: string
  meta?: string
}

const defaultTypes = ['基础识别', '部位定位', '病变属性', '一图多问', '报告纠错']
const trainingTaxonomy = new Set(defaultTypes)
const questionTypeOptions: QuestionTypeFilter[] = ['全部题型', '单选', '多选', '判断', '问答评分', '报告修改']
const localFavoriteStorageKey = 'aris:practice:favorites:v1'
const modelAssignmentStorageKey = 'aris:model-task-assignment:v1'
const dailyPlanStorageKey = 'aris:practice:daily-target:v1'
const defaultDailyTarget = 50

type ModelTaskAssignments = {
  trainingTutorModelId?: string
  reportGenerationModelId?: string
  updatedAt?: string
}

const fallbackModelNames: Record<string, string> = {
  'agent-qwen': '平台研修助手 · Qwen 候选',
  'agent-medgemma': 'MedGemma 候选模型',
  'claude-opus': 'Claude Code opus 4.7',
  gpt55: 'GPT-5.5',
  'qwen3-8b': 'Qwen3-VL-8B',
}

const studyModes: { id: StudyMode; label: string; detail: string }[] = [
  { id: 'practice', label: '刷题模式', detail: '作答后看复盘，右侧可随时梳理观察思路。' },
  { id: 'memory', label: '背题模式', detail: '直接看知识点和参考答案，用于快速巩固。' },
  { id: 'exam', label: '考试模式', detail: '保持独立作答，只保留计时和提交。' },
]
const subPages: { id: SubPage; label: string; detail: string }[] = [
  { id: 'daily', label: '今日题组', detail: '平台推荐的混合题型。' },
  { id: 'wrong', label: '错题复盘', detail: '优先拉取待复盘题。' },
  { id: 'favorites', label: '收藏背题', detail: '快速回看收藏题。' },
]

export function TrainingCenter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [state, setState] = useState<PracticeState | null>(null)
  const [questions, setQuestions] = useState<Question[]>([v3DemoQuestion])
  const [selectedType, setSelectedType] = useState(searchParams.get('type') || '全部')
  const [selectedQuestionType, setSelectedQuestionType] = useState<QuestionTypeFilter>((searchParams.get('question_type') as QuestionTypeFilter) || '全部题型')
  const [studyMode, setStudyMode] = useState<StudyMode>((searchParams.get('mode') as StudyMode) || 'practice')
  const [subPage, setSubPage] = useState<SubPage>((searchParams.get('view') as SubPage) || 'daily')
  const [activeIndex, setActiveIndex] = useState(0)
  const [questionTotal, setQuestionTotal] = useState(1)
  const [questionTypeCounts, setQuestionTypeCounts] = useState<Record<string, number>>({})
  const [poolReceipt, setPoolReceipt] = useState<{ total: number; poolTotal: number; seed?: number | null }>({ total: 1, poolTotal: 1, seed: null })
  const [shuffleSeed, setShuffleSeed] = useState(() => Date.now())
  const [favoriteIds, setFavoriteIds] = useState<string[]>(() => readFavoriteIds())
  const [modelAssignments, setModelAssignments] = useState<ModelTaskAssignments>(() => readModelAssignments())
  const [dailyTarget, setDailyTarget] = useState(() => readDailyTarget())
  const [selectedAnswers, setSelectedAnswers] = useState<string[]>([])
  const [freeAnswer, setFreeAnswer] = useState('')
  const [submission, setSubmission] = useState<PracticeSubmitResponse | null>(null)
  const [portfolioRun, setPortfolioRun] = useState<PortfolioAgentRun | null>(null)
  const [portfolioRunBusy, setPortfolioRunBusy] = useState(false)
  const [savingCard, setSavingCard] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [agentBusy, setAgentBusy] = useState(false)
  const [annotationEnabled, setAnnotationEnabled] = useState(false)
  const [hasAnnotation, setHasAnnotation] = useState(false)
  const [examStartedAt] = useState(() => Date.now())
  const [now, setNow] = useState(() => Date.now())
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'agent',
      text: '我在旁边陪你梳理这道题。可以先说你看到的部位、形态或拿不准的选项，我们一起把依据理顺。',
      meta: '当前题上下文',
    },
  ])
  const feedbackRef = useRef<HTMLElement | null>(null)
  const chatLogRef = useRef<HTMLDivElement | null>(null)
  const annotationCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const annotationImageRef = useRef<HTMLImageElement | null>(null)
  const isAnnotatingRef = useRef(false)
  const question = questions[activeIndex] || questions[0]

  const clearAnnotation = useCallback((disableTool = false) => {
    const canvas = annotationCanvasRef.current
    const ctx = canvas?.getContext('2d')
    if (canvas && ctx) {
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
    isAnnotatingRef.current = false
    setHasAnnotation(false)
    if (disableTool) {
      setAnnotationEnabled(false)
    }
  }, [])

  const resetAnswerState = useCallback(() => {
    setSelectedAnswers([])
    setFreeAnswer('')
    setSubmission(null)
    setPortfolioRun(null)
    setChatInput('')
    clearAnnotation(true)
  }, [clearAnnotation])

  const syncAnnotationCanvas = useCallback(() => {
    const canvas = annotationCanvasRef.current
    const host = canvas?.parentElement
    const image = annotationImageRef.current
    if (!canvas || !host || !image) return
    const width = image.clientWidth || host.clientWidth
    const height = image.clientHeight || host.clientHeight
    if (!width || !height) return
    const ratio = window.devicePixelRatio || 1
    const nextWidth = Math.max(1, Math.round(width * ratio))
    const nextHeight = Math.max(1, Math.round(height * ratio))
    if (canvas.width === nextWidth && canvas.height === nextHeight) return
    const snapshot = document.createElement('canvas')
    snapshot.width = Math.max(1, canvas.width)
    snapshot.height = Math.max(1, canvas.height)
    snapshot.getContext('2d')?.drawImage(canvas, 0, 0)
    canvas.width = nextWidth
    canvas.height = nextHeight
    canvas.getContext('2d')?.drawImage(snapshot, 0, 0, nextWidth, nextHeight)
  }, [])

  useEffect(() => {
    v3Api.practiceState().then(setState).catch(() => setState(null))
  }, [])

  useEffect(() => {
    const syncAssignments = () => setModelAssignments(readModelAssignments())
    window.addEventListener('storage', syncAssignments)
    return () => window.removeEventListener('storage', syncAssignments)
  }, [])

  useEffect(() => {
    if (!state?.favorite_questions?.length) return
    const incomingFavorites = state.favorite_questions.map((item) => String(item)).filter(Boolean)
    const timer = window.setTimeout(() => {
      setFavoriteIds((current) => {
        const merged = [...new Set([...current, ...incomingFavorites])]
        return sameStringArray(current, merged) ? current : writeFavoriteIds(merged)
      })
    }, 0)
    return () => window.clearTimeout(timer)
  }, [state?.favorite_questions])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    const isGoldenDefault = selectedType === '全部'
      && selectedQuestionType === '全部题型'
      && studyMode === 'practice'
      && subPage === 'daily'
    if (isGoldenDefault) {
      v3Api.portfolioCases()
        .then((result) => {
          const items = result.items.map(portfolioCaseToQuestion)
          setQuestionTotal(items.length)
          setQuestionTypeCounts({ 问答评分: items.length })
          setPoolReceipt({ total: items.length, poolTotal: items.length, seed: null })
          setQuestions(items.length ? items : [v3DemoQuestion])
          setActiveIndex(0)
          resetAnswerState()
        })
        .catch(() => setQuestions([v3DemoQuestion]))
      return
    }
    const params = {
      ...(selectedType === '全部' ? {} : { questionClass: selectedType }),
      ...(selectedQuestionType === '全部题型' ? {} : { questionType: selectedQuestionType }),
      ...(subPage === 'wrong' ? { onlyWrong: true } : {}),
      limit: subPage === 'favorites' ? 60 : studyMode === 'exam' ? 12 : 30,
      shuffleSeed,
    }
    v3Api.practiceQuestions(params)
      .then((result) => {
        setQuestionTotal(result.total || result.items.length)
        setQuestionTypeCounts(result.available_type_counts || countQuestionTypes(result.items))
        setPoolReceipt({
          total: result.total || result.items.length,
          poolTotal: result.pool_total || result.total || result.items.length,
          seed: result.pool_seed ?? shuffleSeed,
        })
        const pool = shuffleSeed && !result.pool_seed ? shuffleQuestions(result.items, shuffleSeed) : result.items
        const filtered = filterQuestionsBySubPage(pool, subPage, favoriteIds)
        const nextQuestions = subPage === 'favorites'
          ? filtered
          : filtered.length
            ? filtered
            : result.items.length
              ? result.items
              : [v3DemoQuestion]
        setQuestions(nextQuestions)
        setActiveIndex(0)
        resetAnswerState()
      })
      .catch(() => setQuestions([v3DemoQuestion]))
  }, [selectedType, selectedQuestionType, studyMode, subPage, shuffleSeed, favoriteIds, resetAnswerState])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      resetAnswerState()
      setMessages([
        {
          id: `context_${question?.id || 'none'}`,
          role: 'agent',
          text: studyMode === 'exam'
            ? '考试模式已启用，先独立完成本题；提交后再做复盘。'
            : `已切换到“${question?.title || '当前题'}”。先说出你看到的部位、形态和数量，再决定选项。`,
          meta: studyMode === 'exam' ? '独立作答中' : '题目已就绪',
        },
      ])
    }, 0)
    return () => window.clearTimeout(timer)
  }, [activeIndex, question?.id, question?.title, studyMode, resetAnswerState])

  useEffect(() => {
    chatLogRef.current?.scrollTo({ top: chatLogRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, agentBusy])

  useEffect(() => {
    if (!question?.image_url) return
    const canvas = annotationCanvasRef.current
    const host = canvas?.parentElement
    if (!host) return
    syncAnnotationCanvas()
    const onResize = () => syncAnnotationCanvas()
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(onResize) : null
    observer?.observe(host)
    window.addEventListener('resize', onResize)
    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', onResize)
    }
  }, [question?.image_url, syncAnnotationCanvas])

  const taxonomy = state?.question_types?.length
    ? state.question_types.map((item) => item.name).filter((name) => trainingTaxonomy.has(name))
    : defaultTypes
  const progress = state?.progress
  const progressCompleted = progress?.completed ?? state?.profile.completed_today ?? 0
  const effectiveDailyTarget = Math.max(defaultDailyTarget, dailyTarget || progress?.target || state?.profile.daily_target || defaultDailyTarget)
  const effectiveProgressPercent = Math.min(100, Math.round((progressCompleted / effectiveDailyTarget) * 100))
  const answerValue = getAnswerValue(question, selectedAnswers, freeAnswer)
  const canSubmit = Boolean(question && answerValue.trim() && !submission)
  const isSubmittedOrMemory = Boolean(submission) || studyMode === 'memory'
  const examElapsed = Math.floor((now - examStartedAt) / 1000)
  const trainingModelId = modelAssignments.trainingTutorModelId
  const trainingModelLabel = trainingModelId ? fallbackModelNames[trainingModelId] || trainingModelId : '平台研修辅导'

  const typeCoverage = useMemo(() => {
    const counts = Object.keys(questionTypeCounts).length ? questionTypeCounts : countQuestionTypes(questions)
    return questionTypeOptions
      .filter((item) => item !== '全部题型')
      .map((type) => [type, counts[type] || 0] as [string, number])
  }, [questionTypeCounts, questions])

  const isFavorite = Boolean(question && (favoriteIds.includes(question.id) || question.is_favorited))

  const updateRouteState = (next: { type?: string; questionType?: QuestionTypeFilter; mode?: StudyMode; view?: SubPage }) => {
    const type = next.type ?? selectedType
    const questionType = next.questionType ?? selectedQuestionType
    const mode = next.mode ?? studyMode
    const view = next.view ?? subPage
    const params: Record<string, string> = {}
    if (type !== '全部') params.type = type
    if (questionType !== '全部题型') params.question_type = questionType
    if (mode !== 'practice') params.mode = mode
    if (view !== 'daily') params.view = view
    setSearchParams(params)
  }

  const updateDailyTarget = (value: number) => {
    const next = Math.max(defaultDailyTarget, Math.min(300, Math.round(value || defaultDailyTarget)))
    setDailyTarget(next)
    writeDailyTarget(next)
    window.dispatchEvent(new Event('daily-plan-change'))
  }

  function getAnnotationPoint(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = annotationCanvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height
    return { x, y }
  }

  function paintAnnotationDot(point: { x: number; y: number }, startPath = false) {
    const canvas = annotationCanvasRef.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    const widthScale = Math.max(canvas.width, canvas.height) / 450
    ctx.strokeStyle = '#ef4444'
    ctx.fillStyle = '#ef4444'
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.lineWidth = Math.max(4, 6 * widthScale)
    if (startPath) {
      ctx.beginPath()
      ctx.arc(point.x, point.y, Math.max(3, 4.5 * widthScale), 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.moveTo(point.x, point.y)
      return
    }
    ctx.lineTo(point.x, point.y)
    ctx.stroke()
  }

  function startAnnotation(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!annotationEnabled || !question?.image_url) return
    event.preventDefault()
    syncAnnotationCanvas()
    const point = getAnnotationPoint(event)
    if (!point) return
    const canvas = annotationCanvasRef.current
    if (!canvas) return
    isAnnotatingRef.current = true
    canvas.setPointerCapture?.(event.pointerId)
    paintAnnotationDot(point, true)
    setHasAnnotation(true)
  }

  function moveAnnotation(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!annotationEnabled || !isAnnotatingRef.current) return
    const point = getAnnotationPoint(event)
    if (!point) return
    paintAnnotationDot(point, false)
    setHasAnnotation(true)
  }

  function stopAnnotation(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!annotationEnabled) return
    const canvas = annotationCanvasRef.current
    if (canvas) {
      try {
        canvas.releasePointerCapture(event.pointerId)
      } catch {
        // ignore
      }
    }
    isAnnotatingRef.current = false
  }

  function exportAnnotatedImageDataUrl() {
    const image = annotationImageRef.current
    const canvas = annotationCanvasRef.current
    if (!image || !canvas || !hasAnnotation || !question?.image_url) return undefined
    if (!image.complete || !image.naturalWidth || !image.naturalHeight) return undefined
    try {
      const output = document.createElement('canvas')
      output.width = canvas.width || image.naturalWidth
      output.height = canvas.height || image.naturalHeight
      const ctx = output.getContext('2d')
      if (!ctx) return undefined
      drawImageCover(ctx, image, output.width, output.height)
      ctx.drawImage(canvas, 0, 0, output.width, output.height)
      return output.toDataURL('image/jpeg', 0.92)
    } catch {
      return undefined
    }
  }

  function drawImageCover(ctx: CanvasRenderingContext2D, image: HTMLImageElement, width: number, height: number) {
    const imageRatio = image.naturalWidth / image.naturalHeight
    const outputRatio = width / height
    let sx = 0
    let sy = 0
    let sw = image.naturalWidth
    let sh = image.naturalHeight
    if (imageRatio > outputRatio) {
      sw = image.naturalHeight * outputRatio
      sx = (image.naturalWidth - sw) / 2
    } else if (imageRatio < outputRatio) {
      sh = image.naturalWidth / outputRatio
      sy = (image.naturalHeight - sh) / 2
    }
    ctx.drawImage(image, sx, sy, sw, sh, 0, 0, width, height)
  }

  const nextQuestion = () => {
    setActiveIndex((index) => (index + 1) % Math.max(questions.length, 1))
  }

  const randomQuestion = () => {
    if (questions.length <= 1) return
    setActiveIndex((index) => {
      const next = Math.floor(Math.random() * questions.length)
      return next === index ? (next + 1) % questions.length : next
    })
  }

  const chooseSingle = (option: string) => {
    if (submission || studyMode === 'memory') return
    setSelectedAnswers([option])
  }

  const toggleMulti = (option: string) => {
    if (submission || studyMode === 'memory') return
    setSelectedAnswers((answers) => (
      answers.includes(option) ? answers.filter((item) => item !== option) : [...answers, option]
    ))
  }

  const submit = async () => {
    if (!question || !canSubmit) return
    setPortfolioRunBusy(true)
    try {
      const caseId = portfolioCaseId(question.image_url, question.id)
      if (caseId) {
        try {
          const run = await v3Api.portfolioAgentRun(caseId, answerValue)
          setPortfolioRun(run)
          setSubmission(portfolioRunToSubmission(question, answerValue, run))
        } catch {
          setPortfolioRun(null)
          setSubmission(await v3Api.practiceSubmit(question, answerValue))
        }
      } else {
        setSubmission(await v3Api.practiceSubmit(question, answerValue))
      }
      v3Api.practiceState().then(setState).catch(() => undefined)
      window.setTimeout(() => feedbackRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80)
    } finally {
      setPortfolioRunBusy(false)
    }
  }

  const sendAgentMessage = async (text = chatInput) => {
    const message = text.trim()
    if (!question || !message || agentBusy || studyMode === 'exam') return
    setChatInput('')
    setAgentBusy(true)
    const annotatedImageDataUrl = exportAnnotatedImageDataUrl()
    const doctorMessage: ChatMessage = { id: `doctor_${now}_${messages.length}`, role: 'doctor', text: message }
    setMessages((items) => [...items, { ...doctorMessage, meta: annotatedImageDataUrl ? '带图中圈画' : undefined }])
    try {
      const result = await v3Api.practiceTutor({
        questionId: question.id,
        mode: 'chat',
        selectedAnswer: answerValue || undefined,
        message,
        displayModelName: trainingModelLabel,
        annotatedImageDataUrl,
      })
      const reply = String(result.reply || result.explanation || result.hint || '我会围绕当前题继续追问观察依据。')
      const providerStatus = result.provider_status as { ok?: boolean; mode?: string; provider?: string; latency_ms?: number | null } | undefined
      const providerOk = Boolean(providerStatus?.ok)
      const sourceLabel = providerOk
        ? `${providerStatus?.provider || trainingModelLabel} · Provider`
        : providerStatus?.mode === 'rule'
          ? '本地规则辅导'
          : '显式回退辅导'
      setMessages((items) => [
        ...items,
        {
          id: `agent_${now}_${items.length}`,
          role: 'agent',
          text: reply,
          meta: `${sourceLabel}${annotatedImageDataUrl ? ' · 已接收圈画' : ''}${providerStatus?.latency_ms ? ` · ${providerStatus.latency_ms}ms` : ''}`,
        },
      ])
    } finally {
      setAgentBusy(false)
    }
  }

  const saveMemoryCard = () => {
    if (!question) return
    setSavingCard(true)
    const payload = {
      title: question.title,
      point: memoryPoint(question),
      answer: question.answer,
      saved_at: new Date().toISOString(),
    }
    window.localStorage.setItem(`endo_memory_${question.id}`, JSON.stringify(payload))
    window.setTimeout(() => setSavingCard(false), 650)
  }

  const toggleFavorite = () => {
    if (!question) return
    const nextFavorite = !isFavorite
    setFavoriteIds((current) => {
      const next = nextFavorite
        ? [...new Set([...current, question.id])]
        : current.filter((item) => item !== question.id)
      return writeFavoriteIds(next)
    })
    setQuestions((items) => items.map((item) => item.id === question.id ? { ...item, is_favorited: nextFavorite } : item))
    v3Api.favoriteQuestion(question.id, nextFavorite).catch(() => undefined)
  }

  const scoreTone = submission?.is_correct ? 'green' : submission ? 'amber' : 'blue'

  return (
    <div className="page-stack v3-page">
      <section
        className="v3-page-hero practice-hero"
        data-training-mission="true"
        data-learner-id={state?.profile?.learner_id || 'demo_learner'}
        data-training-mode={studyMode}
      >
        <div>
          <Tag tone="green">Golden Demo · 多模态带教</Tag>
          <h2>观察一个病例，让 Agent 完成证据复盘</h2>
          <p>先看图、圈画并独立作答。提交后，系统会把评分、事实证据、错因、画像影响与下一步推荐组织成可检查的执行收据。</p>
        </div>
        <div className="v3-hero-score compact">
          <span>{studyMode === 'exam' ? '独立作答计时' : '当前病例'}</span>
          <strong>{studyMode === 'exam' ? formatTime(examElapsed) : question?.title || '公开教学病例'}</strong>
          <div className="v3-mini-progress"><i style={{ width: `${studyMode === 'exam' ? 0 : effectiveProgressPercent}%` }} /></div>
          <small>{state?.api_source === 'backend' ? '后端病例服务' : '本地演示回退'} · {question?.source_dataset || '公开教学样例'} · 第 {activeIndex + 1}/{questions.length} 题</small>
        </div>
      </section>

      <div className="practice-command-layout golden-focus">
        <Card className="practice-left-rail">
          <SectionTitle eyebrow="研修子页面" title="模式与题组" />
          <label className="practice-select-label">
            <span>子页面</span>
            <select
              value={subPage}
              onChange={(event) => {
                const value = event.target.value as SubPage
                setSubPage(value)
                updateRouteState({ view: value })
              }}
            >
              {subPages.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
            <small>{subPages.find((item) => item.id === subPage)?.detail}</small>
          </label>
          <div className="practice-mode-list">
            {studyModes.map((mode) => (
              <button
                key={mode.id}
                className={studyMode === mode.id ? 'active' : ''}
                onClick={() => {
                  setStudyMode(mode.id)
                  updateRouteState({ mode: mode.id })
                  setShuffleSeed(Date.now())
                }}
              >
                {mode.id === 'practice' ? <BookOpenCheck size={17} /> : mode.id === 'memory' ? <GraduationCap size={17} /> : <Clock3 size={17} />}
                <span>{mode.label}</span>
                <small>{mode.detail}</small>
              </button>
            ))}
          </div>
          <div className="practice-type-summary">
            <strong>今日计划</strong>
            <label className="daily-target-control">
              <span>刷题目标</span>
              <input
                type="number"
                min={defaultDailyTarget}
                max={300}
                step={5}
                value={effectiveDailyTarget}
                onChange={(event) => updateDailyTarget(Number(event.target.value))}
              />
            </label>
            <small>默认不少于 {defaultDailyTarget} 题，可按研修强度调整。</small>
          </div>
          <div className="practice-question-type-grid" aria-label="题型切换">
            {questionTypeOptions.map((item) => {
              const count = item === '全部题型'
                ? Object.values(questionTypeCounts).reduce((sum, value) => sum + value, 0) || questionTotal
                : questionTypeCounts[item] || 0
              return (
                <button
                  key={item}
                  type="button"
                  className={selectedQuestionType === item ? 'active' : ''}
                  onClick={() => {
                    setSelectedQuestionType(item)
                    updateRouteState({ questionType: item })
                    setShuffleSeed(Date.now())
                  }}
                >
                  <span>{item}</span>
                  <b>{count}</b>
                </button>
              )
            })}
          </div>
          <label className="practice-select-label">
            <span>题型</span>
            <select
              value={selectedQuestionType}
              onChange={(event) => {
                const value = event.target.value as QuestionTypeFilter
                setSelectedQuestionType(value)
                updateRouteState({ questionType: value })
                setShuffleSeed(Date.now())
              }}
            >
            {questionTypeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <small>切换后会重新拉取对应题型题组。</small>
          </label>
          <div className="practice-type-summary">
            <strong>题型覆盖</strong>
            {typeCoverage.map(([type, count]) => (
              <span key={type}>{type}<b>{count}</b></span>
            ))}
          </div>
        </Card>

        <main className="practice-main-column">
          <Card className="practice-task-bar">
            <div>
              <span>专项维度</span>
              <strong>{selectedType === '全部' ? '综合题组' : selectedType} · {selectedQuestionType}</strong>
            </div>
            <div className="v3-chip-row">
              <button className={selectedType === '全部' ? 'active' : ''} onClick={() => { setSelectedType('全部'); updateRouteState({ type: '全部' }); setShuffleSeed(Date.now()) }}>全部</button>
              {taxonomy.map((type) => (
                <button key={type} className={selectedType === type ? 'active' : ''} onClick={() => { setSelectedType(type); updateRouteState({ type }); setShuffleSeed(Date.now()) }}>
                  {type}
                </button>
              ))}
            </div>
            <div className="practice-pool-receipt">
              <span>随机题组</span>
              <b>{poolReceipt.poolTotal || questionTotal} 题池</b>
              <small>{selectedQuestionType} · 当前筛选返回 {questionTotal} 题</small>
            </div>
            <div className="practice-question-tools">
              <button type="button" onClick={() => setShuffleSeed(Date.now())}>
                <Shuffle size={15} /> 刷新题组
              </button>
              <button type="button" onClick={randomQuestion} disabled={questions.length <= 1}>
                <Shuffle size={15} /> 随机一题
              </button>
            </div>
          </Card>

          {question ? (
            <div className="practice-workbench">
              <Card className="practice-image-panel">
                <div className="practice-image">
                  {question.image_url ? (
                    <>
                      <img
                        ref={annotationImageRef}
                        src={question.image_url}
                        alt={question.title}
                        data-real-sample-image="true"
                        data-real-sample-role="primary"
                        onLoad={() => {
                          syncAnnotationCanvas()
                        }}
                      />
                      <canvas
                        ref={annotationCanvasRef}
                        className={`practice-annotation-canvas ${annotationEnabled ? 'enabled' : ''}`}
                        aria-hidden="true"
                        onPointerDown={startAnnotation}
                        onPointerMove={moveAnnotation}
                        onPointerUp={stopAnnotation}
                        onPointerLeave={stopAnnotation}
                        onPointerCancel={stopAnnotation}
                      />
                    </>
                  ) : (
                    <div className="practice-image-placeholder">{question.image_placeholder}</div>
                  )}
                  {question.image_url ? (
                    <div className="practice-annotation-tools">
                      <button
                        type="button"
                        className={annotationEnabled ? 'active' : ''}
                        onClick={() => setAnnotationEnabled((value) => !value)}
                        aria-pressed={annotationEnabled}
                        aria-label={annotationEnabled ? '结束圈画图像' : '开始圈画图像'}
                        title="圈画图像重点"
                      >
                        <PenLine size={15} /> {annotationEnabled ? '圈画中' : '圈画'}
                      </button>
                      <button type="button" onClick={() => clearAnnotation()} disabled={!hasAnnotation} aria-label="清除圈画">
                        <Trash2 size={15} /> 清除
                      </button>
                    </div>
                  ) : null}
                </div>
                <div className="practice-image-meta">
                  <Tag tone="blue">{question.question_class}</Tag>
                  <Tag tone="green">{question.question_type}</Tag>
                  <Tag tone={question.difficulty === '挑战' ? 'amber' : 'blue'}>{question.difficulty}</Tag>
                  <span>{question.body_part} · {question.source_dataset}</span>
                  {hasAnnotation ? <span className="practice-annotation-hint">提问时会带上圈画重点</span> : null}
                </div>
              </Card>

              <Card className="practice-question-panel">
                <SectionTitle
                  eyebrow={`第 ${activeIndex + 1}/${questions.length} 题`}
                  title={question.title}
                  action={
                    <div className="practice-question-head-actions">
                      <button
                        type="button"
                        className={`practice-favorite-toggle ${isFavorite ? 'active' : ''}`}
                        aria-pressed={isFavorite}
                        onClick={toggleFavorite}
                      >
                        <Star size={16} /> {isFavorite ? '已收藏' : '收藏'}
                      </button>
                      <Tag tone={scoreTone}>{submission ? `${submission.score} 分` : studyMode === 'memory' ? '背题' : '待作答'}</Tag>
                    </div>
                  }
                />
                <p className="practice-case">{question.case_summary}</p>
                <h3>{question.question}</h3>
                <AnswerControl
                  question={question}
                  selectedAnswers={selectedAnswers}
                  freeAnswer={freeAnswer}
                  locked={Boolean(submission) || studyMode === 'memory'}
                  showAnswer={isSubmittedOrMemory}
                  onSingle={chooseSingle}
                  onMulti={toggleMulti}
                  onFreeAnswer={setFreeAnswer}
                />
                {submission ? (
                  <SubmissionFeedbackPanel question={question} submission={submission} agentRun={portfolioRun} />
                ) : studyMode === 'memory' ? null : (
                  <div className="practice-feedback-lock">
                    <CheckCircle2 size={16} />
                    <span>先按自己的判断作答；提交后会看到对错、参考答案、错因标签和观察依据。</span>
                  </div>
                )}
                <div className="practice-actions">
                  <button className="button primary" onClick={submit} disabled={!canSubmit || studyMode === 'memory' || portfolioRunBusy}>
                    {portfolioRunBusy ? <LoaderCircle size={16} className="spin" /> : null}
                    提交并运行 Agent <ArrowRight size={16} />
                  </button>
                  <button className="button secondary" onClick={saveMemoryCard} disabled={!question}>
                    <Save size={16} /> {savingCard ? '已保存' : '记忆卡'}
                  </button>
                  <button className="button secondary" onClick={nextQuestion}>
                    下一题
                  </button>
                </div>
              </Card>
            </div>
          ) : (
            <Card className="practice-empty-state">
              <Star size={30} />
              <h3>{subPage === 'favorites' ? '暂无收藏题' : '当前筛选暂无题目'}</h3>
              <p>{subPage === 'favorites' ? '在今日题组中点击题头星标后，这里会只显示你收藏的题。' : '换一个专项维度或刷新题组即可继续研修。'}</p>
              <button className="button secondary" onClick={() => { setSubPage('daily'); updateRouteState({ view: 'daily' }); setShuffleSeed(Date.now()) }}>
                返回今日题组
              </button>
            </Card>
          )}

          {question ? <div className="practice-feedback-grid">
            <Card className="practice-feedback-card" ref={feedbackRef}>
              <SectionTitle eyebrow="观察依据复盘" title={submission ? '证据点与下一步' : studyMode === 'memory' ? '背题要点' : '先作答再复盘'} />
              {submission || studyMode === 'memory' ? (
                <>
                  <p>{submission?.explanation || question.explanation}</p>
                  <div className="fact-list">
                    {(submission?.fact_feedback || question.atomic_trace).map((fact) => (
                      <div key={fact.id}>
                        <Layers3 size={16} />
                        <div>
                          <strong>{fact.fact}</strong>
                          <span>{fact.evidence}</span>
                        </div>
                        <Tag tone={fact.supported ? 'green' : 'amber'}>{fact.skill_dimension}</Tag>
                      </div>
                    ))}
                  </div>
                  <div className="v3-next-callout">
                    <Target size={18} />
                    <span>{submission?.next_recommendation || memoryPoint(question)}</span>
                  </div>
                </>
              ) : (
                <p>先按自己的判断完成本题；提交后，这里会整理证据点、参考答案和下一题建议。</p>
              )}
            </Card>

            <Card className="practice-side-card">
              <SectionTitle eyebrow="轻量记忆卡" title="一句话知识点" />
              <div className="memory-card-preview">
                <Sparkles size={22} />
                <strong>{question ? memoryPoint(question) : '先选择一道研修题'}</strong>
                <span>{question?.question_class || '研修'}</span>
              </div>
            </Card>
          </div> : null}
        </main>

        <aside className={`practice-agent-panel ${studyMode === 'exam' ? 'locked' : ''}`}>
          <div className="agent-chat-head">
            <div>
              <Tag tone={studyMode === 'exam' ? 'amber' : 'green'}>{studyMode === 'exam' ? '独立作答' : '实时辅导'}</Tag>
              <h3><Bot size={19} /> 研修辅导</h3>
            </div>
            <span>{question?.question_type || '题目'} · 来源按响应标注</span>
          </div>
          <div className="agent-chat-purpose">
            <MessageCircle size={15} />
            <span>把拿不准的观察点写在这里即可；先独立判断，再一起把图像依据和表达边界理顺。</span>
          </div>
          <div className="agent-chat-log" ref={chatLogRef}>
            {messages.map((message) => (
              <div key={message.id} className={`agent-chat-message ${message.role}`}>
                <p>{message.text}</p>
                {message.meta ? <span>{message.meta}</span> : null}
              </div>
            ))}
            {agentBusy ? (
              <div className="agent-chat-message agent">
                <p><LoaderCircle size={15} className="spin" /> 正在回复...</p>
              </div>
            ) : null}
          </div>
          <div className="agent-quick-prompts compact">
            {['提示我先看哪里', '梳理观察步骤', '给我一个追问', '总结成记忆卡'].map((prompt) => (
              <button key={prompt} onClick={() => sendAgentMessage(prompt)} disabled={!question || studyMode === 'exam' || agentBusy}>
                {prompt}
              </button>
            ))}
          </div>
          <form
            className="agent-chat-input"
            onSubmit={(event) => {
              event.preventDefault()
              sendAgentMessage()
            }}
          >
            <input
              value={studyMode === 'exam' ? '考试模式先独立作答' : chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              disabled={!question || studyMode === 'exam' || agentBusy}
              placeholder="写下你的观察疑问，或说说你卡在哪一步。"
            />
            <button className="button primary" disabled={!question || studyMode === 'exam' || agentBusy || !chatInput.trim()} aria-label="发送研修提问">
              <Send size={16} />
            </button>
          </form>
          <div className="agent-chat-boundary">
            <MessageCircle size={15} />
            <span>这里聊研修思路和图像依据；临床结论仍需医生复核。</span>
          </div>
        </aside>
      </div>

      <SafetyNotice text={state?.safety_notice || v3SafetyNotice} />
    </div>
  )
}

function SubmissionFeedbackPanel({ question, submission, agentRun }: { question: Question; submission: PracticeSubmitResponse; agentRun: PortfolioAgentRun | null }) {
  const resultLabel = submission.is_correct ? '回答正确' : '需要复盘'
  const userAnswer = submission.selected_answer || '未记录'
  const sourceLabel = agentRun ? 'Backend Agent Runtime' : submission.api_source === 'backend' ? 'Backend 评分服务' : 'Frontend 演示回退'
  return (
    <section className={`practice-inline-feedback ${submission.is_correct ? 'correct' : 'review'}`} aria-label="提交后作答反馈">
      <div className="practice-inline-feedback-head">
        <div>
          <span>作答反馈已生成</span>
          <strong>{resultLabel} · {submission.score} 分</strong>
        </div>
        <Tag tone={submission.is_correct ? 'green' : 'amber'}>{submission.practice_summary?.result || resultLabel}</Tag>
      </div>
      <div className="practice-answer-compare">
        <div>
          <span>你的答案</span>
          <b>{userAnswer}</b>
        </div>
        <div>
          <span>参考答案</span>
          <b>{question.answer}</b>
        </div>
      </div>
      <p>{submission.explanation || question.explanation}</p>
      <div className="practice-feedback-tags">
        {(submission.error_tags.length ? submission.error_tags : ['无明显错因']).map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="practice-feedback-next">
        <Target size={16} />
        <span>{submission.next_recommendation || submission.practice_summary?.next_step || '继续完成下一题研修。'}</span>
      </div>
      <div className="agent-run-receipt" data-agent-receipt="true">
        <div className="agent-run-receipt-head">
          <span><Bot size={16} /> Agent 执行收据</span>
          <Tag tone={agentRun || submission.api_source === 'backend' ? 'green' : 'amber'}>{sourceLabel}</Tag>
        </div>
        <div className="agent-run-steps" aria-label="Agent 执行步骤">
          {agentRun ? agentRun.trace.map((step, index) => (
            <div key={step.node}>
              <b>{String(index + 1).padStart(2, '0')}</b>
              <span><strong>{step.node}</strong><small>{step.summary} · {step.latency_ms.toFixed(3)}ms</small></span>
            </div>
          )) : (
            <>
              <div><b>01</b><span><strong>读取上下文</strong><small>病例、题目与本次作答</small></span></div>
              <div><b>02</b><span><strong>调用评分工具</strong><small>返回分数与错因标签</small></span></div>
              <div><b>03</b><span><strong>核对事实证据</strong><small>{submission.fact_feedback.length} 条原子事实</small></span></div>
              <div><b>04</b><span><strong>学习记忆</strong><small>{submission.profile_updated ? '画像已更新' : '本次未更新画像'}</small></span></div>
            </>
          )}
        </div>
        <div className="agent-run-outcome">
          <span><strong>运行标识</strong>{agentRun?.run_id || '兼容评分链路'}</span>
          <span><strong>证据</strong>{agentRun ? `${agentRun.result.matched_fact_ids.length} 条命中 · F1 ${(agentRun.result.fact_f1 * 100).toFixed(0)}%` : submission.fact_feedback.length ? `${submission.fact_feedback.filter((fact) => fact.supported).length}/${submission.fact_feedback.length} 条支持` : '暂无事实项'}</span>
          <span><strong>画像影响</strong>{agentRun ? `${agentRun.memory_delta.dimension_deltas.length} 项 Delta 预览（未落盘）` : submission.practice_summary?.profile_delta || (submission.profile_updated ? '已记录本次表现' : '无变化')}</span>
          <span><strong>总耗时</strong>{agentRun ? `${agentRun.latency_ms.toFixed(3)}ms（规则服务）` : '未采集'}</span>
          <span><strong>下一步</strong>{agentRun?.result.next_recommendation || submission.next_recommendation || '继续病例研修'}</span>
        </div>
      </div>
    </section>
  )
}

function portfolioCaseId(imageUrl?: string | null, questionId?: string) {
  if (String(questionId || '').startsWith('case_')) return String(questionId)
  const mappings: Array<[string, string]> = [
    ['x1_clb0kvxvm90y4074yf50vf5nq', 'case_esophagus_landmark'],
    ['x1_cl8k2u1qa1ekz08324rek2qcv', 'case_polyp_followup'],
    ['x1_cla820gmss67b071u3h7o5k3t', 'case_negative_findings'],
    ['x1_clb0lbwzpdpgo086ucmqx7nyu', 'case_instrument_field'],
    ['endo_image_0', 'case_capsule_anatomy'],
  ]
  return mappings.find(([needle]) => String(imageUrl || '').includes(needle))?.[1]
}

function portfolioRunToSubmission(question: Question, learnerAnswer: string, run: PortfolioAgentRun): PracticeSubmitResponse {
  const matched = new Set(run.result.matched_fact_ids)
  const factFeedback = question.atomic_trace.map((fact) => ({ ...fact, supported: matched.has(fact.id) }))
  const missedFacts = factFeedback.filter((fact) => !fact.supported)
  return {
    id: run.run_id,
    question_id: question.id,
    learner_id: run.learner_id,
    selected_answer: learnerAnswer,
    is_correct: run.result.score >= 80,
    score: run.result.score,
    error_tags: missedFacts.map((fact) => `${fact.skill_dimension}遗漏`).slice(0, 3),
    fact_feedback: factFeedback,
    explanation: run.result.feedback,
    next_recommendation: run.result.next_recommendation,
    created_at: run.created_at,
    profile_updated: run.memory_delta.committed,
    doctor_review_required: run.doctor_review_required,
    safety_notice: run.safety_notice,
    api_source: 'backend',
    practice_summary: {
      result: run.result.score >= 80 ? '事实覆盖达标' : '需要复盘',
      profile_delta: `${run.memory_delta.dimension_deltas.length} 项 Delta 预览（未落盘）`,
      next_step: run.result.next_recommendation,
    },
  }
}

function portfolioCaseToQuestion(item: PortfolioCase): Question {
  return {
    id: item.id,
    title: item.title,
    image_url: item.image_url,
    image_placeholder: `${item.title}公开教学图像`,
    case_summary: `${item.source_type}。请围绕当前视野完成观察记录，不包含真实患者身份信息。`,
    question: item.prompt,
    options: [],
    answer: item.gold_answer,
    explanation: `参考表达：${item.gold_answer}`,
    complexity: item.difficulty === '挑战' ? 3 : 2,
    question_class: '一图多问',
    source_type: '教学样例',
    atomic_trace: item.facts.map((fact) => ({
      id: fact.id,
      fact: fact.label,
      expected: fact.aliases.join(' / '),
      supported: true,
      evidence: fact.evidence,
      skill_dimension: fact.dimension as Question['atomic_trace'][number]['skill_dimension'],
    })),
    false_premise_flag: false,
    teaching_tags: [...new Set(item.facts.map((fact) => fact.dimension))].slice(0, 4),
    difficulty: item.difficulty as Question['difficulty'],
    doctor_review_required: true,
    safety_notice: v3SafetyNotice,
    body_part: item.title.includes('食管') ? '食管' : item.title.includes('胶囊') ? '小肠' : '消化道',
    task: '医生观察记录',
    question_type: '问答评分',
    source_dataset: '公开脱敏教学病例',
    citation_note: `${item.source_dataset} 公开教学样例，仅用于研修演示。`,
    is_favorited: false,
    review_status: '未开始',
    ai_benchmark_answer: null,
    expected_keywords: item.facts.flatMap((fact) => fact.aliases.slice(0, 1)),
  }
}

function AnswerControl({
  question,
  selectedAnswers,
  freeAnswer,
  locked,
  showAnswer,
  onSingle,
  onMulti,
  onFreeAnswer,
}: {
  question: Question
  selectedAnswers: string[]
  freeAnswer: string
  locked: boolean
  showAnswer: boolean
  onSingle: (option: string) => void
  onMulti: (option: string) => void
  onFreeAnswer: (value: string) => void
}) {
  if (question.question_type === '问答评分' || question.question_type === '报告修改') {
    return (
      <div className="practice-free-answer">
        <label>
          <span>{question.question_type === '报告修改' ? '修改后的报告表达' : '你的回答'}</span>
          <textarea
            rows={7}
            value={locked && !freeAnswer ? question.answer : freeAnswer}
            onChange={(event) => onFreeAnswer(event.target.value)}
            disabled={locked}
            placeholder="请输入观察依据、判断和复核边界。"
          />
        </label>
        {showAnswer ? <div className="practice-reference-answer"><strong>参考答案</strong><p>{question.answer}</p></div> : null}
      </div>
    )
  }

  const multi = question.question_type === '多选'
  return (
    <div className={`practice-options ${multi ? 'multi' : ''}`}>
      {question.options.map((option) => {
        const selected = selectedAnswers.includes(option)
        const correct = showAnswer && isCorrectOption(question, option)
        return (
          <button
            key={option}
            className={`${selected ? 'selected' : ''} ${correct ? 'correct' : ''}`}
            onClick={() => (multi ? onMulti(option) : onSingle(option))}
            disabled={locked}
            type="button"
          >
            {correct ? <CheckCircle2 size={16} /> : <span />}
            {option}
          </button>
        )
      })}
    </div>
  )
}

function getAnswerValue(question: Question | undefined, selectedAnswers: string[], freeAnswer: string) {
  if (!question) return ''
  if (question.question_type === '问答评分' || question.question_type === '报告修改') return freeAnswer
  if (question.question_type === '多选') return selectedAnswers.join('；')
  return selectedAnswers[0] || ''
}

function isCorrectOption(question: Question, option: string) {
  if (question.question_type === '多选') {
    return question.answer.split(/[；;]/).map((item) => item.trim()).filter(Boolean).includes(option)
  }
  return option === question.answer
}

function filterQuestionsBySubPage(items: Question[], subPage: SubPage, favoriteIds: string[]) {
  if (subPage === 'wrong') {
    const wrong = items.filter((item) => item.review_status === '待复盘')
    return wrong.length ? wrong : items.slice(0, 12)
  }
  if (subPage === 'favorites') {
    const favorites = items.filter((item) => favoriteIds.includes(item.id) || item.is_favorited || item.review_status === '收藏中')
    return favorites
  }
  return items
}

function countQuestionTypes(items: Question[]) {
  return items.reduce<Record<string, number>>((counts, item) => {
    counts[item.question_type] = (counts[item.question_type] || 0) + 1
    return counts
  }, {})
}

function shuffleQuestions(items: Question[], seed: number) {
  const shuffled = [...items]
  let cursor = seed || 1
  for (let index = shuffled.length - 1; index > 0; index -= 1) {
    cursor = (cursor * 9301 + 49297) % 233280
    const swapIndex = Math.floor((cursor / 233280) * (index + 1))
    ;[shuffled[index], shuffled[swapIndex]] = [shuffled[swapIndex], shuffled[index]]
  }
  return shuffled
}

function readFavoriteIds() {
  if (typeof window === 'undefined') return []
  try {
    const parsed = JSON.parse(window.localStorage.getItem(localFavoriteStorageKey) || '[]')
    return Array.isArray(parsed) ? parsed.map((item) => String(item)).filter(Boolean) : []
  } catch {
    return []
  }
}

function writeFavoriteIds(ids: string[]) {
  const next = [...new Set(ids)]
  window.localStorage.setItem(localFavoriteStorageKey, JSON.stringify(next))
  return next
}

function sameStringArray(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index])
}

function readModelAssignments(): ModelTaskAssignments {
  if (typeof window === 'undefined') return {}
  try {
    return JSON.parse(window.localStorage.getItem(modelAssignmentStorageKey) || '{}') as ModelTaskAssignments
  } catch {
    return {}
  }
}

function readDailyTarget() {
  if (typeof window === 'undefined') return defaultDailyTarget
  const stored = Number(window.localStorage.getItem(dailyPlanStorageKey) || defaultDailyTarget)
  return Number.isFinite(stored) ? Math.max(defaultDailyTarget, stored) : defaultDailyTarget
}

function writeDailyTarget(value: number) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(dailyPlanStorageKey, String(value))
}

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, '0')
  const seconds = (totalSeconds % 60).toString().padStart(2, '0')
  return `${minutes}:${seconds}`
}

function memoryPoint(question: Question) {
  if (question.question_class === '报告纠错') return '报告表达要区分观察事实、倾向判断和医生复核前边界。'
  if (question.question_class === '一图多问') return '同一图片先拆部位、形态、数量和可见器械，再归纳答案。'
  if (question.question_type === '多选') return '多选题先逐项排除没有图像依据的选项，再提交。'
  return '内镜研修优先描述可观察事实，再说明判断依据和限制。'
}

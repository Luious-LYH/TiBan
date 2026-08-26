import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowRight,
  BookMarked,
  BookOpenCheck,
  Brain,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  Filter,
  Image as ImageIcon,
  Layers3,
  Library,
  MessageSquareText,
  RotateCcw,
  Search,
  Send,
  Sparkles,
  Target,
  Upload,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { PracticeQuestionsPayload, PracticeState, PracticeSubmitResponse, QuestionBankImportTemplates, QuestionBankImportValidation } from '../lib/types'

type BankMode = 'all' | 'wrong' | 'favorite' | 'review'
type TutorMessage = { role: 'assistant' | 'user'; text: string }

const bodyPartOrder = ['全部', '食管', '胃', '小肠', '结直肠', '通用']
const typeOrder = ['全部', '单选', '多选', '判断', '问答评分', '报告修改']

export function StudyCenter() {
  const [state, setState] = useState<PracticeState | null>(null)
  const [payload, setPayload] = useState<PracticeQuestionsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<BankMode>('all')
  const [bodyPart, setBodyPart] = useState('全部')
  const [questionType, setQuestionType] = useState('全部')
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const [choice, setChoice] = useState('')
  const [multiChoice, setMultiChoice] = useState<Set<string>>(new Set())
  const [freeText, setFreeText] = useState('')
  const [result, setResult] = useState<PracticeSubmitResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [tutorInput, setTutorInput] = useState('')
  const [tutorBusy, setTutorBusy] = useState(false)
  const [showImport, setShowImport] = useState(false)
  const [importFormat, setImportFormat] = useState<'jsonl' | 'csv' | 'markdown'>('jsonl')
  const [importText, setImportText] = useState('')
  const [importTemplates, setImportTemplates] = useState<QuestionBankImportTemplates | null>(null)
  const [importResult, setImportResult] = useState<QuestionBankImportValidation | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [tutorMessages, setTutorMessages] = useState<TutorMessage[]>([
    { role: 'assistant', text: '我会陪你先判断题型，再拆知识点、选项和观察依据。需要提示时直接问，不会提前透露标准答案。' },
  ])

  const onlyWrong = mode === 'wrong' || mode === 'review'
  const onlyFavorites = mode === 'favorite'

  useEffect(() => {
    let mounted = true
    setLoading(true)
    Promise.all([
      v3Api.practiceState(),
      v3Api.practiceQuestions({
        bodyPart: bodyPart === '全部' ? undefined : bodyPart,
        questionType: questionType === '全部' ? undefined : questionType,
        onlyWrong,
        onlyFavorites,
        limit: 60,
        shuffleSeed: 22,
      }),
    ])
      .then(([nextState, nextPayload]) => {
        if (!mounted) return
        setState(nextState)
        setPayload(nextPayload)
        setActiveIndex(0)
        resetAnswer()
      })
      .catch(() => {
        if (!mounted) return
        setPayload(null)
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => { mounted = false }
  }, [bodyPart, onlyFavorites, onlyWrong, questionType])

  const questions = useMemo(() => {
    const items = payload?.items || []
    const needle = query.trim().toLowerCase()
    if (!needle) return items
    return items.filter((item) => [
      item.title,
      item.question,
      item.body_part,
      item.question_type,
      item.question_class,
      item.task,
      ...item.teaching_tags,
    ].join(' ').toLowerCase().includes(needle))
  }, [payload, query])

  const activeQuestion = questions[Math.min(activeIndex, Math.max(questions.length - 1, 0))]

  useEffect(() => {
    resetAnswer()
    if (activeQuestion) {
      setTutorMessages([
        { role: 'assistant', text: `${activeQuestion.question_type} · ${activeQuestion.body_part}。你可以让我给一个小提示、解释某个选项，或帮你检查开放回答是否漏掉关键点。` },
      ])
    }
  }, [activeQuestion?.id])

  const answerValue = activeQuestion?.question_type === '多选'
    ? [...multiChoice].join('；')
    : activeQuestion?.question_type === '问答评分'
      ? freeText.trim()
      : choice.trim()

  const profile = state?.profile
  const stats = {
    total: payload?.pool_total ?? payload?.total ?? questions.length,
    text: questions.filter((item) => !item.image_url).length,
    visual: questions.filter((item) => item.image_url).length,
    due: state?.progress.review_queue ?? 0,
  }

  useEffect(() => {
    if (!showImport || importTemplates) return
    let mounted = true
    v3Api.questionBankImportTemplates().then((templates) => {
      if (!mounted) return
      setImportTemplates(templates)
      setImportText(templates.examples?.[importFormat] || '')
    }).catch(() => undefined)
    return () => { mounted = false }
  }, [importFormat, importTemplates, showImport])

  function resetAnswer() {
    setChoice('')
    setMultiChoice(new Set())
    setFreeText('')
    setResult(null)
  }

  function chooseOption(option: string) {
    if (!activeQuestion) return
    if (result) return
    if (activeQuestion.question_type === '多选') {
      setMultiChoice((current) => {
        const next = new Set(current)
        if (next.has(option)) next.delete(option)
        else next.add(option)
        return next
      })
      return
    }
    setChoice(option)
  }

  async function submitAnswer() {
    if (!activeQuestion || !answerValue || submitting) return
    setSubmitting(true)
    try {
      const response = await v3Api.practiceSubmit(activeQuestion, answerValue)
      setResult(response)
      setTutorMessages((items) => [
        ...items,
        {
          role: 'assistant',
          text: response.is_correct
            ? `这题答对了。重点记住：${response.explanation}`
            : `这题需要复盘。${response.explanation}`,
        },
      ])
    } finally {
      setSubmitting(false)
    }
  }

  async function askTutor(message: string) {
    if (!activeQuestion || tutorBusy) return
    const text = message.trim()
    if (!text) return
    setTutorBusy(true)
    setTutorInput('')
    setTutorMessages((items) => [...items, { role: 'user', text }])
    try {
      const reply = await v3Api.practiceTutor({
        questionId: activeQuestion.id,
        mode: 'chat',
        selectedAnswer: answerValue || undefined,
        message: text,
        displayModelName: '智能带教',
      })
      setTutorMessages((items) => [...items, { role: 'assistant', text: readableTutorReply(reply) }])
    } finally {
      setTutorBusy(false)
    }
  }

  async function askHint() {
    if (!activeQuestion || tutorBusy) return
    setTutorBusy(true)
    try {
      const reply = await v3Api.practiceTutor({ questionId: activeQuestion.id, mode: 'hint' })
      setTutorMessages((items) => [...items, { role: 'assistant', text: readableTutorReply(reply) }])
    } finally {
      setTutorBusy(false)
    }
  }

  function fillImportExample(format: 'jsonl' | 'csv' | 'markdown') {
    setImportFormat(format)
    setImportResult(null)
    setImportText(importTemplates?.examples?.[format] || '')
  }

  async function validateImport() {
    if (!importText.trim() || importBusy) return
    setImportBusy(true)
    try {
      const response = await v3Api.validateQuestionBankImport({
        format: importFormat,
        content: importText,
        sourceName: '个人内镜研修题库',
        defaultBodyPart: bodyPart === '全部' ? '通用' : bodyPart,
      })
      setImportResult(response)
    } finally {
      setImportBusy(false)
    }
  }

  function nextQuestion() {
    if (!questions.length) return
    setActiveIndex((index) => Math.min(index + 1, questions.length - 1))
  }

  return (
    <section className="v22-study" data-study-center="true">
      <header className="v22-study-top">
        <div>
          <span>内镜医师刷题 Agent</span>
          <h1>题库研修台</h1>
          <p>单选、多选、判断和开放题统一进入刷题流程；智能带教在作答前给提示，提交后讲错因和复习动作。</p>
        </div>
        <div className="v22-top-actions">
          <Link to="/lab"><Target size={16} />模型评测</Link>
          <Link to="/workbench"><Sparkles size={16} />技术链路</Link>
        </div>
      </header>

      <div className="v22-bank-strip">
        <Metric icon={<Library size={18} />} label="当前题池" value={`${stats.total} 题`} />
        <Metric icon={<FileText size={18} />} label="纯文本题" value={`${stats.text} 题`} />
        <Metric icon={<ImageIcon size={18} />} label="图文题" value={`${stats.visual} 题`} />
        <Metric icon={<Clock3 size={18} />} label="待复习" value={`${stats.due} 题`} />
      </div>

      <div className="v22-study-grid">
        <aside className="v22-bank-panel">
          <div className="v22-panel-head">
            <span><BookMarked size={17} />题库</span>
            <small>{loading ? '载入中' : `${questions.length} 道可练习`}</small>
          </div>

          <label className="v22-search">
            <Search size={16} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜部位、题型、知识点" />
          </label>

          <Segment title="部位" items={bodyPartOrder} value={bodyPart} onChange={setBodyPart} />
          <Segment title="题型" items={typeOrder} value={questionType} onChange={setQuestionType} />

          <div className="v22-mode-tabs" aria-label="练习模式">
            <button className={mode === 'all' ? 'is-active' : ''} onClick={() => setMode('all')}><Layers3 size={15} />全部</button>
            <button className={mode === 'review' ? 'is-active' : ''} onClick={() => setMode('review')}><Clock3 size={15} />复习</button>
            <button className={mode === 'wrong' ? 'is-active' : ''} onClick={() => setMode('wrong')}><RotateCcw size={15} />错题</button>
            <button className={mode === 'favorite' ? 'is-active' : ''} onClick={() => setMode('favorite')}><BookMarked size={15} />收藏</button>
          </div>

          <div className="v22-question-list">
            {loading ? <div className="v22-empty">正在准备题库…</div> : questions.length ? questions.map((item, index) => (
              <button key={item.id} className={index === activeIndex ? 'is-active' : ''} onClick={() => setActiveIndex(index)}>
                <span>{item.image_url ? <ImageIcon size={14} /> : <FileText size={14} />}{item.question_type}</span>
                <strong>{item.title}</strong>
                <small>{item.body_part} · {item.question_class} · {item.difficulty}</small>
              </button>
            )) : <div className="v22-empty"><BookOpenCheck size={22} />当前筛选下暂无题目</div>}
          </div>

          <div className={showImport ? 'v22-import-card is-open' : 'v22-import-card'}>
            <button onClick={() => setShowImport((value) => !value)}>
              <Upload size={18} />
              <span>
                <strong>个人题库入口</strong>
                <p>粘贴 JSONL、CSV 或 Markdown，先校验字段和答案，再进入发布流程。</p>
              </span>
            </button>
            {showImport ? (
              <div className="v22-import-lab">
                <div className="v22-import-tabs">
                  {(['jsonl', 'csv', 'markdown'] as const).map((format) => (
                    <button key={format} className={importFormat === format ? 'is-active' : ''} onClick={() => fillImportExample(format)}>
                      {format.toUpperCase()}
                    </button>
                  ))}
                </div>
                <textarea value={importText} onChange={(event) => { setImportText(event.target.value); setImportResult(null) }} />
                <button className="v22-import-validate" onClick={validateImport} disabled={!importText.trim() || importBusy}>
                  {importBusy ? '校验中…' : '校验题库'} <ArrowRight size={15} />
                </button>
                {importResult ? (
                  <div className={importResult.ready_to_publish ? 'v22-import-result is-ready' : 'v22-import-result'}>
                    <strong>{importResult.accepted_count} 题通过 · {importResult.rejected_count} 个问题</strong>
                    <small>文本题 {importResult.summary.text_question_count} · 图文题 {importResult.summary.visual_question_count} · Hash {importResult.summary.content_hash || '—'}</small>
                    {importResult.issues.length ? (
                      <ul>
                        {importResult.issues.slice(0, 3).map((issue) => <li key={`${issue.row}_${issue.code}`}>第 {issue.row} 行：{issue.message}</li>)}
                      </ul>
                    ) : (
                      <p>{importResult.items.slice(0, 2).map((item) => item.title).join('；')}</p>
                    )}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </aside>

        <main className="v22-practice-panel">
          {activeQuestion ? (
            <>
              <div className="v22-question-head">
                <div>
                  <span>{activeQuestion.body_part} · {activeQuestion.question_type} · {activeQuestion.difficulty}</span>
                  <h2>{activeQuestion.title}</h2>
                  <p>{activeQuestion.case_summary}</p>
                </div>
                <span className={activeQuestion.image_url ? 'v22-modality is-visual' : 'v22-modality'}>
                  {activeQuestion.image_url ? <ImageIcon size={15} /> : <FileText size={15} />}
                  {activeQuestion.image_url ? '图文题' : '纯文本题'}
                </span>
              </div>

              {activeQuestion.image_url ? (
                <figure className="v22-image-stage">
                  <img src={activeQuestion.image_url} alt={`${activeQuestion.body_part}内镜研修图像`} data-real-sample-image="true" data-real-sample-role="primary" />
                  <figcaption>{activeQuestion.image_placeholder}</figcaption>
                </figure>
              ) : null}

              <section className="v22-question-card">
                <p className="v22-stem">{activeQuestion.question}</p>
                {activeQuestion.question_type === '问答评分' ? (
                  <textarea
                    value={freeText}
                    onChange={(event) => setFreeText(event.target.value)}
                    disabled={Boolean(result)}
                    placeholder="写下你的观察要素或知识点答案，提交后会按要点覆盖和表达边界评分。"
                  />
                ) : (
                  <div className="v22-options">
                    {activeQuestion.options.map((option, index) => {
                      const selected = activeQuestion.question_type === '多选' ? multiChoice.has(option) : choice === option
                      return (
                        <button key={option} className={selected ? 'is-selected' : ''} onClick={() => chooseOption(option)} disabled={Boolean(result)}>
                          <b>{String.fromCharCode(65 + index)}</b>
                          <span>{option}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </section>

              {result ? (
                <section className={result.is_correct ? 'v22-result is-correct' : 'v22-result'}>
                  <div>
                    <span>{result.is_correct ? <CheckCircle2 size={18} /> : <RotateCcw size={18} />}{result.is_correct ? '回答正确' : '需要复盘'}</span>
                    <strong>{result.score} 分</strong>
                  </div>
                  <p>{result.explanation}</p>
                  <div className="v22-review-points">
                    {result.fact_feedback.slice(0, 3).map((fact) => (
                      <span key={fact.id}>{fact.fact}：{fact.expected}</span>
                    ))}
                  </div>
                </section>
              ) : null}

              <div className="v22-actions">
                <button className="v22-ghost" onClick={askHint} disabled={tutorBusy || Boolean(result)}>
                  <Brain size={16} />要一个提示
                </button>
                <button className="v22-primary" onClick={submitAnswer} disabled={!answerValue || submitting || Boolean(result)}>
                  {submitting ? '提交中…' : '提交答案'} <ArrowRight size={16} />
                </button>
                <button className="v22-ghost" onClick={nextQuestion} disabled={!questions.length || activeIndex >= questions.length - 1}>
                  下一题 <ChevronRight size={16} />
                </button>
              </div>
            </>
          ) : (
            <div className="v22-practice-empty"><BookOpenCheck size={28} />请选择一道题开始研修</div>
          )}
        </main>

        <aside className="v22-tutor-panel">
          <div className="v22-panel-head">
            <span><MessageSquareText size={17} />智能带教</span>
            <small>{profile ? `${profile.completed_today}/${profile.daily_target} 今日` : '研修中'}</small>
          </div>
          <div className="v22-tutor-intents">
            <button onClick={() => askTutor('帮我拆一下这道题考什么知识点')} disabled={!activeQuestion || tutorBusy}>拆知识点</button>
            <button onClick={() => askTutor('我想排除一个干扰选项')} disabled={!activeQuestion || tutorBusy}>排除干扰项</button>
            <button onClick={() => askTutor('根据我当前答案给一个不泄露答案的提示')} disabled={!activeQuestion || tutorBusy}>给提示</button>
          </div>
          <div className="v22-chat-log">
            {tutorMessages.map((message, index) => (
              <div key={`${message.role}_${index}`} className={message.role === 'user' ? 'is-user' : ''}>{message.text}</div>
            ))}
            {tutorBusy ? <div>正在组织讲解…</div> : null}
          </div>
          <form className="v22-chat-box" onSubmit={(event) => { event.preventDefault(); void askTutor(tutorInput) }}>
            <input value={tutorInput} onChange={(event) => setTutorInput(event.target.value)} placeholder="问带教：我卡在哪个选项？" />
            <button disabled={!tutorInput.trim() || tutorBusy || !activeQuestion} aria-label="发送给智能带教"><Send size={16} /></button>
          </form>
          <div className="v22-mentor-card">
            <strong>带教计划</strong>
            <p>{state?.next_plan?.[0]?.reason || '完成几道题后，会根据错题和掌握度推荐下一组练习。'}</p>
            <span>{profile?.weakness_tags?.slice(0, 3).join(' · ') || '观察依据 · 部位定位 · 表达边界'}</span>
          </div>
        </aside>
      </div>

      <footer className="v22-study-safety">{payload?.safety_notice || state?.safety_notice || v3SafetyNotice}</footer>
    </section>
  )
}

function Segment({ title, items, value, onChange }: { title: string; items: string[]; value: string; onChange: (value: string) => void }) {
  return (
    <div className="v22-segment">
      <span><Filter size={14} />{title}</span>
      <div>
        {items.map((item) => (
          <button key={item} className={value === item ? 'is-active' : ''} onClick={() => onChange(item)}>{item}</button>
        ))}
      </div>
    </div>
  )
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="v22-bank-metric">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function readableTutorReply(payload: Record<string, unknown>) {
  const reply = typeof payload.reply === 'string' ? payload.reply : ''
  const hint = typeof payload.hint === 'string' ? payload.hint : ''
  const explanation = typeof payload.explanation === 'string' ? payload.explanation : ''
  return reply || hint || explanation || '我建议先回到题干，找出部位、关键表现和不能越界推断的内容。'
}

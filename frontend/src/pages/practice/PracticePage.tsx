import { ArrowLeft, Bookmark, Check, CheckCircle2, ChevronDown, Flag, ImageIcon, List, MessageCircle, NotebookPen, Target, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createPracticeSession, getQuestionBanks, getQuestions, submitFsrsReview, submitPracticeAnswer, type AnswerValue, type Question, type ReviewCard, type SessionResponse, type SubmitResult } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { TutorSidecar } from '../../components/tutor/TutorSidecar'

type Mode = 'study' | 'exam' | 'review'
type StatusFilter = 'all' | 'unused' | 'incorrect' | 'marked'

const typeLabels: Record<string, string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断', short_answer: '简答' }
const modeLabels: Record<Mode, string> = { study: '学习辅导', exam: '考试模式', review: '复习模式' }
const statusLabels: Record<StatusFilter, string> = { all: '全部', unused: '未作答', incorrect: '错题', marked: '已标记' }
const difficultyLabels: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

export function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const mode = normalizeMode(searchParams.get('mode'))
  const bankId = searchParams.get('bank_id') ?? undefined
  const [activeIndex, setActiveIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, AnswerValue | null>>({})
  const [results, setResults] = useState<Record<string, SubmitResult>>({})
  const [marked, setMarked] = useState<Record<string, boolean>>({})
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [questionCount, setQuestionCount] = useState(20)
  const [navigatorOpen, setNavigatorOpen] = useState(true)
  const [tutorOpen, setTutorOpen] = useState(false)
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [sessionBuilding, setSessionBuilding] = useState(false)
  const sessionRequest = useRef<{ key: string; promise: Promise<SessionResponse> } | null>(null)
  const queryClient = useQueryClient()

  const banksQuery = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const selectedBankId = bankId ?? banksQuery.data?.[0]?.bank_id
  const activeSession = session && session.bank_id === selectedBankId && session.mode === mode ? session : null
  const questionsQuery = useQuery({
    queryKey: ['practice-questions', selectedBankId, activeSession?.session_id ?? 'catalog-fallback'],
    queryFn: () => getQuestions({ bankId: selectedBankId, sessionId: activeSession?.session_id }),
    enabled: Boolean(selectedBankId) && Boolean(activeSession || sessionError),
  })

  useEffect(() => {
    if (!selectedBankId) return
    const key = `${selectedBankId}:${mode}:${questionCount}`
    let current = true
    const activeRequest = sessionRequest.current?.key === key
      ? sessionRequest.current.promise
      : createPracticeSession(selectedBankId, 'demo_learner', mode, questionCount)
    sessionRequest.current = { key, promise: activeRequest }
    activeRequest
      .then((nextSession) => { if (current) setSession(nextSession) })
      .catch((error: unknown) => {
        if (!current) return
        if (sessionRequest.current?.key === key) sessionRequest.current = null
        setSessionError(error instanceof Error ? error.message : '无法创建服务端练习 session。')
      })
      .finally(() => { if (current) setSessionBuilding(false) })
    return () => { current = false }
  }, [mode, questionCount, selectedBankId])

  const pool = useMemo(() => {
    const items = questionsQuery.data?.items ?? []
    return activeSession ? items : items.slice(0, questionCount)
  }, [activeSession, questionCount, questionsQuery.data?.items])
  const visibleQuestions = useMemo(() => pool.filter((question) => {
    if (statusFilter === 'unused') return !results[question.id]
    if (statusFilter === 'incorrect') return results[question.id] && !results[question.id].is_correct
    if (statusFilter === 'marked') return marked[question.id]
    return true
  }), [marked, pool, results, statusFilter])
  const currentIndex = Math.min(activeIndex, Math.max(visibleQuestions.length - 1, 0))
  const question = visibleQuestions[currentIndex]
  const answer = question ? answers[question.id] ?? null : null
  const result = question ? results[question.id] : undefined
  const selectedBank = banksQuery.data?.find((bank) => bank.bank_id === selectedBankId)

  const submitMutation = useMutation({
    mutationFn: (payload: { question: Question; answer: AnswerValue }) => submitPracticeAnswer({ question_id: payload.question.id, selected_answer: payload.answer, session_id: activeSession?.session_id, mode, learner_id: 'demo_learner' }),
    onSuccess: (data, variables) => {
      setResults((current) => ({ ...current, [variables.question.id]: data }))
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      void queryClient.invalidateQueries({ queryKey: ['question-banks'] })
    },
  })
  const reviewMutation = useMutation({
    mutationFn: (payload: { questionId: string; rating: 'Again' | 'Hard' | 'Good' | 'Easy' }) => submitFsrsReview(payload.questionId, payload.rating),
  })

  if (banksQuery.isPending || !selectedBankId || (sessionBuilding && !activeSession) || (!activeSession && !sessionError) || questionsQuery.isPending) return <LoadingState label="正在根据学习记录准备练习工作台…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />
  if (questionsQuery.isError) return <ErrorState message={questionsQuery.error.message} onRetry={() => void questionsQuery.refetch()} />

  function changeBank(nextBankId: string) {
    setSearchParams({ bank_id: nextBankId, ...(mode !== 'study' ? { mode } : {}) })
    setActiveIndex(0); setAnswers({}); setResults({}); setMarked({}); setNotes({}); setSession(null); setSessionError(null)
  }

  function changeMode(nextMode: Mode) {
    setSearchParams({ ...(selectedBankId ? { bank_id: selectedBankId } : {}), ...(nextMode !== 'study' ? { mode: nextMode } : {}) })
    setActiveIndex(0); setAnswers({}); setResults({}); setStatusFilter('all'); setSession(null); setSessionError(null)
  }

  function setAnswer(value: AnswerValue) {
    if (!question || result) return
    setAnswers((current) => ({ ...current, [question.id]: value }))
  }

  function chooseOption(optionId: string) {
    if (!question || result) return
    if (question.question_type === 'multiple_choice') {
      const previous = Array.isArray(answer) ? answer : []
      setAnswer(previous.includes(optionId) ? previous.filter((item) => item !== optionId) : [...previous, optionId])
    } else setAnswer(optionId)
  }

  function submit() {
    if (!question || !isAnswered(answer) || result) return
    submitMutation.mutate({ question, answer })
  }

  const completeCount = visibleQuestions.filter((item) => results[item.id]).length
  const correctCount = visibleQuestions.filter((item) => results[item.id]?.is_correct).length
  const isComplete = visibleQuestions.length > 0 && completeCount === visibleQuestions.length

  return <div className="s1-page s1-practice-page" data-testid="practice-page">
    <section className="s1-practice-top">
      <div><Link className="s1-back-link" to="/banks"><ArrowLeft size={15} />返回题库</Link><span className="s1-kicker">LEARNING WORKSPACE</span><h1>{selectedBank?.name ?? '练习工作台'}</h1><p>先作答，再理解；Tutor 会在右侧陪你完成这次练习。</p></div>
      <div className="s1-practice-top-controls"><label className="s1-select s1-bank-select"><span>题库</span><select aria-label="选择题库" value={selectedBankId ?? ''} onChange={(event) => changeBank(event.target.value)}>{banksQuery.data.map((bank) => <option key={bank.bank_id} value={bank.bank_id}>{bank.name}</option>)}</select></label><label className="s1-select"><span>模式</span><select aria-label="选择练习模式" value={mode} onChange={(event) => changeMode(event.target.value as Mode)}>{Object.entries(modeLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label className="s1-select"><span>题量</span><select aria-label="选择题量" value={questionCount} onChange={(event) => { const value = event.target.value; setQuestionCount(value === 'all' ? 100 : Number(value)); setActiveIndex(0); setAnswers({}); setResults({}); setMarked({}); setNotes({}); setSession(null); setSessionError(null) }}><option value="10">10</option><option value="20">20</option><option value="40">40</option><option value="all">全部</option></select></label></div>
    </section>
    <div className="s1-practice-statusbar" aria-label="题目状态筛选"><span>题目状态</span>{(Object.keys(statusLabels) as StatusFilter[]).map((status) => { const count = status === 'all' ? pool.length : status === 'unused' ? pool.filter((item) => !results[item.id]).length : status === 'incorrect' ? pool.filter((item) => results[item.id] && !results[item.id].is_correct).length : pool.filter((item) => marked[item.id]).length; return <button key={status} type="button" className={statusFilter === status ? 'is-active' : ''} onClick={() => { setStatusFilter(status); setActiveIndex(0) }}>{statusLabels[status]} <b>{count}</b></button> })}</div>
    {activeSession && <section className="s1-session-recommendation" data-testid="session-recommendation" data-selection-strategy={activeSession.selection_strategy}><div className="s1-session-recommendation-main"><Target size={18} /><div><span className="s1-kicker">LEARNING PLAN</span><h2>本次选题依据</h2><p>{activeSession.selection_reason}</p></div></div>{(activeSession.selection_evidence ?? []).length > 0 && <ul>{(activeSession.selection_evidence ?? []).map((item) => <li key={item}>{item}</li>)}</ul>}</section>}
    {sessionError && <div className="s1-session-fallback" role="status">服务端 session 暂不可用，当前仅按题库目录展示：{sessionError}</div>}
    {pool.length === 0 ? <section className="s1-card"><EmptyState title="当前题库还没有可用题目" detail="返回题库目录选择其他题库。" /></section> : <>
      <button className="s1-mobile-tutor-trigger" onClick={() => setTutorOpen(true)}><MessageCircle size={16} />打开 Tutor <span>边刷边聊</span></button>
      <div className="s1-practice-layout s1-practice-layout-wide">
        <section className={`s1-card s1-question-card ${question?.image_url ? 'has-image' : 'text-only'}`} data-testid="question-card" data-question-layout={question?.image_url ? 'image' : 'text-only'}>
          <div className="s1-practice-toolbar"><div className="s1-practice-progress"><strong>{currentIndex + 1} / {visibleQuestions.length}</strong><span>{completeCount} 已完成</span></div><span className="s1-type-pill">{typeLabels[question?.question_type ?? 'short_answer']}</span><span>{difficultyLabels[question?.difficulty ?? ''] ?? question?.difficulty}</span><button type="button" className={question && marked[question.id] ? 's1-toolbar-button is-active' : 's1-toolbar-button'} onClick={() => question && setMarked((current) => ({ ...current, [question.id]: !current[question.id] }))}><Bookmark size={15} />标记</button><button type="button" className="s1-toolbar-button" onClick={() => setNavigatorOpen((open) => !open)}><List size={15} />题号</button></div>
          {navigatorOpen && <QuestionNavigator questions={visibleQuestions} activeIndex={currentIndex} results={results} marked={marked} onSelect={setActiveIndex} />}
          {question ? <>
            <div className={`s1-question-heading ${question.image_url ? 'has-image' : 'text-only'}`}><div><span className="s1-kicker">{question.title}</span><h2>{question.stem}</h2>{learnerCaseSummary(question.case_summary) && <p>{learnerCaseSummary(question.case_summary)}</p>}</div>{question.image_url && <figure className="s1-question-image"><img src={question.image_url} alt={question.image_alt ?? '内镜教学图像'} /><figcaption><ImageIcon size={13} />{question.image_alt ?? '图像题'}</figcaption></figure>}</div>
            <div className="s1-question-labels"><span>{question.subject ?? question.body_part}</span><span>{question.topic ?? '综合练习'}</span><span>{question.business_usage === 'user_ready' ? '可直接练习' : '需复核来源'}</span></div>
            <AnswerControl question={question} answer={answer} disabled={Boolean(result)} onChoose={chooseOption} onText={setAnswer} />
            {submitMutation.isError && <div className="s1-inline-error" role="alert">提交失败：{submitMutation.error.message}</div>}
            {result && <ResultPanel question={question} result={result} mode={mode} reviewCard={reviewMutation.data?.question_id === question.id ? reviewMutation.data : undefined} reviewPending={reviewMutation.isPending} reviewError={reviewMutation.isError ? reviewMutation.error.message : undefined} onReview={(rating) => reviewMutation.mutate({ questionId: question.id, rating })} />}
            <div className="s1-practice-note"><NotebookPen size={15} /><label><span>本题笔记</span><textarea aria-label="本题笔记" value={notes[question.id] ?? ''} onChange={(event) => setNotes((current) => ({ ...current, [question.id]: event.target.value }))} placeholder="记录一个需要回看的观察点…" rows={1} /></label></div>
            <div className="s1-question-actions"><button className="s1-button s1-button-primary" data-testid="submit-answer" onClick={submit} disabled={!isAnswered(answer) || submitMutation.isPending || Boolean(result)}>{submitMutation.isPending ? '正在记录…' : <><Check size={16} />提交答案</>}</button><button className="s1-button s1-button-light" data-testid="next-question" onClick={() => { setActiveIndex((index) => Math.min(index + 1, visibleQuestions.length - 1)) }} disabled={!result || currentIndex >= visibleQuestions.length - 1}>下一题 <ChevronDown size={16} className="rotate-270" /></button></div>
          </> : <EmptyState title="筛选后没有题目" detail="切换题目状态筛选，或回到全部。" />}
        </section>
        {question && <TutorSidecar questionId={question.id} attemptId={result?.attempt_id} mode={mode} open={tutorOpen} onClose={() => setTutorOpen(false)} />}
      </div>
      <section className="s1-card s1-session-summary"><div><span className="s1-kicker">SESSION</span><h2>{mode === 'exam' ? '考试进度' : '本次练习'}</h2><p>{selectedBank?.name} · {modeLabels[mode]}</p></div><div className="s1-summary-metrics"><strong>{completeCount}<small> / {visibleQuestions.length} 题</small></strong><span><b>{correctCount}</b> 正确</span>{isComplete && <span><b>{Math.round((correctCount / visibleQuestions.length) * 100)}%</b> 完成度</span>}</div>{isComplete && <div className="s1-summary-actions"><button type="button" onClick={() => setStatusFilter('incorrect')} disabled={correctCount === visibleQuestions.length}>复习错题</button><button type="button" onClick={() => setStatusFilter('marked')} disabled={!visibleQuestions.some((item) => marked[item.id])}>查看标记</button></div>}</section>
    </>}
    <p className="s1-safety">{question?.safety_notice ?? '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'}</p>
  </div>
}

function normalizeMode(value: string | null): Mode { return value === 'exam' || value === 'review' ? value : 'study' }
function isAnswered(value: AnswerValue | null): value is AnswerValue { return value !== null && (!(Array.isArray(value)) || value.length > 0) && (typeof value !== 'string' || value.trim().length > 0) }
function learnerCaseSummary(value: string): string | null {
  const summary = value.trim()
  if (!summary || (summary.startsWith('来自 ') && summary.includes('真实题目') && summary.includes('上游来源与授权边界'))) return null
  return summary
}

function QuestionNavigator({ questions, activeIndex, results, marked, onSelect }: { questions: Question[]; activeIndex: number; results: Record<string, SubmitResult>; marked: Record<string, boolean>; onSelect: (index: number) => void }) {
  return <div className="s1-question-navigator" aria-label="题目导航">{questions.map((item, index) => { const result = results[item.id]; const state = result ? (result.is_correct ? 'correct' : 'incorrect') : marked[item.id] ? 'marked' : 'unanswered'; return <button key={item.id} type="button" className={`is-${state} ${index === activeIndex ? 'is-current' : ''}`} onClick={() => onSelect(index)} aria-label={`第 ${index + 1} 题，${state}`}>{index + 1}</button> })}</div>
}

function AnswerControl({ question, answer, disabled, onChoose, onText }: { question: Question; answer: AnswerValue | null; disabled: boolean; onChoose: (value: string) => void; onText: (value: AnswerValue) => void }) {
  if (question.question_type === 'short_answer') return <label className="s1-answer-text"><span>你的回答</span><textarea aria-label="你的回答" value={typeof answer === 'string' ? answer : ''} onChange={(event) => onText(event.target.value)} disabled={disabled} placeholder="用观察性语言描述你的依据…" rows={5} /></label>
  if (question.question_type === 'true_false') return <div className="s1-answer-options s1-boolean-options">{[['true', '正确'], ['false', '错误']].map(([value, label]) => { const boolValue = value === 'true'; return <button key={value} type="button" className={answer === boolValue ? 'is-selected' : ''} onClick={() => onText(boolValue)} disabled={disabled}><span className="s1-option-letter">{answer === boolValue ? <Check size={16} /> : value === 'true' ? 'T' : 'F'}</span><span>{label}</span></button> })}</div>
  return <div className="s1-answer-options">{question.options.map((option, index) => { const selected = Array.isArray(answer) ? answer.includes(option.id) : answer === option.id; return <button key={option.id} type="button" className={selected ? 'is-selected' : ''} onClick={() => onChoose(option.id)} disabled={disabled}><span className="s1-option-letter">{selected ? <Check size={16} /> : String.fromCharCode(65 + index)}</span><span>{option.text}</span></button> })}</div>
}

function ResultPanel({ question, result, mode, reviewCard, reviewPending, reviewError, onReview }: { question: Question; result: SubmitResult; mode: Mode; reviewCard?: ReviewCard; reviewPending: boolean; reviewError?: string; onReview: (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void }) {
  const exam = mode === 'exam'
  return <div className={result.is_correct ? 's1-result is-correct' : 's1-result is-incorrect'} data-testid="feedback"><div className="s1-result-status">{result.is_correct ? <CheckCircle2 size={18} /> : <XCircle size={18} />}<strong>{result.is_correct ? '回答正确' : '回答错误'}</strong></div>{exam ? <p>{result.explanation}</p> : <><div className="s1-result-answer"><span>你的答案</span><strong>{result.selected_answer_display}</strong></div><div className="s1-result-answer"><span>正确答案</span><strong>{result.correct_answer_display}</strong></div><div className="s1-result-explanation"><div><strong>解析</strong><span>{result.official_explanation_available ? '官方解析' : result.explanation_source === 'none' ? '解析提示' : 'AI 补充解释'}</span></div><p>{result.explanation}</p></div>{question.question_type === 'short_answer' && <small className="s1-score-note">本题按回答中的关键事实评分：{result.score} 分</small>}{mode === 'review' ? <div className="s1-review-controls"><strong>这次复习感觉如何？</strong><div>{(['Again', 'Hard', 'Good', 'Easy'] as const).map((rating) => <button key={rating} type="button" disabled={reviewPending} onClick={() => onReview(rating)}>{rating}</button>)}</div>{reviewCard && <small>下次复习：{new Date(reviewCard.due_at).toLocaleString()} · 间隔 {reviewCard.interval_days} 天</small>}{reviewError && <small role="alert">复习记录失败：{reviewError}</small>}</div> : <button type="button" className="s1-review-quick-action"><Flag size={14} />加入复习</button>}</>}</div>
}

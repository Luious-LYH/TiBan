import { ArrowLeft, Bookmark, Check, CheckCircle2, ChevronRight, Clock3, ImageIcon, ListChecks, Play, RotateCcw, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getBankQuestionProgress, getPracticeSession, getQuestionBanks, getQuestions, getResumablePracticeSession, leavePracticeSession, resumePracticeSession, setQuestionMark, submitFsrsReview, submitPracticeAnswer, type AnswerValue, type PracticeResumable, type Question, type ReviewCard, type SubmitResult, type TutorThread } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { TutorPanel } from '../../components/tutor/TutorPanel'

type Mode = 'study' | 'exam' | 'review'

const typeLabels: Record<string, string> = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '简答题' }
const modeLabels: Record<Mode, string> = { study: '刷题', exam: '考试', review: '错题复习' }

export function PracticePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const mode = normalizeMode(searchParams.get('mode'))
  const sessionId = searchParams.get('session_id') ?? undefined
  const routeTutorThreadId = searchParams.get('tutor_thread_id') ?? undefined
  const [activeIndex, setActiveIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, AnswerValue | null>>({})
  const [results, setResults] = useState<Record<string, SubmitResult>>({})
  const [markOverrides, setMarkOverrides] = useState<Record<string, boolean>>({})
  const [tutorOpen, setTutorOpen] = useState(true)
  const [questionMapOpen, setQuestionMapOpen] = useState(false)
  const [resumedThread, setResumedThread] = useState<TutorThread | null>(null)
  const [saveStatus, setSaveStatus] = useState<'saving' | 'saved' | null>(null)
  const restoredPosition = useRef<string | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (saveStatus !== 'saved') return
    const timer = window.setTimeout(() => setSaveStatus(null), 1600)
    return () => window.clearTimeout(timer)
  }, [saveStatus])

  const banksQuery = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const restoredSessionQuery = useQuery({ queryKey: ['practice-session', sessionId], queryFn: () => getPracticeSession(sessionId ?? ''), enabled: Boolean(sessionId), retry: false })
  const resumableQuery = useQuery({ queryKey: ['practice-session-resumable'], queryFn: () => getResumablePracticeSession(), enabled: !sessionId, retry: false })
  const restoredSession = restoredSessionQuery.data ?? null
  const activeSession = restoredSession
  const selectedBankId = restoredSession?.bank_id
  const tutorThreadId = routeTutorThreadId ?? resumedThread?.tutor_thread_id
  const resumeMutation = useMutation({ mutationFn: (targetSessionId: string) => resumePracticeSession(targetSessionId) })
  const questionsQuery = useQuery({
    queryKey: ['practice-questions', selectedBankId, activeSession?.session_id],
    queryFn: () => getQuestions({ bankId: selectedBankId, sessionId: activeSession?.session_id }),
    enabled: Boolean(selectedBankId && activeSession?.session_id),
  })
  const marksQuery = useQuery({ queryKey: ['bank-question-progress', selectedBankId, 'marked'], queryFn: () => getBankQuestionProgress(selectedBankId ?? '', 'marked'), enabled: Boolean(selectedBankId) })

  useEffect(() => {
    // A direct session URL without an issued thread is a genuine resume.
    // Resume preserves position while deliberately creating a fresh Tutor
    // context; a new builder session already supplies its thread in the URL.
    if (!sessionId || routeTutorThreadId || resumedThread || !restoredSession || resumeMutation.isPending) return
    resumeMutation.mutate(sessionId, { onSuccess: setResumedThread })
  }, [resumeMutation, resumedThread, restoredSession, routeTutorThreadId, sessionId])

  useEffect(() => {
    if (!activeSession?.session_id) return
    const checkpoint = () => { void leavePracticeSession(activeSession.session_id).catch(() => undefined) }
    const onVisibility = () => { if (document.visibilityState === 'hidden') checkpoint() }
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', checkpoint)
    return () => {
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', checkpoint)
    }
  }, [activeSession?.session_id])

  const questions = useMemo(() => {
    const items = questionsQuery.data?.items ?? []
    return items
  }, [questionsQuery.data?.items])
  const currentIndex = Math.min(activeIndex, Math.max(questions.length - 1, 0))
  const question = questions[currentIndex]
  const answer = question ? answers[question.id] ?? null : null
  const result = question ? results[question.id] : undefined
  const learnerId = activeSession?.learner_id ?? 'demo_learner'
  const selectedBank = banksQuery.data?.find((bank) => bank.bank_id === selectedBankId)

  useEffect(() => {
    if (!restoredSession || questions.length === 0 || restoredPosition.current === restoredSession.session_id) return
    const states = new Map((restoredSession.items ?? []).map((item) => [item.question_id, item.state]))
    const savedPosition = Math.min(Math.max(restoredSession.current_position, 0), questions.length - 1)
    const firstUnanswered = questions.findIndex((item, index) => index >= savedPosition && (states.get(item.id) ?? 'unanswered') === 'unanswered')
    setActiveIndex(firstUnanswered >= 0 ? firstUnanswered : savedPosition)
    restoredPosition.current = restoredSession.session_id
  }, [questions, restoredSession])

  const marked = useMemo(() => ({
    ...Object.fromEntries((marksQuery.data?.items ?? []).map((item) => [item.question_id, true])),
    ...markOverrides,
  }), [markOverrides, marksQuery.data?.items])

  const submitMutation = useMutation({
    mutationFn: (payload: { question: Question; answer: AnswerValue }) => submitPracticeAnswer({ question_id: payload.question.id, selected_answer: payload.answer, session_id: activeSession?.session_id, mode, learner_id: learnerId }),
    onMutate: () => setSaveStatus('saving'),
    onSuccess: (data, variables) => {
      setResults((current) => ({ ...current, [variables.question.id]: data }))
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      void queryClient.invalidateQueries({ queryKey: ['question-banks'] })
      void queryClient.invalidateQueries({ queryKey: ['review-summary'] })
      void queryClient.invalidateQueries({ queryKey: ['review-items'] })
      void queryClient.invalidateQueries({ queryKey: ['review-item'] })
      if (activeSession?.session_id) void queryClient.invalidateQueries({ queryKey: ['practice-session', activeSession.session_id] })
      setSaveStatus('saved')
    },
    onError: () => setSaveStatus(null),
  })
  const reviewMutation = useMutation({
    mutationFn: (payload: { questionId: string; rating: 'Again' | 'Hard' | 'Good' | 'Easy' }) => submitFsrsReview(payload.questionId, payload.rating),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['review-summary'] })
      void queryClient.invalidateQueries({ queryKey: ['review-items'] })
      void queryClient.invalidateQueries({ queryKey: ['review-item'] })
    },
  })
  const markMutation = useMutation({
    mutationFn: ({ questionId, marked }: { questionId: string; marked: boolean }) => setQuestionMark(questionId, marked),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['question-banks'] }); void queryClient.invalidateQueries({ queryKey: ['bank-question-progress'] }); void queryClient.invalidateQueries({ queryKey: ['review-summary'] }); void queryClient.invalidateQueries({ queryKey: ['review-items'] }); void queryClient.invalidateQueries({ queryKey: ['review-item'] }) },
  })

  if (!sessionId) {
    if (resumableQuery.isPending) return <LoadingState label="正在检查未完成练习…" />
    if (resumableQuery.isError) return <ErrorState message={resumableQuery.error.message} onRetry={() => void resumableQuery.refetch()} />
    return <PracticeEntryGate resumable={resumableQuery.data} onContinue={async (item) => {
      const thread = await resumePracticeSession(item.session_id)
      const params = new URLSearchParams({ session_id: item.session_id, tutor_thread_id: thread.tutor_thread_id, mode: item.mode === 'exam' ? 'exam' : item.mode === 'review' ? 'review' : 'study' })
      navigate(`/practice?${params.toString()}`, { replace: true })
    }} onChooseBank={async () => {
      if (resumableQuery.data) await leavePracticeSession(resumableQuery.data.session_id, 'demo_learner', true)
      navigate('/banks')
    }} />
  }
  if (banksQuery.isPending || restoredSessionQuery.isPending || !selectedBankId || !activeSession || questionsQuery.isPending || (!routeTutorThreadId && resumeMutation.isPending)) return <LoadingState label="正在恢复本次练习…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />
  if (restoredSessionQuery.isError) return <ErrorState message="无法恢复本次练习 session。" onRetry={() => void restoredSessionQuery.refetch()} />
  if (resumeMutation.isError) return <ErrorState message={resumeMutation.error.message} onRetry={() => { setResumedThread(null); resumeMutation.reset() }} />
  if (questionsQuery.isError) return <ErrorState message={questionsQuery.error.message} onRetry={() => void questionsQuery.refetch()} />

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

  const restoredStates = new Map((restoredSession?.items ?? []).map((item) => [item.question_id, item.state]))
  const completeCount = questions.filter((item) => results[item.id] || (restoredStates.get(item.id) ?? 'unanswered') !== 'unanswered').length
  const progress = questions.length ? Math.round((completeCount / questions.length) * 100) : 0

  return <div className="practice-workspace" data-testid="practice-page">
    <main className="practice-main">
      {questions.length === 0 ? <div className="practice-empty"><EmptyState title="当前题库还没有可用题目" detail="返回题库目录选择其他题库。" /></div> : question && <div className="practice-content">
        <Link className="practice-back" to="/banks"><ArrowLeft size={16} />返回题库</Link>
        <header className="practice-progress-bar">
          <div className="s1-practice-progress practice-progress-copy"><span>{displayBankName(selectedBank?.name) ?? '当前题库'}</span><strong>第 {currentIndex + 1} / {questions.length} 题</strong><small>{modeLabels[mode]}</small></div>
          <div className="practice-progress-track" aria-label={`已完成 ${completeCount} / ${questions.length}，${progress}%`}><i style={{ width: `${progress}%` }} /></div>
          <span className="practice-progress-percent">已完成 {progress}%</span>
          <div className="question-map-wrap"><button type="button" className="question-map-trigger" aria-expanded={questionMapOpen} aria-controls="question-map" onClick={() => setQuestionMapOpen((value) => !value)}><ListChecks size={15} />题单</button>{questionMapOpen && <QuestionMap questions={questions} currentIndex={currentIndex} results={results} marked={marked} sessionItems={restoredSession?.items} onJump={(index) => { setActiveIndex(index); setQuestionMapOpen(false) }} />}</div>
          <button type="button" className={marked[question.id] ? 'practice-mark is-marked' : 'practice-mark'} onClick={() => { const next = !marked[question.id]; setMarkOverrides((current) => ({ ...current, [question.id]: next })); markMutation.mutate({ questionId: question.id, marked: next }) }}><Bookmark size={15} fill={marked[question.id] ? 'currentColor' : 'none'} />{marked[question.id] ? '已标记' : '标记'}</button>
        </header>

        <section className={`practice-question ${question.image_url ? 'has-image' : 'is-text-only'}`} data-testid="question-card" data-question-layout={question.image_url ? 'image' : 'text-only'}>
          <div className="practice-question-kicker"><span>{typeLabels[question.question_type]}</span></div>
          <div className={question.image_url ? 'practice-question-heading has-image' : 'practice-question-heading'}><div><h1>{question.stem}</h1>{learnerCaseSummary(question.case_summary) && <p>{learnerCaseSummary(question.case_summary)}</p>}</div>{question.image_url && <figure className="practice-question-image"><img src={question.image_url} alt={question.image_alt ?? '内镜教学图像'} /><figcaption><ImageIcon size={13} />{question.image_alt ?? '图像题'}</figcaption></figure>}</div>
          <AnswerControl question={question} answer={answer} disabled={Boolean(result)} result={result} onChoose={chooseOption} onText={setAnswer} />
          {submitMutation.isError && <div className="practice-inline-error" role="alert">提交失败：{submitMutation.error.message}</div>}
          {result && <ResultPanel question={question} result={result} mode={mode} reviewCard={reviewMutation.data?.question_id === question.id ? reviewMutation.data : undefined} reviewPending={reviewMutation.isPending} reviewError={reviewMutation.isError ? reviewMutation.error.message : undefined} onReview={(rating) => reviewMutation.mutate({ questionId: question.id, rating })} />}
          <div className="practice-actions"><span className="practice-save-status" aria-live="polite">{saveStatus === 'saving' ? '正在保存学习进度…' : saveStatus === 'saved' ? (restoredSession?.reflection_status === 'completed' ? '学习记忆已更新' : '学习进度已保存') : ''}</span><button className="practice-submit" data-testid="submit-answer" onClick={submit} disabled={!isAnswered(answer) || submitMutation.isPending || Boolean(result)}>{submitMutation.isPending ? '正在记录…' : <><Check size={16} />提交答案</>}</button><button className="practice-next" data-testid="next-question" onClick={() => setActiveIndex((index) => Math.min(index + 1, questions.length - 1))} disabled={!result || currentIndex >= questions.length - 1}>下一题 <ChevronRight size={16} /></button></div>
        </section>
      </div>}
    </main>
    {question && tutorThreadId && <TutorPanel questionId={question.id} practiceSessionId={activeSession.session_id} tutorThreadId={tutorThreadId} attemptId={result?.attempt_id} learnerId={learnerId} mode={mode} open={tutorOpen} onClose={() => setTutorOpen(false)} contextLabel={learnerTopic(question.topic) ?? question.subject ?? displayBankName(selectedBank?.name) ?? '当前题目'} />}
  </div>
}

function PracticeEntryGate({ resumable, onContinue, onChooseBank }: { resumable: PracticeResumable | null; onContinue: (item: PracticeResumable) => Promise<void>; onChooseBank: () => Promise<void> }) {
  const [continuing, setContinuing] = useState(false)
  const [choosing, setChoosing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!resumable) return <div className="practice-entry-shell"><section className="practice-entry-card practice-entry-empty"><span className="practice-entry-icon"><Play size={20} /></span><div><span className="practice-entry-eyebrow">开始练习</span><h1>从题库开始一组练习</h1><p>选择题库、范围和题量后，进入专注刷题。</p></div><div className="practice-entry-actions"><button type="button" className="practice-submit" disabled={choosing} onClick={() => { setChoosing(true); void onChooseBank().catch((reason: unknown) => { setError(reason instanceof Error ? reason.message : '无法打开题库。'); setChoosing(false) }) }}>{choosing ? '正在打开…' : '选择题库'}<ChevronRight size={16} /></button></div>{error && <p className="practice-entry-error" role="alert">{error}</p>}</section></div>
  const label = resumable.mode === 'exam' ? '考试' : resumable.mode === 'review' ? '错题复习' : '刷题'
  return <div className="practice-entry-shell"><section className="practice-entry-card practice-resume-gate" role="dialog" aria-label="继续上次练习"><div className="practice-entry-icon"><RotateCcw size={20} /></div><div className="practice-entry-copy"><span className="practice-entry-eyebrow">未完成练习</span><h1>继续上次{label}？</h1><p>从第 {resumable.current_position + 1} 题继续；智能辅导会开启一段新的本次会话。</p></div><div className="practice-resume-meta"><span><Clock3 size={14} />上次活动 {formatResumeTime(resumable.last_active_at)}</span><span>{label}</span></div><div className="practice-entry-actions"><button type="button" className="practice-submit" disabled={continuing || choosing} onClick={() => { setContinuing(true); setError(null); void onContinue(resumable).catch((reason: unknown) => { setError(reason instanceof Error ? reason.message : '无法恢复上次练习。'); setContinuing(false) }) }}>{continuing ? '正在恢复…' : <><Play size={15} />继续上次练习</>}</button><button type="button" className="practice-next" disabled={continuing || choosing} onClick={() => { setChoosing(true); setError(null); void onChooseBank().catch((reason: unknown) => { setError(reason instanceof Error ? reason.message : '无法重新选择题库。'); setChoosing(false) }) }}>{choosing ? '正在打开…' : '重新选择题库'}</button></div>{error && <p className="practice-entry-error" role="alert">{error}</p>}</section></div>
}

function normalizeMode(value: string | null): Mode { return value === 'exam' || value === 'review' ? value : 'study' }
function isAnswered(value: AnswerValue | null): value is AnswerValue { return value !== null && (!(Array.isArray(value)) || value.length > 0) && (typeof value !== 'string' || value.trim().length > 0) }
function learnerCaseSummary(value: string): string | null { const summary = value.trim(); return !summary || summary.includes('本地导入') || (summary.startsWith('来自 ') && summary.includes('真实题目') && summary.includes('上游来源与授权边界')) ? null : summary }
function displayBankName(name?: string) { return name?.replace(/医疗\s*\/\s*消化内镜\s*·\s*Factory\s*生成题草稿库/g, '医疗 / 消化内镜 · 资料生成题库').replace(/\s*[（(]本地导入[）)]/g, '').trim() }
function learnerTopic(value: string | null | undefined) { const topic = String(value ?? '').trim(); return /^(不符合|未知|其他|n\/?a|import|csv|jsonl)$/i.test(topic) || /模块\s*\d+/i.test(topic) ? null : topic || null }
function formatResumeTime(value: string) { const date = new Date(value); if (Number.isNaN(date.getTime())) return '刚刚'; const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000)); if (minutes < 2) return '刚刚'; if (minutes < 60) return `${minutes} 分钟前`; if (minutes < 24 * 60) return `${Math.floor(minutes / 60)} 小时前`; return `${date.getMonth() + 1}/${date.getDate()}` }

function QuestionMap({ questions, currentIndex, results, marked, sessionItems, onJump }: { questions: Question[]; currentIndex: number; results: Record<string, SubmitResult>; marked: Record<string, boolean>; sessionItems?: Array<{ question_id: string; state: 'unanswered' | 'correct' | 'incorrect' }>; onJump: (index: number) => void }) {
  const states = new Map(sessionItems?.map((item) => [item.question_id, item.state]))
  return <section className="question-map" id="question-map" aria-label="题单"><header><strong>题单</strong><span>点击题号跳转</span></header><div className="question-map-legend"><span>未答</span><span>正确</span><span>错误</span><span>标记</span></div><div className="question-map-grid">{questions.map((item, index) => { const result = results[item.id]; const state = result ? (result.is_correct ? 'correct' : 'incorrect') : (states.get(item.id) ?? 'unanswered'); return <button type="button" key={item.id} aria-label={`第 ${index + 1} 题，${state === 'correct' ? '正确' : state === 'incorrect' ? '错误' : '未作答'}${marked[item.id] ? '，已标记' : ''}`} className={`is-${state} ${index === currentIndex ? 'is-current' : ''} ${marked[item.id] ? 'is-marked' : ''}`} onClick={() => onJump(index)}>{index + 1}</button> })}</div></section>
}

function AnswerControl({ question, answer, disabled, result, onChoose, onText }: { question: Question; answer: AnswerValue | null; disabled: boolean; result?: SubmitResult; onChoose: (value: string) => void; onText: (value: AnswerValue) => void }) {
  if (question.question_type === 'short_answer') return <label className="practice-answer-text"><span>你的回答</span><textarea aria-label="你的回答" value={typeof answer === 'string' ? answer : ''} onChange={(event) => onText(event.target.value)} disabled={disabled} placeholder="写下你的判断依据…" rows={5} /></label>
  if (question.question_type === 'true_false') return <div className="s1-answer-options practice-answer-options">{[['true', '正确'], ['false', '错误']].map(([value, label], index) => <OptionButton key={value} label={label} letter={index === 0 ? 'T' : 'F'} selected={answer === (value === 'true')} correct={Boolean(result && (result.correct_answer_display === label || result.correct_answer_display === value))} wrong={Boolean(result && answer === (value === 'true') && !result.is_correct)} disabled={disabled} onClick={() => onText(value === 'true')} />)}</div>
  return <div className="s1-answer-options practice-answer-options">{question.options.map((option, index) => { const selected = Array.isArray(answer) ? answer.includes(option.id) : answer === option.id; const correct = Boolean(result && (result.correct_answer_display.includes(option.text) || result.correct_answer_display.startsWith(String.fromCharCode(65 + index)))); return <OptionButton key={option.id} label={option.text} letter={String.fromCharCode(65 + index)} selected={selected} correct={correct} wrong={Boolean(result && selected && !correct)} disabled={disabled} onClick={() => onChoose(option.id)} /> })}</div>
}

function OptionButton({ label, letter, selected, correct, wrong, disabled, onClick }: { label: string; letter: string; selected: boolean; correct: boolean; wrong: boolean; disabled: boolean; onClick: () => void }) { return <button type="button" className={`${selected ? 'is-selected ' : ''}${correct ? 'is-correct ' : ''}${wrong ? 'is-wrong' : ''}`} onClick={onClick} disabled={disabled}><span className="practice-option-letter">{correct ? <Check size={15} /> : letter}</span><span>{label}</span></button> }

function ResultPanel({ question, result, mode, reviewCard, reviewPending, reviewError, onReview }: { question: Question; result: SubmitResult; mode: Mode; reviewCard?: ReviewCard; reviewPending: boolean; reviewError?: string; onReview: (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void }) {
  const exam = mode === 'exam'
  const labels = { Again: '再来一次', Hard: '困难', Good: '掌握', Easy: '简单' } as const
  return <section className={result.is_correct ? 'practice-feedback is-correct' : 'practice-feedback is-incorrect'} data-testid="feedback">
    <div className="practice-feedback-strip"><span>{result.is_correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{exam ? '答案已提交，完成后统一复盘' : result.is_correct ? '回答正确' : '需要复盘'}</span></div>
    <div className="practice-explanation">{result.official_explanation_available && result.explanation.trim() ? <><strong>解析</strong><p>{result.explanation}</p></> : !exam && <><strong>暂无解析</strong></>}{learnerTopic(question.topic) && <div className="practice-related-topic">知识点关联 <span>{learnerTopic(question.topic)}</span></div>}{question.question_type === 'short_answer' && <small>本题按回答中的关键事实评分：{result.score} 分</small>}</div>
    {mode === 'review' && <div className="practice-review-controls">
      <strong>这次复习感觉如何？</strong>
      <div>{(['Again', 'Hard', 'Good', 'Easy'] as const).map((rating) => <button key={rating} type="button" disabled={reviewPending} onClick={() => onReview(rating)}>{labels[rating]}</button>)}</div>
      {reviewCard && <small>下次复习：{new Date(reviewCard.due_at).toLocaleString()} · 间隔 {reviewCard.interval_days} 天</small>}
      {reviewError && <small role="alert">复习记录失败：{reviewError}</small>}
    </div>}
  </section>
}

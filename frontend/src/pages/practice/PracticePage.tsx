import { ArrowLeft, Bookmark, Check, CheckCircle2, ChevronRight, ImageIcon, ListChecks, MessageCircle, XCircle } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createPracticeSession, getPracticeSession, getQuestionBanks, getQuestions, submitFsrsReview, submitPracticeAnswer, type AnswerValue, type Question, type ReviewCard, type SessionResponse, type SubmitResult } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { TutorPanel } from '../../components/tutor/TutorPanel'

type Mode = 'study' | 'exam' | 'review'

const typeLabels: Record<string, string> = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '简答题' }
const modeLabels: Record<Mode, string> = { study: '刷题', exam: '考试', review: '错题复习' }
const difficultyLabels: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' }

export function PracticePage() {
  const [searchParams] = useSearchParams()
  const mode = normalizeMode(searchParams.get('mode'))
  const bankId = searchParams.get('bank_id') ?? undefined
  const sessionId = searchParams.get('session_id') ?? undefined
  const [activeIndex, setActiveIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, AnswerValue | null>>({})
  const [results, setResults] = useState<Record<string, SubmitResult>>({})
  const [marked, setMarked] = useState<Record<string, boolean>>({})
  const questionCount = normalizeCount(searchParams.get('count'))
  const [tutorOpen, setTutorOpen] = useState(false)
  const [questionMapOpen, setQuestionMapOpen] = useState(false)
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const sessionRequest = useRef<{ key: string; promise: Promise<SessionResponse> } | null>(null)
  const restoredPosition = useRef<string | null>(null)
  const queryClient = useQueryClient()

  const banksQuery = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const restoredSessionQuery = useQuery({ queryKey: ['practice-session', sessionId], queryFn: () => getPracticeSession(sessionId ?? ''), enabled: Boolean(sessionId), retry: false })
  const restoredSession = restoredSessionQuery.data ?? null
  const selectedBankId = bankId ?? restoredSession?.bank_id ?? banksQuery.data?.[0]?.bank_id
  const activeSession = restoredSession ?? (session && session.bank_id === selectedBankId && session.mode === mode ? session : null)
  const questionsQuery = useQuery({
    queryKey: ['practice-questions', selectedBankId, activeSession?.session_id ?? 'catalog-fallback'],
    queryFn: () => getQuestions({ bankId: selectedBankId, sessionId: activeSession?.session_id }),
    enabled: Boolean(selectedBankId) && Boolean(activeSession || sessionError),
  })

  useEffect(() => {
    if (sessionId) return
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
    return () => { current = false }
  }, [mode, questionCount, selectedBankId, sessionId])

  const questions = useMemo(() => {
    const items = questionsQuery.data?.items ?? []
    return activeSession ? items : items.slice(0, questionCount)
  }, [activeSession, questionCount, questionsQuery.data?.items])
  const currentIndex = Math.min(activeIndex, Math.max(questions.length - 1, 0))
  const question = questions[currentIndex]
  const answer = question ? answers[question.id] ?? null : null
  const result = question ? results[question.id] : undefined
  const learnerId = activeSession?.learner_id ?? 'demo_learner'
  const selectedBank = banksQuery.data?.find((bank) => bank.bank_id === selectedBankId)

  useEffect(() => {
    if (!restoredSession || questions.length === 0 || restoredPosition.current === restoredSession.session_id) return
    const states = new Map((restoredSession.items ?? []).map((item) => [item.question_id, item.state]))
    const firstUnanswered = questions.findIndex((item) => (states.get(item.id) ?? 'unanswered') === 'unanswered')
    setActiveIndex(firstUnanswered >= 0 ? firstUnanswered : 0)
    restoredPosition.current = restoredSession.session_id
  }, [questions, restoredSession])

  const submitMutation = useMutation({
    mutationFn: (payload: { question: Question; answer: AnswerValue }) => submitPracticeAnswer({ question_id: payload.question.id, selected_answer: payload.answer, session_id: activeSession?.session_id, mode, learner_id: learnerId }),
    onSuccess: (data, variables) => {
      setResults((current) => ({ ...current, [variables.question.id]: data }))
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      void queryClient.invalidateQueries({ queryKey: ['question-banks'] })
      if (activeSession?.session_id) void queryClient.invalidateQueries({ queryKey: ['practice-session', activeSession.session_id] })
    },
  })
  const reviewMutation = useMutation({ mutationFn: (payload: { questionId: string; rating: 'Again' | 'Hard' | 'Good' | 'Easy' }) => submitFsrsReview(payload.questionId, payload.rating) })

  if (banksQuery.isPending || (Boolean(sessionId) && restoredSessionQuery.isPending) || !selectedBankId || (!activeSession && !sessionError) || questionsQuery.isPending) return <LoadingState label="正在准备本次练习…" />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />
  if (restoredSessionQuery.isError) return <ErrorState message="无法恢复本次练习 session。" onRetry={() => void restoredSessionQuery.refetch()} />
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
      {sessionError && <div className="practice-session-note" role="status">本次练习暂时按题库内容展示：{sessionError}</div>}
      {questions.length === 0 ? <div className="practice-empty"><EmptyState title="当前题库还没有可用题目" detail="返回题库目录选择其他题库。" /></div> : question && <div className="practice-content">
        <Link className="practice-back" to="/banks"><ArrowLeft size={16} />返回题库</Link>
        <header className="practice-progress-bar">
          <div className="s1-practice-progress practice-progress-copy"><strong>第 {currentIndex + 1} / {questions.length} 题</strong><span>{modeLabels[mode]}</span></div>
          <div className="practice-progress-track" aria-label={`已完成 ${completeCount} / ${questions.length}，${progress}%`}><i style={{ width: `${progress}%` }} /></div>
          <span className="practice-progress-percent">已完成 {completeCount} / {questions.length} · {progress}%</span>
          <div className="question-map-wrap"><button type="button" className="question-map-trigger" aria-expanded={questionMapOpen} aria-controls="question-map" onClick={() => setQuestionMapOpen((value) => !value)}><ListChecks size={15} />题单</button>{questionMapOpen && <QuestionMap questions={questions} currentIndex={currentIndex} results={results} marked={marked} sessionItems={restoredSession?.items} onJump={(index) => { setActiveIndex(index); setQuestionMapOpen(false) }} />}</div>
          <button type="button" className={marked[question.id] ? 'practice-mark is-marked' : 'practice-mark'} onClick={() => setMarked((current) => ({ ...current, [question.id]: !current[question.id] }))}><Bookmark size={15} />{marked[question.id] ? '已标记' : '标记'}</button>
        </header>

        {question.topic || question.subject || question.source_dataset ? <section className="practice-context" aria-label="当前练习上下文"><dl>{(question.topic || question.subject) && <div><dt>知识点</dt><dd>{question.topic ?? question.subject}</dd></div>}{question.difficulty && <div><dt>难度</dt><dd>{difficultyLabels[question.difficulty] ?? '未标注'}</dd></div>}{question.source_dataset && <div><dt>来源</dt><dd>{question.source_dataset}</dd></div>}</dl></section> : null}

        <section className={`practice-question ${question.image_url ? 'has-image' : 'is-text-only'}`} data-testid="question-card" data-question-layout={question.image_url ? 'image' : 'text-only'}>
          <div className="practice-question-kicker"><span>{typeLabels[question.question_type]}</span></div>
          <div className={question.image_url ? 'practice-question-heading has-image' : 'practice-question-heading'}><div><h1>{question.stem}</h1>{learnerCaseSummary(question.case_summary) && <p>{learnerCaseSummary(question.case_summary)}</p>}</div>{question.image_url && <figure className="practice-question-image"><img src={question.image_url} alt={question.image_alt ?? '内镜教学图像'} /><figcaption><ImageIcon size={13} />{question.image_alt ?? '图像题'}</figcaption></figure>}</div>
          <AnswerControl question={question} answer={answer} disabled={Boolean(result)} result={result} onChoose={chooseOption} onText={setAnswer} />
          {submitMutation.isError && <div className="practice-inline-error" role="alert">提交失败：{submitMutation.error.message}</div>}
          {result && <ResultPanel question={question} result={result} mode={mode} reviewCard={reviewMutation.data?.question_id === question.id ? reviewMutation.data : undefined} reviewPending={reviewMutation.isPending} reviewError={reviewMutation.isError ? reviewMutation.error.message : undefined} onReview={(rating) => reviewMutation.mutate({ questionId: question.id, rating })} onAskTutor={() => setTutorOpen(true)} />}
          <div className="practice-actions"><button className="practice-help" type="button" onClick={() => setTutorOpen(true)}><MessageCircle size={16} />提示</button><span /><button className="practice-submit" data-testid="submit-answer" onClick={submit} disabled={!isAnswered(answer) || submitMutation.isPending || Boolean(result)}>{submitMutation.isPending ? '正在记录…' : <><Check size={16} />提交答案</>}</button><button className="practice-next" data-testid="next-question" onClick={() => setActiveIndex((index) => Math.min(index + 1, questions.length - 1))} disabled={!result || currentIndex >= questions.length - 1}>下一题 <ChevronRight size={16} /></button></div>
        </section>
      </div>}
    </main>
    {question && <TutorPanel questionId={question.id} attemptId={result?.attempt_id} learnerId={learnerId} mode={mode} open={tutorOpen} onClose={() => setTutorOpen(false)} contextLabel={question.topic ?? question.subject ?? displayBankName(selectedBank?.name) ?? '当前题目'} />}
  </div>
}

function normalizeMode(value: string | null): Mode { return value === 'exam' || value === 'review' ? value : 'study' }
function normalizeCount(value: string | null) { const count = Number(value); return Number.isInteger(count) && count >= 1 && count <= 100 ? count : 20 }
function isAnswered(value: AnswerValue | null): value is AnswerValue { return value !== null && (!(Array.isArray(value)) || value.length > 0) && (typeof value !== 'string' || value.trim().length > 0) }
function learnerCaseSummary(value: string): string | null { const summary = value.trim(); return !summary || summary.includes('本地导入') || (summary.startsWith('来自 ') && summary.includes('真实题目') && summary.includes('上游来源与授权边界')) ? null : summary }
function displayBankName(name?: string) { return name?.replace(/医疗\s*\/\s*消化内镜\s*·\s*Factory\s*生成题草稿库/g, '医疗 / 消化内镜 · 资料生成题库').replace(/\s*[（(]本地导入[）)]/g, '').trim() }

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

function ResultPanel({ question, result, mode, reviewCard, reviewPending, reviewError, onReview, onAskTutor }: { question: Question; result: SubmitResult; mode: Mode; reviewCard?: ReviewCard; reviewPending: boolean; reviewError?: string; onReview: (rating: 'Again' | 'Hard' | 'Good' | 'Easy') => void; onAskTutor: () => void }) {
  const exam = mode === 'exam'
  const labels = { Again: '再来一次', Hard: '困难', Good: '掌握', Easy: '简单' } as const
  return <section className={result.is_correct ? 'practice-feedback is-correct' : 'practice-feedback is-incorrect'} data-testid="feedback">
    <div className="practice-feedback-strip"><span>{result.is_correct ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{exam ? '答案已提交，完成后统一复盘' : result.is_correct ? '回答正确' : '需要复盘'}</span></div>
    <div className="practice-explanation">{result.official_explanation_available && result.explanation.trim() ? <><strong>解析</strong><p>{result.explanation}</p></> : !exam && <><strong>暂无题库解析</strong><p>这道题暂未提供可展示的题库解析。</p><button type="button" className="practice-ask-tutor" onClick={onAskTutor}><MessageCircle size={14} />让智能辅导讲解</button></>}{question.topic && <div className="practice-related-topic">知识点关联 <span>{question.topic}</span></div>}{question.question_type === 'short_answer' && <small>本题按回答中的关键事实评分：{result.score} 分</small>}</div>
    {mode === 'review' && <div className="practice-review-controls">
      <strong>这次复习感觉如何？</strong>
      <div>{(['Again', 'Hard', 'Good', 'Easy'] as const).map((rating) => <button key={rating} type="button" disabled={reviewPending} onClick={() => onReview(rating)}>{labels[rating]}</button>)}</div>
      {reviewCard && <small>下次复习：{new Date(reviewCard.due_at).toLocaleString()} · 间隔 {reviewCard.interval_days} 天</small>}
      {reviewError && <small role="alert">复习记录失败：{reviewError}</small>}
    </div>}
  </section>
}

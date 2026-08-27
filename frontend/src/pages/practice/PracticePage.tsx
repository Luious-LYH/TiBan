import { ArrowLeft, ArrowRight, Check, CheckCircle2, CircleHelp, Image as ImageIcon, Send, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getQuestionBanks, getQuestions, getTutorHint, submitPracticeAnswer } from '../../api/client'
import type { AnswerValue, MultipleChoiceQuestion, Question, SubmitResult } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

const typeLabels: Record<Question['question_type'], string> = { single_choice: '单选', multiple_choice: '多选', true_false: '判断', short_answer: '简答' }

export function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const bankId = searchParams.get('bank_id') ?? undefined
  const [activeIndex, setActiveIndex] = useState(0)
  const [answer, setAnswer] = useState<AnswerValue | null>(null)
  const [result, setResult] = useState<SubmitResult | null>(null)
  const [tutorOpen, setTutorOpen] = useState(false)

  const banksQuery = useQuery({ queryKey: ['question-banks'], queryFn: () => getQuestionBanks() })
  const questionsQuery = useQuery({ queryKey: ['practice-questions', bankId], queryFn: () => getQuestions({ bankId }) })
  const queryClient = useQueryClient()
  const submitMutation = useMutation({
    mutationFn: submitPracticeAnswer,
    onSuccess: (data) => {
      setResult(data)
      void queryClient.invalidateQueries({ queryKey: ['overview'] })
      void queryClient.invalidateQueries({ queryKey: ['question-banks'] })
    },
  })
  const hintMutation = useMutation({ mutationFn: (questionId: string) => getTutorHint(questionId) })

  if (questionsQuery.isPending || banksQuery.isPending) return <LoadingState label="正在准备练习工作台…" />
  if (questionsQuery.isError) return <ErrorState message={questionsQuery.error.message} onRetry={() => void questionsQuery.refetch()} />
  if (banksQuery.isError) return <ErrorState message={banksQuery.error.message} onRetry={() => void banksQuery.refetch()} />

  const items = questionsQuery.data.items
  const currentIndex = activeIndex < items.length ? activeIndex : 0
  const question = items[currentIndex]
  const selectedBank = banksQuery.data.find((bank) => bank.bank_id === bankId)

  function chooseBank(nextBankId: string) {
    setSearchParams(nextBankId ? { bank_id: nextBankId } : {})
    setActiveIndex(0)
    setAnswer(null)
    setResult(null)
    hintMutation.reset()
  }

  function chooseOption(optionId: string) {
    if (!question || result) return
    if (question.question_type === 'multiple_choice') {
      const previous = Array.isArray(answer) ? answer : []
      setAnswer(previous.includes(optionId) ? previous.filter((id) => id !== optionId) : [...previous, optionId])
    } else {
      setAnswer(optionId)
    }
  }

  function submit() {
    if (!question || answer === null || (Array.isArray(answer) && answer.length === 0)) return
    submitMutation.mutate({ question_id: question.id, selected_answer: answer })
  }

  function nextQuestion() {
    if (currentIndex >= items.length - 1) return
    setActiveIndex((index) => index + 1)
    setAnswer(null)
    setResult(null)
    hintMutation.reset()
  }

  return (
    <div className="s1-page s1-practice-page" data-testid="practice-page">
      <section className="s1-practice-top"><div><Link className="s1-back-link" to="/banks"><ArrowLeft size={15} />返回题库</Link><span className="s1-kicker">PRACTICE WORKSPACE</span><h1>练习工作台</h1><p>{selectedBank?.name ?? '全部题库'} · 确定性评分与学习状态记录</p></div><label className="s1-select s1-bank-select"><span>当前题库</span><select aria-label="选择题库" value={bankId ?? ''} onChange={(event) => chooseBank(event.target.value)}><option value="">全部题库</option>{banksQuery.data.map((bank) => <option key={bank.bank_id} value={bank.bank_id}>{bank.name}</option>)}</select></label></section>
      {items.length === 0 ? <section className="s1-card"><EmptyState title="当前筛选没有题目" detail="换一个题库或返回题库目录重新选择。" /></section> : <><button className="s1-mobile-tutor-trigger" onClick={() => setTutorOpen(true)}><CircleHelp size={16} />打开 Tutor 规则提示 <span>Stage 2 Agent 未启用</span></button><div className="s1-practice-layout"><section className="s1-card s1-question-card"><div className="s1-question-meta"><span className="s1-question-count">{currentIndex + 1} / {items.length}</span><span className="s1-type-pill">{typeLabels[question.question_type]}</span><span>{question.body_part}</span><span>{question.difficulty}</span></div><div className="s1-question-heading"><div><span className="s1-kicker">{question.title}</span><h2>{question.stem}</h2><p>{question.case_summary}</p></div>{question.image_url && <figure className="s1-question-image"><img src={question.image_url} alt={question.image_alt ?? '内镜教学图像'} /><figcaption><ImageIcon size={13} />{question.image_alt ?? '真实样例图像'}</figcaption></figure>}</div><AnswerControl question={question} answer={answer} disabled={Boolean(result)} onChoose={chooseOption} onText={(value) => setAnswer(value)} />{submitMutation.isError && <div className="s1-inline-error" role="alert">提交失败：{submitMutation.error.message}</div>}{result && <ResultPanel result={result} />}
        <div className="s1-question-actions"><button className="s1-button s1-button-primary" data-testid="submit-answer" onClick={submit} disabled={answer === null || (Array.isArray(answer) && answer.length === 0) || submitMutation.isPending || Boolean(result)}>{submitMutation.isPending ? '正在记录…' : <><Send size={16} />提交答案</>}</button><button className="s1-button s1-button-light" data-testid="next-question" onClick={nextQuestion} disabled={!result || currentIndex >= items.length - 1}><ArrowRight size={16} />下一题</button></div></section>
        <aside className={tutorOpen ? 's1-card s1-tutor-card is-open' : 's1-card s1-tutor-card'} aria-label="Tutor 规则提示"><div className="s1-tutor-header"><div><span className="s1-tutor-orb"><CircleHelp size={17} /></span><span><strong>Tutor</strong><small>规则提示 · Stage 2 Agent 未启用</small></span></div><button className="s1-icon-button s1-tutor-close" onClick={() => setTutorOpen(false)} aria-label="关闭规则提示"><X size={17} /></button></div><p className="s1-tutor-explainer">提示只来自当前题目的规则边界，不替你做确定性学习状态更新。</p>{hintMutation.data ? <div className="s1-hint-result"><strong>观察路径</strong><p>{hintMutation.data.message}</p><small>来源：{(hintMutation.data.sources ?? []).join('；')}</small></div> : <div className="s1-tutor-empty"><CircleHelp size={28} /><span>需要时获取一个小提示，先从可支持的观察事实开始。</span></div>}<button className="s1-button s1-button-secondary" data-testid="tutor-hint" onClick={() => { setTutorOpen(true); if (question) hintMutation.mutate(question.id) }} disabled={hintMutation.isPending}>{hintMutation.isPending ? '生成提示…' : '获取规则提示'}</button></aside></div></>}
      <p className="s1-safety">{question?.safety_notice ?? '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'}</p>
    </div>
  )
}

function AnswerControl({ question, answer, disabled, onChoose, onText }: { question: Question; answer: AnswerValue | null; disabled: boolean; onChoose: (value: string) => void; onText: (value: string | boolean) => void }) {
  if (question.question_type === 'short_answer') return <label className="s1-answer-text"><span>你的观察与解释</span><textarea aria-label="你的回答" value={typeof answer === 'string' ? answer : ''} onChange={(event) => onText(event.target.value)} disabled={disabled} placeholder="用观察性语言描述证据，保留医生复核边界…" /></label>
  if (question.question_type === 'true_false') return <div className="s1-answer-options s1-boolean-options">{[['true', '正确'], ['false', '错误']].map(([value, label]) => <button key={value} className={answer === (value === 'true') ? 'is-selected' : ''} onClick={() => onText(value === 'true')} disabled={disabled}>{answer === (value === 'true') ? <Check size={17} /> : <span className="s1-option-letter">{value === 'true' ? 'T' : 'F'}</span>}<span>{label}</span></button>)}</div>
  const choiceQuestion = question as MultipleChoiceQuestion
  return <div className="s1-answer-options">{choiceQuestion.options.map((option, index) => { const selected = Array.isArray(answer) ? answer.includes(option.id) : answer === option.id; return <button key={option.id} className={selected ? 'is-selected' : ''} onClick={() => onChoose(option.id)} disabled={disabled}><span className="s1-option-letter">{selected ? <Check size={16} /> : String.fromCharCode(65 + index)}</span><span>{option.text}</span></button> })}</div>
}

function ResultPanel({ result }: { result: SubmitResult }) {
  return <div className={result.is_correct ? 's1-result is-correct' : 's1-result'} data-testid="feedback"><div><span>{result.is_correct ? <CheckCircle2 size={16} /> : '需要复盘'}</span><strong>{result.score}</strong><small> / 100</small></div><div><h3>{result.is_correct ? '回答符合当前评分规则' : '这次记录进入复盘队列'}</h3><p>{result.explanation}</p><small>{result.next_recommendation}</small></div></div>
}

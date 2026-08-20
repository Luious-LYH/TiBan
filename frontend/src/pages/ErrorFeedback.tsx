import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ActivitySquare, CheckCircle2, ClipboardList, RotateCcw, XCircle } from 'lucide-react'
import { Card, EmptyState, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { ExamSessionRecord, Question, SubmissionResponse } from '../lib/types'

export function ErrorFeedback({
  submission,
  question,
}: {
  submission: SubmissionResponse | null
  question: Question | null
}) {
  const [searchParams] = useSearchParams()
  const [restoredQuestion, setRestoredQuestion] = useState<Question | null>(null)
  const [restoreSource, setRestoreSource] = useState('')
  const [examSession, setExamSession] = useState<ExamSessionRecord | null>(null)
  const sessionId = searchParams.get('session') || ''

  useEffect(() => {
    if (submission || question) return
    let mounted = true
    api.trainingState()
      .then(async (state) => {
        const matchedSession = sessionId
          ? state.exam_sessions.find((session) => session.session_id === sessionId || session.id === sessionId) || null
          : null
        const fallbackSession = matchedSession || (!sessionId ? state.latest_exam_session || null : null)
        const reviewQueue = fallbackSession?.wrong_questions?.length ? fallbackSession.wrong_questions : state.wrong_questions
        const reviewId = reviewQueue[0] || state.profile.recent_errors[0] || state.profile.training_records.find((record) => record.result === '待复盘')?.question_id
        if (!reviewId) return
        const item = await api.question(reviewId)
        if (mounted) {
          setExamSession(fallbackSession)
          setRestoredQuestion(item)
          setRestoreSource(fallbackSession
            ? `已从考试 Session ${fallbackSession.session_id} 恢复错题：${reviewId}`
            : `已从后端错题本恢复最近复盘题：${reviewId}`)
        }
      })
      .catch(() => {
        if (mounted) setRestoreSource('后端训练状态暂不可用，展示本地复盘样例。')
      })
    return () => {
        mounted = false
      }
  }, [question, sessionId, submission])

  const activeQuestion = question || restoredQuestion || mockQuestions.find((item) => item.review_status === '待复盘') || mockQuestions[1]
  const activeSubmission =
    submission ||
    buildReviewSnapshot(activeQuestion)
  const isRestoredReview = !submission
  const sourceText = submission ? '来自本轮提交' : restoreSource || '直接打开页面时自动展示最近错题复盘快照，不写入后端。'
  const selectedAnswerLabel = isRestoredReview ? '复盘示例答案' : '用户答案'

  return (
    <div className="page-stack">
      <Card className="feedback-source-card">
        <ActivitySquare size={20} />
        <div>
          <span className="eyebrow">Feedback source</span>
          <strong>{sourceText}</strong>
          <p>{isRestoredReview ? '这是复盘视图，基于题目标准答案和原子事实生成示例错误答案，不会伪装成真实提交或重复计入训练记录。' : '本次提交已由训练中心写入医师画像和审计日志。'}</p>
        </div>
      </Card>

      {examSession ? (
        <Card className="feedback-session-card">
          <div className="feedback-session-main">
            <ClipboardList size={22} />
            <div>
              <span className="eyebrow">Exam session replay</span>
              <strong>{examSession.session_id}</strong>
              <p>本场考试已写入林知远医师画像；复盘页按 session 恢复错题队列，不重复增加答题记录。</p>
            </div>
          </div>
          <div className="feedback-session-metrics">
            <div><span>题量</span><strong>{examSession.answered_count}</strong></div>
            <div><span>正确率</span><strong>{examSession.accuracy}%</strong></div>
            <div><span>错题</span><strong>{examSession.wrong_questions.length}</strong></div>
            <div><span>画像</span><strong>{examSession.profile_updated ? '已回灌' : '未写入'}</strong></div>
          </div>
          <div className="feedback-session-queue">
            {examSession.wrong_questions.length
              ? examSession.wrong_questions.map((item) => <span key={item}>{item}</span>)
              : <span>本场没有错题，当前展示最近复盘题。</span>}
          </div>
        </Card>
      ) : null}

      <div className="grid two">
        <Card>
          <SectionTitle
            eyebrow="Submission trace"
            title={isRestoredReview ? '错题复盘快照' : '作答记录'}
            action={isRestoredReview ? <Tag tone="blue">review snapshot</Tag> : <Tag tone="green">live submission</Tag>}
          />
          <div className="answer-compare">
            <div>
              <span>{selectedAnswerLabel}</span>
              <strong>{activeSubmission.selected_answer}</strong>
            </div>
            <div>
              <span>参考答案</span>
              <strong>{activeQuestion.answer}</strong>
            </div>
          </div>
          <div className="tag-row">
            {activeSubmission.error_tags.length ? activeSubmission.error_tags.map((tag) => <Tag key={tag} tone="red">{tag}</Tag>) : <Tag tone="green">无错因</Tag>}
          </div>
          <p className="feedback-text">{activeSubmission.explanation}</p>
          <div className="next-card">{activeSubmission.next_recommendation}</div>
        </Card>
        <Card>
          <SectionTitle eyebrow="Question" title={activeQuestion.title} />
          <p className="question-text">{activeQuestion.question}</p>
          <div className="tag-row">
            {activeQuestion.teaching_tags.map((tag) => <Tag key={tag} tone="blue">{tag}</Tag>)}
          </div>
          <EmptyState>
            <RotateCcw size={16} /> 原子事实表会随真实提交或复盘快照更新，用来解释“错在哪里”而不是只给分。
          </EmptyState>
        </Card>
      </div>

      <Card>
        <SectionTitle eyebrow="Atomic facts" title="原子事实级反馈" />
        <div className="fact-table">
          <div className="fact-row fact-head">
            <span>支持</span>
            <span>能力维度</span>
            <span>事实</span>
            <span>期望</span>
            <span>依据</span>
          </div>
          {activeSubmission.fact_feedback.map((fact) => (
            <div className="fact-row" key={fact.id}>
              <span>{fact.supported ? <CheckCircle2 className="ok" size={18} /> : <XCircle className="bad" size={18} />}</span>
              <span>{fact.skill_dimension}</span>
              <span>{fact.fact}</span>
              <span>{fact.expected}</span>
              <span>{fact.evidence}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function buildReviewSnapshot(question: Question): SubmissionResponse {
  const wrongOption = question.options.find((option) => option !== question.answer) || question.answer
  const errorTags = question.false_premise_flag ? ['过度推断', '证据不足'] : ['证据不足']
  const focusedFacts = question.atomic_trace.filter((fact) => !fact.supported || fact.skill_dimension === '证据不足识别')
  return {
    id: `review_${question.id}`,
    question_id: question.id,
    learner_id: 'demo_learner',
    selected_answer: wrongOption,
    is_correct: false,
    score: 0,
    error_tags: errorTags,
    fact_feedback: focusedFacts.length ? focusedFacts : question.atomic_trace,
    explanation: `复盘快照：${question.explanation} 请对照参考答案重新检查证据链。`,
    next_recommendation: question.false_premise_flag ? '建议继续练习报告纠错与证据不足判断题。' : '建议回到错题本，继续练习证据链表达。',
    created_at: new Date().toISOString(),
    profile_updated: false,
    doctor_review_required: true,
    safety_notice: safetyNotice,
  }
}

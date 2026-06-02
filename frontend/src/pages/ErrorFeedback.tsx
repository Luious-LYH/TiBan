import { CheckCircle2, XCircle } from 'lucide-react'
import { Card, EmptyState, SectionTitle, Tag } from '../components/Primitives'
import { mockQuestions, safetyNotice } from '../lib/mock'
import type { Question, SubmissionResponse } from '../lib/types'

export function ErrorFeedback({
  submission,
  question,
}: {
  submission: SubmissionResponse | null
  question: Question | null
}) {
  const activeQuestion = question || mockQuestions[1]
  const activeSubmission =
    submission ||
    ({
      id: 'demo_feedback',
      question_id: activeQuestion.id,
      learner_id: 'demo_learner',
      selected_answer: activeQuestion.options[1],
      is_correct: false,
      score: 0,
      error_tags: ['错误前提', '证据不足'],
      fact_feedback: activeQuestion.atomic_trace,
      explanation: activeQuestion.explanation,
      next_recommendation: '建议继续练习错误前提与证据不足判断题。',
      created_at: new Date().toISOString(),
      doctor_review_required: true,
      safety_notice: safetyNotice,
    } satisfies SubmissionResponse)

  return (
    <div className="page-stack">
      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Submission trace" title="作答记录" />
          <div className="answer-compare">
            <div>
              <span>用户答案</span>
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
          <EmptyState>原子事实表会随每次提交更新，用来解释“错在哪里”而不是只给分。</EmptyState>
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

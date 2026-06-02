import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, ShieldCheck } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { mockQuestions } from '../lib/mock'
import type { Question } from '../lib/types'

export function FalsePremiseTraining() {
  const [questions, setQuestions] = useState<Question[]>(mockQuestions.filter((q) => q.false_premise_flag))

  useEffect(() => {
    api.questions({ falsePremise: true }).then((items) => setQuestions(items.length ? items : mockQuestions.filter((q) => q.false_premise_flag)))
  }, [])

  return (
    <div className="page-stack">
      <Card className="focus-band">
        <div>
          <span className="eyebrow">False premise guard</span>
          <h2>训练“证据不足 / 不适用 / 题干假设不成立”的意识</h2>
          <p>内镜 Agent 的安全价值不只是答对，也包括在图像证据不足时拒绝接受错误前提。</p>
        </div>
        <ShieldCheck size={42} />
      </Card>
      <div className="grid two">
        {questions.map((question) => (
          <Card key={question.id}>
            <SectionTitle eyebrow={question.question_class} title={question.title} />
            <p className="question-text">{question.question}</p>
            <div className="premise-box">
              <AlertTriangle size={18} />
              <span>题干前提需要验证：{question.atomic_trace.find((fact) => !fact.supported)?.fact || '检查图像证据是否足够'}</span>
            </div>
            <div className="option-list compact">
              {question.options.map((option) => (
                <div key={option} className={`option-button readonly ${option === question.answer ? 'selected' : ''}`}>
                  <span>{option}</span>
                  {option === question.answer ? <CheckCircle2 size={18} /> : null}
                </div>
              ))}
            </div>
            <p className="feedback-text">{question.explanation}</p>
            <div className="tag-row">
              {question.teaching_tags.map((tag) => <Tag key={tag} tone="amber">{tag}</Tag>)}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}


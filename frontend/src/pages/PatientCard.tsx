import { useState } from 'react'
import { MessageCircleHeart, WandSparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { PatientCard as PatientCardType } from '../lib/types'

export function PatientCard() {
  const [summary, setSummary] = useState('胃黏膜炎症样改变，待医生审核后用于患者解释。')
  const [card, setCard] = useState<PatientCardType | null>(null)

  const generate = async () => {
    setCard(await api.patientCard(summary))
  }

  return (
    <div className="page-stack">
      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Patient education" title="科普卡片生成" />
          <textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={7} />
          <button className="button primary" type="button" onClick={generate}>
            <WandSparkles size={17} /> 生成患者友好解释
          </button>
        </Card>
        <Card>
          <SectionTitle eyebrow="Review gate" title="沟通边界" />
          <div className="notice-card">
            <MessageCircleHeart size={20} />
            <p>科普卡片可先生成医生待审草稿；只有医生确认输入后，才可用于患者沟通，不替代医患沟通，也不生成治疗承诺。</p>
          </div>
          <div className="tag-row">
            <Tag tone="red">免责声明</Tag>
            <Tag tone="green">患者友好</Tag>
            <Tag tone="amber">不承诺疗效</Tag>
          </div>
        </Card>
      </div>

      {card ? (
        <Card className="patient-card-preview">
          <SectionTitle eyebrow="Preview" title={card.card_title} action={<Tag tone="red">需医生审核</Tag>} />
          <div className="tag-row">
            <Tag tone={card.review_status === 'doctor_reviewed_input' ? 'green' : 'amber'}>
              {card.review_status === 'doctor_reviewed_input' ? '医生已审核输入' : '医生待审核输入'}
            </Tag>
          </div>
          <p className="patient-main">{card.plain_language_explanation}</p>
          <div className="draft-grid">
            <InfoBlock title="这意味着什么" items={card.what_it_means} />
            <InfoBlock title="需要关注什么" items={card.what_to_watch} />
          </div>
          <div className="next-card">{card.follow_up_reminder}</div>
          <p className="disclaimer">{card.disclaimer}</p>
        </Card>
      ) : null}
    </div>
  )
}

function InfoBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="draft-block">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}

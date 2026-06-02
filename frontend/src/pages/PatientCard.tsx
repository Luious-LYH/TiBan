import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'
import { ImagePlus, MessageCircleHeart, Printer, Share2, Sparkles, WandSparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { KnowledgeBase, PatientCard as PatientCardType } from '../lib/types'

const sampleImages = [
  '/assets/real_samples/kv_cla820gl0s3nv071u4fgd7xgq.jpg',
  '/assets/real_samples/x1_clb0kvxvm90y4074yf50vf5nq.jpg',
  '/assets/real_samples/endo_image_0.jpg',
]

export function PatientCard() {
  const [summary, setSummary] = useState('胃窦黏膜炎症样改变，需结合完整报告和医生复核后用于患者解释。')
  const [templateId, setTemplateId] = useState('calm_blue')
  const [imageUrl, setImageUrl] = useState(sampleImages[0])
  const [card, setCard] = useState<PatientCardType | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeBase | null>(null)
  const [cardStatus, setCardStatus] = useState('选择模板和图像后，可生成医生审核前科普卡片草稿。')
  const [uploadedImageName, setUploadedImageName] = useState('')

  useEffect(() => {
    api.cardKnowledge().then(setKnowledge)
  }, [])

  const generate = async () => {
    setCardStatus('正在生成医生审核前科普卡片...')
    try {
      const generated = await api.patientCard(summary, { templateId, imageUrl })
      setCard(generated)
      setCardStatus(`已生成 ${generated.review_status === 'doctor_review_pending' ? '医生待审核' : '医生已审核'} 卡片草稿。`)
    } catch {
      setCardStatus('卡片接口暂不可用，请稍后重试；当前仍保留本地预览草稿。')
    }
  }

  const onUploadImage = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const objectUrl = URL.createObjectURL(file)
    setImageUrl(objectUrl)
    setUploadedImageName(file.name)
    setCardStatus(`已载入本地图片：${file.name}。仅用于本机预览，不会自动上传或写入后端。`)
  }

  const printPreview = () => {
    window.print()
    setCardStatus('已打开浏览器打印预览；正式发放前仍需医生审核卡片内容。')
  }

  const shareCard = async () => {
    const text = `${card?.card_title || '内镜检查结果说明卡'}：${card?.plain_language_explanation || summary}`
    try {
      if (navigator.share) {
        await navigator.share({ title: card?.card_title || '内镜科普卡片', text })
        setCardStatus('已调用系统分享面板。请确认只分享医生审核后的卡片。')
      } else {
        await navigator.clipboard.writeText(text)
        setCardStatus('已复制分享文案到剪贴板。请只在医生审核后用于患者沟通。')
      }
    } catch {
      setCardStatus('分享动作已取消或浏览器不支持；卡片仍保留在当前页面预览。')
    }
  }

  const activeTemplate = knowledge?.templates?.find((item) => item.id === templateId)

  return (
    <div className="page-stack card-studio">
      <Card className="focus-band card-focus">
        <div>
          <span className="eyebrow">Patient education studio</span>
          <h2>科普卡片工作室</h2>
          <p>把医生审核前报告摘要转成图文并茂的患者沟通卡片。卡片支持模板风格、浮动预览、打印/分享视觉状态，但仍必须医生审核。</p>
        </div>
        <Sparkles size={42} />
      </Card>

      <div className="grid two card-builder">
        <Card>
          <SectionTitle eyebrow="Input" title="卡片内容与模板" />
          <textarea value={summary} onChange={(event) => setSummary(event.target.value)} rows={7} />
          <div className="template-switcher">
            {knowledge?.templates?.map((template) => (
              <button
                key={template.id}
                className={`template-chip ${template.id === templateId ? 'active' : ''}`}
                type="button"
                onClick={() => setTemplateId(template.id || 'calm_blue')}
              >
                <span className={`swatch swatch-${template.id || 'calm_blue'}`} />
                <strong>{template.name}</strong>
                <em>{template.tone}</em>
              </button>
            ))}
          </div>
          <div className="image-strip">
            {sampleImages.map((item) => (
              <button
                key={item}
                className={item === imageUrl ? 'active' : ''}
                type="button"
                onClick={() => {
                  setImageUrl(item)
                  setUploadedImageName('')
                  setCardStatus('已切换为公开样例图片，卡片仍需医生审核后才能分享。')
                }}
                title="选择卡片图像"
              >
                <img src={item} alt="公开内镜样例缩略图" />
              </button>
            ))}
            <label className={`image-placeholder ${uploadedImageName ? 'active-upload' : ''}`} title="上传本地卡片图像">
              <input type="file" accept="image/*" onChange={onUploadImage} />
              <ImagePlus size={18} />
            </label>
          </div>
          {uploadedImageName ? <div className="source-note">本地上传预览：{uploadedImageName}</div> : null}
          <button className="button primary" type="button" onClick={generate}>
            <WandSparkles size={17} /> 生成浮动科普卡片
          </button>
          <div className="card-status-line">{cardStatus}</div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Review gate" title="沟通边界" />
          <div className="notice-card">
            <MessageCircleHeart size={20} />
            <p>科普卡片可先生成医生待审草稿；只有医生确认输入后，才可用于患者沟通，不替代医患沟通，也不生成治疗承诺。</p>
          </div>
          <div className="tag-row">
            <Tag tone="red">医生审核</Tag>
            <Tag tone="green">图文多模态</Tag>
            <Tag tone="amber">不承诺疗效</Tag>
          </div>
          <div className="visual-rules">
            {knowledge?.visual_rules?.map((rule) => <span key={rule}>{rule}</span>)}
          </div>
        </Card>
      </div>

      <div className="floating-stage">
        <div className="stage-aura" />
        <article className={`floating-patient-card template-${card?.template_id || templateId}`}>
          <div className="card-media">
            <img src={card?.image_url || imageUrl} alt="科普卡片使用的内镜示例图" />
            <span>{activeTemplate?.name || card?.visual_tone || '医生审核前草稿'}</span>
          </div>
          <div className="card-copy">
            <div className="card-header">
              <div>
                <span>Endo Patient Card</span>
                <h3>{card?.card_title || '内镜检查结果说明卡'}</h3>
              </div>
              <Tag tone="red">需医生审核</Tag>
            </div>
            <p className="patient-main">
              {card?.plain_language_explanation || `医生待审核摘要：${summary}`}
            </p>
            <div className="card-info-grid">
              <InfoBlock title="这意味着什么" items={card?.what_it_means || ['内镜描述反映检查中看到的黏膜外观。', '部分表现需要结合病史和病理。']} />
              <InfoBlock title="需要关注什么" items={card?.what_to_watch || ['按医生要求复诊或进一步检查。', '症状变化时及时联系医疗机构。']} />
            </div>
            <div className="next-card">{card?.follow_up_reminder || '请按照医生给出的复诊或检查安排执行。'}</div>
            <p className="disclaimer">{card?.disclaimer || '本卡片为医生审核前沟通草稿，不能替代医生解释。'}</p>
            <div className="card-actions">
              <button className="button secondary" type="button" onClick={printPreview}><Printer size={16} /> 打印预览</button>
              <button className="button secondary" type="button" onClick={shareCard}><Share2 size={16} /> 分享文案</button>
            </div>
          </div>
        </article>
      </div>
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

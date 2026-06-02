import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'
import { CheckCircle2, ImagePlus, LockKeyhole, Printer, Share2, Sparkles, WandSparkles } from 'lucide-react'
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
  const [reviewerName, setReviewerName] = useState('林知远医师')
  const [reviewNotes, setReviewNotes] = useState('摘要与报告训练输入一致，可作为患者沟通前说明草稿。')
  const [reviewChecks, setReviewChecks] = useState({
    summaryMatched: false,
    noUnsupportedClaim: false,
    disclaimerKept: false,
  })
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    api.cardKnowledge().then(setKnowledge)
  }, [])

  const isReviewed = card?.share_status === 'reviewed_ready_to_share' || card?.review_status === 'doctor_reviewed_input'
  const allReviewChecksDone = Object.values(reviewChecks).every(Boolean)
  const canApprove = Boolean(card) && !isReviewed && allReviewChecksDone && reviewerName.trim().length > 0 && !reviewing
  const shareLocked = !isReviewed

  const markDraftDirty = (message: string) => {
    if (card) {
      setCard(null)
      setReviewChecks({ summaryMatched: false, noUnsupportedClaim: false, disclaimerKept: false })
    }
    setCardStatus(message)
  }

  const generate = async () => {
    setCardStatus('正在生成医生审核前科普卡片...')
    try {
      const generated = await api.patientCard(summary, { templateId, imageUrl })
      setCard(generated)
      setReviewChecks({ summaryMatched: false, noUnsupportedClaim: false, disclaimerKept: false })
      setCardStatus(`已生成 ${generated.review_status === 'doctor_review_pending' ? '医生待审核' : '医生已审核'} 卡片草稿。`)
    } catch {
      setCardStatus('卡片接口暂不可用，请稍后重试；当前仍保留本地预览草稿。')
    }
  }

  const approveCard = async () => {
    if (!canApprove) return
    setReviewing(true)
    setCardStatus('正在提交医生审核确认，并重新生成可沟通版本...')
    try {
      const reviewed = await api.patientCard(summary, {
        templateId,
        imageUrl,
        reviewedByDoctor: true,
        reviewerName,
        reviewNotes,
      })
      setCard(reviewed)
      setCardStatus(`已由 ${reviewed.reviewer_name || reviewerName} 完成审核；分享和打印已解锁，并写入审计日志。`)
    } catch {
      setCardStatus('审核确认提交失败，请确认后端在线后重试。')
    } finally {
      setReviewing(false)
    }
  }

  const onUploadImage = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const objectUrl = URL.createObjectURL(file)
    setImageUrl(objectUrl)
    setUploadedImageName(file.name)
    markDraftDirty(`已载入本地图片：${file.name}。仅用于本机预览；请重新生成草稿并完成医生审核。`)
  }

  const printPreview = () => {
    if (shareLocked) {
      setCardStatus('打印已锁定：请先完成医生审核确认。')
      return
    }
    window.print()
    setCardStatus('已打开浏览器打印预览；当前卡片已完成医生审核确认。')
  }

  const shareCard = async () => {
    if (shareLocked) {
      setCardStatus('分享已锁定：请先完成医生审核确认。')
      return
    }
    const text = `${card?.card_title || '内镜检查结果说明卡'}：${card?.plain_language_explanation || summary}`
    try {
      if (navigator.share) {
        await navigator.share({ title: card?.card_title || '内镜科普卡片', text })
        setCardStatus('已调用系统分享面板；当前卡片为医生审核后版本。')
      } else {
        await navigator.clipboard.writeText(text)
        setCardStatus('已复制分享文案到剪贴板；当前卡片为医生审核后版本。')
      }
    } catch {
      setCardStatus('分享动作已取消或浏览器不支持；卡片仍保留在当前页面预览。')
    }
  }

  const activeTemplate = knowledge?.templates?.find((item) => item.id === templateId)
  const reviewSteps = isReviewed && card?.review_steps?.length
    ? card.review_steps
    : [
        { label: '摘要来自医生确认的报告或训练输入', checked: Boolean(reviewChecks.summaryMatched), detail: '未确认前，卡片只能用于教学预览。' },
        { label: '未加入未提供的病理、治疗或疗效承诺', checked: Boolean(reviewChecks.noUnsupportedClaim), detail: '高风险医学表述保持解释性和复核边界。' },
        { label: '患者沟通前保留免责声明和复诊提醒', checked: Boolean(reviewChecks.disclaimerKept), detail: '卡片始终提示不替代医生面对面解释。' },
      ]

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
          <textarea
            value={summary}
            onChange={(event) => {
              setSummary(event.target.value)
              markDraftDirty('摘要已修改，请重新生成科普卡片草稿。')
            }}
            rows={7}
          />
          <div className="template-switcher">
            {knowledge?.templates?.map((template) => (
              <button
                key={template.id}
                className={`template-chip ${template.id === templateId ? 'active' : ''}`}
                type="button"
                onClick={() => {
                  setTemplateId(template.id || 'calm_blue')
                  markDraftDirty('模板已切换，请重新生成草稿以刷新审核状态。')
                }}
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
                  markDraftDirty('已切换为公开样例图片，请重新生成草稿并完成医生审核。')
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
          <SectionTitle
            eyebrow="Review gate"
            title="医生审核闸门"
            action={<Tag tone={isReviewed ? 'green' : 'red'}>{isReviewed ? '已解锁分享' : '分享锁定'}</Tag>}
          />
          <div className={`notice-card review-gate-panel ${isReviewed ? 'reviewed' : ''}`}>
            {isReviewed ? <CheckCircle2 size={20} /> : <LockKeyhole size={20} />}
            <p>{isReviewed ? '医生已经确认摘要、边界和免责声明；当前卡片可用于患者沟通前说明。' : '科普卡片可先生成待审草稿；只有医生确认输入和边界后，才会解锁打印和分享。'}</p>
          </div>
          <div className="review-checklist">
            <label>
              <input
                type="checkbox"
                checked={reviewChecks.summaryMatched || isReviewed}
                disabled={!card || isReviewed}
                onChange={(event) => setReviewChecks((state) => ({ ...state, summaryMatched: event.target.checked }))}
              />
              <span>摘要与医生报告或训练输入一致</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={reviewChecks.noUnsupportedClaim || isReviewed}
                disabled={!card || isReviewed}
                onChange={(event) => setReviewChecks((state) => ({ ...state, noUnsupportedClaim: event.target.checked }))}
              />
              <span>未新增病理、治疗方案或疗效承诺</span>
            </label>
            <label>
              <input
                type="checkbox"
                checked={reviewChecks.disclaimerKept || isReviewed}
                disabled={!card || isReviewed}
                onChange={(event) => setReviewChecks((state) => ({ ...state, disclaimerKept: event.target.checked }))}
              />
              <span>免责声明和复诊提醒保留</span>
            </label>
          </div>
          <div className="review-field-grid">
            <label>
              <span>审核医生</span>
              <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} disabled={isReviewed} />
            </label>
            <label>
              <span>审核备注</span>
              <textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} rows={3} disabled={isReviewed} />
            </label>
          </div>
          <button className="button primary" type="button" onClick={approveCard} disabled={!canApprove}>
            <CheckCircle2 size={17} /> 确认可用于沟通
          </button>
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
              <Tag tone={isReviewed ? 'green' : 'red'}>{isReviewed ? '医生已审核' : '需医生审核'}</Tag>
            </div>
            <p className="patient-main">
              {card?.plain_language_explanation || `医生待审核摘要：${summary}`}
            </p>
            <div className={`card-share-lock ${isReviewed ? 'unlocked' : ''}`}>
              {isReviewed ? <CheckCircle2 size={17} /> : <LockKeyhole size={17} />}
              <span>
                {isReviewed
                  ? `${card?.reviewer_name || reviewerName} 已确认，可打印或分享文案。`
                  : '打印和分享锁定，等待医生完成审核确认。'}
              </span>
            </div>
            <div className="card-info-grid">
              <InfoBlock title="这意味着什么" items={card?.what_it_means || ['内镜描述反映检查中看到的黏膜外观。', '部分表现需要结合病史和病理。']} />
              <InfoBlock title="需要关注什么" items={card?.what_to_watch || ['按医生要求复诊或进一步检查。', '症状变化时及时联系医疗机构。']} />
            </div>
            <div className="review-step-list">
              {reviewSteps.map((step) => (
                <div className={step.checked ? 'checked' : ''} key={step.label}>
                  <CheckCircle2 size={15} />
                  <span>{step.label}</span>
                  <em>{step.detail}</em>
                </div>
              ))}
            </div>
            <div className="next-card">{card?.follow_up_reminder || '请按照医生给出的复诊或检查安排执行。'}</div>
            <p className="disclaimer">{card?.disclaimer || '本卡片为医生审核前沟通草稿，不能替代医生解释。'}</p>
            <div className="card-actions">
              <button className="button secondary" type="button" onClick={printPreview} disabled={shareLocked}><Printer size={16} /> 打印预览</button>
              <button className="button secondary" type="button" onClick={shareCard} disabled={shareLocked}><Share2 size={16} /> 分享文案</button>
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

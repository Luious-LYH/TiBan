import { useEffect, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import { CheckCircle2, ImagePlus, LockKeyhole, Printer, Share2, Sparkles, WandSparkles } from 'lucide-react'
import { Card, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import type { KnowledgeBase, PatientCard as PatientCardType, Question } from '../lib/types'

type CardImageOption = {
  id: string
  imageUrl: string
  label: string
  dataset: string
  source: 'backend' | 'fallback'
}

const fallbackCardImages: CardImageOption[] = [
  {
    id: 'fallback_kvasir_01',
    imageUrl: '/assets/real_samples/kv_cla820gl0s3nv071u4fgd7xgq.jpg',
    label: '本地公开样例',
    dataset: 'fallback asset',
    source: 'fallback',
  },
  {
    id: 'fallback_x1_01',
    imageUrl: '/assets/real_samples/x1_clb0kvxvm90y4074yf50vf5nq.jpg',
    label: '本地公开样例',
    dataset: 'fallback asset',
    source: 'fallback',
  },
  {
    id: 'fallback_demo_01',
    imageUrl: '/assets/real_samples/endo_image_0.jpg',
    label: '本地公开样例',
    dataset: 'fallback asset',
    source: 'fallback',
  },
]

function realSamplesToCardImages(samples: Question[]): CardImageOption[] {
  const seen = new Set<string>()
  return samples
    .filter((sample) => sample.image_url && sample.image_url.startsWith('/assets/real_samples/'))
    .map((sample) => ({
      id: sample.id,
      imageUrl: sample.image_url || '',
      label: sample.title || sample.id,
      dataset: sample.source_dataset || 'public sample',
      source: 'backend' as const,
    }))
    .filter((sample) => {
      if (!sample.imageUrl || seen.has(sample.imageUrl)) return false
      seen.add(sample.imageUrl)
      return true
    })
    .slice(0, 6)
}

export function PatientCard() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const locationState = location.state as { reportSummary?: string; source?: string; summarySource?: 'judge_suggestion' | 'doctor_revision' } | null
  const incomingSummary = locationState?.reportSummary || searchParams.get('summary') || ''
  const isReportJudgeImport = locationState?.source === 'report_judge' && Boolean(locationState?.reportSummary?.trim())
  const isJudgeSuggestion = isReportJudgeImport && locationState?.summarySource !== 'doctor_revision'
  const defaultSummary = '胃窦黏膜炎症样改变，需结合完整报告和医生复核后用于患者解释。'
  const defaultStatus = '选择模板和图像后，可生成医生审核前科普卡片草稿。'
  const importedStatus = isReportJudgeImport
    ? '已接收报告修改训练摘要；请生成科普卡片草稿，并完成医生审核闸门。'
    : '已接收外部摘要；请生成科普卡片草稿，并完成医生审核闸门。'
  const importedReviewNotes = isReportJudgeImport
    ? `${isJudgeSuggestion ? '摘要来自报告修改训练评分后的安全改写' : '摘要来自报告修改训练中的医生修改稿'}，生成卡片后仍需逐项审核。`
    : '摘要来自外部入口，生成卡片后仍需医生审核。'
  const [summary, setSummary] = useState(() => incomingSummary || defaultSummary)
  const [templateId, setTemplateId] = useState('calm_blue')
  const [imageOptions, setImageOptions] = useState<CardImageOption[]>(fallbackCardImages)
  const [imageUrl, setImageUrl] = useState(fallbackCardImages[0].imageUrl)
  const [selectedImageId, setSelectedImageId] = useState(fallbackCardImages[0].id)
  const [imageSourceStatus, setImageSourceStatus] = useState('正在读取公开样例图像池...')
  const [card, setCard] = useState<PatientCardType | null>(null)
  const [knowledge, setKnowledge] = useState<KnowledgeBase | null>(null)
  const [cardStatus, setCardStatus] = useState(() => incomingSummary ? importedStatus : defaultStatus)
  const [uploadedImageName, setUploadedImageName] = useState('')
  const [reviewerName, setReviewerName] = useState('林知远医师')
  const [reviewNotes, setReviewNotes] = useState(() => incomingSummary ? importedReviewNotes : '摘要与报告训练输入一致，可作为患者沟通前说明草稿。')
  const [reviewChecks, setReviewChecks] = useState({
    summaryMatched: false,
    noUnsupportedClaim: false,
    disclaimerKept: false,
  })
  const [reviewing, setReviewing] = useState(false)

  useEffect(() => {
    api.cardKnowledge().then(setKnowledge)
  }, [])

  useEffect(() => {
    let cancelled = false
    api.realSamples()
      .then((samples) => {
        if (cancelled) return
        const options = realSamplesToCardImages(samples)
        if (options.length) {
          setImageOptions(options)
          setImageUrl((current) => {
            if (current.startsWith('blob:')) return current
            const currentStillAvailable = options.some((option) => option.imageUrl === current)
            return currentStillAvailable ? current : options[0].imageUrl
          })
          setSelectedImageId((current) => {
            if (current === 'local_upload') return current
            const currentStillAvailable = options.some((option) => option.id === current)
            return currentStillAvailable ? current : options[0].id
          })
          setImageSourceStatus(`已从 real_sample_knowledge.json 读取 ${options.length} 张公开教学样例；仅作医生审核前卡片配图，不代表自动诊断。`)
        } else {
          setImageOptions(fallbackCardImages)
          setImageSourceStatus('后端公开样例暂无可用图片，当前使用本地 fallback 公开样例资产。')
        }
      })
      .catch(() => {
        if (cancelled) return
        setImageOptions(fallbackCardImages)
        setImageSourceStatus('后端公开样例接口暂不可用，当前使用本地 fallback 公开样例资产。')
      })
    return () => {
      cancelled = true
    }
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
      const persistedImageUrl = imageUrl.startsWith('blob:') ? undefined : imageUrl
      const generated = await api.patientCard(summary, { templateId, imageUrl: persistedImageUrl })
      setCard(generated)
      setReviewChecks({ summaryMatched: false, noUnsupportedClaim: false, disclaimerKept: false })
      setCardStatus(
        imageUrl.startsWith('blob:')
          ? `已生成 ${generated.review_status === 'doctor_review_pending' ? '医生待审核' : '医生已审核'} 卡片草稿；本地上传图仅保留当前浏览器预览，不写入后端卡片记录。`
          : `已生成 ${generated.review_status === 'doctor_review_pending' ? '医生待审核' : '医生已审核'} 卡片草稿。`,
      )
    } catch {
      setCardStatus('卡片接口暂不可用，请稍后重试；当前仍保留本地预览草稿。')
    }
  }

  const approveCard = async () => {
    if (!canApprove || !card) return
    setReviewing(true)
    setCardStatus(`正在审核当前草稿 ${card.id}，不会重新生成新卡片...`)
    try {
      const reviewed = await api.approvePatientCard(card, {
        reviewerName,
        reviewNotes,
        reviewChecks,
      })
      setCard(reviewed)
      setCardStatus(`已由 ${reviewed.reviewer_name || reviewerName} 审核通过草稿 ${reviewed.id}；分享和打印已解锁，并写入审计日志。`)
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
    setSelectedImageId('local_upload')
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
  const selectedImageOption = imageOptions.find((item) => item.id === selectedImageId)
  const displayedCardImageUrl = card?.image_url || imageUrl
  const displayedImageOption = imageOptions.find((item) => item.imageUrl === displayedCardImageUrl)
  const displayedImageDataset = displayedImageOption?.dataset
    || (displayedCardImageUrl.startsWith('blob:') ? 'local_upload' : displayedCardImageUrl.startsWith('/assets/real_samples/') ? 'public_sample_unknown' : selectedImageOption?.dataset || 'public_sample')
  const reviewSteps = isReviewed && card?.review_steps?.length
    ? card.review_steps
    : [
        { label: '摘要来自医生确认的报告或训练输入', checked: Boolean(reviewChecks.summaryMatched), detail: '未确认前，卡片只能用于教学预览。' },
        { label: '未加入未提供的病理、治疗或疗效承诺', checked: Boolean(reviewChecks.noUnsupportedClaim), detail: '高风险医学表述保持解释性和复核边界。' },
        { label: '患者沟通前保留免责声明和复诊提醒', checked: Boolean(reviewChecks.disclaimerKept), detail: '卡片始终提示不替代医生面对面解释。' },
      ]
  const cardSourceTrace = card?.source_trace || []

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
          {isReportJudgeImport ? (
            <div className="report-card-source">
              <CheckCircle2 size={18} />
              <div>
                <strong>来源：报告修改训练</strong>
                <span>已带入{isJudgeSuggestion ? ' AI judge 建议改写摘要' : '医生修改稿摘要'}；分享/打印仍需医生完成审核清单。</span>
              </div>
            </div>
          ) : null}
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
            {imageOptions.map((item) => (
              <button
                key={item.id}
                className={item.id === selectedImageId && !uploadedImageName ? 'active' : ''}
                type="button"
                onClick={() => {
                  setImageUrl(item.imageUrl)
                  setSelectedImageId(item.id)
                  setUploadedImageName('')
                  markDraftDirty(`${item.source === 'backend' ? '已切换为后端公开样例' : '已切换为本地 fallback 样例'}：${item.label}。请重新生成草稿并完成医生审核。`)
                }}
                title={`${item.label} · ${item.dataset}`}
              >
                <img
                  src={item.imageUrl}
                  alt={`${item.label} 缩略图`}
                  data-real-sample-image={item.imageUrl.startsWith('/assets/real_samples/') ? 'true' : 'false'}
                  data-real-sample-role="thumbnail"
                  data-source-dataset={item.dataset}
                />
              </button>
            ))}
            <label className={`image-placeholder ${uploadedImageName ? 'active-upload' : ''}`} title="上传本地卡片图像">
              <input type="file" accept="image/*" onChange={onUploadImage} />
              <ImagePlus size={18} />
            </label>
          </div>
          <div className="card-image-source">
            <Tag tone={selectedImageOption?.source === 'backend' ? 'green' : 'amber'}>{selectedImageOption?.source === 'backend' ? 'backend sample' : uploadedImageName ? 'local preview' : 'fallback asset'}</Tag>
            <span>{uploadedImageName ? `本地上传：${uploadedImageName}` : selectedImageOption ? `${selectedImageOption.id} · ${selectedImageOption.dataset}` : '等待选择图像'}</span>
          </div>
          <div className="source-note">{imageSourceStatus}</div>
          {uploadedImageName ? <div className="source-note">本地上传预览：{uploadedImageName}。未接入受控上传前，该图片不会写入后端卡片记录。</div> : null}
          <button className="button primary" type="button" onClick={generate}>
            <WandSparkles size={17} /> 生成浮动科普卡片
          </button>
          <div className="card-status-line">{cardStatus}</div>
          {card ? (
            <div className={`card-generation-receipt ${card.audit_logged ? 'synced' : 'fallback'}`}>
              <div className="receipt-head">
                <CheckCircle2 size={18} />
                <div>
                  <strong>{card.audit_logged ? '后端草稿收据' : '本地预览收据'}</strong>
                  <span>{card.audit_logged ? '已写入 patient_card 审计；仍需医生审核后才可分享。' : '后端不可用时的前端预览；未写入审计。'}</span>
                </div>
              </div>
              <div className="receipt-metrics">
                <div><span>生成模式</span><strong>{card.generation_mode || card.api_source || 'rule'}</strong></div>
                <div><span>模板知识库</span><strong>{card.knowledge_base_id || '未连接'}</strong></div>
                <div><span>审计 ID</span><strong>{card.audit_log_id || '未写入'}</strong></div>
              </div>
              {cardSourceTrace.length ? (
                <div className="card-source-trace">
                  {cardSourceTrace.map((source) => (
                    <span className={source.used ? 'used' : ''} key={`${source.source_type}_${source.label}`}>
                      {source.label}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
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
            <img
              src={displayedCardImageUrl}
              alt="科普卡片使用的内镜示例图"
              data-real-sample-image={displayedCardImageUrl.startsWith('/assets/real_samples/') ? 'true' : 'false'}
              data-real-sample-role="primary"
              data-source-dataset={displayedImageDataset}
            />
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
                  ? `${card?.reviewer_name || reviewerName} 已确认 ${card?.id || '当前卡片'}，可打印或分享文案。`
                  : '打印和分享锁定，等待医生完成审核确认。'}
              </span>
            </div>
            {card ? (
              <div className="card-trace-row">
                <span>Card ID</span>
                <strong>{card.id}</strong>
                <em>{card.reviewed_at ? `审核时间 ${new Date(card.reviewed_at).toLocaleString()}` : '等待医生审核'}</em>
              </div>
            ) : null}
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

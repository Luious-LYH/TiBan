import { AlertTriangle, ArrowRight, Check, CheckCircle2, Download, FileText, LibraryBig, LoaderCircle, RotateCcw, Save, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { createQuestionImportBatch, deleteQuestionImportBatch, getDomains, getQuestionBanks, getQuestionImportBatch, getQuestionImportBatches, getQuestionImportTemplates, publishQuestionImportBatch, resolveApiUrl, reviewQuestionImportBatch, reviewQuestionImportDraft, uploadQuestionImage, validateQuestionBankImport } from '../../api/client'
import type { ImageAsset, QuestionBank, QuestionImageAssetRef, QuestionImportBatch, QuestionImportDraft, QBankValidation } from '../../api/client'

const formatLabels = { json: 'JSON', jsonl: 'JSONL', csv: 'CSV', markdown: 'Markdown' } as const
const visibleFormatKeys: Format[] = ['json', 'jsonl', 'csv', 'markdown']
const questionTypeLabels: Record<string, string> = { single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题', short_answer: '简答题' }
const reviewStatusLabels: Record<string, string> = { pending: '待审核', approved: '已通过', rejected: '已退回', published: '已入库' }
const maxQuestionBankUploadBytes = 10 * 1024 * 1024
type FactoryTab = 'generate' | 'review'
type Format = keyof typeof formatLabels

function readTextFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(reader.error)
    reader.onload = () => resolve(String(reader.result))
    reader.readAsText(file)
  })
}

export function FactoryStudio() {
  const [tab, setTab] = useState<FactoryTab>('generate')
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const batchesQuery = useQuery({ queryKey: ['question-import-batches'], queryFn: () => getQuestionImportBatches(), enabled: tab === 'review', staleTime: 5_000 })
  const selectedBatchQuery = useQuery({ queryKey: ['question-import-batch', selectedBatchId], queryFn: () => getQuestionImportBatch(selectedBatchId as string), enabled: tab === 'review' && Boolean(selectedBatchId) })

  function openReview(batchId?: string) {
    setTab('review')
    setSelectedBatchId(batchId ?? null)
  }

  async function removeBatch(batch: QuestionImportBatch) {
    if (!window.confirm(`确定删除“${batch.source_name}”的待审核记录吗？未发布的题目和审核进度都会删除。`)) return
    await deleteQuestionImportBatch(batch.batch_id)
    if (selectedBatchId === batch.batch_id) setSelectedBatchId(null)
    await queryClient.invalidateQueries({ queryKey: ['question-import-batches'] })
  }

  return <section className="factory-workspace" data-testid="factory-studio">
    <header className="factory-header"><div><h1>题库生成</h1><p>上传题目资料 → 审核题目 → 发布为新题库或补充到已有题库。</p></div></header>
    <div className="factory-tabs" role="tablist" aria-label="题库生成工作区"><button type="button" role="tab" aria-selected={tab === 'generate'} onClick={() => setTab('generate')}><LibraryBig size={15} />题库生成</button><button type="button" role="tab" aria-selected={tab === 'review'} onClick={() => setTab('review')}><CheckCircle2 size={15} />待审核题库{batchesQuery.data?.filter((item) => item.pending_count > 0).length ? <b>{batchesQuery.data.filter((item) => item.pending_count > 0).length}</b> : null}</button></div>
    {tab === 'generate' ? <GeneratePanel onCreated={(batch) => openReview(batch.batch_id)} /> : <ReviewCenter batches={batchesQuery.data ?? []} batchesLoading={batchesQuery.isPending} batchesError={batchesQuery.error as Error | null} selectedBatchId={selectedBatchId} selectedBatch={selectedBatchQuery.data ?? null} detailLoading={selectedBatchQuery.isPending} onSelect={setSelectedBatchId} onRetry={() => void batchesQuery.refetch()} onDelete={(batch) => void removeBatch(batch)} onCreated={() => void queryClient.invalidateQueries({ queryKey: ['question-import-batches'] })} />}
  </section>
}

function GeneratePanel({ onCreated }: { onCreated: (batch: QuestionImportBatch) => void }) {
  const [format, setFormat] = useState<Format>('json')
  const [content, setContent] = useState('')
  const [fileName, setFileName] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [imageAssets, setImageAssets] = useState<QuestionImageAssetRef[]>([])
  const [domainName, setDomainName] = useState('通用科学')
  const [domainEdited, setDomainEdited] = useState(false)
  const [validation, setValidation] = useState<QBankValidation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const domainsQuery = useQuery({ queryKey: ['domains'], queryFn: getDomains, staleTime: 5 * 60 * 1000 })
  const templatesQuery = useQuery({ queryKey: ['question-import-templates'], queryFn: getQuestionImportTemplates, staleTime: Infinity })

  function resetPreview() { setValidation(null); setError(null) }

  async function chooseFiles(fileList?: FileList) {
    const files = Array.from(fileList ?? [])
    const file = files.find((candidate) => /\.(jsonl?|csv|md|markdown)$/i.test(candidate.name))
    if (!file) { setError('请选择一份 JSON、JSONL、CSV 或 Markdown 题目文件。'); return }
    if (file.size > maxQuestionBankUploadBytes) { setError('题库文件不能超过 10 MiB。'); return }
    const imageFiles = files.filter((candidate) => candidate !== file)
    if (imageFiles.some((candidate) => !candidate.type.startsWith('image/'))) { setError('除题目文件外，只能同时选择图片文件。'); return }
    try {
      setBusy(true)
      const suffix = file.name.split('.').pop()?.toLowerCase()
      const detected: Format = suffix === 'json' ? 'json' : suffix === 'jsonl' ? 'jsonl' : suffix === 'csv' ? 'csv' : 'markdown'
      const uploaded = await Promise.all(imageFiles.map((image) => uploadQuestionImage(image)))
      setContent(await readTextFile(file)); setFileName(file.name); setSourceName((current) => current || file.name.replace(/\.[^.]+$/, '')); setFormat(detected); setImageAssets(uploaded.map(toImageAssetRef)); resetPreview()
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function validate() {
    setBusy(true); setError(null)
    try { setValidation(await validateQuestionBankImport({ format, content, source_name: sourceName || '个人导入题库', image_assets: imageAssets })) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function createBatch() {
    if (!validation?.accepted_count) return
    const normalizedDomainName = domainName.trim()
    if (!normalizedDomainName) { setError('请填写学习领域名称。'); return }
    const selectedDomain = domainOptions.find((domain) => domain.display_name.trim() === normalizedDomainName || domain.domain_id === normalizedDomainName)
    setBusy(true); setError(null)
    try { onCreated(await createQuestionImportBatch({ format, content, domain_id: selectedDomain?.domain_id ?? 'general_science', custom_domain_name: selectedDomain ? undefined : normalizedDomainName, source_name: sourceName.trim() || '个人导入题库', file_name: fileName || undefined, image_assets: imageAssets })) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  function downloadTemplate(templateFormat: Format) {
    const value = templatesQuery.data?.examples[templateFormat]
    if (!value) return
    const extension = templateFormat === 'markdown' ? 'md' : templateFormat
    const downloadValue = templateFormat === 'csv' ? `\uFEFF${value}` : value
    const url = URL.createObjectURL(new Blob([downloadValue], { type: templateFormat === 'csv' ? 'text/csv;charset=utf-8' : 'text/plain;charset=utf-8' }))
    const link = document.createElement('a'); link.href = url; link.download = `tiban-question-template.${extension}`; link.click(); URL.revokeObjectURL(url)
  }

  const domainOptions = domainsQuery.data ?? []
  return <section className="factory-panel qbank-generate-panel"><div className="factory-panel-heading"><div><span className="factory-eyebrow">01 · 生成待审核题目</span><h2>把常见题目文件变成可刷题的题库</h2><p>上传题目文件后先校验预览，再逐题审核并发布。</p></div></div><div className="factory-flow"><span className="is-current"><i>1</i>上传文件</span><span><i>2</i>预览校验</span><span><i>3</i>进入审核</span><span><i>4</i>发布题库</span></div><div className="qbank-source-grid"><label className="qbank-file-drop"><span className="qbank-field-label">题目文件与图片</span><span className="qbank-file-drop-inner"><FileText size={20} /><strong>{fileName || '选择 JSON / JSONL / CSV / Markdown'}</strong><small>可同时选择题目文件和对应图片；题目中的图片字段填写相对文件名</small><input aria-label="选择题目文件和图片" type="file" multiple accept=".json,.jsonl,.csv,.md,.markdown,application/json,text/csv,text/markdown,image/png,image/jpeg,image/webp" onChange={(event) => { if (event.target.files) void chooseFiles(event.target.files) }} /></span>{imageAssets.length > 0 && <em className="qbank-image-count">已附加 {imageAssets.length} 张图片</em>}</label><label><span className="qbank-field-label">文件格式</span><select value={format} onChange={(event) => { setFormat(event.target.value as Format); resetPreview() }}>{visibleFormatKeys.map((key) => <option key={key} value={key}>{formatLabels[key]}</option>)}</select></label><label><span className="qbank-field-label">资料名称 <small>用于审核记录</small></span><input value={sourceName} onChange={(event) => { setSourceName(event.target.value); resetPreview() }} placeholder="例如：Python 基础练习" maxLength={120} /></label><label><span className="qbank-field-label">学习领域</span><input className={`qbank-domain-input${domainEdited ? '' : ' is-default'}`} aria-label="学习领域" value={domainName} onFocus={(event) => { if (!domainEdited) event.currentTarget.select() }} onChange={(event) => { setDomainName(event.target.value); setDomainEdited(true); resetPreview() }} placeholder="通用科学" maxLength={48} /></label><label className="qbank-content-field"><span className="qbank-field-label">题目内容 <small>支持批量题目</small></span><textarea value={content} onChange={(event) => { setContent(event.target.value); resetPreview() }} placeholder={format === 'markdown' ? '## 题目标题\n题型: 单选\n- [x] 正确选项\n- [ ] 其他选项' : '每道题至少包含 question、question_type、answer；选择题再提供 options'} rows={9} spellCheck={false} /></label></div><div className="qbank-template-bar"><div><strong>题目文件参考</strong><span>题干 · 题型 · 选项 · 答案 · 解析 · 图片（可选）</span><small>下载示例查看字段写法；系统会兼容常见中英文表头和选项格式。</small></div><div className="qbank-template-actions">{visibleFormatKeys.map((item) => <button type="button" key={item} onClick={() => downloadTemplate(item)} disabled={templatesQuery.isPending}><Download size={13} />{formatLabels[item]} 模板</button>)}</div></div><div className="factory-panel-actions"><button className="factory-secondary" type="button" disabled={!content.trim() || busy} onClick={() => void validate()}>{busy && !validation ? <LoaderCircle className="s1-spin" size={16} /> : <Check size={16} />}校验并预览</button>{validation?.accepted_count ? <button className="factory-primary" type="button" disabled={busy} onClick={() => void createBatch()}>{busy ? <LoaderCircle className="s1-spin" size={16} /> : <ArrowRight size={16} />}生成审核批次（{validation.accepted_count} 题）</button> : null}</div>{error && <p className="factory-error" role="alert">{error}</p>}{validation && <ValidationPreview result={validation} />}</section>
}

function ValidationPreview({ result }: { result: QBankValidation }) {
  const [filter, setFilter] = useState<'all' | 'single_choice' | 'multiple_choice' | 'true_false' | 'short_answer'>('all')
  const [page, setPage] = useState(1)
  const typeCounts = result.summary.question_type_counts
  const filteredItems = filter === 'all' ? result.items : result.items.filter((item) => item.question_type === filter)
  const pageSize = 12
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / pageSize))
  const currentPage = Math.min(page, pageCount)
  const visibleItems = filteredItems.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  const setFilterAndReset = (nextFilter: typeof filter) => { setFilter(nextFilter); setPage(1) }
  const filterOptions = (['all', 'single_choice', 'multiple_choice', 'true_false', 'short_answer'] as const).filter((key) => key === 'all' || (typeCounts[key] ?? 0) > 0)
  return <div className="qbank-validation"><div className="qbank-validation-summary"><CheckCircle2 size={17} /><strong>已识别 {result.accepted_count} 道题</strong><span>{result.rejected_count ? `另有 ${result.rejected_count} 行需要修正，生成时会跳过。` : '格式校验通过，可以进入审核。'}</span></div>{result.items.length ? <><div className="qbank-preview-toolbar"><div><strong>题目预览</strong><small>当前显示 {visibleItems.length} / {filteredItems.length} 道</small></div><div className="qbank-preview-filters" role="tablist" aria-label="按题型筛选">{filterOptions.map((key) => <button type="button" role="tab" aria-selected={filter === key} key={key} onClick={() => setFilterAndReset(key)}>{key === 'all' ? '全部' : questionTypeLabels[key]} <b>{key === 'all' ? result.items.length : typeCounts[key] ?? 0}</b></button>)}</div></div><div className="qbank-preview-cards">{visibleItems.map((item, index) => <QuestionPreview key={`${item.title}-${item.question}-${index}`} item={item} index={(currentPage - 1) * pageSize + index} />)}</div>{pageCount > 1 ? <div className="qbank-preview-pagination"><small>第 {currentPage} / {pageCount} 页</small><div><button type="button" disabled={currentPage === 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>上一页</button><button type="button" disabled={currentPage === pageCount} onClick={() => setPage((value) => Math.min(pageCount, value + 1))}>下一页</button></div></div> : null}</> : null}{result.issues.length ? <div className="qbank-issues"><div><AlertTriangle size={15} /><strong>需要留意的内容</strong></div><ul>{result.issues.map((item, index) => <li key={`${item.row}-${item.code}-${index}`}>第 {item.row || '文件'} 行：{item.message}</li>)}</ul></div> : null}</div>
}

function QuestionPreview({ item, index }: { item: QBankValidation['items'][number]; index: number }) {
  return <article className="qbank-preview-card"><header><span>{String(index + 1).padStart(2, '0')}</span><small>{questionTypeLabels[item.question_type] ?? item.question_type}{item.body_part ? ` · ${item.body_part}` : ''}</small></header>{item.image_url && <img className="qbank-question-image" src={resolveApiUrl(item.image_url)} alt={item.image_alt ?? '题目图片'} /> }<h3>{item.question || item.title}</h3>{item.question_type === 'true_false' ? <ol className="qbank-preview-boolean"><li><b>T</b>正确</li><li><b>F</b>错误</li></ol> : item.options?.length ? <ol>{item.options.map((option, optionIndex) => <li key={option.id}><b>{String.fromCharCode(65 + optionIndex)}</b>{option.text}</li>)}</ol> : <p className="qbank-preview-no-options">非选择题 · 将按导入答案进行审核</p>}</article>
}

function toImageAssetRef(asset: ImageAsset): QuestionImageAssetRef { return { asset_id: asset.asset_id, filename: asset.filename } }

function ReviewCenter({ batches, batchesLoading, batchesError, selectedBatchId, selectedBatch, detailLoading, onSelect, onRetry, onDelete, onCreated }: { batches: QuestionImportBatch[]; batchesLoading: boolean; batchesError: Error | null; selectedBatchId: string | null; selectedBatch: QuestionImportBatch | null; detailLoading: boolean; onSelect: (batchId: string) => void; onRetry: () => void; onDelete: (batch: QuestionImportBatch) => void; onCreated: () => void }) {
  return <section className="factory-review-shell"><div className="factory-panel-heading"><div><span className="factory-eyebrow">02 · 持久化审核工作区</span><h2>待审核题库</h2><p>每次生成都会保留在这里。你可以先审核一部分，稍后回来继续；审核通过后再决定保存到哪里。</p></div><span className="factory-panel-icon"><CheckCircle2 size={22} /></span></div>{batchesError ? <div className="factory-error" role="alert">待审核题库读取失败：{batchesError.message}<button type="button" onClick={onRetry}>重试</button></div> : null}{batchesLoading ? <div className="factory-empty"><LoaderCircle className="s1-spin" size={18} />正在读取审核记录…</div> : batches.length === 0 ? <div className="factory-empty"><LibraryBig size={21} /><strong>还没有待审核题库</strong><span>上传一份 JSON、JSONL、CSV 或 Markdown 题目文件，就会在这里生成可持续审核的题库批次。</span></div> : <div className="factory-review-layout"><aside className="factory-batch-list"><div className="factory-batch-list-heading"><strong>审核记录</strong><span>{batches.length} 批</span></div>{batches.map((batch) => <article key={batch.batch_id} className={batch.batch_id === selectedBatchId ? 'is-selected' : ''}><button type="button" onClick={() => onSelect(batch.batch_id)}><span className="factory-batch-icon"><FileText size={16} /></span><span className="factory-batch-copy"><strong>{batch.source_name}</strong><small>{batch.file_name || formatLabels[batch.format as Format]} · {batch.total_count} 题</small><em>{batch.pending_count ? `待审核 ${batch.pending_count} 题` : batch.status === 'published' ? '已全部入库' : '审核已完成'}</em></span></button><button className="factory-icon-button is-danger" type="button" title="删除审核记录" aria-label={`删除 ${batch.source_name}`} onClick={() => onDelete(batch)}><Trash2 size={14} /></button></article>)}</aside><main className="factory-review-detail">{!selectedBatchId ? <div className="factory-empty"><CheckCircle2 size={22} /><strong>选择一批题目开始审核</strong><span>左侧记录会显示每一批题目的审核进度。</span></div> : detailLoading || !selectedBatch ? <div className="factory-empty"><LoaderCircle className="s1-spin" size={18} />正在读取题目…</div> : <ReviewBatch key={selectedBatch.batch_id} batch={selectedBatch} onUpdated={onCreated} />}</main></div>}</section>
}

function ReviewBatch({ batch, onUpdated }: { batch: QuestionImportBatch; onUpdated: () => void }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('pending')
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [publishMode, setPublishMode] = useState<'create_bank' | 'append_questions'>('create_bank')
  const [bankName, setBankName] = useState('')
  const [bankDescription, setBankDescription] = useState('')
  const [targetBankId, setTargetBankId] = useState('')
  const [publishedBankId, setPublishedBankId] = useState<string | null>(batch.published_bank_id ?? null)
  const [publishedCount, setPublishedCount] = useState(batch.published_count)
  const banksQuery = useQuery({ queryKey: ['question-banks', 'factory-review'], queryFn: () => getQuestionBanks(), enabled: publishMode === 'append_questions' })
  const items = useMemo(() => batch.items ?? [], [batch.items])
  const filteredItems = useMemo(() => filter === 'all' ? items : items.filter((item) => item.status === filter), [filter, items])
  const current = filteredItems.find((item) => item.draft_id === currentId) ?? filteredItems[0] ?? null

  async function updateDraft(status: 'pending' | 'approved' | 'rejected') {
    if (!current) return
    setSaving(true); setError(null)
    try { const next = await reviewQuestionImportDraft(batch.batch_id, current.draft_id, status); await queryClient.setQueryData(['question-import-batch', batch.batch_id], next); await queryClient.invalidateQueries({ queryKey: ['question-import-batches'] }); setCurrentId((next.items ?? []).find((item) => item.status === 'pending')?.draft_id ?? (next.items ?? []).find((item) => item.status === 'approved')?.draft_id ?? null); onUpdated() } catch (reason) { setError((reason as Error).message) } finally { setSaving(false) }
  }

  async function approveAllPending() {
    const pendingIds = items.filter((item) => item.status === 'pending').map((item) => item.draft_id)
    if (!pendingIds.length) return
    setSaving(true); setError(null)
    try { const next = await reviewQuestionImportBatch(batch.batch_id, 'approved', pendingIds); await queryClient.setQueryData(['question-import-batch', batch.batch_id], next); await queryClient.invalidateQueries({ queryKey: ['question-import-batches'] }); onUpdated() } catch (reason) { setError((reason as Error).message) } finally { setSaving(false) }
  }

  async function publish() {
    setSaving(true); setError(null)
    try { const result = await publishQuestionImportBatch(batch.batch_id, { mode: publishMode, bank_name: publishMode === 'create_bank' && !publishedBankId ? bankName.trim() : undefined, bank_description: publishMode === 'create_bank' && !publishedBankId ? bankDescription.trim() || undefined : undefined, target_bank_id: publishMode === 'append_questions' && !publishedBankId ? targetBankId : publishedBankId ?? undefined }); setPublishedBankId(result.bank_id); setPublishedCount(result.published_count); await queryClient.invalidateQueries({ queryKey: ['question-import-batch', batch.batch_id] }); await queryClient.invalidateQueries({ queryKey: ['question-import-batches'] }); await queryClient.invalidateQueries({ queryKey: ['question-banks'] }); onUpdated() } catch (reason) { setError((reason as Error).message) } finally { setSaving(false) }
  }

  const publishDisabled = saving || batch.approved_count === 0 || (publishMode === 'create_bank' && !publishedBankId && !bankName.trim()) || (publishMode === 'append_questions' && !publishedBankId && !targetBankId)
  return <div className="factory-review-workspace"><header className="factory-review-heading"><div><span className="factory-eyebrow">{batch.file_name || formatLabels[batch.format as Format]}</span><h3>{batch.source_name}</h3><p>已通过 {batch.approved_count} · 待审核 {batch.pending_count} · 已退回 {batch.rejected_count} · 已入库 {batch.published_count}</p></div><span className="factory-review-progress"><b>{batch.total_count ? Math.round(((batch.approved_count + batch.rejected_count + batch.published_count) / batch.total_count) * 100) : 0}%</b><small>审核进度</small></span></header><div className="factory-review-toolbar"><div className="factory-review-filters" role="tablist" aria-label="审核状态筛选">{([['pending', '待审核', batch.pending_count], ['approved', '已通过', batch.approved_count], ['rejected', '已退回', batch.rejected_count], ['all', '全部', batch.total_count]] as const).map(([key, label, count]) => <button type="button" role="tab" aria-selected={filter === key} key={key} onClick={() => setFilter(key)}>{label} <b>{count}</b></button>)}</div><button type="button" className="factory-batch-action" disabled={saving || !batch.pending_count} onClick={() => void approveAllPending()}><Check size={14} />批量通过待审核题目</button></div>{error && <p className="factory-error" role="alert">{error}</p>}<div className="factory-review-body">{filteredItems.length === 0 ? <div className="factory-empty factory-empty-inline"><CheckCircle2 size={21} /><strong>{filter === 'pending' ? '这批题目已经审核完了' : '当前筛选没有题目'}</strong><span>可以切换状态查看，或在下方发布已通过题目。</span></div> : <><nav className="factory-question-list" aria-label="审核题目列表">{filteredItems.map((item) => <button type="button" key={item.draft_id} className={item.draft_id === current?.draft_id ? 'is-selected' : ''} onClick={() => setCurrentId(item.draft_id)}><span>{String(item.ordinal).padStart(2, '0')}</span><div><strong>{item.title}</strong><small>{questionTypeLabels[item.question_type] ?? item.question_type}</small></div><em className={`is-${item.status}`}>{reviewStatusLabels[item.status]}</em></button>)}</nav><div className="factory-question-review">{current ? <ReviewQuestionCard draft={current} saving={saving} onReview={(status) => void updateDraft(status)} /> : null}</div></>}</div><PublishPanel mode={publishMode} setMode={setPublishMode} bankName={bankName} setBankName={setBankName} bankDescription={bankDescription} setBankDescription={setBankDescription} targetBankId={targetBankId} setTargetBankId={setTargetBankId} banks={banksQuery.data ?? []} publishedBankId={publishedBankId} approvedCount={batch.approved_count} publishedCount={publishedCount} disabled={publishDisabled} saving={saving} onPublish={() => void publish()} onOpenBank={() => { if (publishedBankId) navigate(`/banks/${encodeURIComponent(publishedBankId)}`) }} /></div>
}

function ReviewQuestionCard({ draft, saving, onReview }: { draft: QuestionImportDraft; saving: boolean; onReview: (status: 'pending' | 'approved' | 'rejected') => void }) {
  const selected = (index: number) => draft.question_type === 'true_false' ? (index === 0 ? draft.answer_key === true : draft.answer_key === false) : String(draft.answer_key) === String(index) || (Array.isArray(draft.answer_key) && draft.answer_key.includes(index))
  return <article className="factory-question-card"><header><div><span className="factory-eyebrow">第 {draft.ordinal} 题 · {questionTypeLabels[draft.question_type] ?? draft.question_type}</span></div><span className={`factory-status-pill is-${draft.status}`}>{reviewStatusLabels[draft.status]}</span></header>{draft.image_url && <img className="factory-question-image" src={resolveApiUrl(draft.image_url)} alt={draft.image_alt ?? '题目图片'} />}<p className="factory-question-stem">{draft.question}</p>{draft.question_type === 'true_false' ? <ol className="factory-question-options factory-boolean-options"><li className={selected(0) ? 'is-answer' : ''}><b>T</b><span>正确</span>{selected(0) ? <Check size={15} /> : null}</li><li className={selected(1) ? 'is-answer' : ''}><b>F</b><span>错误</span>{selected(1) ? <Check size={15} /> : null}</li></ol> : draft.options?.length ? <ol className="factory-question-options">{draft.options.map((option, index) => <li key={option.id} className={selected(index) ? 'is-answer' : ''}><b>{String.fromCharCode(65 + index)}</b><span>{option.text}</span>{selected(index) ? <Check size={15} /> : null}</li>)}</ol> : <div className="factory-short-answer"><span>参考答案</span><strong>{draft.answer}</strong></div>}<div className="factory-question-meta"><span>难度 · {draft.difficulty === 'easy' ? '简单' : draft.difficulty === 'hard' ? '困难' : '中等'}</span><span>来源 · {draft.source_dataset}</span>{draft.body_part ? <span>分类 · {draft.body_part}</span> : null}</div><details className="factory-explanation"><summary>查看解析与导入答案</summary><p>{draft.explanation || '暂无解析'}</p><small>参考答案：{draft.answer}</small></details><footer className="factory-question-actions">{draft.status !== 'pending' && draft.status !== 'published' ? <button className="factory-secondary" type="button" disabled={saving} onClick={() => onReview('pending')}><RotateCcw size={14} />改回待审核</button> : null}<button className="factory-reject-button" type="button" disabled={saving || draft.status === 'published'} onClick={() => onReview('rejected')}><X size={15} />退回</button><button className="factory-primary" type="button" disabled={saving || draft.status === 'published'} onClick={() => onReview('approved')}>{saving ? <LoaderCircle className="s1-spin" size={15} /> : <Check size={15} />}审核通过</button></footer></article>
}

function PublishPanel({ mode, setMode, bankName, setBankName, bankDescription, setBankDescription, targetBankId, setTargetBankId, banks, publishedBankId, approvedCount, publishedCount, disabled, saving, onPublish, onOpenBank }: { mode: 'create_bank' | 'append_questions'; setMode: (mode: 'create_bank' | 'append_questions') => void; bankName: string; setBankName: (value: string) => void; bankDescription: string; setBankDescription: (value: string) => void; targetBankId: string; setTargetBankId: (value: string) => void; banks: QuestionBank[]; publishedBankId: string | null; approvedCount: number; publishedCount: number; disabled: boolean; saving: boolean; onPublish: () => void; onOpenBank: () => void }) {
  return <section className="factory-publish-panel"><header><div><span className="factory-eyebrow">审核通过后</span><h4>发布到题库</h4><p>{publishedBankId ? '审核通过的题目会继续进入已选题库。' : '选择创建新题库，或补充到已有题库。未审核和退回的题目不会写入。'}</p></div><Save size={19} /></header>{publishedBankId ? <div className="factory-published-target"><div className="factory-published-copy"><CheckCircle2 size={17} /><div><span>已发布 {publishedCount} 题</span><small>{approvedCount ? `还有 ${approvedCount} 道已通过题目等待发布。` : '当前没有新的已通过题目。'}</small></div></div><div className="factory-published-actions"><button className="factory-primary" type="button" disabled={disabled} onClick={onPublish}>{saving ? <LoaderCircle className="s1-spin" size={16} /> : <Save size={16} />}继续发布新通过题目</button><button type="button" onClick={onOpenBank}>打开题库 <ArrowRight size={14} /></button></div></div> : <><div className="factory-publish-mode"><button type="button" className={mode === 'create_bank' ? 'is-selected' : ''} onClick={() => setMode('create_bank')}>新建题库</button><button type="button" className={mode === 'append_questions' ? 'is-selected' : ''} onClick={() => setMode('append_questions')}>补充已有题库</button></div>{mode === 'create_bank' ? <div className="factory-publish-fields"><label><span>题库名称 <b>*</b></span><input value={bankName} onChange={(event) => setBankName(event.target.value)} placeholder="例如：Python 基础练习" maxLength={200} /></label><label><span>题库说明 <small>可选</small></span><input value={bankDescription} onChange={(event) => setBankDescription(event.target.value)} placeholder="这个题库适合什么学习目标？" maxLength={1000} /></label></div> : <label className="factory-publish-target"><span>选择已有题库 <b>*</b></span><select value={targetBankId} onChange={(event) => setTargetBankId(event.target.value)} disabled={!banks.length}><option value="">请选择题库</option>{banks.map((bank) => <option value={bank.bank_id} key={bank.bank_id}>{bank.name} · {bank.question_count} 题</option>)}</select></label>}<button className="factory-primary factory-publish-button" type="button" disabled={disabled} onClick={onPublish}>{saving ? <LoaderCircle className="s1-spin" size={16} /> : <Save size={16} />}发布已通过题目</button></>}</section>
}

import { ChevronDown, FileUp, LoaderCircle, Play, Send } from 'lucide-react'
import { useEffect, useState } from 'react'

import { createFactoryJob, getFactoryJob, publishFactoryRevision, uploadFactoryDocument, validateQuestionBankImport } from '../../api/client'
import type { FactoryJob } from '../../api/client'
import { EvidencePreview } from './EvidencePreview'
import { FactoryStepper } from './FactoryStepper'

const factoryStatusLabels: Record<string, string> = { queued: '等待开始', parsing: '正在解析资料', indexing: '正在整理资料', generating: '正在生成题目', judging: '正在检查草稿', repairing: '正在修订草稿', ready_for_review: '等待审核', published: '已入库', failed: '生成失败' }
const factoryStatusLabel = (status: string) => factoryStatusLabels[status] ?? '正在处理'
const maxFactoryUploadBytes = 5 * 1024 * 1024
function readFile(file: File): Promise<string> { return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(reader.error); reader.onload = () => resolve(String(reader.result).split(',')[1] ?? ''); reader.readAsDataURL(file) }) }

export function FactoryStudio() {
  const [tab, setTab] = useState<'import' | 'generate'>('import')
  const [file, setFile] = useState<File | null>(null)
  const [job, setJob] = useState<FactoryJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [published, setPublished] = useState<string | null>(null)
  useEffect(() => { if (!job || !['queued', 'running', 'retrying'].includes(job.status)) return; const timer = window.setInterval(() => { void getFactoryJob(job.job_id).then(setJob).catch((reason: Error) => setError(reason.message)) }, 1200); return () => window.clearInterval(timer) }, [job])
  async function start() { if (!file) return; if (file.size > maxFactoryUploadBytes) { setError('资料超过 5 MiB，当前资料生成链路不支持上传。请拆分文档后重试。'); return } setBusy(true); setError(null); setPublished(null); try { const document = await uploadFactoryDocument(file.name, await readFile(file), file.type || undefined); const created = await createFactoryJob(document.document_id); setJob(await getFactoryJob(created.job_id)) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) } }
  async function publish() { const revision = job?.revisions.find((item) => item.status === 'ready_for_review'); if (!job || !revision) return; setBusy(true); setError(null); try { const result = await publishFactoryRevision(job.job_id, revision.revision_id); setPublished(result.question_id); setJob(await getFactoryJob(job.job_id)) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) } }

  return <section className={`factory-workspace ${job ? 'has-job' : ''}`} data-testid="factory-studio">
    <header className="factory-header"><div><h1>题库导入</h1><p>先校验已有题目，或从教学资料生成可审核的题目草稿。</p></div>{job && <span>{factoryStatusLabel(job.stage)}</span>}</header>
    {!job && <><div className="factory-tabs" role="tablist"><button type="button" role="tab" aria-selected={tab === 'import'} onClick={() => setTab('import')}>导入已有题目</button><button type="button" role="tab" aria-selected={tab === 'generate'} onClick={() => setTab('generate')}>从资料生成题目</button></div>{tab === 'import' ? <ExistingQuestionImport /> : <section className="factory-upload"><FileUp size={22} /><div><strong>从资料生成题目</strong><p>支持 .md / .pdf，单个文件不超过 5 MiB；生成后先审核再入库。</p></div><label><span>{file?.name ?? '选择资料'}</span><input aria-label="上传教学资料" type="file" accept=".md,.pdf,text/markdown,application/pdf" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setError(null) }} /></label><button className="factory-primary" data-testid="factory-generate" disabled={!file || busy} onClick={() => void start()}>{busy ? <LoaderCircle className="s1-spin" size={16} /> : <Play size={16} />}上传并生成</button></section>}</>}
    {error && <div className="factory-error" role="alert">{error}</div>}
    {job && <div className="factory-job-layout"><section className="factory-job-summary"><strong>当前任务</strong><span>{job.progress}% · 第 {Math.max(1, job.attempt)} 次执行</span><FactoryStepper stage={job.stage} />{job.error_message && <div className="factory-error">{job.error_message}</div>}<details><summary>展开执行详情 <ChevronDown size={14} /></summary><div>{job.detail.events?.map((event) => <span key={`${event.at}-${event.status}`}>{factoryStatusLabel(event.status)}</span>)}</div></details></section><section className="factory-drafts"><div className="factory-drafts-heading"><strong>题目草稿</strong><span>{job.revisions.length} 个版本</span></div>{job.revisions.map((revision) => <article key={revision.revision_id}><div><strong>{revision.parent_revision_id ? '修订草稿' : '初始草稿'}</strong><span>{factoryStatusLabel(revision.status)}</span></div><p>{revision.draft.stem}</p><small>内容检查：{revision.judge.passed ? '符合要求' : '需人工确认'}</small>{visibleRewriteInstruction(revision.rewrite_instruction) && <small>修改建议：{visibleRewriteInstruction(revision.rewrite_instruction)}</small>}<EvidencePreview sourceChunkIds={revision.source_chunk_ids ?? []} /></article>)}{job.stage === 'ready_for_review' && <button className="factory-primary" data-testid="factory-publish" disabled={busy} onClick={() => void publish()}><Send size={16} />发布到题库</button>}{published && <p className="factory-published">题目已发布，可在题库中开始练习。</p>}</section></div>}
  </section>
}

function visibleRewriteInstruction(value?: string | null) {
  if (!value || /医生复核|独立诊断|教学边界|免责声明/.test(value)) return null
  return value
}

function ExistingQuestionImport() {
  const [format, setFormat] = useState<'csv' | 'jsonl' | 'markdown'>('csv')
  const [content, setContent] = useState('')
  const [result, setResult] = useState<Awaited<ReturnType<typeof validateQuestionBankImport>> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  async function choose(file?: File) { if (!file) return; setContent(await file.text()); setResult(null); setError(null); const suffix = file.name.split('.').pop()?.toLowerCase(); if (suffix === 'jsonl' || suffix === 'csv' || suffix === 'md') setFormat(suffix === 'md' ? 'markdown' : suffix) }
  async function validate() { setChecking(true); setError(null); try { setResult(await validateQuestionBankImport({ format, content, source_name: '个人导入题库' })) } catch (reason) { setError((reason as Error).message) } finally { setChecking(false) } }
  return <section className="qbank-import"><div><strong>导入已有题目</strong><p>支持 CSV、JSONL、Markdown。当前链路会真实校验并预览；批量写入题库仍在后续版本，不会伪造“导入成功”。</p></div><div className="qbank-import-controls"><label>格式<select value={format} onChange={(event) => setFormat(event.target.value as typeof format)}><option value="csv">CSV</option><option value="jsonl">JSONL</option><option value="markdown">Markdown</option></select></label><label className="qbank-file">选择题库文件<input aria-label="选择题库文件" type="file" accept=".csv,.jsonl,.md,text/csv,application/json,text/markdown" onChange={(event) => void choose(event.target.files?.[0])} /></label><button className="factory-primary" type="button" disabled={!content.trim() || checking} onClick={() => void validate()}>{checking ? '正在校验…' : '校验并预览'}</button></div>{error && <p className="factory-error" role="alert">{error}</p>}{result && <div className="qbank-validation"><strong>校验结果：{result.accepted_count} 道可用，{result.rejected_count} 条问题</strong>{result.items.length > 0 && <ul>{result.items.map((item, index) => <li key={`${item.title}-${index}`}>{item.question_type} · {item.title}</li>)}</ul>}{result.issues.length > 0 && <ul className="is-errors">{result.issues.map((item) => <li key={`${item.row}-${item.code}`}>第 {item.row} 行：{item.message}</li>)}</ul>}</div>}</section>
}

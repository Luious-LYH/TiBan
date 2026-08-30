import { FileUp, LoaderCircle, Play, Send, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'

import { createFactoryJob, getFactoryJob, publishFactoryRevision, uploadFactoryDocument } from '../../api/client'
import type { FactoryJob } from '../../api/client'

const factoryStatusLabels: Record<string, string> = {
  queued: '等待生成',
  parsing: '正在读取资料',
  indexing: '正在整理资料',
  generating: '正在生成题目',
  judging: '正在检查题目',
  repairing: '正在优化草稿',
  ready_for_review: '待你审核',
  published: '已发布',
  failed: '生成失败',
}

function factoryStatusLabel(status: string) {
  return factoryStatusLabels[status] ?? '正在处理'
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(reader.error); reader.onload = () => resolve(String(reader.result).split(',')[1] ?? ''); reader.readAsDataURL(file) })
}

export function FactoryStudio() {
  const [file, setFile] = useState<File | null>(null)
  const [job, setJob] = useState<FactoryJob | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [published, setPublished] = useState<string | null>(null)

  useEffect(() => {
    if (!job || !['queued', 'running', 'retrying'].includes(job.status)) return
    const timer = window.setInterval(() => { void getFactoryJob(job.job_id).then(setJob).catch((reason: Error) => setError(reason.message)) }, 1200)
    return () => window.clearInterval(timer)
  }, [job])

  async function start() {
    if (!file) return
    setBusy(true); setError(null); setPublished(null)
    try {
      const document = await uploadFactoryDocument(file.name, await readFile(file), file.type || undefined)
      const created = await createFactoryJob(document.document_id)
      setJob(await getFactoryJob(created.job_id))
    } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  async function publish() {
    const revision = job?.revisions.find((item) => item.status === 'ready_for_review')
    if (!job || !revision) return
    setBusy(true); setError(null)
    try { const result = await publishFactoryRevision(job.job_id, revision.revision_id); setPublished(result.question_id); setJob(await getFactoryJob(job.job_id)) } catch (reason) { setError((reason as Error).message) } finally { setBusy(false) }
  }

  return <section className="s1-card s1-factory" data-testid="factory-studio">
    <div className="s1-factory-head"><div><span className="s1-kicker">QUESTION FACTORY</span><h2>从教学资料到题目草稿</h2><p>上传资料后生成题目草稿；你可以查看结果、根据建议修改，再发布到题库。</p></div><ShieldCheck size={26} /></div>
    <label className="s1-file-input"><FileUp size={17} /><span>{file?.name ?? '选择 .md 或 .pdf 教学资料（≤5 MiB）'}</span><input aria-label="上传教学资料" type="file" accept=".md,.pdf,text/markdown,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
    <div className="s1-question-actions"><button className="s1-button s1-button-secondary" data-testid="factory-generate" disabled={!file || busy} onClick={() => void start()}>{busy ? <LoaderCircle className="s1-spin" size={15} /> : <Play size={15} />}上传并生成</button></div>
    {error && <div className="s1-inline-error" role="alert">{error}</div>}
    {job && <div className="s1-factory-ledger"><strong>生成进度</strong><span className={`s1-status-pill is-${job.stage}`}>{factoryStatusLabel(job.stage)}</span><small>{job.progress}% · 第 {Math.max(1, job.attempt)} 次执行</small>{job.error_message && <small className="s1-inline-error">{job.error_message}</small>}{job.detail.events?.map((event) => <small key={`${event.at}-${event.status}`}>{factoryStatusLabel(event.status)}</small>)}</div>}
    {job?.revisions.map((revision) => <article key={revision.revision_id} className="s1-factory-revision"><div><strong>{revision.parent_revision_id ? '优化后草稿' : '初始草稿'}</strong><span>{factoryStatusLabel(revision.status)}</span></div><p>{revision.draft.stem}</p><small>内容检查：{revision.judge.passed ? '符合要求' : '建议调整'}</small>{revision.rewrite_instruction && <small>修改建议：{revision.rewrite_instruction}</small>}</article>)}
    {job?.stage === 'ready_for_review' && <button className="s1-button s1-button-primary" data-testid="factory-publish" disabled={busy} onClick={() => void publish()}><Send size={15} />发布到题库</button>}
    {published && <p className="s1-safety">题目已发布，可在题库中开始练习。仅供教学研修或医生复核前辅助，不作为独立诊断依据。</p>}
  </section>
}

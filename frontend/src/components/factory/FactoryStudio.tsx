import { FileUp, LoaderCircle, Play, Send, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'

import { createFactoryJob, getFactoryJob, publishFactoryRevision, uploadFactoryDocument } from '../../api/client'
import type { FactoryJob } from '../../api/client'

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
    if (!job || !['queued', 'parsing', 'indexing', 'generating', 'judging', 'repairing'].includes(job.status)) return
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
    <div className="s1-factory-head"><div><span className="s1-kicker">FACTORY STUDIO</span><h2>从允许资料到可审核草稿</h2><p>真实 Dramatiq job 状态；Generator/Judge 独立 schema；每次 repair 保留 revision lineage。</p></div><ShieldCheck size={26} /></div>
    <label className="s1-file-input"><FileUp size={17} /><span>{file?.name ?? '选择 .md 或 .pdf 教学资料（≤5 MiB）'}</span><input aria-label="上传教学资料" type="file" accept=".md,.pdf,text/markdown,application/pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
    <div className="s1-question-actions"><button className="s1-button s1-button-secondary" data-testid="factory-generate" disabled={!file || busy} onClick={() => void start()}>{busy ? <LoaderCircle className="s1-spin" size={15} /> : <Play size={15} />}上传并生成</button></div>
    {error && <div className="s1-inline-error" role="alert">{error}</div>}
    {job && <div className="s1-factory-ledger"><strong>Job {job.job_id}</strong><span className={`s1-status-pill is-${job.status}`}>{job.status}</span>{job.detail.events?.map((event) => <small key={`${event.at}-${event.status}`}>{event.status} · {event.detail}</small>)}</div>}
    {job?.revisions.map((revision) => <article key={revision.revision_id} className="s1-factory-revision"><div><strong>{revision.parent_revision_id ? 'Repair revision' : 'Initial draft'}</strong><span>{revision.status}</span></div><p>{revision.draft.stem}</p><small>Judge: {revision.judge.passed ? 'pass' : 'fail'} · citation chunk 已保留</small>{revision.rewrite_instruction && <small>Rewrite: {revision.rewrite_instruction}</small>}</article>)}
    {job?.status === 'ready_for_review' && <button className="s1-button s1-button-primary" data-testid="factory-publish" disabled={busy} onClick={() => void publish()}><Send size={15} />人工发布到题库</button>}
    {published && <p className="s1-safety">已发布为 {published}；可在题库中进入练习。仅供教学研修或医生复核前辅助，不作为独立诊断依据。</p>}
  </section>
}

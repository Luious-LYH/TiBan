import { FileUp, FileText, LoaderCircle, MoreHorizontal, RefreshCw, ToggleLeft, ToggleRight, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { deleteKnowledgeSource, getKnowledgeSource, getKnowledgeSources, reindexKnowledgeSource, setKnowledgeSourceEnabled, uploadKnowledgeSource, type KnowledgeSource } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type Tab = 'user' | 'system'

const sourceTabs: Array<[Tab, string]> = [['user', '我的资料'], ['system', '系统资料']]
const maxSize = 25 * 1024 * 1024

export function KnowledgePage() {
  const [tab, setTab] = useState<Tab>('user')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const client = useQueryClient()
  const sources = useQuery({ queryKey: ['knowledge-sources'], queryFn: () => getKnowledgeSources(), retry: false })
  const visible = (sources.data ?? []).filter((item) => tab === 'user' ? item.scope === 'user' : item.scope !== 'user')
  const effectiveSelected = selectedId && visible.some((item) => item.id === selectedId) ? selectedId : visible[0]?.id ?? null
  const detail = useQuery({ queryKey: ['knowledge-source', effectiveSelected], queryFn: () => getKnowledgeSource(effectiveSelected ?? ''), enabled: Boolean(effectiveSelected) })
  const invalidate = () => void client.invalidateQueries({ queryKey: ['knowledge-sources'] })
  const upload = useMutation({ mutationFn: uploadKnowledgeSource, onSuccess: (item) => { setTab('user'); setSelectedId(item.id); invalidate() } })
  const toggle = useMutation({ mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setKnowledgeSourceEnabled(id, enabled), onSuccess: () => { invalidate(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) } })
  const reindex = useMutation({ mutationFn: reindexKnowledgeSource, onSuccess: () => { invalidate(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) } })
  const remove = useMutation({ mutationFn: deleteKnowledgeSource, onSuccess: () => { setSelectedId(null); invalidate(); void client.removeQueries({ queryKey: ['knowledge-source'] }) } })

  function chooseFile(file?: File) {
    if (!file) return
    if (file.size > maxSize) return
    upload.mutate(file)
  }

  return <div className="knowledge-page" data-testid="knowledge-page">
    <header className="knowledge-header"><div><span>知识</span><h1>知识库</h1><p>管理智能辅导和带教 Agent 可使用的学习资料。</p></div><div><input ref={fileInput} aria-label="上传知识资料" type="file" accept=".pdf,.docx,.md,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain" onChange={(event) => chooseFile(event.target.files?.[0])} /><button className="knowledge-upload" type="button" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>{upload.isPending ? <LoaderCircle className="s1-spin" size={16} /> : <FileUp size={16} />}{upload.isPending ? '正在索引…' : '上传资料'}</button></div></header>
    <p className="knowledge-support">支持 PDF、DOCX、Markdown、TXT；上传后会解析、分段、向量索引。单个文件不超过 25 MiB。</p>
    {upload.isError && <p className="knowledge-error" role="alert">{upload.error.message}</p>}
    <div className="knowledge-tabs" role="tablist">{sourceTabs.map(([value, label]) => <button type="button" role="tab" aria-selected={tab === value} key={value} onClick={() => { setTab(value); setSelectedId(null) }}>{label}</button>)}</div>
    <section className="knowledge-workspace">
      <div className="knowledge-source-list">{sources.isPending ? <KnowledgeListSkeleton /> : sources.isError ? <ErrorState message={sources.error.message} onRetry={() => void sources.refetch()} /> : visible.length === 0 ? <EmptyState title={tab === 'user' ? '还没有个人资料' : '系统资料准备中'} detail={tab === 'user' ? '上传一份学习资料后，它会在索引完成后供 Agent 检索。' : '系统资料只保留经过许可、可追溯的少量来源。'} /> : <ol>{visible.map((source) => <SourceRow key={source.id} source={source} selected={source.id === effectiveSelected} onSelect={() => setSelectedId(source.id)} />)}</ol>}</div>
      <article className="knowledge-detail">{sources.isPending ? <KnowledgeDetailSkeleton /> : sources.isError ? <EmptyState title="资料列表暂不可用" detail="请重试读取知识库目录后再查看资料详情。" /> : !effectiveSelected ? <EmptyState title="选择一份资料查看详情" detail="这里只展示已真实解析和索引的来源。" /> : detail.isPending ? <LoadingState label="正在读取资料详情…" /> : detail.isError ? <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} /> : detail.data && <><header><div><span>{scopeLabel(detail.data.scope)}</span><h2>{detail.data.title}</h2><p>{fileLabel(detail.data.media_type)} · {formatSize(detail.data.size_bytes)} · {detail.data.chunk_count} 个片段</p></div><MoreHorizontal size={19} /></header><div className="knowledge-state"><span className={detail.data.enabled ? 'is-ready' : 'is-disabled'}>{detail.data.enabled ? '已索引' : '已停用'}</span>{detail.data.attribution && <small>{detail.data.attribution}</small>}</div><div className="knowledge-actions"><button type="button" onClick={() => toggle.mutate({ id: detail.data.id, enabled: !detail.data.enabled })} disabled={toggle.isPending}>{detail.data.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}{detail.data.enabled ? '停用' : '启用'}</button><button type="button" onClick={() => reindex.mutate(detail.data.id)} disabled={reindex.isPending}>{reindex.isPending ? <LoaderCircle className="s1-spin" size={16} /> : <RefreshCw size={16} />}重新索引</button>{detail.data.scope === 'user' && <button type="button" className="is-danger" onClick={() => { if (window.confirm(`删除「${detail.data.title}」及其索引？`)) remove.mutate(detail.data.id) }} disabled={remove.isPending}><Trash2 size={16} />删除</button>}</div><section className="knowledge-preview"><h3>解析预览</h3>{detail.data.preview?.length ? detail.data.preview.map((item, index) => <article key={`${String(item.section)}-${index}`}><small>{previewLabel(item.section, item.page)}</small><p>{String(item.text)}</p></article>) : <p>当前资料没有可显示的解析片段。</p>}</section></>}</article>
    </section>
  </div>
}

function KnowledgeListSkeleton() { return <div className="workspace-list-skeleton" role="status" aria-label="正在读取知识库"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }
function KnowledgeDetailSkeleton() { return <div className="workspace-detail-skeleton" role="status" aria-label="正在读取知识资料"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }

function SourceRow({ source, selected, onSelect }: { source: KnowledgeSource; selected: boolean; onSelect: () => void }) { return <li><button type="button" className={selected ? 'is-selected' : ''} onClick={onSelect}><span><FileText size={17} /></span><div><strong>{source.title}</strong><small>{fileLabel(source.media_type)} · {source.chunk_count} 个片段</small></div><i className={source.enabled ? 'is-ready' : 'is-disabled'}>{source.enabled ? '已索引' : '已停用'}</i></button></li> }
function scopeLabel(value: string) { return value === 'user' ? '我的资料' : value === 'qbank_explanations' ? '题库解析' : '系统资料' }
function fileLabel(mediaType: string) { return mediaType.includes('pdf') ? 'PDF' : mediaType.includes('wordprocessingml') ? 'DOCX' : mediaType.includes('markdown') ? 'Markdown' : 'TXT' }
function formatSize(bytes: number) { return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB` }
function previewLabel(section: unknown, page: unknown) { const label = String(section); return page && !/第\s*\d+\s*页/.test(label) ? `${label} · 第 ${String(page)} 页` : label }

import { FileUp, FileText, LoaderCircle, MoreHorizontal, RefreshCw, Search, ToggleLeft, ToggleRight, Trash2, X } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { deleteKnowledgeSource, getKnowledgeSource, getKnowledgeSources, reindexKnowledgeSource, searchKnowledge, setKnowledgeSourceEnabled, uploadKnowledgeSource, type KnowledgeSource } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type Tab = 'user' | 'system'

const sourceTabs: Array<[Tab, string]> = [['user', '我的资料'], ['system', '系统资料']]
const maxSize = 5 * 1024 * 1024

export function KnowledgePage() {
  // The system collection contains the ready-to-use illustrated endoscopy
  // guide.  Show it first so the knowledge page immediately communicates what
  // the product can do; personal uploads remain one click away.
  const [tab, setTab] = useState<Tab>('system')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [searchText, setSearchText] = useState('')
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
  const remove = useMutation({ mutationFn: deleteKnowledgeSource, onSuccess: (_result, deletedId) => { setSelectedId((current) => current === deletedId ? null : current); invalidate(); void client.removeQueries({ queryKey: ['knowledge-source', deletedId] }) } })
  const search = useMutation({ mutationFn: (query: string) => searchKnowledge(query), onError: () => undefined })

  function requestDelete(source: KnowledgeSource) {
    if (remove.isPending) return
    if (window.confirm(`删除「${source.title}」及其索引？`)) remove.mutate(source.id)
  }

  useEffect(() => {
    const pending = (sources.data ?? []).some((item) => ['queued', 'rebuilding', 'indexing'].includes(item.status))
    if (!pending) return
    const timer = window.setInterval(() => {
      void sources.refetch()
      if (effectiveSelected) void detail.refetch()
    }, 2_000)
    return () => window.clearInterval(timer)
  }, [detail, effectiveSelected, sources])

  function chooseFile(file?: File) {
    if (!file) return
    if (file.size > maxSize) return
    upload.mutate(file)
  }

  return <div className="knowledge-page" data-testid="knowledge-page">
    <header className="knowledge-header"><div><span>知识</span><h1>知识库</h1><p>管理智能辅导和带教 Agent 可使用的文字、图片资料。</p></div><div><input ref={fileInput} aria-label="上传知识资料" type="file" accept=".pdf,.docx,.md,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/markdown,text/plain" onChange={(event) => chooseFile(event.target.files?.[0])} /><button className="knowledge-upload" type="button" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>{upload.isPending ? <LoaderCircle className="s1-spin" size={16} /> : <FileUp size={16} />}{upload.isPending ? '正在上传…' : '上传并排队'}</button></div></header>
        <p className="knowledge-support">支持 PDF、DOCX、Markdown、TXT；含图片的 PDF 会保留图片预览，并把图片和对应文字关联起来。单个文件不超过 5 MiB。</p>
    {upload.isError && <p className="knowledge-error" role="alert">{upload.error.message}</p>}
    {remove.isError && <p className="knowledge-error" role="alert">删除失败：{remove.error.message}</p>}
    <form className="knowledge-search" onSubmit={(event) => { event.preventDefault(); const query = searchText.trim(); if (query) search.mutate(query) }}><Search size={16} aria-hidden="true" /><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="搜索已启用的学习资料" aria-label="搜索学习资料" /><button type="submit" disabled={!searchText.trim() || search.isPending}>{search.isPending ? <LoaderCircle className="s1-spin" size={15} /> : '搜索'}</button>{searchText && <button type="button" className="knowledge-search-clear" aria-label="清除搜索" onClick={() => { setSearchText(''); search.reset() }}><X size={15} /></button>}</form>
    {search.isError && <p className="knowledge-error" role="alert">资料搜索暂不可用，请稍后重试。</p>}
    {search.data && <KnowledgeSearchResults result={search.data} />}
    <div className="knowledge-tabs" role="tablist">{sourceTabs.map(([value, label]) => <button type="button" role="tab" aria-selected={tab === value} key={value} onClick={() => { setTab(value); setSelectedId(null) }}>{label}</button>)}</div>
    <section className="knowledge-workspace">
      <div className="knowledge-source-list">{sources.isPending ? <KnowledgeListSkeleton /> : sources.isError ? <ErrorState message={sources.error.message} onRetry={() => void sources.refetch()} /> : visible.length === 0 ? <EmptyState title={tab === 'user' ? '还没有个人资料' : '系统资料准备中'} detail={tab === 'user' ? '上传一份学习资料后，它会在处理完成后出现在这里。' : '系统资料准备中，完成后即可直接用于学习。'} /> : <ol>{visible.map((source) => <SourceRow key={source.id} source={source} selected={source.id === effectiveSelected} onSelect={() => setSelectedId(source.id)} onDelete={() => requestDelete(source)} deleting={remove.isPending} />)}</ol>}</div>
      <article className="knowledge-detail">{sources.isPending ? <KnowledgeDetailSkeleton /> : sources.isError ? <EmptyState title="资料列表暂不可用" detail="请重试读取知识库目录后再查看资料详情。" /> : !effectiveSelected ? <EmptyState title="选择一份资料查看详情" detail="选择资料后可查看解析内容和图片。" /> : detail.isPending ? <LoadingState label="正在读取资料详情…" /> : detail.isError ? <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} /> : detail.data && <><header><div><span>{scopeLabel(detail.data.scope)}</span><h2>{detail.data.title}</h2><p>{fileLabel(detail.data.media_type)} · {formatSize(detail.data.size_bytes)} · {detail.data.chunk_count} 个片段{(detail.data.image_count ?? 0) > 0 ? ` · ${detail.data.image_count} 张图片` : ''}</p></div><MoreHorizontal size={19} /></header><div className="knowledge-state"><span className={stateClass(detail.data.status)}>{stateLabel(detail.data)}</span>{(detail.data.image_count ?? 0) > 0 && <span className="knowledge-capability">{imageIndexLabel(detail.data.image_index_status ?? 'empty')}</span>}{detail.data.graph_status === 'ready' && <span className="knowledge-capability">图文已关联</span>}{detail.data.attribution && <small>{detail.data.attribution}</small>}</div>{isIndexing(detail.data) && <p className="knowledge-index-progress" role="status">{detail.data.index_stage ?? '正在准备资料'} · {detail.data.index_progress}%</p>}{detail.data.index_error && <p className="knowledge-error" role="alert">处理提示：{friendlyIndexError(detail.data.index_error)}</p>}{(detail.data.image_count ?? 0) > 0 && <section className="knowledge-media-preview"><div><h3>资料图片</h3><span>{imageIndexLabel(detail.data.image_index_status ?? 'empty')}</span></div>{detail.data.image_index_error && <p className="knowledge-media-error">图片搜索提示：{friendlyIndexError(detail.data.image_index_error)}</p>}<div className="knowledge-media-grid">{detail.data.media_preview?.map((item) => <img key={String(item.asset_id)} src={String(item.url)} alt={String(item.alt_text ?? '资料中的教学图片')} loading="lazy" />)}</div></section>}<div className="knowledge-actions"><button type="button" onClick={() => toggle.mutate({ id: detail.data.id, enabled: !detail.data.enabled })} disabled={toggle.isPending || isIndexing(detail.data)}>{detail.data.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}{detail.data.enabled ? '停用' : '启用'}</button><button type="button" onClick={() => reindex.mutate(detail.data.id)} disabled={reindex.isPending || isIndexing(detail.data)}>{reindex.isPending ? <LoaderCircle className="s1-spin" size={16} /> : <RefreshCw size={16} />}重新处理</button>{detail.data.scope === 'user' && <button type="button" className="is-danger" onClick={() => { if (window.confirm(`删除「${detail.data.title}」及其索引？`)) remove.mutate(detail.data.id) }} disabled={remove.isPending}><Trash2 size={16} />删除</button>}</div><section className="knowledge-preview"><h3>解析预览</h3>{detail.data.preview?.length ? detail.data.preview.map((item, index) => <article key={`${String(item.section)}-${index}`}><small>{previewLabel(item.section, item.page)}</small><p>{String(item.text)}</p></article>) : <p>{isIndexing(detail.data) ? '资料正在处理中，完成后会在这里显示内容。' : '当前资料没有可显示的解析片段。'}</p>}</section></>}</article>
    </section>
  </div>
}

function KnowledgeListSkeleton() { return <div className="workspace-list-skeleton" role="status" aria-label="正在读取知识库"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }
function KnowledgeDetailSkeleton() { return <div className="workspace-detail-skeleton" role="status" aria-label="正在读取知识资料"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }

function KnowledgeSearchResults({ result }: { result: { citations?: Array<Record<string, unknown>>; image_results?: Array<Record<string, unknown>>; graph_paths?: Array<Record<string, unknown>> } }) {
  const citations = result.citations ?? []
  const imageResults = result.image_results ?? []
  const graphPaths = result.graph_paths ?? []
  const hasResults = citations.length > 0 || imageResults.length > 0 || graphPaths.length > 0
    return <section className="knowledge-search-results"><header><div><span>搜索结果</span><h2>{hasResults ? '已找到相关资料' : '没有找到相关资料'}</h2></div><small>{imageResults.length ? `${imageResults.length} 张相关图片` : graphPaths.length ? `${graphPaths.length} 条资料关联` : '文字资料'}</small></header>{!hasResults ? <p>可以换一个关键词，或先上传一份学习资料。</p> : <div className="knowledge-search-grid">{citations.slice(0, 5).map((item, index) => <article key={`${String(item.chunk_id)}-${index}`}><strong>{String(item.document_name ?? '学习资料')}</strong><small>{item.page ? `第 ${String(item.page)} 页` : '资料片段'}</small><p>{String(item.snippet ?? '')}</p></article>)}{imageResults.slice(0, 4).map((item, index) => <article className="has-image" key={`${String(item.asset_id)}-${index}`}><img src={String(item.url)} alt={String(item.caption ?? '相关资料图片')} loading="lazy" /><div><strong>{String(item.document_name ?? '学习资料')}</strong><small>{item.section ? String(item.section) : `第 ${String(item.page ?? 1)} 页`}</small><p>{String(item.caption ?? '相关资料图片')}</p></div></article>)}{graphPaths.slice(0, 4).map((item, index) => <article className="knowledge-graph-result" key={`${String(item.chunk_id ?? 'graph')}-${index}`}><strong>相关资料关联</strong><small>{String(item.from ?? '')}{item.to ? ` → ${String(item.to)}` : ''}</small><p>{String(item.document_name ?? '同一份资料中的相邻片段')}</p></article>)}</div>}</section>
}

function SourceRow({ source, selected, onSelect, onDelete, deleting }: { source: KnowledgeSource; selected: boolean; onSelect: () => void; onDelete: () => void; deleting: boolean }) {
  return <li className="knowledge-source-row"><button type="button" className={selected ? 'is-selected' : ''} onClick={onSelect}><span><FileText size={17} /></span><div><strong>{source.title}</strong><small>{fileLabel(source.media_type)} · {isIndexing(source) ? `${source.index_stage ?? '正在索引'} ${source.index_progress}%` : `${source.chunk_count} 个片段`}{(source.image_count ?? 0) > 0 ? ` · ${source.image_count} 张图片` : ''}</small></div><i className={stateClass(source.status)}>{stateLabel(source)}</i></button>{source.scope === 'user' && <button type="button" className="knowledge-source-delete" aria-label={`删除${source.title}`} onClick={(event) => { event.stopPropagation(); onDelete() }} disabled={deleting}><Trash2 size={15} aria-hidden="true" /></button>}</li>
}
function isIndexing(source: KnowledgeSource) { return ['queued', 'rebuilding', 'indexing'].includes(source.status) }
function stateClass(status: string) { return status === 'ready' ? 'is-ready' : status === 'failed' ? 'is-failed' : 'is-disabled' }
function stateLabel(source: KnowledgeSource) { if (source.status === 'queued') return '等待索引'; if (source.status === 'rebuilding' || source.status === 'indexing') return '索引中'; if (source.status === 'failed') return '索引失败'; return source.enabled ? '已索引' : source.status === 'disabled' ? '已停用' : source.status }
function scopeLabel(value: string) { return value === 'user' ? '我的资料' : value === 'qbank_explanations' ? '题库解析' : '系统资料' }
function fileLabel(mediaType: string) { return mediaType.includes('pdf') ? 'PDF' : mediaType.includes('wordprocessingml') ? 'DOCX' : mediaType.includes('markdown') ? 'Markdown' : 'TXT' }
function formatSize(bytes: number) { return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB` }
function previewLabel(section: unknown, page: unknown) { const label = String(section); return page && !/第\s*\d+\s*页/.test(label) ? `${label} · 第 ${String(page)} 页` : label }
function imageIndexLabel(status: string) { return status === 'ready' ? '图片可用于资料搜索' : status === 'pending' ? '图片处理中' : status === 'failed' ? '图片处理失败，可重新处理' : status === 'empty' ? '没有图片' : '图片待更新' }
function friendlyIndexError(error: string) {
  if (/unexpectedresponse|qdrant|vector|embedding|connection|timeout/i.test(error)) return '图片处理未完成，文字内容和图片预览仍可查看；请稍后重新处理。'
  return error
}

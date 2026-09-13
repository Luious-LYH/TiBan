import { ArrowLeft, Check, ChevronRight, Database, FileText, FileUp, Folder, FolderOpen, FolderPlus, LoaderCircle, Pencil, RefreshCw, Search, Trash2, ToggleLeft, ToggleRight, UserRound, X } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState, type DragEvent, type FormEvent, type ReactNode } from 'react'

import {
  createKnowledgeFolder,
  deleteKnowledgeFolder,
  deleteKnowledgeSource,
  getKnowledgeFolders,
  getKnowledgeSource,
  getKnowledgeSources,
  moveKnowledgeSource,
  processKnowledgeSources,
  reindexKnowledgeSource,
  searchKnowledge,
  setKnowledgeSourceEnabled,
  updateKnowledgeFolder,
  uploadKnowledgeSource,
  type KnowledgeFolder,
  type KnowledgeSource,
  type KnowledgeSourceDetail,
} from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type Tab = 'user' | 'system' | 'qbank_explanations'

const sourceTabs: Array<[Tab, string]> = [['user', '我的资料'], ['system', '系统资料'], ['qbank_explanations', '题库解析']]
const maxSize = 5 * 1024 * 1024

export function KnowledgePage() {
  const [tab, setTab] = useState<Tab>('user')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [searchText, setSearchText] = useState('')
  const [selectedForProcessing, setSelectedForProcessing] = useState<string[]>([])
  const [managementMode, setManagementMode] = useState(false)
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null)
  const [folderDraft, setFolderDraft] = useState('')
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [createFolderDraft, setCreateFolderDraft] = useState('')
  const [draggedSourceId, setDraggedSourceId] = useState<string | null>(null)
  const [dragOverTarget, setDragOverTarget] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const client = useQueryClient()
  const sources = useQuery({ queryKey: ['knowledge-sources'], queryFn: () => getKnowledgeSources(), retry: false, refetchOnMount: 'always', refetchOnWindowFocus: true })
  const folders = useQuery({ queryKey: ['knowledge-folders'], queryFn: getKnowledgeFolders, retry: false })
  const visibleFolders = (folders.data ?? []).filter((folder) => tab === 'user'
    ? folder.scope === 'user'
    : tab === 'qbank_explanations'
      ? folder.scope === 'qbank_explanations' || folder.id === 'folder-qbank-explanations'
      : folder.scope === 'system')
  const scopedSources = (sources.data ?? [])
    .filter((item) => item.scope === tab)
    .sort(compareKnowledgeSources)
  const visible = scopedSources.filter((item) => Boolean(selectedFolderId) && item.folder_id === selectedFolderId)
  const rootSources = scopedSources.filter((item) => !item.folder_id)
  const selectedFolder = visibleFolders.find((folder) => folder.id === selectedFolderId) ?? null
  const effectiveSelected = selectedFolder && selectedId && visible.some((item) => item.id === selectedId)
    ? selectedId
    : selectedFolder ? visible[0]?.id ?? null
      : selectedId && rootSources.some((item) => item.id === selectedId) ? selectedId : null
  const detail = useQuery({ queryKey: ['knowledge-source', effectiveSelected], queryFn: () => getKnowledgeSource(effectiveSelected ?? ''), enabled: Boolean(effectiveSelected) })

  const invalidateSources = () => void client.invalidateQueries({ queryKey: ['knowledge-sources'] })
  const invalidateFolders = () => void client.invalidateQueries({ queryKey: ['knowledge-folders'] })
  const upload = useMutation({
    mutationFn: uploadKnowledgeSource,
    onSuccess: (item) => { setTab('user'); setSelectedFolderId(item.folder_id ?? null); setSelectedId(item.id); invalidateSources(); invalidateFolders() },
  })
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setKnowledgeSourceEnabled(id, enabled),
    onSuccess: () => { invalidateSources(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) },
  })
  const reindex = useMutation({
    mutationFn: reindexKnowledgeSource,
    onSuccess: () => { invalidateSources(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) },
  })
  const remove = useMutation({
    mutationFn: deleteKnowledgeSource,
    onSuccess: (_result, deletedId) => { setSelectedId((current) => current === deletedId ? null : current); invalidateSources(); invalidateFolders(); void client.removeQueries({ queryKey: ['knowledge-source', deletedId] }) },
  })
  const createFolder = useMutation({ mutationFn: ({ name, scope }: { name: string; scope: 'user' | 'qbank_explanations' }) => createKnowledgeFolder(name, '', scope), onSuccess: () => { setCreatingFolder(false); setCreateFolderDraft(''); invalidateFolders() } })
  const renameFolder = useMutation({ mutationFn: ({ id, name }: { id: string; name: string }) => updateKnowledgeFolder(id, { name }), onSuccess: () => { setEditingFolderId(null); setFolderDraft(''); invalidateFolders(); invalidateSources(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) } })
  const removeFolder = useMutation({ mutationFn: deleteKnowledgeFolder, onSuccess: (_result, folderId) => { if (selectedFolderId === folderId) setSelectedFolderId(null); invalidateFolders(); invalidateSources() } })
  const processSelected = useMutation({
    mutationFn: processKnowledgeSources,
    onSuccess: () => { setSelectedForProcessing([]); invalidateSources(); void client.invalidateQueries({ queryKey: ['knowledge-source'] }) },
  })
  const moveSource = useMutation({
    mutationFn: ({ documentId, folderId }: { documentId: string; folderId: string | null }) => moveKnowledgeSource(documentId, folderId),
    onSuccess: (item) => {
      setSelectedId(item.id)
      setSelectedFolderId(item.folder_id ?? null)
      setDraggedSourceId(null)
      setDragOverTarget(null)
      invalidateSources()
      invalidateFolders()
      void client.invalidateQueries({ queryKey: ['knowledge-source', item.id] })
    },
    onError: () => {
      setDraggedSourceId(null)
      setDragOverTarget(null)
    },
  })
  const search = useMutation({ mutationFn: (query: string) => searchKnowledge(query), onError: () => undefined })

  function requestDelete(source: KnowledgeSource) {
    if (remove.isPending) return
    const detail = source.scope === 'user'
      ? '删除后将一并移除这份资料及其索引。'
      : '资料会从知识库和检索结果中移除，原始文件不会被删除。'
    if (window.confirm(`删除「${source.title}」？\n${detail}`)) remove.mutate(source.id)
  }

  function requestCreateFolder() {
    setCreatingFolder(true)
    setCreateFolderDraft('')
    setEditingFolderId(null)
  }

  function requestRenameFolder(folder: KnowledgeFolder) {
    setCreatingFolder(false)
    setEditingFolderId(folder.id)
    setFolderDraft(folder.name)
  }

  function submitCreateFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = createFolderDraft.trim()
    if (!name || createFolder.isPending) return
    createFolder.mutate({ name, scope: tab === 'qbank_explanations' ? 'qbank_explanations' : 'user' })
  }

  function submitRenameFolder(event: FormEvent<HTMLFormElement>, folder: KnowledgeFolder) {
    event.preventDefault()
    const name = folderDraft.trim()
    if (!name || name === folder.name || renameFolder.isPending) {
      if (name === folder.name) { setEditingFolderId(null); setFolderDraft('') }
      return
    }
    renameFolder.mutate({ id: folder.id, name })
  }

  function requestDeleteFolder(folder: KnowledgeFolder) {
    if (folder.source_count > 0) {
      window.alert('目录中仍有资料，请先将资料移动到其他目录。')
      return
    }
    if (window.confirm(`删除资料目录「${folder.name}」？`)) removeFolder.mutate(folder.id)
  }

  useEffect(() => {
    const pending = (sources.data ?? []).some((item) => ['rebuilding', 'indexing'].includes(item.status))
    if (!pending) return
    const timer = window.setInterval(() => {
      void sources.refetch()
      if (effectiveSelected) void detail.refetch()
    }, 2_000)
    return () => window.clearInterval(timer)
  }, [detail, effectiveSelected, sources])

  function chooseFile(file?: File) {
    if (!file) return
    if (file.name.toLowerCase().endsWith('.doc')) {
      window.alert('当前支持 DOCX，不支持旧版 DOC。请先将文件另存为 DOCX 或 PDF 后再上传。')
      return
    }
    if (file.size > maxSize) {
      window.alert('单个资料不能超过 5 MiB。')
      return
    }
    upload.mutate(file)
  }

  function switchTab(nextTab: Tab) {
    setTab(nextTab)
    setSelectedFolderId(null)
    setSelectedId(null)
    setSelectedForProcessing([])
    setManagementMode(false)
    setEditingFolderId(null)
    setCreatingFolder(false)
  }

  function openFolder(folderId: string) {
    setSelectedFolderId(folderId)
    setSelectedId(null)
    setSelectedForProcessing([])
    setManagementMode(false)
    setEditingFolderId(null)
    setCreatingFolder(false)
  }

  function openRootSource(sourceId: string) {
    setSelectedFolderId(null)
    setSelectedId(sourceId)
    setSelectedForProcessing([])
    setManagementMode(false)
  }

  function startDragging(sourceId: string, event: DragEvent<HTMLElement>) {
    if (managementMode || moveSource.isPending) {
      event.preventDefault()
      return
    }
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', sourceId)
    setDraggedSourceId(sourceId)
  }

  function stopDragging() {
    setDraggedSourceId(null)
    setDragOverTarget(null)
  }

  function dragOverTargetFolder(folderId: string | null, event: DragEvent<HTMLElement>) {
    if (!draggedSourceId || managementMode) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    setDragOverTarget(folderId ?? ROOT_DROP_TARGET)
  }

  function dropSource(folderId: string | null, event: DragEvent<HTMLElement>) {
    event.preventDefault()
    const sourceId = event.dataTransfer.getData('text/plain') || draggedSourceId
    setDragOverTarget(null)
    if (!sourceId || moveSource.isPending) {
      setDraggedSourceId(null)
      return
    }
    const source = scopedSources.find((item) => item.id === sourceId)
    if (!source || source.folder_id === folderId) {
      setDraggedSourceId(null)
      return
    }
    moveSource.mutate({ documentId: sourceId, folderId })
  }

  function requestDeleteSelected() {
    if (!selectedForProcessing.length || remove.isPending) return
    if (!window.confirm(`删除已选 ${selectedForProcessing.length} 份资料？\n资料会从知识库和检索结果中移除，原始文件不会被删除。`)) return
    void Promise.all(selectedForProcessing.map((id) => remove.mutateAsync(id))).then(() => {
      setSelectedForProcessing([])
      setManagementMode(false)
      invalidateSources()
      invalidateFolders()
    })
  }

  function toggleProcessSelection(documentId: string) {
    setSelectedForProcessing((current) => current.includes(documentId)
      ? current.filter((id) => id !== documentId)
      : current.length >= 5 ? current : [...current, documentId])
  }

  const scopedSourceCount = scopedSources.length

  function renderLibraryContent() {
    if (sources.isPending) return <div className="knowledge-root-state"><KnowledgeListSkeleton /></div>
    if (sources.isError) return <div className="knowledge-root-state"><ErrorState message={sources.error.message} onRetry={() => void sources.refetch()} /></div>
    if (!selectedFolder) {
      if (effectiveSelected && rootSources.some((item) => item.id === effectiveSelected)) {
        return <RootSourceWorkspace scope={tab} sources={rootSources} selectedId={effectiveSelected} onBack={() => { setSelectedId(null); setSelectedFolderId(null) }} onSelect={setSelectedId} onStartDragging={startDragging} onStopDragging={stopDragging} renderDetail={renderDetailPane} />
      }
      return <FolderOverview folders={visibleFolders} sources={rootSources} tab={tab} onOpen={openFolder} onOpenSource={openRootSource} onStartDragging={startDragging} onStopDragging={stopDragging} />
    }

    return <section className="knowledge-folder-workspace" aria-label={`${selectedFolder.name}中的资料`}>
      <header className="knowledge-folder-content-header">
        <button type="button" className="knowledge-back" onClick={() => { setSelectedFolderId(null); setSelectedId(null); setSelectedForProcessing([]) }}><ArrowLeft size={15} />全部目录</button>
        <div><span>{scopeLabel(tab)}</span><h2>{selectedFolder.name}</h2><p>{selectedFolder.description || `共 ${selectedFolder.source_count} 份资料`}</p></div>
          <div className="knowledge-folder-toolbar"><small>{selectedFolder.source_count} 份资料</small>{!managementMode ? <button type="button" onClick={() => setManagementMode(true)} disabled={!visible.length}>管理</button> : <div className="knowledge-management-actions"><span>已选 {selectedForProcessing.length}</span><button type="button" onClick={() => processSelected.mutate(selectedForProcessing)} disabled={!selectedForProcessing.length || processSelected.isPending}>{processSelected.isPending ? '正在索引…' : '开始索引'}</button><button type="button" className="is-danger" onClick={requestDeleteSelected} disabled={!selectedForProcessing.length || remove.isPending}>删除</button><button type="button" onClick={() => { setSelectedForProcessing([]); setManagementMode(false) }}>完成管理</button></div>}</div>
      </header>
      {processSelected.isError && <p className="knowledge-error knowledge-inline-error" role="alert">索引未开始：{processSelected.error.message}</p>}
      <div className="knowledge-workspace">
        <div className="knowledge-source-list">
          {visible.length === 0
            ? <EmptyState title="这个目录还没有资料" detail={tab === 'user' ? '上传一份学习资料后，它会出现在这里。' : '该目录中的资料正在准备，请稍后刷新。'} />
             : <ol>{visible.map((source) => <SourceRow key={source.id} source={source} selected={source.id === effectiveSelected} onSelect={() => setSelectedId(source.id)} selectable={managementMode} checked={selectedForProcessing.includes(source.id)} onToggle={() => toggleProcessSelection(source.id)} onStartDragging={startDragging} onStopDragging={stopDragging} />)}</ol>}
        </div>
        <article className="knowledge-detail">{renderDetailPane()}</article>
      </div>
    </section>
  }

  function renderDetailPane() {
    return !effectiveSelected
      ? <EmptyState title="选择一份资料查看详情" detail="选择资料后可查看解析内容和图片。" />
       : detail.isPending ? <LoadingState label="正在读取资料详情…" />
        : detail.isError ? <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />
          : detail.data && <KnowledgeDetail source={detail.data} onToggle={() => toggle.mutate({ id: detail.data!.id, enabled: !detail.data!.enabled })} toggling={toggle.isPending} onReindex={() => reindex.mutate(detail.data!.id)} reindexing={reindex.isPending} onDelete={() => requestDelete(detail.data!)} deleting={remove.isPending} />
  }

  return <div className="knowledge-page" data-testid="knowledge-page">
    <header className="knowledge-header">
      <div><span>知识</span><h1>知识库</h1><p>管理智能辅导和带教 Agent 可使用的文字、图片资料。</p></div>
      <div><input ref={fileInput} aria-label="上传知识资料" type="file" accept=".pdf,.docx,.doc,.md,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,text/markdown,text/plain" onChange={(event) => chooseFile(event.target.files?.[0])} /><button className="knowledge-upload" type="button" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>{upload.isPending ? <LoaderCircle className="s1-spin" size={16} /> : <FileUp size={16} />}{upload.isPending ? '正在上传…' : '上传资料'}</button></div>
    </header>
    <p className="knowledge-support">支持 PDF、DOCX、Markdown、TXT；含图片的 PDF 会保留图片预览，并把图片和对应文字关联起来。旧版 DOC 请先另存为 DOCX 或 PDF。单个文件不超过 5 MiB。</p>
    {upload.isError && <p className="knowledge-error" role="alert">{upload.error.message}</p>}
    {remove.isError && <p className="knowledge-error" role="alert">删除失败：{remove.error.message}</p>}
    {(createFolder.isError || renameFolder.isError || removeFolder.isError) && <p className="knowledge-error" role="alert">目录操作失败：{(createFolder.error ?? renameFolder.error ?? removeFolder.error)?.message}</p>}

    <form className="knowledge-search" onSubmit={(event) => { event.preventDefault(); const query = searchText.trim(); if (query) search.mutate(query) }}><Search size={16} aria-hidden="true" /><input value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="搜索已启用的学习资料" aria-label="搜索学习资料" /><button type="submit" disabled={!searchText.trim() || search.isPending}>{search.isPending ? <LoaderCircle className="s1-spin" size={15} /> : '搜索'}</button>{searchText && <button type="button" className="knowledge-search-clear" aria-label="清除搜索" onClick={() => { setSearchText(''); search.reset() }}><X size={15} /></button>}</form>
    {search.isError && <p className="knowledge-error" role="alert">资料搜索暂不可用，请稍后重试。</p>}
    {search.data && <KnowledgeSearchResults result={search.data} />}

    <div className="knowledge-library">
      <aside className="knowledge-sidebar" aria-label="知识库导航">
        <section className="knowledge-sidebar-section">
          <span className="knowledge-sidebar-label">资料范围</span>
          <div className="knowledge-scope-list" role="tablist" aria-label="资料范围">
            {sourceTabs.map(([value, label]) => <button type="button" role="tab" aria-selected={tab === value} key={value} onClick={() => switchTab(value)}>{value === 'system' ? <Database size={16} /> : value === 'qbank_explanations' ? <FileText size={16} /> : <UserRound size={16} />}<span>{label}</span><small>{value === tab ? scopedSourceCount : ''}</small></button>)}
          </div>
        </section>
        <div className="knowledge-sidebar-divider" />
        <section className="knowledge-directory-nav" aria-labelledby="knowledge-directory-title">
          <header><div><span>目录</span><h2 id="knowledge-directory-title">{scopeLabel(tab)}</h2></div>{(tab === 'user' || tab === 'qbank_explanations') && !creatingFolder && <button type="button" onClick={requestCreateFolder} disabled={createFolder.isPending}><FolderPlus size={15} />新建目录</button>}{creatingFolder && <form className="knowledge-inline-folder-form" onSubmit={submitCreateFolder}><input autoFocus aria-label="新目录名称" value={createFolderDraft} onChange={(event) => setCreateFolderDraft(event.target.value)} placeholder="目录名称" maxLength={120} /><button type="submit" aria-label="保存新目录" disabled={!createFolderDraft.trim() || createFolder.isPending}><Check size={14} /></button><button type="button" aria-label="取消新建目录" onClick={() => { setCreatingFolder(false); setCreateFolderDraft('') }}><X size={14} /></button></form>}</header>
          {folders.isError ? <p className="knowledge-folder-hint">目录读取失败，资料仍可查看。</p> : <nav className="knowledge-directory-list"><button type="button" className={`${!selectedFolderId ? 'is-selected ' : ''}${dragOverTarget === ROOT_DROP_TARGET ? 'is-drag-over' : ''}`} aria-pressed={!selectedFolderId} onDragOver={(event) => dragOverTargetFolder(null, event)} onDrop={(event) => dropSource(null, event)} onClick={() => { setSelectedFolderId(null); setSelectedId(null) }}><Folder size={15} /><span>全部资料</span><small>{scopedSourceCount}</small></button>{visibleFolders.map((folder) => <div className={`knowledge-directory-item${selectedFolderId === folder.id ? ' is-selected' : ''}${dragOverTarget === folder.id ? ' is-drag-over' : ''}`} key={folder.id} onDragOver={(event) => dragOverTargetFolder(folder.id, event)} onDrop={(event) => dropSource(folder.id, event)} onClick={(event) => { if (event.target === event.currentTarget) openFolder(folder.id) }}>{editingFolderId === folder.id ? <form className="knowledge-inline-folder-edit" onSubmit={(event) => submitRenameFolder(event, folder)} onClick={(event) => event.stopPropagation()}><Folder size={15} /><input autoFocus aria-label={`修改${folder.name}`} value={folderDraft} onChange={(event) => setFolderDraft(event.target.value)} maxLength={120} /><button type="submit" aria-label="保存目录名称" disabled={!folderDraft.trim() || renameFolder.isPending}><Check size={13} /></button><button type="button" aria-label="取消修改目录名称" onClick={() => { setEditingFolderId(null); setFolderDraft('') }}><X size={13} /></button></form> : <><button type="button" aria-pressed={selectedFolderId === folder.id} onClick={() => openFolder(folder.id)}><Folder size={15} /><span>{folder.name}</span><small>{folder.source_count}</small></button>{!folder.is_system && <span className="knowledge-folder-actions"><button type="button" aria-label={`重命名${folder.name}`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.preventDefault(); event.stopPropagation(); requestRenameFolder(folder) }}><Pencil size={13} /></button><button type="button" aria-label={`删除${folder.name}`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => { event.preventDefault(); event.stopPropagation(); requestDeleteFolder(folder) }}><Trash2 size={13} /></button></span>}</>}</div>)}</nav>}
        </section>
      </aside>
      <main className="knowledge-library-main">{renderLibraryContent()}</main>
    </div>
  </div>
}

function FolderOverview({ folders, sources, tab, onOpen, onOpenSource, onStartDragging, onStopDragging }: { folders: KnowledgeFolder[]; sources: KnowledgeSource[]; tab: Tab; onOpen: (folderId: string) => void; onOpenSource: (sourceId: string) => void; onStartDragging: (sourceId: string, event: DragEvent<HTMLElement>) => void; onStopDragging: () => void }) {
  return <section className="knowledge-folder-overview" aria-labelledby="knowledge-folder-overview-title">
    <header><div><span>{scopeLabel(tab)}</span><h2 id="knowledge-folder-overview-title">资料目录</h2><p>选择一个目录，查看其中的学习资料。</p></div><small>{folders.length} 个目录{sources.length ? ` · ${sources.length} 份资料` : ''}</small></header>
    <div className="knowledge-folder-grid">{folders.map((folder) => <button type="button" className="knowledge-folder-card" key={folder.id} aria-label={`打开${folder.name}`} onClick={() => onOpen(folder.id)}><span className="knowledge-folder-card-icon"><FolderOpen size={20} /></span><span className="knowledge-folder-card-copy"><strong>{folder.name}</strong><small>{folder.description || '学习资料目录'}</small></span><span className="knowledge-folder-card-count">{folder.source_count} 份</span><ChevronRight size={16} /></button>)}{sources.map((source) => { const imageCount = sourceImageCount(source); return <button type="button" draggable onDragStart={(event) => onStartDragging(source.id, event)} onDragEnd={onStopDragging} className="knowledge-folder-card knowledge-source-card" key={source.id} aria-label={`打开${source.title}`} onClick={() => onOpenSource(source.id)}><span className="knowledge-folder-card-icon"><FileText size={20} /></span><span className="knowledge-folder-card-copy"><strong>{source.title}</strong><small>{fileLabel(source.media_type, source.scope)} · {source.chunk_count} 个片段{imageCount > 0 ? ` · ${imageCount} 张图片` : ''}</small></span><span className="knowledge-folder-card-count">独立资料</span><ChevronRight size={16} /></button> })}{folders.length === 0 && sources.length === 0 && <EmptyState title="还没有资料" detail="上传一份学习资料开始整理。" />}</div>
  </section>
}

function RootSourceWorkspace({ scope, sources, selectedId, onBack, onSelect, onStartDragging, onStopDragging, renderDetail }: { scope: Tab; sources: KnowledgeSource[]; selectedId: string; onBack: () => void; onSelect: (sourceId: string) => void; onStartDragging: (sourceId: string, event: DragEvent<HTMLElement>) => void; onStopDragging: () => void; renderDetail: () => ReactNode }) {
  return <section className="knowledge-root-source-workspace" aria-label="独立资料详情"><header className="knowledge-folder-content-header"><button type="button" className="knowledge-back" onClick={onBack}><ArrowLeft size={15} />全部目录</button><div><span>{scopeLabel(scope)}</span><h2>独立资料</h2><p>根目录中的资料</p></div><small>{sources.length} 份资料</small></header><div className="knowledge-workspace"><div className="knowledge-source-list"><ol>{sources.map((source) => <SourceRow key={source.id} source={source} selected={source.id === selectedId} onSelect={() => onSelect(source.id)} onStartDragging={onStartDragging} onStopDragging={onStopDragging} />)}</ol></div><article className="knowledge-detail">{renderDetail()}</article></div></section>
}

function KnowledgeDetail({ source, onToggle, toggling, onReindex, reindexing, onDelete, deleting }: { source: KnowledgeSourceDetail; onToggle: () => void; toggling: boolean; onReindex: () => void; reindexing: boolean; onDelete: () => void; deleting: boolean }) {
  const preview = source.preview ?? []
  const media = source.media_preview ?? []
  const hasMedia = (source.image_count ?? 0) > 0 || media.length > 0
  const stats = source.parse_stats ?? {}
  const stat = (key: string) => Number(stats[key] ?? 0)
  const hasStats = Object.keys(stats).length > 0
  const textCount = source.chunk_count ?? 0
  const imageCount = source.image_count ?? media.length
  return <div className="knowledge-detail-content"><header><div><span>{source.folder_name ?? scopeLabel(source.scope)}</span><h2>{source.title}</h2><p>{fileLabel(source.media_type, source.scope)} · {formatSize(source.size_bytes)} · {textCount} 个片段{imageCount > 0 ? ` · ${imageCount} 张图片` : ''}</p></div></header><div className="knowledge-state"><span className={stateClass(source.status)}>{stateLabel(source)}</span>{hasMedia && <span className="knowledge-capability">{imageIndexLabel(source.image_index_status ?? 'empty', true)}</span>}{source.graph_status === 'ready' && <span className="knowledge-capability">图文已关联</span>}{source.attribution && <small>{source.attribution}</small>}</div>{isIndexing(source) && <p className="knowledge-index-progress" role="status">{source.index_stage ?? '正在准备资料'} · {source.index_progress}%</p>}{source.index_error && <p className="knowledge-error" role="alert">处理提示：{friendlyIndexError(source.index_error)}</p>}{hasStats && <section className="knowledge-parse-summary" aria-label="解析摘要"><div><strong>{stat('page_count')}</strong><small>总页数</small></div><div><strong>{stat('chunk_count') || textCount}</strong><small>切块片段</small></div><div><strong>{stat('figure_count') || imageCount}</strong><small>已保留图片</small></div>{stat('pages_needing_ocr') > 0 && <div className="is-warning"><strong>{stat('pages_needing_ocr')}</strong><small>待文字识别</small></div>}</section>}{media.length > 0 && <section className="knowledge-media-preview"><div><h3>资料图片</h3><span>{media.length < imageCount ? `预览 ${media.length} / ${imageCount} 张 · ` : ''}{imageIndexLabel(source.image_index_status ?? 'empty', true)}</span></div>{source.image_index_error && <p className="knowledge-media-error">图片搜索提示：{friendlyIndexError(source.image_index_error)}</p>}<div className="knowledge-media-grid">{media.map((item) => <figure key={String(item.asset_id)}><img src={String(item.url)} alt={String(item.alt_text ?? '资料中的教学图片')} loading="lazy" /><figcaption>{String(item.alt_text ?? '资料中的教学图片')} · 第 {String(item.page ?? 1)} 页</figcaption></figure>)}</div></section>}<div className="knowledge-actions"><button type="button" onClick={onToggle} disabled={toggling || isIndexing(source)}>{source.enabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}{source.enabled ? '停用' : '启用'}</button><button type="button" onClick={onReindex} disabled={reindexing || isIndexing(source)}>{reindexing ? <LoaderCircle className="s1-spin" size={16} /> : <RefreshCw size={16} />}重新索引</button><button type="button" className="is-danger" onClick={onDelete} disabled={deleting}><Trash2 size={16} />删除资料</button></div><section className="knowledge-preview"><div className="knowledge-preview-heading"><h3>正文解析</h3>{preview.length < textCount && <span>预览 {preview.length} / {textCount} 个片段</span>}</div><div className="knowledge-preview-scroll">{preview.length ? preview.map((item, index) => <article key={`${String(item.section)}-${index}`}><small>{previewLabel(item.section, item.page)}</small><p>{String(item.text)}</p></article>) : <p>{isIndexing(source) ? '资料正在处理中，完成后会在这里显示内容。' : '当前资料没有可显示的解析片段。'}</p>}</div></section></div>
}

function KnowledgeListSkeleton() { return <div className="workspace-list-skeleton" role="status" aria-label="正在读取知识库"><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /><span className="ui-skeleton" /></div> }

function KnowledgeSearchResults({ result }: { result: { citations?: Array<Record<string, unknown>>; image_results?: Array<Record<string, unknown>>; graph_paths?: Array<Record<string, unknown>> } }) {
  const citations = result.citations ?? []
  const imageResults = result.image_results ?? []
  const graphPaths = result.graph_paths ?? []
  const hasResults = citations.length > 0 || imageResults.length > 0 || graphPaths.length > 0
  return <section className="knowledge-search-results"><header><div><span>搜索结果</span><h2>{hasResults ? '已找到相关资料' : '没有找到相关资料'}</h2></div><small>{imageResults.length ? `${imageResults.length} 张相关图片` : graphPaths.length ? `${graphPaths.length} 条资料关联` : '文字资料'}</small></header>{!hasResults ? <p>可以换一个关键词，或先上传一份学习资料。</p> : <div className="knowledge-search-grid">{citations.slice(0, 5).map((item, index) => <article key={`${String(item.chunk_id)}-${index}`}><strong>{String(item.document_name ?? '学习资料')}</strong><small>{item.page ? `第 ${String(item.page)} 页` : '切块片段'}</small><p>{String(item.snippet ?? '')}</p></article>)}{imageResults.slice(0, 4).map((item, index) => <article className="has-image" key={`${String(item.asset_id)}-${index}`}><img src={String(item.url)} alt={String(item.caption ?? '相关资料图片')} loading="lazy" /><div><strong>{String(item.document_name ?? '学习资料')}</strong><small>{item.section ? String(item.section) : `第 ${String(item.page ?? 1)} 页`}</small><p>{String(item.caption ?? '相关资料图片')}</p></div></article>)}{graphPaths.slice(0, 4).map((item, index) => <article className="knowledge-graph-result" key={`${String(item.chunk_id ?? 'graph')}-${index}`}><strong>相关资料关联</strong><small>{String(item.from ?? '')}{item.to ? ` → ${String(item.to)}` : ''}</small><p>{String(item.document_name ?? '同一份资料中的相邻片段')}</p></article>)}</div>}</section>
}

function SourceRow({ source, selected, onSelect, selectable = false, checked = false, onToggle, onStartDragging, onStopDragging }: { source: KnowledgeSource; selected: boolean; onSelect: () => void; selectable?: boolean; checked?: boolean; onToggle?: () => void; onStartDragging?: (sourceId: string, event: DragEvent<HTMLElement>) => void; onStopDragging?: () => void }) {
  const imageCount = sourceImageCount(source)
  return <li className={`knowledge-source-row${selectable ? ' has-selection' : ''}`}>{selectable && <label className="knowledge-source-check"><input type="checkbox" aria-label={`选择处理${source.title}`} checked={checked} onChange={onToggle} /></label>}<button type="button" draggable={!selectable} className={selected ? 'is-selected' : ''} onClick={onSelect} onDragStart={(event) => onStartDragging?.(source.id, event)} onDragEnd={onStopDragging}><span><FileText size={17} /></span><div><strong>{source.title}</strong><small>{isIndexing(source) ? `${source.index_stage ?? '正在索引'} ${source.index_progress}%` : `${fileLabel(source.media_type, source.scope)} · ${source.chunk_count} 个片段`}{imageCount > 0 ? ` · ${imageCount} 张图片` : ''}</small></div><i className={stateClass(source.status)}>{stateLabel(source)}</i></button></li>
}

function isIndexing(source: KnowledgeSource) { return ['rebuilding', 'indexing'].includes(source.status) }
function stateClass(status: string) { return status === 'ready' ? 'is-ready' : status === 'failed' ? 'is-failed' : status === 'needs_ocr' ? 'is-warning' : 'is-disabled' }
function stateLabel(source: KnowledgeSource) { if (source.status === 'queued') return '待处理'; if (source.status === 'rebuilding' || source.status === 'indexing') return '索引中'; if (source.status === 'needs_ocr') return '需要文字识别'; if (source.status === 'failed') return '索引失败'; return source.enabled ? '已索引' : source.status === 'disabled' ? '已停用' : source.status }
function compareKnowledgeSources(left: KnowledgeSource, right: KnowledgeSource) {
  const statusOrder = (source: KnowledgeSource) => {
    if (source.status === 'ready') return 0
    if (isIndexing(source)) return 1
    if (source.status === 'failed') return 2
    if (source.status === 'queued' || source.status === 'needs_ocr') return 3
    return 4
  }
  const statusDifference = statusOrder(left) - statusOrder(right)
  if (statusDifference !== 0) return statusDifference
  const titleDifference = left.title.localeCompare(right.title, 'zh-CN', { numeric: true, sensitivity: 'base' })
  return titleDifference !== 0 ? titleDifference : left.id.localeCompare(right.id)
}
function scopeLabel(value: string) { return value === 'user' ? '我的资料' : value === 'qbank_explanations' ? '题库解析' : '系统资料' }
function fileLabel(mediaType: string, scope?: string) { return scope === 'qbank_explanations' ? '题目解析' : mediaType.includes('pdf') ? 'PDF' : mediaType.includes('wordprocessingml') ? 'DOCX' : mediaType.includes('markdown') ? 'Markdown' : 'TXT' }
function formatSize(bytes: number) { return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB` }
function sourceImageCount(source: KnowledgeSource) { return source.image_count ?? Number((source.parse_stats ?? {}).figure_count ?? 0) }
function previewLabel(section: unknown, page: unknown) { const label = String(section); return page && !/第\s*\d+\s*页/.test(label) ? `${label} · 第 ${String(page)} 页` : label }
function imageIndexLabel(status: string, hasMedia = false) { return status === 'ready' ? '图片可用于资料搜索' : status === 'pending' ? '图片处理中' : status === 'failed' ? '图片处理失败，可重新索引' : status === 'empty' && hasMedia ? '图片已提取，可在资料中查看' : status === 'empty' ? '没有图片' : '图片待更新' }
function friendlyIndexError(error: string) { if (/unexpectedresponse|qdrant|vector|embedding|connection|timeout/i.test(error)) return '图片处理未完成，文字内容和图片预览仍可查看；请稍后重新索引。'; return error }

const ROOT_DROP_TARGET = '__knowledge_root__'

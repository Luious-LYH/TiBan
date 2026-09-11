import { BookOpenText, ChevronRight, FileText, LoaderCircle, MessageSquarePlus, Plus, Send, Sparkles, Trash2 } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { createMentorConversation, deleteMentorConversation, getKnowledgeSources, getMentorConversation, listMentorConversations, resolveApiUrl, streamMentorMessage, uploadChatImage, type MentorMessage, type TutorStreamEvent } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { ImageAttachment } from '../../components/shared/ImageAttachment'

type MentorSource = { document_name?: string; section?: string; page?: string; snippet?: string }
type LiveMessage = { id: string; role: 'user' | 'assistant'; content: string; imageUrl?: string; imageAssetId?: string; imageAttached?: boolean; activity?: Array<{ label?: string; status?: string }>; sources?: MentorSource[] }
const starters = ['根据我最近的错题，告诉我接下来应该复习什么', '总结我最近容易混淆的知识点', '帮我制定今天 30 分钟的刷题计划']

export function MentorPage() {
  const query = useQueryClient()
  const conversations = useQuery({ queryKey: ['mentor-conversations'], queryFn: () => listMentorConversations() })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const effectiveId = selectedId ?? conversations.data?.[0]?.id ?? null
  const detail = useQuery({ queryKey: ['mentor-conversation', effectiveId], queryFn: () => getMentorConversation(effectiveId ?? ''), enabled: Boolean(effectiveId) })
  const knowledge = useQuery({ queryKey: ['knowledge-sources'], queryFn: () => getKnowledgeSources() })
  const [draft, setDraft] = useState('')
  const [attachment, setAttachment] = useState<File | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [live, setLive] = useState<LiveMessage[]>([])
  const [running, setRunning] = useState(false)
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null)
  const controller = useRef<AbortController | null>(null)
  const streaming = useRef(false)
  const turnSequence = useRef(0)
  const loadedConversation = useRef<string | null>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const [follow, setFollow] = useState(true)
  const [contextMenu, setContextMenu] = useState<{ conversationId: string; x: number; y: number } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; title: string } | null>(null)
  const create = useMutation({ mutationFn: createMentorConversation, onSuccess: (item) => { setSelectedId(item.id); void query.invalidateQueries({ queryKey: ['mentor-conversations'] }) } })
  const remove = useMutation({
    mutationFn: (conversationId: string) => deleteMentorConversation(conversationId),
    onSuccess: async (_result, conversationId) => {
      if (effectiveId === conversationId) {
        controller.current?.abort()
        streaming.current = false
        setRunning(false)
        setActiveMessageId(null)
        setSelectedId(null)
        setLive([])
        loadedConversation.current = null
      }
      setContextMenu(null)
      setDeleteTarget(null)
      query.removeQueries({ queryKey: ['mentor-conversation', conversationId] })
      await query.invalidateQueries({ queryKey: ['mentor-conversations'] })
    },
  })

  const savedMessages = useMemo(() => (detail.data?.messages ?? []) as MentorMessage[], [detail.data?.messages])
  // Keep the completed streamed turn visible until a later navigation or a
  // page reload intentionally hydrates persisted history.  Otherwise the
  // render would switch to the stale query snapshot as soon as `running`
  // becomes false and the learner would see their first reply disappear.
  const messages: LiveMessage[] = live.length > 0 ? live : savedMessages.map(toLiveMessage)
  useEffect(() => {
    const conversationId = detail.data?.id
    if (!conversationId || loadedConversation.current === conversationId || streaming.current) return
    loadedConversation.current = conversationId
    setLive(savedMessages.map(toLiveMessage))
  }, [detail.data?.id, savedMessages])
  useEffect(() => { const node = transcript.current; if (!node || !follow) return; const frame = requestAnimationFrame(() => { node.scrollTop = node.scrollHeight }); return () => cancelAnimationFrame(frame) }, [follow, messages.length, running])

  async function startConversation() {
    const item = await create.mutateAsync()
    loadedConversation.current = item.id
    setLive([])
    return item.id
  }

  async function send(value = draft, nextAttachment = attachment, existingAssetId?: string) {
    const text = value.trim()
    if (!text || running) return
    const conversationId = effectiveId ?? await startConversation()
    if (!conversationId) return
    setSendError(null)
    setDraft('')
    // Mark synchronously: the detail query for a newly-created conversation
    // can resolve between these state updates. It must not replace the first
    // live assistant turn with an empty persisted message list.
    streaming.current = true
    setRunning(true)
    setFollow(true)
    const next = new AbortController()
    controller.current?.abort()
    controller.current = next
    try {
      const uploaded = nextAttachment && !existingAssetId ? await uploadChatImage(nextAttachment) : null
      const assetId = existingAssetId ?? uploaded?.asset_id
      const sequence = ++turnSequence.current
      const user: LiveMessage = { id: `local-user-${sequence}`, role: 'user', content: text, imageUrl: resolveApiUrl(uploaded?.url), imageAssetId: assetId, imageAttached: Boolean(assetId) }
      const assistantId = `local-assistant-${sequence}`
      setLive((current) => [...(effectiveId ? current : []), user, { id: assistantId, role: 'assistant', content: '', activity: [], sources: [] }])
      setActiveMessageId(assistantId)
      setAttachment(null)
      if (assetId) await streamMentorMessage(conversationId, text, (event) => handleEvent(event, assistantId), next.signal, 'demo_learner', assetId)
      else await streamMentorMessage(conversationId, text, (event) => handleEvent(event, assistantId), next.signal)
      await query.invalidateQueries({ queryKey: ['mentor-conversations'] })
      await query.invalidateQueries({ queryKey: ['mentor-conversation', conversationId] })
    } catch (error) {
      if ((error as Error).name !== 'AbortError') setSendError((error as Error).message)
    } finally {
      streaming.current = false
      setRunning(false)
      setActiveMessageId(null)
    }
  }

  function handleEvent(event: TutorStreamEvent, assistantId: string) {
    setLive((current) => current.map((item) => {
      if (item.id !== assistantId) return item
      if (event.event === 'token') return { ...item, content: item.content + String(event.data.text ?? '') }
      if (event.event === 'activity') return { ...item, activity: [...(item.activity ?? []).filter((entry) => entry.label !== String(event.data.label ?? '')), { label: String(event.data.label ?? ''), status: String(event.data.status ?? '') }] }
      if (event.event === 'source') return { ...item, sources: [...(item.sources ?? []), event.data as MentorSource] }
      if (event.event === 'error') return { ...item, content: String(event.data.message ?? '带教 Agent 暂不可用。') }
      return item
    }))
  }

  if (conversations.isPending) return <LoadingState label="正在准备带教 Agent…" />
  if (conversations.isError) return <ErrorState message={conversations.error.message} onRetry={() => void conversations.refetch()} />

  const enabledSources = (knowledge.data ?? []).filter((item) => item.enabled)
  return <div className="mentor-page" data-testid="mentor-page" onClick={() => setContextMenu(null)}>
    <aside className="mentor-history"><header><div><span>Agent</span><h1>带教 Agent</h1></div><button type="button" onClick={() => void startConversation()} disabled={create.isPending} aria-label="新建带教对话"><Plus size={17} /></button></header><p>跨题库读取你的作答、复习安排和学习记忆。</p><div className="mentor-history-label"><span>最近对话</span><small>右键管理</small></div><nav>{(conversations.data ?? []).length === 0 ? <p className="mentor-history-empty">还没有带教对话</p> : conversations.data?.map((item) => <button type="button" key={item.id} className={item.id === effectiveId ? 'is-selected' : ''} title="右键删除对话" onContextMenu={(event) => { event.preventDefault(); event.stopPropagation(); setContextMenu({ conversationId: item.id, x: event.clientX, y: event.clientY }) }} onClick={() => { loadedConversation.current = null; setSelectedId(item.id); setLive([]) }}><span>{item.title}</span><small>{formatTime(item.updated_at)}</small></button>)}</nav></aside>
    <main className="mentor-conversation"><header><div><span className="mentor-avatar"><Sparkles size={17} /></span><div><strong>带教 Agent</strong><small>基于真实学习记录与已启用资料</small></div></div>{running && <span className="mentor-running" role="status"><LoaderCircle className="s1-spin" size={14} />正在生成回答…<i className="tutor-status-dots" aria-hidden="true">•••</i></span>}</header><div className="mentor-transcript" ref={transcript} onScroll={(event) => { const node = event.currentTarget; setFollow(node.scrollHeight - node.scrollTop - node.clientHeight < 36) }}>
      {!effectiveId && <MentorEmpty onSend={(text) => void send(text)} disabled={false} />}
      {effectiveId && detail.isPending && <LoadingState label="正在读取对话…" />}
      {effectiveId && detail.isError && <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />}
      {messages.map((item) => <MentorTurn key={item.id} item={item} isStreaming={running && item.id === activeMessageId} />)}
    </div>{!follow && <button className="mentor-jump" type="button" onClick={() => { setFollow(true); transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: 'smooth' }) }}>回到底部</button>}
    <footer><ImageAttachment file={attachment} onChange={setAttachment} disabled={running}><label><span className="s1-visually-hidden">向带教 Agent 提问</span><textarea aria-label="向带教 Agent 提问" rows={2} value={draft} placeholder="问问我最近该复习什么，或直接提一个知识问题…" disabled={running} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} /><button type="button" aria-label="发送给带教 Agent" disabled={!draft.trim() || running} onClick={() => void send()}><Send size={17} /></button></label></ImageAttachment>{sendError && <p className="mentor-composer-error" role="alert">{sendError}</p>}</footer></main>
    <aside className="mentor-knowledge"><header><BookOpenText size={17} /><div><strong>已启用资料</strong><small>相关问题会自动参考这些资料</small></div></header><div>{knowledge.isPending ? <LoadingState label="正在读取资料…" /> : enabledSources.length === 0 ? <EmptyState title="没有启用资料" detail="到知识库添加或启用一份学习资料。" /> : enabledSources.map((source) => <article key={source.id}><FileText size={16} /><div><strong>{source.title}</strong><small>{source.scope === 'user' ? '我的资料' : source.scope === 'qbank_explanations' ? '题库解析' : '系统资料'} · {source.chunk_count} 个片段</small></div></article>)}</div><Link to="/knowledge">管理知识库 <ChevronRight size={14} /></Link></aside>
    {contextMenu && <div className="mentor-context-menu" role="menu" style={{ left: Math.min(contextMenu.x, window.innerWidth - 176), top: Math.min(contextMenu.y, window.innerHeight - 60) }} onClick={(event) => event.stopPropagation()}><button type="button" role="menuitem" onClick={() => { const item = conversations.data?.find((entry) => entry.id === contextMenu.conversationId); if (item) setDeleteTarget({ id: item.id, title: item.title }); setContextMenu(null) }}><Trash2 size={15} />删除对话</button></div>}
    {deleteTarget && <div className="mentor-delete-confirm" role="dialog" aria-modal="true" aria-labelledby="mentor-delete-title" onClick={(event) => event.stopPropagation()}><div><span className="mentor-delete-icon"><Trash2 size={16} /></span><div><strong id="mentor-delete-title">删除这段对话？</strong><p>“{deleteTarget.title}”及其中消息将被永久删除。</p></div></div><footer><button type="button" onClick={() => setDeleteTarget(null)} disabled={remove.isPending}>取消</button><button type="button" className="mentor-delete-action" onClick={() => remove.mutate(deleteTarget.id)} disabled={remove.isPending}>{remove.isPending ? '正在删除…' : '删除对话'}</button></footer>{remove.isError && <p role="alert">删除失败：{remove.error.message}</p>}</div>}
  </div>
}

function MentorEmpty({ onSend, disabled = false }: { onSend: (text: string) => void; disabled?: boolean }) { return <section className="mentor-empty"><span className="mentor-empty-mark"><MessageSquarePlus size={22} /></span><h2>今天想从哪里开始？</h2><p>我会结合你的学习记录、复习安排和相关资料陪你制定下一步。</p><div>{starters.map((item) => <button type="button" key={item} disabled={disabled} onClick={() => onSend(item)}>{item}<ChevronRight size={15} /></button>)}</div></section> }
function MentorTurn({ item, isStreaming = false }: { item: LiveMessage; isStreaming?: boolean }) { const evidence = dedupe(item.sources ?? []); const completed = (item.activity ?? []).filter((entry) => entry.status === 'completed'); return <article className={`mentor-turn is-${item.role}`}><span>{item.role === 'user' ? '你' : '带教 Agent'}</span>{item.imageUrl && <img className="mentor-turn-image" src={item.imageUrl} alt="你附加的图片" />}{item.imageAttached && !item.imageUrl && <small className="mentor-image-status">已附图片</small>}{item.content && <p>{item.content}</p>}{item.role === 'assistant' && isStreaming && <div className="mentor-answer-status" role="status" aria-live="polite"><LoaderCircle className="s1-spin" size={14} /><span>正在生成回答…</span><i className="tutor-status-dots" aria-hidden="true">•••</i></div>}{completed.length > 0 && <details><summary>{completed.map((entry) => entry.label).filter(Boolean).join(' · ')}</summary></details>}{evidence.length > 0 && <details className="mentor-evidence"><summary>参考资料 {evidence.length} 条</summary><div>{evidence.map((source, index) => <article key={`${source.document_name}-${source.section}-${index}`}><strong>{source.document_name ?? '学习资料'}</strong><small>{source.section ?? source.page}</small><p>{source.snippet?.slice(0, 160)}</p></article>)}</div></details>}</article> }
function toLiveMessage(item: MentorMessage): LiveMessage { return { id: item.id, role: item.role, content: item.content, imageAttached: item.image_attached, imageAssetId: item.image_asset_id ?? undefined, imageUrl: item.image_asset_id ? resolveApiUrl(`/api/v3/assets/chat-images/${item.image_asset_id}`) : undefined, activity: (item.activity ?? []) as LiveMessage['activity'], sources: (item.sources ?? []) as LiveMessage['sources'] } }
function dedupe(sources: MentorSource[]) { const seen = new Set<string>(); return sources.filter((source) => { const key = `${source.document_name ?? ''}:${source.section ?? ''}`; if (seen.has(key)) return false; seen.add(key); return true }) }
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? '' : `${date.getMonth() + 1}/${date.getDate()}` }

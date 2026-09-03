import { BookOpenText, ChevronRight, FileText, LoaderCircle, MessageSquarePlus, Plus, Send, Sparkles } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { createMentorConversation, getKnowledgeSources, getMentorConversation, listMentorConversations, streamMentorMessage, type MentorMessage, type TutorStreamEvent } from '../../api/client'
import { EmptyState, ErrorState, LoadingState } from '../../components/shared/AsyncState'

type MentorSource = { document_name?: string; section?: string; page?: string; snippet?: string }
type LiveMessage = { id: string; role: 'user' | 'assistant'; content: string; activity?: Array<{ label?: string; status?: string }>; sources?: MentorSource[] }
const starters = ['根据我最近的错题，告诉我接下来应该复习什么', '总结我最近容易混淆的知识点', '帮我制定今天 30 分钟的刷题计划']

export function MentorPage() {
  const query = useQueryClient()
  const conversations = useQuery({ queryKey: ['mentor-conversations'], queryFn: () => listMentorConversations() })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const effectiveId = selectedId ?? conversations.data?.[0]?.id ?? null
  const detail = useQuery({ queryKey: ['mentor-conversation', effectiveId], queryFn: () => getMentorConversation(effectiveId ?? ''), enabled: Boolean(effectiveId) })
  const knowledge = useQuery({ queryKey: ['knowledge-sources'], queryFn: () => getKnowledgeSources() })
  const [draft, setDraft] = useState('')
  const [live, setLive] = useState<LiveMessage[]>([])
  const [running, setRunning] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const streaming = useRef(false)
  const loadedConversation = useRef<string | null>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const [follow, setFollow] = useState(true)
  const create = useMutation({ mutationFn: createMentorConversation, onSuccess: (item) => { setSelectedId(item.id); void query.invalidateQueries({ queryKey: ['mentor-conversations'] }) } })

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

  async function send(value = draft) {
    const text = value.trim()
    if (!text || running) return
    const conversationId = effectiveId ?? await startConversation()
    const user: LiveMessage = { id: `local-user-${Date.now()}`, role: 'user', content: text }
    const assistantId = `local-assistant-${Date.now()}`
    setLive((current) => [...(effectiveId ? current : []), user, { id: assistantId, role: 'assistant', content: '', activity: [], sources: [] }])
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
      await streamMentorMessage(conversationId, text, (event) => handleEvent(event, assistantId), next.signal)
      await query.invalidateQueries({ queryKey: ['mentor-conversations'] })
      await query.invalidateQueries({ queryKey: ['mentor-conversation', conversationId] })
    } catch (error) {
      if ((error as Error).name !== 'AbortError') setLive((current) => current.map((item) => item.id === assistantId ? { ...item, content: `暂时无法完成这次回答：${(error as Error).message}` } : item))
    } finally {
      streaming.current = false
      setRunning(false)
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
  return <div className="mentor-page" data-testid="mentor-page">
    <aside className="mentor-history"><header><div><span>Agent</span><h1>带教 Agent</h1></div><button type="button" onClick={() => void startConversation()} disabled={create.isPending} aria-label="新建带教对话"><Plus size={17} /></button></header><p>跨题库读取你的作答、复习安排和学习记忆。</p><div className="mentor-history-label">最近对话</div><nav>{(conversations.data ?? []).length === 0 ? <p className="mentor-history-empty">还没有带教对话</p> : conversations.data?.map((item) => <button type="button" key={item.id} className={item.id === effectiveId ? 'is-selected' : ''} onClick={() => { loadedConversation.current = null; setSelectedId(item.id); setLive([]) }}><span>{item.title}</span><small>{formatTime(item.updated_at)}</small></button>)}</nav></aside>
    <main className="mentor-conversation"><header><div><span className="mentor-avatar"><Sparkles size={17} /></span><div><strong>带教 Agent</strong><small>基于真实学习记录与已启用资料</small></div></div>{running && <span className="mentor-running"><LoaderCircle className="s1-spin" size={14} />正在整理</span>}</header><div className="mentor-transcript" ref={transcript} onScroll={(event) => { const node = event.currentTarget; setFollow(node.scrollHeight - node.scrollTop - node.clientHeight < 36) }}>
      {!effectiveId && <MentorEmpty onSend={(text) => void send(text)} />}
      {effectiveId && detail.isPending && <LoadingState label="正在读取对话…" />}
      {effectiveId && detail.isError && <ErrorState message={detail.error.message} onRetry={() => void detail.refetch()} />}
      {messages.map((item) => <MentorTurn key={item.id} item={item} />)}
    </div>{!follow && <button className="mentor-jump" type="button" onClick={() => { setFollow(true); transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: 'smooth' }) }}>回到底部</button>}
    <footer><label><span className="s1-visually-hidden">向带教 Agent 提问</span><textarea aria-label="向带教 Agent 提问" rows={2} value={draft} placeholder="问问我最近该复习什么，或直接提一个知识问题…" disabled={running} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} /><button type="button" aria-label="发送给带教 Agent" disabled={!draft.trim() || running} onClick={() => void send()}><Send size={17} /></button></label></footer></main>
    <aside className="mentor-knowledge"><header><BookOpenText size={17} /><div><strong>已启用资料</strong><small>带教 Agent 仅在需要时检索</small></div></header><div>{knowledge.isPending ? <LoadingState label="正在读取资料…" /> : enabledSources.length === 0 ? <EmptyState title="没有启用资料" detail="到知识库添加或启用一份学习资料。" /> : enabledSources.map((source) => <article key={source.id}><FileText size={16} /><div><strong>{source.title}</strong><small>{source.scope === 'user' ? '我的资料' : source.scope === 'qbank_explanations' ? '题库解析' : '系统资料'} · {source.chunk_count} 个片段</small></div></article>)}</div><Link to="/knowledge">管理知识库 <ChevronRight size={14} /></Link></aside>
  </div>
}

function MentorEmpty({ onSend }: { onSend: (text: string) => void }) { return <section className="mentor-empty"><span className="mentor-empty-mark"><MessageSquarePlus size={22} /></span><h2>今天想从哪里开始？</h2><p>我会在需要时读取真实的学习记录、复习队列和已启用资料。</p><div>{starters.map((item) => <button type="button" key={item} onClick={() => onSend(item)}>{item}<ChevronRight size={15} /></button>)}</div></section> }
function MentorTurn({ item }: { item: LiveMessage }) { const evidence = dedupe(item.sources ?? []); const completed = (item.activity ?? []).filter((entry) => entry.status === 'completed'); return <article className={`mentor-turn is-${item.role}`}><span>{item.role === 'user' ? '你' : '带教 Agent'}</span>{item.content && <p>{item.content}</p>}{completed.length > 0 && <details><summary>{completed.map((entry) => entry.label).filter(Boolean).join(' · ')}</summary></details>}{evidence.length > 0 && <div className="mentor-evidence">{evidence.map((source, index) => <article key={`${source.document_name}-${source.section}-${index}`}><strong>{source.document_name ?? '学习资料'}</strong><small>{source.section ?? source.page}</small><p>{source.snippet?.slice(0, 160)}</p></article>)}</div>}</article> }
function toLiveMessage(item: MentorMessage): LiveMessage { return { id: item.id, role: item.role, content: item.content, activity: (item.activity ?? []) as LiveMessage['activity'], sources: (item.sources ?? []) as LiveMessage['sources'] } }
function dedupe(sources: MentorSource[]) { const seen = new Set<string>(); return sources.filter((source) => { const key = `${source.document_name ?? ''}:${source.section ?? ''}`; if (seen.has(key)) return false; seen.add(key); return true }) }
function formatTime(value: string) { const date = new Date(value); return Number.isNaN(date.getTime()) ? '' : `${date.getMonth() + 1}/${date.getDate()}` }

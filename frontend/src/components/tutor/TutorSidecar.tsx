import { Bot, Check, ChevronDown, CornerDownLeft, ExternalLink, LoaderCircle, RotateCcw, Square, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { resolveApiUrl, streamTutor, uploadChatImage, type TutorStreamEvent } from '../../api/client'
import { ImageAttachment } from '../shared/ImageAttachment'

type TutorMode = 'study' | 'exam' | 'review'
type Source = { document_name?: string; page?: string; section?: string; snippet?: string; source_uri?: string; namespace?: string }
type Activity = { activity?: string; status?: string; label?: string; elapsed_ms?: number }
type Turn = { id: string; role: 'user' | 'assistant'; text: string; imageUrl?: string; imageAssetId?: string; sources?: Source[]; error?: string; reasoning?: string[]; activities?: Activity[]; durationMs?: number }

const starterPrompts = ['给我一点提示', '解释这道题', '为什么我这个选项错了？']

export function TutorSidecar({ questionId, practiceSessionId, tutorThreadId, attemptId, learnerId = 'demo_learner', mode, open, onClose, contextLabel }: { questionId: string; practiceSessionId: string; tutorThreadId: string; attemptId?: string; learnerId?: string; mode: TutorMode; open: boolean; onClose: () => void; contextLabel?: string }) {
  const controller = useRef<AbortController | null>(null)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [running, setRunning] = useState(false)
  const [activity, setActivity] = useState<string | null>(null)
  const [attachment, setAttachment] = useState<File | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [followTranscript, setFollowTranscript] = useState(true)
  const [activeAssistantId, setActiveAssistantId] = useState<string | null>(null)
  const transcript = useRef<HTMLDivElement>(null)
  const turnSequence = useRef(0)

  function reset() {
    controller.current?.abort()
    setTurns([])
    setMessage('')
    setAttachment(null)
    setSendError(null)
    setActivity(null)
    setActiveAssistantId(null)
  }

  useEffect(() => {
    const node = transcript.current
    if (!node || !followTranscript) return
    const frame = window.requestAnimationFrame(() => { node.scrollTop = node.scrollHeight })
    return () => window.cancelAnimationFrame(frame)
  }, [followTranscript, running, turns])

  async function send(nextMessage = message, nextAttachment = attachment, existingAssetId?: string) {
    const text = nextMessage.trim()
    if (!text || running || mode === 'exam') return
    const next = new AbortController()
    controller.current?.abort()
    controller.current = next
    setSendError(null)
    setMessage('')
    setRunning(true)
    setActivity(nextAttachment ? '正在准备图片…' : '正在整理回答…')
    setFollowTranscript(true)
    const sequence = ++turnSequence.current
    const assistantId = `assistant-${sequence}`
    // Reserve the assistant turn before uploading an optional attachment so
    // the single in-card status remains the only progress indicator once the
    // turn is mounted.
    setActiveAssistantId(assistantId)
    try {
      const uploaded = nextAttachment && !existingAssetId ? await uploadChatImage(nextAttachment) : null
      const assetId = existingAssetId ?? uploaded?.asset_id
      const userTurn: Turn = { id: `user-${sequence}`, role: 'user', text, imageUrl: resolveApiUrl(uploaded?.url), imageAssetId: assetId }
      const assistantTurn: Turn = { id: assistantId, role: 'assistant', text: '', sources: [], reasoning: [], activities: [] }
      setTurns((current) => [...current, userTurn, assistantTurn])
      setActiveAssistantId(assistantId)
      setAttachment(null)
      await streamTutor({ practice_session_id: practiceSessionId, tutor_thread_id: tutorThreadId, question_id: questionId, learner_id: learnerId, message: text, image_asset_id: assetId ?? null, attempt_id: attemptId ?? null, mode }, (event) => handleEvent(event, assistantId), next.signal)
    } catch (reason) {
      if ((reason as Error).name !== 'AbortError') setSendError((reason as Error).message)
    } finally { setRunning(false); setActivity(null); setActiveAssistantId(null) }
  }

  function handleEvent(event: TutorStreamEvent, assistantId: string) {
    if (event.event === 'message_start') {
      setActivity('正在理解当前题目…')
      return
    }
    if (event.event === 'tool_start') {
      setActivity(event.data.tool_name === 'retrieve_knowledge' ? '正在查找相关资料…' : '正在整理当前学习上下文…')
      return
    }
    setTurns((current) => current.map((turn) => {
      if (turn.id !== assistantId) return turn
      if (event.event === 'token') return { ...turn, text: turn.text + String(event.data.text ?? '') }
      if (event.event === 'reasoning') return { ...turn, reasoning: Array.isArray(event.data.summary) ? event.data.summary.map(String) : [] }
      if (event.event === 'activity') return { ...turn, activities: [...(turn.activities ?? []).filter((item) => item.activity !== String(event.data.activity ?? '')), event.data as Activity] }
      if (event.event === 'done') return { ...turn, durationMs: Number(event.data.duration_ms ?? 0) }
      // The runtime emits the question's public provenance when retrieval has
      // no match.  It is useful to the protocol, but it is not a RAG citation
      // and must not be presented as one to the learner.
      if (event.event === 'source' && event.data.status !== 'none' && event.data.namespace !== 'question_source') return { ...turn, sources: [...(turn.sources ?? []), event.data as Source] }
      if (event.event === 'error') return { ...turn, error: String(event.data.message ?? '智能辅导暂不可用，请重试。') }
      return turn
    }))
  }

  const lastUser = [...turns].reverse().find((turn) => turn.role === 'user')
  const sourceCount = useMemo(() => turns.reduce((count, turn) => count + (turn.sources?.length ?? 0), 0), [turns])
  const showEmpty = turns.length === 0
  const asideClass = open ? 'tutor-workspace is-open' : 'tutor-workspace'

  return <aside className={asideClass} aria-label="智能辅导" data-testid="tutor-sidecar">
    <header className="tutor-workspace-header">
      <div><span className="tutor-mark"><Bot size={17} /></span><span><strong>智能辅导</strong><small>当前题目 · {contextLabel ?? '当前题目'}</small></span></div>
      <div><button className="tutor-reset" type="button" onClick={reset}>新对话</button><button className="tutor-close" type="button" onClick={onClose} aria-label="关闭智能辅导"><X size={18} /></button></div>
    </header>
    {mode === 'exam' ? <div className="tutor-exam-lock"><strong>考试进行中</strong><span>完成本次考试后再一起复盘题目。</span></div> : <>
      <div className="tutor-context-status"><span><Check size={14} />当前题目已就绪</span>{sourceCount > 0 && <span><Check size={14} />已参考资料 {sourceCount} 条</span>}</div>
      <div className="tutor-transcript" ref={transcript} onScroll={(event) => { const node = event.currentTarget; setFollowTranscript(node.scrollHeight - node.scrollTop - node.clientHeight < 36) }} aria-live="polite" data-testid="tutor-transcript">
        {showEmpty && <div className="tutor-empty"><strong>智能辅导已准备好</strong><p>我会结合题目、你的作答和已返回的资料，陪你一步步梳理判断依据。</p></div>}
        {turns.map((turn) => <article className={`tutor-turn is-${turn.role}`} key={turn.id}>
          {turn.role === 'user' && <span className="tutor-role">你</span>}
          {turn.role === 'assistant' && <span className="s1-visually-hidden">智能辅导</span>}
          {turn.imageUrl && <img className="tutor-turn-image" src={turn.imageUrl} alt="你附加的图片" />}
          {turn.text && <p>{turn.text}</p>}
          {turn.role === 'assistant' && running && turn.id === activeAssistantId && !turn.error && <div className="tutor-answer-status" role="status" aria-live="polite"><LoaderCircle className="s1-spin" size={14} /><span>{activity ?? '正在生成回答…'}</span><i className="tutor-status-dots" aria-hidden="true">•••</i></div>}
          {turn.role === 'assistant' && <ActivitySummary activities={turn.activities ?? []} reasoning={turn.reasoning} durationMs={turn.durationMs} />}
          {turn.sources && turn.sources.length > 0 && <CitationList sources={turn.sources} />}
          {turn.error && <div className="tutor-error" role="alert">{turn.error}</div>}
        </article>)}
        {running && !turns.some((turn) => turn.id === activeAssistantId) && <div className="tutor-streaming" role="status" aria-live="polite"><LoaderCircle className="s1-spin" size={14} />{activity ?? '正在准备回答…'}<i className="tutor-status-dots" aria-hidden="true">•••</i></div>}
      </div>
      {!followTranscript && <button type="button" className="tutor-jump-bottom" onClick={() => { setFollowTranscript(true); transcript.current?.scrollTo({ top: transcript.current.scrollHeight, behavior: 'smooth' }) }}>回到底部</button>}
      {showEmpty && <div className="tutor-suggestions">{starterPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => void send(prompt)}>{prompt}</button>)}</div>}
      <div className="tutor-composer-wrap"><ImageAttachment file={attachment} onChange={setAttachment} disabled={running}><label className="tutor-composer"><span className="s1-visually-hidden">向智能辅导提问</span><textarea aria-label="向智能辅导提问" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} disabled={running} placeholder="继续追问当前题目…" rows={2} /><button type="button" aria-label="发送给智能辅导" disabled={!message.trim() || running} onClick={() => void send()}><CornerDownLeft size={17} /></button></label></ImageAttachment>
        {sendError && <p className="tutor-composer-error" role="alert">{sendError}</p>}
        <div className="tutor-actions">{running ? <button type="button" onClick={() => controller.current?.abort()}><Square size={14} />停止</button> : lastUser && <button type="button" onClick={() => void send(lastUser.text, null, lastUser.imageAssetId)}><RotateCcw size={14} />重新生成</button>}</div>
      </div>
    </>}
  </aside>
}

function ActivitySummary({ activities, reasoning, durationMs }: { activities: Activity[]; reasoning?: string[]; durationMs?: number }) {
  const completed = activities.filter((item) => item.status === 'completed')
  if (completed.length === 0 && !reasoning?.length && !durationMs) return null
  return <details className="tutor-activity-summary"><summary>{completed.length ? completed.map((item) => item.label ?? '已完成学习信息读取').join(' · ') : '已整理回答'}{durationMs ? ` · ${(durationMs / 1000).toFixed(1)} 秒` : ''}</summary><div>{reasoning?.map((item) => <span key={item}>{item}</span>)}{completed.map((item, index) => <span key={`${item.activity}-${index}`}>{item.label ?? '已完成'}</span>)}</div></details>
}

function displaySnippet(snippet?: string) { return snippet?.replace(/本地受治理导入。?/g, '').trim() }

function CitationList({ sources }: { sources: Source[] }) {
  const unique = useMemo(() => {
    const seen = new Set<string>()
    return sources.filter((source) => {
      const key = `${source.document_name ?? ''}::${source.section ?? source.page ?? ''}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [sources])
  return <details className="tutor-citations" data-testid="tutor-sources"><summary className="tutor-citations-title"><ChevronDown size={13} />参考资料 {unique.length} 条</summary><div className="tutor-citation-list">{unique.map((source, index) => <div className="tutor-citation" key={`${source.document_name}-${source.section ?? source.page ?? index}`}><strong>ⓘ {source.document_name ?? '教学资料'}</strong>{(source.page || source.section) && <small>{source.page && source.page !== '题目来源' ? `第 ${source.page} 页` : ''}{source.page && source.section ? ' · ' : ''}{source.section}</small>}{displaySnippet(source.snippet) && <p>{displaySnippet(source.snippet)?.slice(0, 180)}{(displaySnippet(source.snippet)?.length ?? 0) > 180 ? '…' : ''}</p>}{safeSourceUri(source.source_uri) && <a href={safeSourceUri(source.source_uri)} target="_blank" rel="noreferrer">查看来源 <ExternalLink size={11} /></a>}</div>)}</div></details>
}

function safeSourceUri(value?: string) {
  if (!value) return undefined
  try { return /^https?:$/.test(new URL(value).protocol) ? value : undefined } catch { return undefined }
}

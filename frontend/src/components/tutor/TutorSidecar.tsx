import { Bot, CornerDownLeft, LoaderCircle, RotateCcw, Square, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { streamTutor, type TutorStreamEvent } from '../../api/client'

type Source = { document_name?: string; page?: string; section?: string; snippet?: string }
type Turn = { id: string; role: 'user' | 'assistant'; text: string; tools?: string[]; sources?: Source[]; error?: string }

const starterPrompts = ['帮我梳理题干里可见的证据。', '这道题哪些说法超出了资料范围？', '请给我下一步观察的思路，不要透露答案。']

export function TutorSidecar({ questionId, attemptId, open, onClose }: { questionId: string; attemptId?: string; open: boolean; onClose: () => void }) {
  const controller = useRef<AbortController | null>(null)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  async function send(nextMessage = message) {
    const text = nextMessage.trim()
    if (!text || running) return
    const userTurn: Turn = { id: `user-${Date.now()}`, role: 'user', text }
    const assistantId = `assistant-${Date.now()}`
    const assistantTurn: Turn = { id: assistantId, role: 'assistant', text: '', tools: [], sources: [] }
    const conversation = [...turns, userTurn].slice(-12).map((turn) => ({ role: turn.role, content: turn.text }))
    const next = new AbortController()
    controller.current?.abort(); controller.current = next
    setTurns((current) => [...current, userTurn, assistantTurn]); setMessage(''); setActiveId(assistantId); setRunning(true)
    try {
      await streamTutor({ question_id: questionId, learner_id: 'demo_learner', message: text, attempt_id: attemptId ?? null, conversation }, (event) => handleEvent(event, assistantId), next.signal)
    } catch (reason) {
      if ((reason as Error).name !== 'AbortError') setTurns((current) => current.map((turn) => turn.id === assistantId ? { ...turn, error: (reason as Error).message } : turn))
    } finally { setRunning(false); setActiveId(null) }
  }

  function handleEvent(event: TutorStreamEvent, assistantId: string) {
    setTurns((current) => current.map((turn) => {
      if (turn.id !== assistantId) return turn
      if (event.event === 'token') return { ...turn, text: turn.text + String(event.data.text ?? '') }
      if (event.event === 'tool_start') return { ...turn, tools: [...(turn.tools ?? []), `正在读取 ${String(event.data.tool_name)}`] }
      if (event.event === 'tool_end') return { ...turn, tools: [...(turn.tools ?? []), `已完成 ${String(event.data.tool_name)}`] }
      if (event.event === 'source') return { ...turn, sources: [...(turn.sources ?? []), event.data as Source] }
      if (event.event === 'error') return { ...turn, error: String(event.data.message ?? 'Tutor 暂不可用。') }
      return turn
    }))
  }

  const lastUser = [...turns].reverse().find((turn) => turn.role === 'user')
  return <aside className={open ? 's1-card s1-tutor-card is-open' : 's1-card s1-tutor-card'} aria-label="Tutor Agent 连续辅导">
    <div className="s1-tutor-header"><div><span className="s1-tutor-orb"><Bot size={17} /></span><span><strong>Tutor Agent</strong><small>连续辅导 · 真实 SSE · 受限工具</small></span></div><button className="s1-icon-button s1-tutor-close" onClick={onClose} aria-label="关闭 Tutor"><X size={17} /></button></div>
    <p className="s1-tutor-explainer">提交前只能读取公开题面、资料和学习概览；提交后才可读取本次评分。这里展示的是资料依据和工具记录，不是原始模型思维链。</p>
    <div className="s1-chat-transcript" aria-live="polite" data-testid="tutor-transcript">
      {turns.length === 0 && <div className="s1-chat-empty"><strong>边答边问。</strong><span>我会围绕当前题面与可追溯资料引导观察，不会提供提交前答案。</span></div>}
      {turns.map((turn) => <article className={`s1-chat-turn is-${turn.role}`} key={turn.id}>
        <span className="s1-chat-role">{turn.role === 'user' ? '你' : 'Tutor'}</span>
        {turn.text && <p>{turn.text}</p>}
        {turn.tools && turn.tools.length > 0 && <details className="s1-chat-receipt" open={running && activeId === turn.id}><summary>辅导依据与工具记录</summary>{turn.tools.map((tool, index) => <small key={`${tool}-${index}`}>{tool}</small>)}</details>}
        {turn.sources && turn.sources.length > 0 && <div className="s1-chat-sources" data-testid="tutor-sources">{turn.sources.map((source, index) => <div className="s1-source-card" key={`${source.document_name}-${index}`}><small>{source.document_name} · 第 {source.page} 页 · {source.section}</small>{source.snippet && <p>{source.snippet}</p>}</div>)}</div>}
        {turn.error && <div className="s1-inline-error" role="alert">{turn.error}</div>}
      </article>)}
      {running && <div className="s1-chat-streaming"><LoaderCircle className="s1-spin" size={14} />正在依据允许的资料组织回复…</div>}
    </div>
    {turns.length === 0 && <div className="s1-starter-prompts">{starterPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => void send(prompt)}>{prompt}</button>)}</div>}
    <label className="s1-chat-composer"><span className="s1-visually-hidden">向 Tutor 提问</span><textarea aria-label="向 Tutor 提问" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} disabled={running} placeholder="例如：我遗漏了哪些可见证据？" rows={2} /><button className="s1-icon-button" type="button" aria-label="发送给 Tutor" disabled={!message.trim() || running} onClick={() => void send()}><CornerDownLeft size={17} /></button></label>
    <div className="s1-tutor-actions">{running ? <button className="s1-button s1-button-light" onClick={() => controller.current?.abort()}><Square size={15} />取消本轮</button> : lastUser && <button className="s1-button s1-button-light" onClick={() => void send(lastUser.text)}><RotateCcw size={15} />重试本轮</button>}</div>
  </aside>
}

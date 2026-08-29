import { Bot, CornerDownLeft, LoaderCircle, RotateCcw, Square, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { streamTutor, type TutorStreamEvent } from '../../api/client'

type TutorMode = 'study' | 'exam' | 'review'
type Source = { document_name?: string; page?: string; section?: string; snippet?: string; source_uri?: string }
type Turn = { id: string; role: 'user' | 'assistant'; text: string; sources?: Source[]; error?: string; reasoning?: string[] }

const starterPrompts = ['给我一点提示', '解释这道题', '为什么我这个选项错了？']

export function TutorSidecar({ questionId, attemptId, mode, open, onClose }: { questionId: string; attemptId?: string; mode: TutorMode; open: boolean; onClose: () => void }) {
  const controller = useRef<AbortController | null>(null)
  const providerRealRef = useRef(false)
  const [message, setMessage] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [running, setRunning] = useState(false)
  const [providerPending, setProviderPending] = useState(false)

  async function send(nextMessage = message) {
    const text = nextMessage.trim()
    if (!text || running || mode === 'exam') return
    const userTurn: Turn = { id: `user-${Date.now()}`, role: 'user', text }
    const assistantId = `assistant-${Date.now()}`
    const assistantTurn: Turn = { id: assistantId, role: 'assistant', text: '', sources: [], reasoning: [] }
    const conversation = [...turns, userTurn].slice(-12).map((turn) => ({ role: turn.role, content: turn.text }))
    const next = new AbortController()
    controller.current?.abort()
    controller.current = next
    setTurns((current) => [...current, userTurn, assistantTurn])
    setMessage('')
    setRunning(true)
    setProviderPending(false)
    providerRealRef.current = false
    try {
      await streamTutor({ question_id: questionId, learner_id: 'demo_learner', message: text, attempt_id: attemptId ?? null, mode, conversation }, (event) => handleEvent(event, assistantId), next.signal)
    } catch (reason) {
      if ((reason as Error).name !== 'AbortError') setTurns((current) => current.map((turn) => turn.id === assistantId ? { ...turn, error: (reason as Error).message } : turn))
    } finally {
      setRunning(false)
    }
  }

  function handleEvent(event: TutorStreamEvent, assistantId: string) {
    if (event.event === 'message_start') {
      const real = event.data.provider_real === true
      providerRealRef.current = real
      setProviderPending(!real)
      return
    }
    setTurns((current) => current.map((turn) => {
      if (turn.id !== assistantId) return turn
      if (event.event === 'token' && providerRealRef.current) return { ...turn, text: turn.text + String(event.data.text ?? '') }
      if (event.event === 'reasoning') return { ...turn, reasoning: Array.isArray(event.data.summary) ? event.data.summary.map(String) : [] }
      if (event.event === 'source' && event.data.status !== 'none') return { ...turn, sources: [...(turn.sources ?? []), event.data as Source] }
      if (event.event === 'error') return { ...turn, error: String(event.data.message ?? 'Tutor 暂不可用，请重试。') }
      return turn
    }))
  }

  function reset() {
    controller.current?.abort()
    setTurns([])
    setMessage('')
    setProviderPending(false)
    providerRealRef.current = false
  }

  const lastUser = [...turns].reverse().find((turn) => turn.role === 'user')
  const showEmpty = turns.length === 0
  return <aside className={open ? 's1-card s1-tutor-card is-open' : 's1-card s1-tutor-card'} aria-label="Tutor" data-testid="tutor-sidecar">
    <div className="s1-tutor-header">
      <div><span className="s1-tutor-orb"><Bot size={17} /></span><span><strong>Tutor</strong><small>有哪里不懂，直接问我。</small></span></div>
      <div className="s1-tutor-header-actions"><button className="s1-tutor-new-chat" type="button" onClick={reset}>新对话</button><button className="s1-icon-button s1-tutor-close" onClick={onClose} aria-label="关闭 Tutor"><X size={17} /></button></div>
    </div>
    {mode === 'exam' ? <div className="s1-tutor-exam-locked"><strong>考试进行中</strong><span>完成本次考试后再一起复盘题目。</span></div> : <>
      <div className="s1-chat-transcript" aria-live="polite" data-testid="tutor-transcript">
        {showEmpty && <div className="s1-chat-empty"><strong>Tutor</strong><span>有哪里不懂，直接问我。</span></div>}
        {turns.map((turn) => <article className={`s1-chat-turn is-${turn.role}`} key={turn.id}>
          <span className="s1-chat-role">{turn.role === 'user' ? '你' : 'Tutor'}</span>
          {turn.role === 'assistant' && turn.reasoning && turn.reasoning.length > 0 && <details className="s1-chat-reasoning"><summary>解题思路</summary><ol>{turn.reasoning.map((step) => <li key={step}>{step}</li>)}</ol></details>}
          {turn.role === 'assistant' && !turn.text && providerPending && <p className="s1-tutor-provider-pending">尚未配置 AI 模型</p>}
          {turn.text && <p>{turn.text}</p>}
          {turn.sources && turn.sources.length > 0 && <details className="s1-chat-sources" data-testid="tutor-sources"><summary>参考资料 {turn.sources.length}</summary>{turn.sources.map((source, index) => <div className="s1-source-card" key={`${source.document_name}-${index}`}><strong>{source.document_name ?? '教学资料'}</strong><small>{source.page && source.page !== '题目来源' ? `第 ${source.page} 页 · ` : ''}{source.section}</small>{source.snippet && <p>{source.snippet}</p>}</div>)}</details>}
          {turn.error && <div className="s1-inline-error" role="alert">{turn.error}</div>}
        </article>)}
        {running && <div className="s1-chat-streaming"><LoaderCircle className="s1-spin" size={14} />正在整理回答…</div>}
      </div>
      {showEmpty && <div className="s1-starter-prompts">{starterPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => void send(prompt)}>{prompt}</button>)}</div>}
      <label className="s1-chat-composer"><span className="s1-visually-hidden">向 Tutor 提问</span><textarea aria-label="向 Tutor 提问" value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} disabled={running} placeholder="问 Tutor…" rows={2} /><button className="s1-icon-button" type="button" aria-label="发送给 Tutor" disabled={!message.trim() || running} onClick={() => void send()}><CornerDownLeft size={17} /></button></label>
      <div className="s1-tutor-actions">{running ? <button className="s1-button s1-button-light" onClick={() => controller.current?.abort()}><Square size={15} />停止</button> : lastUser && <button className="s1-button s1-button-light" onClick={() => void send(lastUser.text)}><RotateCcw size={15} />重试</button>}</div>
    </>}
  </aside>
}

import { Bot, LoaderCircle, RotateCcw, Send, Square, X } from 'lucide-react'
import { useRef, useState } from 'react'

import { streamTutor, type TutorStreamEvent } from '../../api/client'

type Source = { document_name?: string; page?: string; section?: string; snippet?: string }

export function TutorSidecar({ questionId, attemptId, open, onClose }: { questionId: string; attemptId?: string; open: boolean; onClose: () => void }) {
  const controller = useRef<AbortController | null>(null)
  const [message, setMessage] = useState('请给我一个不透露答案的观察提示。')
  const [tokens, setTokens] = useState('')
  const [toolStatus, setToolStatus] = useState<string[]>([])
  const [sources, setSources] = useState<Source[]>([])
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  async function run() {
    controller.current?.abort()
    const next = new AbortController()
    controller.current = next
    setTokens(''); setToolStatus([]); setSources([]); setError(null); setRunning(true)
    try {
      await streamTutor({ question_id: questionId, learner_id: 'demo_learner', message, attempt_id: attemptId ?? null }, handleEvent, next.signal)
    } catch (reason) {
      if ((reason as Error).name !== 'AbortError') setError((reason as Error).message)
    } finally { setRunning(false) }
  }

  function handleEvent(event: TutorStreamEvent) {
    if (event.event === 'token') setTokens((current) => current + String(event.data.text ?? ''))
    if (event.event === 'tool_start') setToolStatus((current) => [...current, `正在读取：${String(event.data.tool_name)}`])
    if (event.event === 'tool_end') setToolStatus((current) => [...current, `已完成：${String(event.data.tool_name)}`])
    if (event.event === 'source') setSources((current) => [...current, event.data as Source])
    if (event.event === 'error') setError(String(event.data.message ?? 'Tutor 暂不可用。'))
  }

  return <aside className={open ? 's1-card s1-tutor-card is-open' : 's1-card s1-tutor-card'} aria-label="Tutor Agent">
    <div className="s1-tutor-header"><div><span className="s1-tutor-orb"><Bot size={17} /></span><span><strong>Tutor Agent</strong><small>真实 SSE 事件 · 受限工具权限</small></span></div><button className="s1-icon-button s1-tutor-close" onClick={onClose} aria-label="关闭 Tutor"><X size={17} /></button></div>
    <p className="s1-tutor-explainer">提交前仅可访问公开题面、资料和学习概览；提交后才可读取本次评分结果。</p>
    <label className="s1-answer-text"><span>你想获得什么帮助？</span><textarea aria-label="Tutor 消息" value={message} onChange={(event) => setMessage(event.target.value)} disabled={running} /></label>
    {toolStatus.length > 0 && <div className="s1-hint-result" data-testid="tutor-tool-status"><strong>真实工具记录</strong>{toolStatus.map((status, index) => <small key={`${status}-${index}`}>{status}</small>)}</div>}
    {tokens && <div className="s1-hint-result" data-testid="tutor-stream-output"><strong>Tutor 回复</strong><p>{tokens}</p></div>}
    {sources.length > 0 && <div className="s1-hint-result" data-testid="tutor-sources"><strong>资料来源</strong>{sources.map((source, index) => <small key={`${source.document_name}-${index}`}>{source.document_name} · {source.page} · {source.section}</small>)}</div>}
    {error && <div className="s1-inline-error" role="alert">{error}</div>}
    <div className="s1-question-actions">{running ? <button className="s1-button s1-button-light" onClick={() => controller.current?.abort()}><Square size={15} />取消</button> : <button className="s1-button s1-button-secondary" data-testid="tutor-hint" onClick={() => void run()}><Send size={15} />请求提示</button>}<button className="s1-button s1-button-light" onClick={() => void run()} disabled={running || !tokens}><RotateCcw size={15} />重试</button>{running && <LoaderCircle size={16} className="s1-spin" aria-label="Tutor 正在响应" />}</div>
  </aside>
}

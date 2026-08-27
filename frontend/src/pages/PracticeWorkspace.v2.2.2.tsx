import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Send, MessageSquare, Lightbulb, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import type { Question, SubmitResponse, TutorResponse, TutorMode } from '../lib/types.v2.2.2'
import { adaptQuestionFromBackend, adaptSubmitResponseFromBackend, adaptTutorResponseFromBackend, buildSubmitRequest, buildTutorRequest } from '../lib/adapters.v2.2.2'
import { getUserLabel } from '../lib/types.v2.2.2'

export function PracticeWorkspace() {
  const [searchParams] = useSearchParams()
  const bankId = searchParams.get('bank_id') || ''

  const [questions, setQuestions] = useState<Question[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedAnswer, setSelectedAnswer] = useState<string | string[]>('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<SubmitResponse | null>(null)

  // ChatAgent 状态
  const [chatMode, setChatMode] = useState<TutorMode>('hint')
  const [chatMessages, setChatMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; provider?: string }>>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)

  // 开发详情折叠
  const [showDevDetails, setShowDevDetails] = useState(false)

  const currentQuestion = questions[currentIndex]

  useEffect(() => {
    if (!bankId) {
      setError('缺少题库 ID')
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    fetch(`/api/practice/questions?bank_id=${bankId}&limit=20`)
      .then(res => res.json())
      .then(data => {
        const adaptedQuestions = (data.items || []).map(adaptQuestionFromBackend)
        if (adaptedQuestions.length === 0) {
          setError('该题库暂无题目')
        } else {
          setQuestions(adaptedQuestions)
        }
      })
      .catch(err => {
        console.error('Failed to load questions:', err)
        setError('加载题目失败')
      })
      .finally(() => setLoading(false))
  }, [bankId])

  const handleSubmit = () => {
    if (!currentQuestion || !selectedAnswer) return

    setSubmitting(true)
    setFeedback(null)

    const request = buildSubmitRequest(currentQuestion.id, selectedAnswer)

    fetch('/api/practice/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
      .then(res => res.json())
      .then(data => {
        const adaptedFeedback = adaptSubmitResponseFromBackend(data)
        setFeedback(adaptedFeedback)
        setChatMode('explain')
      })
      .catch(err => {
        console.error('Submit failed:', err)
        setError('提交失败，请重试')
      })
      .finally(() => setSubmitting(false))
  }

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1)
      setSelectedAnswer('')
      setFeedback(null)
      setChatMessages([])
      setChatMode('hint')
    }
  }

  const handleChatSend = () => {
    if (!chatInput.trim() || !currentQuestion) return

    const userMessage = chatInput.trim()
    setChatInput('')
    setChatMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setChatLoading(true)

    const request = buildTutorRequest(chatMode, currentQuestion.id, userMessage)

    fetch('/api/practice/tutor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    })
      .then(res => res.json())
      .then(data => {
        const adapted = adaptTutorResponseFromBackend(data)
        setChatMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: adapted.message,
            provider: adapted.provider,
          },
        ])
      })
      .catch(err => {
        console.error('Tutor failed:', err)
        setChatMessages(prev => [
          ...prev,
          {
            role: 'assistant',
            content: '抱歉，带教服务暂时不可用',
            provider: 'error',
          },
        ])
      })
      .finally(() => setChatLoading(false))
  }

  const handleHint = () => {
    setChatMode('hint')
    setChatInput('给我一个提示，不要直接告诉我答案')
    handleChatSend()
  }

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="loading">
          <div className="spinner" />
          <span>加载题目中...</span>
        </div>
      </div>
    )
  }

  if (error || !currentQuestion) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="error-state">
          <p>{error || '题目加载失败'}</p>
          <button className="btn btn-primary" onClick={() => window.history.back()}>
            返回题库
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg)' }}>
      {/* 左侧题目主区 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
        <div className="container" style={{ maxWidth: '800px' }}>
          {/* 进度条 */}
          <div className="flex justify-between items-center text-sm text-muted" style={{ marginBottom: '16px' }}>
            <span>
              题目 {currentIndex + 1} / {questions.length}
            </span>
            <span>{currentQuestion.body_part}</span>
          </div>

          {/* 题目卡片 */}
          <div className="card" style={{ marginBottom: '24px' }}>
            <h2 className="text-xl font-semibold" style={{ marginBottom: '16px' }}>
              {currentQuestion.title}
            </h2>

            {/* 图片 */}
            {currentQuestion.image_url && (
              <div
                style={{
                  marginBottom: '16px',
                  maxHeight: '384px',
                  overflow: 'hidden',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--panel-soft)',
                }}
              >
                <img
                  src={currentQuestion.image_url}
                  alt={currentQuestion.image_alt || '题目图片'}
                  loading="lazy"
                  style={{
                    width: '100%',
                    height: 'auto',
                    maxHeight: '384px',
                    objectFit: 'contain',
                  }}
                />
              </div>
            )}

            <p className="text-base" style={{ marginBottom: '24px', lineHeight: 1.6 }}>
              {currentQuestion.question}
            </p>

            {/* 选项 */}
            {currentQuestion.question_type === 'single_choice' && currentQuestion.options && (
              <div className="flex flex-col gap-sm">
                {currentQuestion.options.map(opt => (
                  <div
                    key={opt.id}
                    className="card card-hover"
                    onClick={() => !feedback && setSelectedAnswer(opt.id)}
                    style={{
                      padding: '16px',
                      cursor: feedback ? 'default' : 'pointer',
                      border: selectedAnswer === opt.id ? '2px solid var(--primary)' : '1px solid var(--line)',
                      background: selectedAnswer === opt.id ? 'var(--primary-soft)' : 'var(--panel)',
                    }}
                  >
                    <div className="flex items-center gap-md">
                      <div
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          border: '2px solid',
                          borderColor: selectedAnswer === opt.id ? 'var(--primary)' : 'var(--line-strong)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        {selectedAnswer === opt.id && (
                          <div
                            style={{
                              width: '12px',
                              height: '12px',
                              borderRadius: '50%',
                              background: 'var(--primary)',
                            }}
                          />
                        )}
                      </div>
                      <span>{opt.text}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {currentQuestion.question_type === 'multiple_choice' && currentQuestion.options && (
              <div className="flex flex-col gap-sm">
                {currentQuestion.options.map(opt => {
                  const selected = Array.isArray(selectedAnswer) && selectedAnswer.includes(opt.id)
                  return (
                    <div
                      key={opt.id}
                      className="card card-hover"
                      onClick={() => {
                        if (feedback) return
                        setSelectedAnswer(prev => {
                          const arr = Array.isArray(prev) ? prev : []
                          return selected ? arr.filter(id => id !== opt.id) : [...arr, opt.id]
                        })
                      }}
                      style={{
                        padding: '16px',
                        cursor: feedback ? 'default' : 'pointer',
                        border: selected ? '2px solid var(--primary)' : '1px solid var(--line)',
                        background: selected ? 'var(--primary-soft)' : 'var(--panel)',
                      }}
                    >
                      <div className="flex items-center gap-md">
                        <div
                          style={{
                            width: '20px',
                            height: '20px',
                            borderRadius: '4px',
                            border: '2px solid',
                            borderColor: selected ? 'var(--primary)' : 'var(--line-strong)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: selected ? 'var(--primary)' : 'transparent',
                          }}
                        >
                          {selected && (
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                              <path d="M2 6L5 9L10 3" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          )}
                        </div>
                        <span>{opt.text}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {currentQuestion.question_type === 'true_false' && (
              <div className="flex gap-md">
                <button
                  className={selectedAnswer === 'true' ? 'btn btn-primary' : 'btn btn-secondary'}
                  onClick={() => !feedback && setSelectedAnswer('true')}
                  disabled={!!feedback}
                  style={{ flex: 1 }}
                >
                  正确
                </button>
                <button
                  className={selectedAnswer === 'false' ? 'btn btn-primary' : 'btn btn-secondary'}
                  onClick={() => !feedback && setSelectedAnswer('false')}
                  disabled={!!feedback}
                  style={{ flex: 1 }}
                >
                  错误
                </button>
              </div>
            )}

            {currentQuestion.question_type === 'short_answer' && (
              <textarea
                className="textarea"
                value={selectedAnswer as string}
                onChange={e => setSelectedAnswer(e.target.value)}
                placeholder="请输入你的答案..."
                disabled={!!feedback}
                style={{ minHeight: '150px' }}
              />
            )}

            {/* 提交按钮 */}
            {!feedback && (
              <div className="flex gap-sm" style={{ marginTop: '24px' }}>
                <button
                  className="btn btn-primary"
                  onClick={handleSubmit}
                  disabled={submitting || !selectedAnswer}
                  style={{ flex: 1 }}
                >
                  {submitting ? '提交中...' : '提交答案'}
                </button>
                <button className="btn btn-secondary" onClick={handleHint} disabled={submitting}>
                  <Lightbulb size={16} />
                  提示
                </button>
              </div>
            )}

            {/* 反馈卡片 */}
            {feedback && (
              <div
                className="card"
                style={{
                  marginTop: '24px',
                  borderLeft: `4px solid ${feedback.is_correct ? 'var(--primary)' : 'var(--danger)'}`,
                  background: feedback.is_correct ? 'var(--primary-soft)' : 'var(--danger-soft)',
                }}
              >
                <div className="flex flex-col gap-md">
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-lg">
                      {feedback.is_correct ? '✓ 回答正确' : '✗ 回答错误'}
                    </span>
                    <span className="text-2xl font-bold">{feedback.score} 分</span>
                  </div>

                  <p>{feedback.explanation}</p>

                  {feedback.knowledge_points && feedback.knowledge_points.length > 0 && (
                    <div>
                      <div className="text-sm font-medium text-muted" style={{ marginBottom: '8px' }}>
                        知识点
                      </div>
                      <div className="flex gap-sm flex-wrap">
                        {feedback.knowledge_points.map((kp, idx) => (
                          <span key={idx} className="badge badge-neutral">
                            {kp}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {feedback.next_recommendation && (
                    <div className="text-sm text-muted">{feedback.next_recommendation}</div>
                  )}

                  <button className="btn btn-primary" onClick={handleNext}>
                    下一题
                  </button>

                  {/* 开发详情折叠 */}
                  <button
                    className="btn btn-ghost text-sm"
                    onClick={() => setShowDevDetails(!showDevDetails)}
                    style={{ marginTop: '8px' }}
                  >
                    {showDevDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    查看本次讲解依据
                  </button>

                  {showDevDetails && (
                    <div
                      className="card"
                      style={{
                        marginTop: '8px',
                        background: 'var(--panel)',
                        fontSize: '12px',
                        fontFamily: 'monospace',
                      }}
                    >
                      <div className="flex flex-col gap-sm">
                        <div>
                          <span className="text-muted">评分依据:</span> {feedback.fact_feedback?.length || 0} 个原子事实
                        </div>
                        <div>
                          <span className="text-muted">状态:</span> {getUserLabel('Verify')} 完成
                        </div>
                        <div>
                          <span className="text-muted">安全提示:</span> {feedback.safety_notice}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 右侧 ChatAgent */}
      <div
        className="hide-mobile"
        style={{
          width: '360px',
          borderLeft: '1px solid var(--line)',
          background: 'var(--panel)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* 头部 */}
        <div
          style={{
            padding: '16px',
            borderBottom: '1px solid var(--line)',
          }}
        >
          <h3 className="font-semibold">学习助手</h3>
          <div className="flex gap-sm" style={{ marginTop: '12px' }}>
            {(['hint', 'explain', 'chat'] as TutorMode[]).map(mode => (
              <button
                key={mode}
                className={chatMode === mode ? 'btn btn-primary' : 'btn btn-ghost'}
                onClick={() => setChatMode(mode)}
                style={{ flex: 1, padding: '6px 12px', fontSize: '13px', minHeight: '32px' }}
              >
                {mode === 'hint' ? '提示' : mode === 'explain' ? '讲解' : '追问'}
              </button>
            ))}
          </div>
        </div>

        {/* 消息列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
          {chatMessages.length === 0 ? (
            <div className="empty-state" style={{ padding: '32px 16px' }}>
              <MessageSquare size={32} className="text-muted" />
              <p className="text-sm text-muted" style={{ marginTop: '8px' }}>
                {chatMode === 'hint'
                  ? '提交前可以向我寻求提示'
                  : chatMode === 'explain'
                    ? '提交后我会为你讲解错因'
                    : '有任何问题都可以问我'}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-md">
              {chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '85%',
                  }}
                >
                  <div
                    className="card"
                    style={{
                      padding: '12px',
                      background: msg.role === 'user' ? 'var(--primary)' : 'var(--panel-soft)',
                      color: msg.role === 'user' ? 'white' : 'var(--text)',
                      fontSize: '14px',
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.content}
                  </div>
                  {msg.provider && msg.role === 'assistant' && (
                    <div className="text-xs text-muted" style={{ marginTop: '4px', textAlign: 'right' }}>
                      {msg.provider === 'agent' ? '智能带教' : msg.provider === 'rule' ? '规则回答' : '兜底回答'}
                    </div>
                  )}
                </div>
              ))}
              {chatLoading && (
                <div style={{ alignSelf: 'flex-start' }}>
                  <div className="loading" style={{ fontSize: '14px' }}>
                    <div className="spinner" style={{ width: '16px', height: '16px' }} />
                    <span>思考中...</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 输入框 */}
        <div style={{ padding: '16px', borderTop: '1px solid var(--line)' }}>
          <div className="flex gap-sm">
            <input
              className="input"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleChatSend()}
              placeholder="输入你的问题..."
              disabled={chatLoading}
              style={{ flex: 1, minHeight: '40px' }}
            />
            <button
              className="btn btn-primary"
              onClick={handleChatSend}
              disabled={chatLoading || !chatInput.trim()}
              style={{ minWidth: '40px', padding: '0 12px' }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

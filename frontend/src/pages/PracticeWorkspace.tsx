import { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  BookmarkPlus,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Send,
  Sparkles,
  X,
} from 'lucide-react'
import { v3Api } from '../lib/v3Api'
import type { PracticeQuestionsPayload, PracticeSubmitResponse } from '../lib/types'

type TutorMessage = { role: 'assistant' | 'user'; text: string }

export function PracticeWorkspace() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const bankId = searchParams.get('bank_id')
  const mode = searchParams.get('mode') // 'review' 等

  const [payload, setPayload] = useState<PracticeQuestionsPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeIndex, setActiveIndex] = useState(0)
  const [choice, setChoice] = useState('')
  const [multiChoice, setMultiChoice] = useState<Set<string>>(new Set())
  const [freeText, setFreeText] = useState('')
  const [result, setResult] = useState<PracticeSubmitResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [showTutor, setShowTutor] = useState(false)
  const [tutorMessages, setTutorMessages] = useState<TutorMessage[]>([
    { role: 'assistant', text: '需要提示吗？我可以帮你拆解知识点或比较选项。' },
  ])
  const [tutorInput, setTutorInput] = useState('')
  const [tutorBusy, setTutorBusy] = useState(false)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    const fetchParams: any = { limit: 60, shuffleSeed: 22 }
    if (bankId) fetchParams.bankId = bankId
    if (mode === 'review') fetchParams.onlyWrong = true

    v3Api
      .practiceQuestions(fetchParams)
      .then((nextPayload) => {
        if (!mounted) return
        setPayload(nextPayload)
        setActiveIndex(0)
        resetAnswer()
      })
      .catch(() => {
        if (!mounted) return
        setPayload(null)
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [bankId, mode])

  const resetAnswer = () => {
    setChoice('')
    setMultiChoice(new Set())
    setFreeText('')
    setResult(null)
  }

  const question = payload?.items?.[activeIndex]

  const handlePrevious = () => {
    if (activeIndex > 0) {
      setActiveIndex(activeIndex - 1)
      resetAnswer()
    }
  }

  const handleNext = () => {
    if (payload && activeIndex < payload.items.length - 1) {
      setActiveIndex(activeIndex + 1)
      resetAnswer()
    }
  }

  const handleSubmit = async () => {
    if (!question) return
    setSubmitting(true)
    try {
      let answer = ''
      const q = question as any
      if (q.type === 'single_choice') {
        answer = choice
      } else if (q.type === 'multiple_choice') {
        answer = Array.from(multiChoice).sort().join(',')
      } else if (q.type === 'true_false') {
        answer = choice
      } else {
        answer = freeText
      }

      const res = await v3Api.practiceSubmit(q.question_id || '', answer)
      setResult(res)
    } catch {
      alert('提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const handleTutorSend = async () => {
    if (!tutorInput.trim() || tutorBusy || !question) return
    const userMsg = tutorInput.trim()
    setTutorMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setTutorInput('')
    setTutorBusy(true)

    try {
      const isSubmitted = result !== null
      const q = question as any
      const res = await v3Api.practiceTutor({
        questionId: q.question_id || '',
        mode: isSubmitted ? 'explain' : 'hint',
        selectedAnswer: choice || freeText,
        message: userMsg,
      })
      setTutorMessages((prev) => [...prev, { role: 'assistant', text: String(res.message || '暂时无法回答') }])
    } catch {
      setTutorMessages((prev) => [
        ...prev,
        { role: 'assistant', text: '暂时无法回答，请稍后重试。' },
      ])
    } finally {
      setTutorBusy(false)
    }
  }

  const handleQuickHint = () => {
    setShowTutor(true)
    setTutorInput('给我一点提示，但不要直接告诉答案')
    setTimeout(() => handleTutorSend(), 100)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-neutral-500">加载题目中...</div>
      </div>
    )
  }

  if (!payload || payload.items.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <p className="text-neutral-600 mb-4">暂无题目</p>
        <button
          onClick={() => navigate('/banks')}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
        >
          返回题库
        </button>
      </div>
    )
  }

  if (!question) return null

  const q = question as any
  const progress = ((activeIndex + 1) / payload.items.length) * 100

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* 主区域 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部栏 */}
        <div className="border-b border-neutral-200 px-6 py-4 bg-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/banks')}
                className="p-2 hover:bg-neutral-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <div className="text-sm text-neutral-600">
                  {q.body_part || '练习'}
                </div>
                <div className="font-medium">
                  第 {activeIndex + 1} / {payload.items.length} 题
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-2 hover:bg-neutral-100 rounded-lg transition-colors">
                <BookmarkPlus className="w-5 h-5 text-neutral-600" />
              </button>
            </div>
          </div>
          <div className="mt-3 w-full bg-neutral-200 rounded-full h-1">
            <div
              className="bg-emerald-600 h-1 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* 题目内容区 */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-3xl mx-auto">
            {/* 题目信息 */}
            <div className="flex gap-3 mb-4 text-sm">
              <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded">
                {q.type_label || q.type || '题目'}
              </span>
              {q.difficulty && (
                <span className="px-2 py-1 bg-neutral-100 text-neutral-600 rounded">
                  {q.difficulty}
                </span>
              )}
            </div>

            {/* 题干 */}
            <div className="text-lg mb-6 leading-relaxed">{question.question}</div>

            {/* 图片（如果有） */}
            {question.image_url && (
              <div className="mb-6">
                <img
                  src={question.image_url}
                  alt={q.image_alt || '题目图片'}
                  className="max-w-full h-auto rounded-lg border border-neutral-200"
                  style={{ aspectRatio: '4/3', objectFit: 'contain' }}
                />
              </div>
            )}

            {/* 选项/输入 */}
            {q.type === 'single_choice' && q.options && (
              <div className="space-y-3 mb-6">
                {q.options.map((opt: any) => (
                  <label
                    key={opt.id || opt}
                    className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      choice === (opt.id || opt)
                        ? 'border-emerald-600 bg-emerald-50'
                        : 'border-neutral-200 hover:border-neutral-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="choice"
                      value={opt.id || opt}
                      checked={choice === (opt.id || opt)}
                      onChange={(e) => setChoice(e.target.value)}
                      disabled={result !== null}
                      className="mt-1"
                    />
                    <span className="flex-1">{opt.text || opt}</span>
                  </label>
                ))}
              </div>
            )}

            {q.type === 'multiple_choice' && q.options && (
              <div className="space-y-3 mb-6">
                {q.options.map((opt: any) => (
                  <label
                    key={opt.id || opt}
                    className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      multiChoice.has(opt.id || opt)
                        ? 'border-emerald-600 bg-emerald-50'
                        : 'border-neutral-200 hover:border-neutral-300'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={multiChoice.has(opt.id || opt)}
                      onChange={(e) => {
                        const next = new Set(multiChoice)
                        if (e.target.checked) {
                          next.add(opt.id || opt)
                        } else {
                          next.delete(opt.id || opt)
                        }
                        setMultiChoice(next)
                      }}
                      disabled={result !== null}
                      className="mt-1"
                    />
                    <span className="flex-1">{opt.text || opt}</span>
                  </label>
                ))}
              </div>
            )}

            {q.type === 'true_false' && (
              <div className="space-y-3 mb-6">
                {['true', 'false'].map((val) => (
                  <label
                    key={val}
                    className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                      choice === val
                        ? 'border-emerald-600 bg-emerald-50'
                        : 'border-neutral-200 hover:border-neutral-300'
                    }`}
                  >
                    <input
                      type="radio"
                      name="choice"
                      value={val}
                      checked={choice === val}
                      onChange={(e) => setChoice(e.target.value)}
                      disabled={result !== null}
                      className="mt-1"
                    />
                    <span className="flex-1">{val === 'true' ? '正确' : '错误'}</span>
                  </label>
                ))}
              </div>
            )}

            {(q.type === 'short_answer' || q.type === 'report_correction') && (
              <div className="mb-6">
                <textarea
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                  disabled={result !== null}
                  placeholder="请输入你的答案..."
                  className="w-full h-32 p-4 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-neutral-50"
                />
              </div>
            )}

            {/* 结果展示 */}
            {result && (
              <div className="mb-6 p-6 bg-white border-2 border-emerald-600 rounded-xl">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                  <span className="text-lg font-medium">
                    {(result as any).correct ? '回答正确！' : '需要复习'}
                  </span>
                </div>
                {result.explanation && (
                  <div className="text-neutral-700 mb-3">{result.explanation}</div>
                )}
                {(result as any).knowledge_points && (result as any).knowledge_points.length > 0 && (
                  <div className="text-sm text-neutral-600 mb-3">
                    知识点：{(result as any).knowledge_points.join('、')}
                  </div>
                )}
                {(result as any).next_review_at && (
                  <div className="text-sm text-neutral-600 mb-4">
                    下次复习：{(result as any).next_review_at}
                  </div>
                )}
                <div className="flex gap-3">
                  <button
                    onClick={handleNext}
                    className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
                  >
                    下一题
                  </button>
                  <button className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50">
                    加入复习
                  </button>
                </div>
              </div>
            )}

            {/* 操作按钮 */}
            {!result && (
              <div className="flex gap-3">
                <button
                  onClick={handlePrevious}
                  disabled={activeIndex === 0}
                  className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 disabled:opacity-50"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={handleNext}
                  disabled={activeIndex >= payload.items.length - 1}
                  className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 disabled:opacity-50"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || (!choice && !freeText && multiChoice.size === 0)}
                  className="flex-1 px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? '提交中...' : '提交答案'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ChatAgent 侧栏 */}
      <div
        className={`w-80 border-l border-neutral-200 bg-white flex flex-col transition-all ${
          showTutor ? '' : 'hidden lg:flex'
        }`}
      >
        <div className="border-b border-neutral-200 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-600" />
            <span className="font-medium">智能带教</span>
          </div>
          <button
            onClick={() => setShowTutor(false)}
            className="lg:hidden p-1 hover:bg-neutral-100 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {!showTutor && (
          <div className="p-4">
            <p className="text-sm text-neutral-600 mb-3">需要提示吗？</p>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleQuickHint}
                className="text-sm px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-full hover:bg-emerald-200"
              >
                给提示
              </button>
              <button
                onClick={() => setShowTutor(true)}
                className="text-sm px-3 py-1.5 bg-neutral-100 text-neutral-700 rounded-full hover:bg-neutral-200"
              >
                拆知识点
              </button>
            </div>
          </div>
        )}

        {showTutor && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {tutorMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] px-4 py-2 rounded-lg ${
                      msg.role === 'user'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-neutral-100 text-neutral-800'
                    }`}
                  >
                    <div className="text-sm whitespace-pre-wrap">{msg.text}</div>
                  </div>
                </div>
              ))}
              {tutorBusy && (
                <div className="flex justify-start">
                  <div className="bg-neutral-100 text-neutral-800 px-4 py-2 rounded-lg">
                    <div className="text-sm">思考中...</div>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-neutral-200 p-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={tutorInput}
                  onChange={(e) => setTutorInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleTutorSend()}
                  placeholder="问问这道题..."
                  disabled={tutorBusy}
                  className="flex-1 px-3 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 text-sm disabled:bg-neutral-50"
                />
                <button
                  onClick={handleTutorSend}
                  disabled={!tutorInput.trim() || tutorBusy}
                  className="p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* 移动端显示 Tutor 按钮 */}
      {!showTutor && (
        <button
          onClick={() => setShowTutor(true)}
          className="lg:hidden fixed bottom-6 right-6 w-14 h-14 bg-emerald-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-emerald-700"
        >
          <Sparkles className="w-6 h-6" />
        </button>
      )}
    </div>
  )
}

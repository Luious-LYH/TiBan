import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  BookOpen,
  Search,
  Upload,
  X,
  Download,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import type { QuestionBankImportTemplates, QuestionBankImportValidation } from '../lib/types'
import { v3Api } from '../lib/v3Api'

interface Bank {
  bankId: string
  name: string
  bodyPart: string
  totalQuestions: number
  progress: number
  questionTypes: string[]
  source: 'official' | 'personal'
  lastPracticeAt?: string
}

type ImportFormat = 'jsonl' | 'csv' | 'markdown'

export function QuestionBanks() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [banks, setBanks] = useState<Bank[]>([])
  const [filter, setFilter] = useState<'all' | 'official' | 'personal'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // 检查 URL 参数是否要求打开导入
    if (searchParams.get('action') === 'import') {
      setShowImport(true)
    }
  }, [searchParams])

  useEffect(() => {
    let mounted = true
    setLoading(true)
    // 模拟题库列表，后续接入真实 API
    const mockBanks: Bank[] = [
      {
        bankId: 'esophagus-teaching',
        name: '食管基础',
        bodyPart: '食管',
        totalQuestions: 42,
        progress: 68,
        questionTypes: ['单选', '判断', '简答'],
        source: 'official',
        lastPracticeAt: '2 小时前',
      },
      {
        bankId: 'stomach-teaching',
        name: '胃部观察',
        bodyPart: '胃',
        totalQuestions: 38,
        progress: 51,
        questionTypes: ['单选', '多选', '图文'],
        source: 'official',
        lastPracticeAt: '昨天',
      },
      {
        bankId: 'small-intestine-teaching',
        name: '小肠胶囊',
        bodyPart: '小肠',
        totalQuestions: 26,
        progress: 20,
        questionTypes: ['判断', '简答'],
        source: 'official',
        lastPracticeAt: '3 天前',
      },
    ]
    setTimeout(() => {
      if (mounted) {
        setBanks(mockBanks)
        setLoading(false)
      }
    }, 300)
    return () => {
      mounted = false
    }
  }, [])

  const filteredBanks = banks.filter((bank) => {
    if (filter !== 'all' && bank.source !== filter) return false
    if (searchQuery) {
      const needle = searchQuery.toLowerCase()
      return (
        bank.name.toLowerCase().includes(needle) ||
        bank.bodyPart.toLowerCase().includes(needle)
      )
    }
    return true
  })

  const handleBankClick = (bankId: string) => {
    navigate(`/practice?bank_id=${bankId}`)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-neutral-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      {/* 标题和导入按钮 */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">题库</h1>
        <button
          onClick={() => setShowImport(true)}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors flex items-center gap-2"
        >
          <Upload className="w-4 h-4" />
          导入题库
        </button>
      </div>

      {/* 筛选和搜索 */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex gap-2">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'all'
                ? 'bg-emerald-600 text-white'
                : 'bg-white border border-neutral-300 text-neutral-700 hover:bg-neutral-50'
            }`}
          >
            全部
          </button>
          <button
            onClick={() => setFilter('official')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'official'
                ? 'bg-emerald-600 text-white'
                : 'bg-white border border-neutral-300 text-neutral-700 hover:bg-neutral-50'
            }`}
          >
            官方教学
          </button>
          <button
            onClick={() => setFilter('personal')}
            className={`px-4 py-2 rounded-lg transition-colors ${
              filter === 'personal'
                ? 'bg-emerald-600 text-white'
                : 'bg-white border border-neutral-300 text-neutral-700 hover:bg-neutral-50'
            }`}
          >
            我的题库
          </button>
        </div>
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            placeholder="搜索题库/知识点"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
      </div>

      {/* 题库列表 */}
      <div className="space-y-3">
        {filteredBanks.map((bank) => (
          <div
            key={bank.bankId}
            className="bg-white border border-neutral-200 rounded-lg p-5 hover:border-neutral-300 transition-colors"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <BookOpen className="w-5 h-5 text-emerald-600" />
                  <h3 className="text-lg font-medium">{bank.name}</h3>
                  <span className="text-xs px-2 py-1 bg-neutral-100 text-neutral-600 rounded">
                    {bank.source === 'official' ? '官方教学' : '个人题库'}
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-600 mb-3">
                  <span>{bank.totalQuestions} 题</span>
                  <span>{bank.progress}%</span>
                  <div className="flex gap-1">
                    {bank.questionTypes.map((type) => (
                      <span
                        key={type}
                        className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded"
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
                {bank.lastPracticeAt && (
                  <div className="text-sm text-neutral-500">
                    最近练习 {bank.lastPracticeAt}
                  </div>
                )}
              </div>
              <button
                onClick={() => handleBankClick(bank.bankId)}
                className="px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors whitespace-nowrap"
              >
                开始练习 →
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredBanks.length === 0 && (
        <div className="text-center py-12 text-neutral-500">
          {searchQuery ? '未找到匹配的题库' : '暂无题库，点击"导入题库"开始'}
        </div>
      )}

      {/* 导入弹窗 */}
      {showImport && (
        <ImportDialog onClose={() => setShowImport(false)} />
      )}
    </div>
  )
}

function ImportDialog({ onClose }: { onClose: () => void }) {
  const [format, setFormat] = useState<ImportFormat>('jsonl')
  const [content, setContent] = useState('')
  const [templates, setTemplates] = useState<QuestionBankImportTemplates | null>(null)
  const [validation, setValidation] = useState<QuestionBankImportValidation | null>(null)
  const [validating, setValidating] = useState(false)

  useEffect(() => {
    v3Api.questionBankImportTemplates().then(setTemplates).catch(() => {})
  }, [])

  const handleValidate = async () => {
    if (!content.trim()) return
    setValidating(true)
    setValidation(null)
    try {
      const result = await v3Api.validateQuestionBankImport({ format, content })
      setValidation(result as any)
    } catch {
      setValidation({
        ok: false,
        errors: [{ line: 0, message: '校验失败，请检查格式' }],
      } as any)
    } finally {
      setValidating(false)
    }
  }

  const handleDownloadTemplate = () => {
    if (!templates) return
    const template = (templates as any)[format]
    if (!template) return
    const blob = new Blob([template], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `template.${format}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-neutral-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">导入题库</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-neutral-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* 1. 选择格式 */}
          <div>
            <h3 className="text-sm font-medium mb-3">1. 选择格式</h3>
            <div className="flex gap-3">
              {(['jsonl', 'csv', 'markdown'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    format === f
                      ? 'bg-emerald-600 text-white'
                      : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
                  }`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* 2. 下载模板 */}
          <div>
            <h3 className="text-sm font-medium mb-3">2. 查看模板</h3>
            <button
              onClick={handleDownloadTemplate}
              disabled={!templates}
              className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              <Download className="w-4 h-4" />
              下载 {format.toUpperCase()} 模板
            </button>
          </div>

          {/* 3. 粘贴内容 */}
          <div>
            <h3 className="text-sm font-medium mb-3">3. 粘贴或上传内容</h3>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="粘贴题目内容..."
              className="w-full h-48 p-3 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono text-sm"
            />
          </div>

          {/* 4. 校验预览 */}
          <div>
            <h3 className="text-sm font-medium mb-3">4. 校验预览</h3>
            <button
              onClick={handleValidate}
              disabled={!content.trim() || validating}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
            >
              {validating ? '校验中...' : '开始校验'}
            </button>

            {validation && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center gap-3">
                  {(validation as any).ok || (validation as any).valid ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-amber-600" />
                  )}
                  <span className="font-medium">
                    通过 {(validation as any).passed || 0} 题
                    {((validation as any).failed || 0) > 0 && ` · 失败 ${(validation as any).failed} 题`}
                  </span>
                </div>

                {(validation as any).errors && (validation as any).errors.length > 0 && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                    <div className="text-sm font-medium text-amber-800 mb-2">
                      错误详情：
                    </div>
                    <ul className="text-sm text-amber-700 space-y-1">
                      {(validation as any).errors.slice(0, 5).map((err: any, idx: number) => (
                        <li key={idx}>
                          · 第 {err.line} 行：{err.message}
                        </li>
                      ))}
                      {(validation as any).errors.length > 5 && (
                        <li className="text-amber-600">
                          ... 还有 {(validation as any).errors.length - 5} 个错误
                        </li>
                      )}
                    </ul>
                  </div>
                )}

                {(validation as any).preview && (validation as any).preview.length > 0 && (
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                    <div className="text-sm font-medium text-emerald-800 mb-2">
                      预览摘要：
                    </div>
                    <ul className="text-sm text-emerald-700 space-y-1">
                      {(validation as any).preview.slice(0, 3).map((item: any, idx: number) => (
                        <li key={idx}>
                          · {item.type} - {item.stem?.substring(0, 40)}...
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 操作按钮 */}
          <div className="flex justify-end gap-3 pt-4 border-t border-neutral-200">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 transition-colors"
            >
              取消
            </button>
            <button
              disabled={!validation || !(validation as any).ok && !(validation as any).valid}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50"
            >
              保存为草稿
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

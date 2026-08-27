import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BookOpen, Filter, Download, Upload } from 'lucide-react'
import type { QuestionBank, ImportValidateResponse } from '../lib/types.v2.2.2'
import { adaptQuestionBankFromBackend, adaptImportValidationFromBackend } from '../lib/adapters.v2.2.2'

export function QuestionBanks() {
  const navigate = useNavigate()
  const [banks, setBanks] = useState<QuestionBank[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 导入相关状态
  const [showImport, setShowImport] = useState(false)
  const [importFormat, setImportFormat] = useState<'jsonl' | 'csv' | 'markdown'>('jsonl')
  const [importContent, setImportContent] = useState('')
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<ImportValidateResponse | null>(null)
  const [templates, setTemplates] = useState<Record<string, string>>({})

  useEffect(() => {
    loadBanks()
    loadTemplates()
  }, [])

  const loadBanks = () => {
    setLoading(true)
    setError(null)

    fetch('/api/question-banks')
      .then(res => res.json())
      .then(data => {
        const adaptedBanks = (data.banks || []).map(adaptQuestionBankFromBackend)
        setBanks(adaptedBanks)
      })
      .catch(err => {
        console.error('Failed to load banks:', err)
        setError('加载题库失败')
      })
      .finally(() => setLoading(false))
  }

  const loadTemplates = () => {
    fetch('/api/question-banks/import/templates')
      .then(res => res.json())
      .then(data => {
        setTemplates(data.examples || {})
      })
      .catch(err => console.error('Failed to load templates:', err))
  }

  const handleValidate = () => {
    if (!importContent.trim()) {
      return
    }

    setValidating(true)
    setValidation(null)

    fetch('/api/question-banks/import/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: importFormat,
        content: importContent,
      }),
    })
      .then(res => res.json())
      .then(data => {
        setValidation(adaptImportValidationFromBackend(data))
      })
      .catch(err => {
        console.error('Validation failed:', err)
        setError('校验失败，请检查格式')
      })
      .finally(() => setValidating(false))
  }

  const handleSave = () => {
    if (!validation || !validation.ready_to_publish) {
      return
    }

    fetch('/api/question-banks/import/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format: importFormat,
        content: importContent,
      }),
    })
      .then(res => res.json())
      .then(() => {
        setShowImport(false)
        setImportContent('')
        setValidation(null)
        loadBanks()
      })
      .catch(err => {
        console.error('Save failed:', err)
        setError('保存失败')
      })
  }

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="loading">
          <div className="spinner" />
          <span>加载题库中...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="container" style={{ paddingTop: '24px', paddingBottom: '48px' }}>
      <div className="flex justify-between items-center" style={{ marginBottom: '24px' }}>
        <h1 className="text-2xl font-bold">题库中心</h1>
        <button className="btn btn-primary" onClick={() => setShowImport(true)}>
          <Upload size={16} />
          导入题库
        </button>
      </div>

      {error && (
        <div className="error-state" style={{ marginBottom: '16px' }}>
          {error}
        </div>
      )}

      {/* 题库列表 */}
      {banks.length === 0 ? (
        <div className="empty-state">
          <BookOpen size={48} />
          <p className="font-medium">暂无题库</p>
          <p className="text-sm">点击"导入题库"按钮开始导入题目</p>
        </div>
      ) : (
        <div className="grid gap-lg" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
          {banks.map(bank => (
            <div key={bank.id} className="card">
              <div className="flex flex-col gap-md">
                <div>
                  <h3 className="text-lg font-semibold">{bank.name}</h3>
                  <p className="text-sm text-muted" style={{ marginTop: '4px' }}>
                    {bank.description || bank.body_parts.join(' / ')}
                  </p>
                </div>

                <div className="flex items-center gap-sm flex-wrap">
                  {Object.entries(bank.question_type_counts).map(([type, count]) => (
                    <span key={type} className="badge badge-neutral">
                      {type} × {count}
                    </span>
                  ))}
                </div>

                <div style={{ marginTop: '8px' }}>
                  <div className="flex justify-between text-sm" style={{ marginBottom: '8px' }}>
                    <span className="text-muted">已完成</span>
                    <span className="font-medium">
                      {bank.completed} / {bank.total}
                    </span>
                  </div>
                  <div
                    style={{
                      height: '6px',
                      background: 'var(--panel-soft)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${bank.progress}%`,
                        background: 'var(--primary)',
                      }}
                    />
                  </div>
                </div>

                <div className="flex gap-sm" style={{ marginTop: '8px' }}>
                  <button
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                    onClick={() => navigate(`/practice?bank_id=${bank.id}`)}
                  >
                    开始练习
                  </button>
                  <button className="btn btn-secondary">
                    <Filter size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 导入对话框 */}
      {showImport && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '16px',
          }}
          onClick={() => setShowImport(false)}
        >
          <div
            className="card"
            style={{
              maxWidth: '800px',
              width: '100%',
              maxHeight: '90vh',
              overflow: 'auto',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center" style={{ marginBottom: '24px' }}>
              <h2 className="text-xl font-semibold">导入题库</h2>
              <button className="btn btn-ghost" onClick={() => setShowImport(false)}>
                关闭
              </button>
            </div>

            {/* 格式选择 */}
            <div style={{ marginBottom: '16px' }}>
              <label className="text-sm font-medium" style={{ display: 'block', marginBottom: '8px' }}>
                格式
              </label>
              <div className="flex gap-sm">
                {(['jsonl', 'csv', 'markdown'] as const).map(fmt => (
                  <button
                    key={fmt}
                    className={importFormat === fmt ? 'btn btn-primary' : 'btn btn-secondary'}
                    onClick={() => setImportFormat(fmt)}
                  >
                    {fmt.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* 模板下载 */}
            {templates[importFormat] && (
              <div className="card" style={{ background: 'var(--panel-soft)', marginBottom: '16px', padding: '12px' }}>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted">模板示例</span>
                  <button
                    className="btn btn-ghost"
                    style={{ padding: '4px 8px', minHeight: '32px' }}
                    onClick={() => {
                      const blob = new Blob([templates[importFormat]], { type: 'text/plain' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `template.${importFormat}`
                      a.click()
                      URL.revokeObjectURL(url)
                    }}
                  >
                    <Download size={14} />
                    下载模板
                  </button>
                </div>
              </div>
            )}

            {/* 内容输入 */}
            <div style={{ marginBottom: '16px' }}>
              <label className="text-sm font-medium" style={{ display: 'block', marginBottom: '8px' }}>
                题目内容
              </label>
              <textarea
                className="textarea"
                value={importContent}
                onChange={e => setImportContent(e.target.value)}
                placeholder="粘贴题目内容..."
                style={{ minHeight: '200px', fontFamily: 'monospace', fontSize: '13px' }}
              />
            </div>

            {/* 校验结果 */}
            {validation && (
              <div className="card" style={{ background: 'var(--panel-soft)', marginBottom: '16px' }}>
                <div className="flex flex-col gap-md">
                  <div className="flex justify-between">
                    <span className="text-sm font-medium">校验结果</span>
                    <span className={validation.ready_to_publish ? 'badge badge-primary' : 'badge badge-warning'}>
                      {validation.ready_to_publish ? '可以导入' : '存在问题'}
                    </span>
                  </div>
                  <div className="flex gap-xl">
                    <div>
                      <div className="text-sm text-muted">通过</div>
                      <div className="text-lg font-bold text-primary">{validation.accepted_count}</div>
                    </div>
                    <div>
                      <div className="text-sm text-muted">拒绝</div>
                      <div className="text-lg font-bold text-danger">{validation.rejected_count}</div>
                    </div>
                  </div>

                  {validation.issues.length > 0 && (
                    <div style={{ marginTop: '8px' }}>
                      <div className="text-sm font-medium" style={{ marginBottom: '8px' }}>
                        问题列表
                      </div>
                      <div className="flex flex-col gap-sm">
                        {validation.issues.slice(0, 5).map((issue, idx) => (
                          <div key={idx} className="text-sm" style={{ padding: '8px', background: 'var(--panel)', borderRadius: 'var(--radius-sm)' }}>
                            <span className="badge badge-warning" style={{ marginRight: '8px' }}>
                              第 {issue.line} 行
                            </span>
                            <span className="text-muted">{issue.message}</span>
                          </div>
                        ))}
                        {validation.issues.length > 5 && (
                          <div className="text-sm text-muted">
                            还有 {validation.issues.length - 5} 个问题...
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 操作按钮 */}
            <div className="flex gap-sm justify-end">
              <button className="btn btn-secondary" onClick={() => setShowImport(false)}>
                取消
              </button>
              <button
                className="btn btn-primary"
                onClick={handleValidate}
                disabled={validating || !importContent.trim()}
              >
                {validating ? '校验中...' : '开始校验'}
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSave}
                disabled={!validation || !validation.ready_to_publish}
              >
                保存为草稿
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

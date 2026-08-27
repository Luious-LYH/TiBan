import { useEffect, useState } from 'react'
import { BarChart3, Clock, AlertCircle } from 'lucide-react'
import type { ModelEvaluation } from '../lib/types.v2.2.2'
import { adaptModelEvaluationFromBackend } from '../lib/adapters.v2.2.2'

export function ModelEvaluation() {
  const [evaluations, setEvaluations] = useState<ModelEvaluation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // 自定义模型评测状态
  const [showCustom, setShowCustom] = useState(false)
  const [customApiBase, setCustomApiBase] = useState('')
  const [customModel, setCustomModel] = useState('')
  const [customApiKey, setCustomApiKey] = useState('')
  const [customRunning, setCustomRunning] = useState(false)
  const [customResult, setCustomResult] = useState<any>(null)

  useEffect(() => {
    loadEvaluations()
  }, [])

  const loadEvaluations = () => {
    setLoading(true)
    setError(null)

    fetch('/api/models/evaluation')
      .then(res => {
        if (!res.ok) {
          throw new Error('API 不可用')
        }
        return res.json()
      })
      .then(data => {
        // 适配真实 Artifact 数据
        const items = data.items || []
        const adaptedEvals = items.map(adaptModelEvaluationFromBackend)
        setEvaluations(adaptedEvals)
      })
      .catch(err => {
        console.error('Failed to load evaluations:', err)
        // 如果后端不可用，显示明确状态而非假数据
        setError('评测服务暂不可用')
        setEvaluations([])
      })
      .finally(() => setLoading(false))
  }

  const handleCustomEvaluate = () => {
    if (!customApiBase || !customModel) {
      setError('请填写 API 地址和模型名称')
      return
    }

    setCustomRunning(true)
    setError(null)
    setCustomResult(null)

    // 调用真实后端评测接口
    // 注意：API Key 仅内存使用，不落盘
    fetch('/api/models/custom-evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_base: customApiBase,
        model_name: customModel,
        eval_set_id: 'default',
        // API Key 通过 header 传递，不进入 body
      }),
      // 如果有 API Key，通过 header 传递
      ...(customApiKey && {
        headers: {
          'Content-Type': 'application/json',
          'X-Custom-Api-Key': customApiKey, // 仅内存，不落盘
        },
      }),
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'completed') {
          setCustomResult(data)
        } else {
          setError('评测未完成，请稍后查看')
        }
      })
      .catch(err => {
        console.error('Custom evaluation failed:', err)
        setError('评测失败，请检查 API 配置')
      })
      .finally(() => {
        setCustomRunning(false)
        // 清空 API Key（不保留）
        setCustomApiKey('')
      })
  }

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: '80px' }}>
        <div className="loading">
          <div className="spinner" />
          <span>加载评测数据...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="container" style={{ paddingTop: '24px', paddingBottom: '48px' }}>
      <h1 className="text-2xl font-bold" style={{ marginBottom: '24px' }}>
        模型评测
      </h1>

      {error && (
        <div className="error-state" style={{ marginBottom: '16px' }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* 平台已有评测 Artifact */}
      <section style={{ marginBottom: '32px' }}>
        <h2 className="text-xl font-semibold" style={{ marginBottom: '16px' }}>
          平台评测记录
        </h2>

        {evaluations.length === 0 ? (
          <div className="card">
            <div className="empty-state">
              <BarChart3 size={48} />
              <p className="font-medium">暂无评测记录</p>
              <p className="text-sm text-muted">
                平台尚未运行模型评测，或评测服务暂不可用
              </p>
            </div>
          </div>
        ) : (
          <div className="grid gap-lg" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
            {evaluations.map(ev => (
              <div key={ev.id} className="card">
                <div className="flex flex-col gap-md">
                  <div>
                    <h3 className="text-lg font-semibold">{ev.model_name}</h3>
                    <p className="text-sm text-muted">{ev.model_provider}</p>
                  </div>

                  <div className="grid gap-sm" style={{ gridTemplateColumns: '1fr 1fr' }}>
                    <div>
                      <div className="text-sm text-muted">准确率</div>
                      <div className="text-2xl font-bold text-primary">
                        {(ev.accuracy * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-muted">题目数</div>
                      <div className="text-2xl font-bold">{ev.total_questions}</div>
                    </div>
                  </div>

                  <div className="flex gap-md text-sm">
                    <div className="flex items-center gap-sm">
                      <Clock size={14} className="text-muted" />
                      <span className="text-muted">P50: {ev.avg_latency_ms.toFixed(0)}ms</span>
                    </div>
                    <div className="flex items-center gap-sm">
                      <Clock size={14} className="text-muted" />
                      <span className="text-muted">P95: {ev.p95_latency_ms.toFixed(0)}ms</span>
                    </div>
                  </div>

                  <div className="text-xs text-muted">
                    评测集: {ev.eval_set_version}
                  </div>

                  <div className="text-xs text-muted">
                    运行时间: {new Date(ev.run_at).toLocaleString()}
                  </div>

                  {ev.artifact_url && (
                    <a
                      href={ev.artifact_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn-secondary text-sm"
                    >
                      查看完整报告
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* 自定义模型评测（预留/演示） */}
      <section>
        <div className="flex justify-between items-center" style={{ marginBottom: '16px' }}>
          <h2 className="text-xl font-semibold">自定义模型评测</h2>
          <span className="badge badge-warning">临时接入预留</span>
        </div>

        <div className="card">
          {!showCustom ? (
            <div className="empty-state">
              <BarChart3 size={48} />
              <p className="font-medium">自定义模型评测</p>
              <p className="text-sm text-muted" style={{ marginBottom: '16px' }}>
                提供你的模型 API，在本平台评测集上运行评测
              </p>
              <button className="btn btn-primary" onClick={() => setShowCustom(true)}>
                开始配置
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-lg">
              <div>
                <label className="text-sm font-medium" style={{ display: 'block', marginBottom: '8px' }}>
                  API 地址
                </label>
                <input
                  className="input"
                  value={customApiBase}
                  onChange={e => setCustomApiBase(e.target.value)}
                  placeholder="https://api.example.com/v1"
                />
              </div>

              <div>
                <label className="text-sm font-medium" style={{ display: 'block', marginBottom: '8px' }}>
                  模型名称
                </label>
                <input
                  className="input"
                  value={customModel}
                  onChange={e => setCustomModel(e.target.value)}
                  placeholder="gpt-4o"
                />
              </div>

              <div>
                <label className="text-sm font-medium" style={{ display: 'block', marginBottom: '8px' }}>
                  API Key（可选）
                </label>
                <input
                  className="input"
                  type="password"
                  value={customApiKey}
                  onChange={e => setCustomApiKey(e.target.value)}
                  placeholder="sk-..."
                />
                <p className="text-xs text-muted" style={{ marginTop: '4px' }}>
                  仅内存使用，不会保存到服务器
                </p>
              </div>

              <div className="card" style={{ background: 'var(--warning-soft)', padding: '12px' }}>
                <p className="text-sm">
                  <strong>注意：</strong>评测将调用你提供的 API 接口，产生的费用由你的账户承担。
                  评测约需 5-10 分钟完成。
                </p>
              </div>

              {customResult ? (
                <div className="card" style={{ background: 'var(--primary-soft)' }}>
                  <div className="flex flex-col gap-md">
                    <div className="flex justify-between">
                      <span className="font-semibold">评测完成</span>
                      <span className="badge badge-primary">成功</span>
                    </div>
                    <div className="grid gap-sm" style={{ gridTemplateColumns: '1fr 1fr' }}>
                      <div>
                        <div className="text-sm text-muted">准确率</div>
                        <div className="text-2xl font-bold text-primary">
                          {(customResult.metrics?.accuracy * 100 || 0).toFixed(1)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-muted">延迟</div>
                        <div className="text-2xl font-bold">
                          {customResult.metrics?.latency_p50_ms?.toFixed(0) || 0}ms
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex gap-sm">
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowCustom(false)
                      setCustomApiBase('')
                      setCustomModel('')
                      setCustomApiKey('')
                      setCustomResult(null)
                    }}
                  >
                    取消
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleCustomEvaluate}
                    disabled={customRunning || !customApiBase || !customModel}
                    style={{ flex: 1 }}
                  >
                    {customRunning ? '评测中...' : '开始评测'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

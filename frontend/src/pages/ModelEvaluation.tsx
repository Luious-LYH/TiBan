import { useState } from 'react'
import { PlayCircle, AlertCircle, CheckCircle2, Clock } from 'lucide-react'

interface EvalSet {
  id: string
  name: string
  description: string
  questionCount: number
  hasImages: boolean
}

type EvalStatus = 'idle' | 'running' | 'completed' | 'failed'

export function ModelEvaluation() {
  const [selectedSet, setSelectedSet] = useState('endoscopy-mini-v1')
  const [baseUrl, setBaseUrl] = useState('https://api.openai.com/v1')
  const [modelName, setModelName] = useState('gpt-4o')
  const [apiKey, setApiKey] = useState('')
  const [status, setStatus] = useState<EvalStatus>('idle')
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<any>(null)

  const evalSets: EvalSet[] = [
    {
      id: 'endoscopy-mini-v1',
      name: 'Endoscopy-mini-v1',
      description: '10 题 · 包含图文题',
      questionCount: 10,
      hasImages: true,
    },
  ]

  const handleTestConnection = async () => {
    if (!apiKey.trim()) {
      alert('请输入 API Key')
      return
    }
    alert('连接测试功能开发中')
  }

  const handleStartEval = async () => {
    if (!apiKey.trim()) {
      alert('请输入 API Key')
      return
    }

    setStatus('running')
    setProgress(0)

    // 模拟评测进度
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setStatus('completed')
          setResults({
            total: 10,
            accuracy: 0.8,
            jsonValidRate: 1.0,
            p50Latency: 2.1,
            p95Latency: 4.8,
            failed: 0,
            items: [
              { questionId: 1, type: '单选', score: 1.0, latency: 2.1, status: 'success' },
              { questionId: 2, type: '图文判断', score: 1.0, latency: 3.2, status: 'success' },
              { questionId: 3, type: '多选', score: 0.5, latency: 2.8, status: 'success' },
            ],
          })
          return 100
        }
        return prev + 10
      })
    }, 500)
  }

  const handleReset = () => {
    setStatus('idle')
    setProgress(0)
    setResults(null)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-semibold mb-8">模型评测</h1>

      <div className="space-y-8">
        {/* 1. 选择评测集 */}
        <section className="bg-white border border-neutral-200 rounded-xl p-6">
          <h2 className="text-lg font-medium mb-4">1. 选择评测集</h2>
          <div className="space-y-3">
            {evalSets.map((set) => (
              <label
                key={set.id}
                className={`flex items-start gap-3 p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                  selectedSet === set.id
                    ? 'border-emerald-600 bg-emerald-50'
                    : 'border-neutral-200 hover:border-neutral-300'
                }`}
              >
                <input
                  type="radio"
                  name="evalSet"
                  value={set.id}
                  checked={selectedSet === set.id}
                  onChange={(e) => setSelectedSet(e.target.value)}
                  disabled={status === 'running'}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-medium mb-1">{set.name}</div>
                  <div className="text-sm text-neutral-600">{set.description}</div>
                </div>
              </label>
            ))}
          </div>
        </section>

        {/* 2. 配置模型 */}
        <section className="bg-white border border-neutral-200 rounded-xl p-6">
          <h2 className="text-lg font-medium mb-4">2. 配置模型（一次性使用，不保存）</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">
                Base URL
              </label>
              <input
                type="text"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                disabled={status === 'running'}
                placeholder="https://api.openai.com/v1"
                className="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-neutral-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">
                Model
              </label>
              <input
                type="text"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                disabled={status === 'running'}
                placeholder="gpt-4o"
                className="w-full px-3 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-neutral-50"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">
                API Key
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  disabled={status === 'running'}
                  placeholder="sk-..."
                  className="flex-1 px-3 py-2 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-neutral-50"
                />
                <button
                  onClick={handleTestConnection}
                  disabled={!apiKey.trim() || status === 'running'}
                  className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50 disabled:opacity-50"
                >
                  测试连接
                </button>
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex gap-2">
              <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-blue-800">
                💡 API key 仅本次评测使用，不写入日志或数据库
              </p>
            </div>
          </div>
        </section>

        {/* 3. 开始评测 */}
        <section className="bg-white border border-neutral-200 rounded-xl p-6">
          <h2 className="text-lg font-medium mb-4">3. 开始评测</h2>
          {status === 'idle' && (
            <button
              onClick={handleStartEval}
              disabled={!apiKey.trim()}
              className="px-6 py-3 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 flex items-center gap-2"
            >
              <PlayCircle className="w-5 h-5" />
              开始评测
            </button>
          )}
          {status === 'running' && (
            <div>
              <div className="flex items-center gap-3 mb-3">
                <Clock className="w-5 h-5 text-emerald-600 animate-spin" />
                <span className="font-medium">评测状态：调用中 {Math.round(progress / 10)}/10</span>
              </div>
              <div className="w-full bg-neutral-200 rounded-full h-2 mb-2">
                <div
                  className="bg-emerald-600 h-2 rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-sm text-neutral-600">
                已完成 {Math.round(progress / 10)} 题，{10 - Math.round(progress / 10)} 题待调用
              </p>
            </div>
          )}
          {status === 'completed' && results && (
            <div>
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                <span className="text-lg font-medium">评测状态：已完成</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                <div className="bg-neutral-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">总题数</div>
                  <div className="text-2xl font-semibold">{results.total}</div>
                </div>
                <div className="bg-emerald-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">事实准确率</div>
                  <div className="text-2xl font-semibold text-emerald-700">
                    {Math.round(results.accuracy * 100)}%
                  </div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">JSON 有效率</div>
                  <div className="text-2xl font-semibold text-blue-700">
                    {Math.round(results.jsonValidRate * 100)}%
                  </div>
                </div>
                <div className="bg-neutral-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">P50 延迟</div>
                  <div className="text-2xl font-semibold">{results.p50Latency}s</div>
                </div>
                <div className="bg-neutral-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">P95 延迟</div>
                  <div className="text-2xl font-semibold">{results.p95Latency}s</div>
                </div>
                <div className="bg-neutral-50 rounded-lg p-4">
                  <div className="text-sm text-neutral-600 mb-1">失败题数</div>
                  <div className="text-2xl font-semibold">{results.failed}</div>
                </div>
              </div>

              <details className="mb-4">
                <summary className="cursor-pointer text-emerald-600 hover:text-emerald-700 font-medium mb-3">
                  查看逐题结果 ↓
                </summary>
                <div className="border border-neutral-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-neutral-50">
                      <tr>
                        <th className="px-4 py-3 text-left">题号</th>
                        <th className="px-4 py-3 text-left">题型</th>
                        <th className="px-4 py-3 text-left">得分</th>
                        <th className="px-4 py-3 text-left">延迟</th>
                        <th className="px-4 py-3 text-left">状态</th>
                        <th className="px-4 py-3 text-left">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.items.map((item: any) => (
                        <tr key={item.questionId} className="border-t border-neutral-200">
                          <td className="px-4 py-3">{item.questionId}</td>
                          <td className="px-4 py-3">{item.type}</td>
                          <td className="px-4 py-3">{item.score.toFixed(1)}</td>
                          <td className="px-4 py-3">{item.latency}s</td>
                          <td className="px-4 py-3">
                            <span className="text-emerald-600">✓</span>
                          </td>
                          <td className="px-4 py-3">
                            <button className="text-emerald-600 hover:text-emerald-700">
                              详情
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>

              <button
                onClick={handleReset}
                className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 rounded-lg hover:bg-neutral-50"
              >
                重新评测
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

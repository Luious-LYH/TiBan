import { AlertCircle, BarChart3, CheckCircle2, Eye, EyeOff, FlaskConical, KeyRound, LockKeyhole, Play, RefreshCw, Server, TimerReset } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  createEvaluationRun,
  getEvaluationDatasets,
  getEvaluationRun,
  testEvaluationConnection,
  type EvaluationConnection,
  type EvaluationRun,
} from '../../api/client'
import { ErrorState, LoadingState } from '../../components/shared/AsyncState'

type CaseFilter = 'all' | 'correct' | 'incorrect' | 'failed'

type EvaluationCase = {
  eval_case_id?: string
  source_item_id?: string
  question?: string
  candidate_output?: string
  parsed_answer?: string | null
  gold_answer?: string | null
  correct?: boolean | null
  valid_parse?: boolean
  latency_ms?: number | null
  error_category?: string | null
  task?: string
  topic?: string | null
  image_attached?: boolean
}

function asCase(item: Record<string, unknown>): EvaluationCase {
  return item as EvaluationCase
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败，请检查模型服务配置与连接状态。'
}

function formatMetric(value: unknown, suffix = ''): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') return `${value}${suffix}`
  return String(value)
}

function learnerDatasetDescription(datasetId: string, fallback: string): string {
  const summaries: Record<string, string> = {
    'cmexam-text-eval-v1': '用于比较模型对医学文本题的回答表现。',
    'endobench-vlm-eval-v1': '用于比较模型对内镜图像题的回答表现。',
    'general-science-text-eval-v1': '用于比较模型对通用科学文本题的回答表现。',
  }
  return summaries[datasetId] ?? fallback
}

function ConnectionReceipt({ result }: { result: EvaluationConnection }) {
  return (
    <div className={`eval-connection-receipt ${result.ok ? 'is-ok' : 'is-error'}`} role="status">
      {result.ok ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
      <div>
        <strong>{result.ok ? '模型连接成功' : '模型连接失败'}</strong>
        <span>{result.ok ? `${result.model} · ${result.latency_ms ?? '—'} ms` : result.error ?? '未返回错误详情'}</span>
      </div>
      <small>本次连接不会保存密钥</small>
    </div>
  )
}

function RunHeader({ run, revealed, onReveal, revealing }: { run: EvaluationRun; revealed: boolean; onReveal: () => void; revealing: boolean }) {
  const label = run.status === 'completed_with_failures' ? '完成，但包含失败样例' : '评测完成'
  return (
    <div className="eval-run-header">
      <div className="eval-run-status">
        <span className={`eval-status-mark ${run.status === 'completed' ? 'is-ok' : 'is-warning'}`}><CheckCircle2 size={17} /></span>
        <div>
          <strong>{label}</strong>
          <span>{run.sample_count} 道题 · 本次评测</span>
        </div>
      </div>
      <button className="s1-button s1-button-secondary" type="button" onClick={onReveal} disabled={revealed || revealing}>
        {revealed ? <EyeOff size={15} /> : <Eye size={15} />}
        {revealed ? '参考答案已展示' : revealing ? '正在读取参考答案…' : '查看对照答案'}
      </button>
    </div>
  )
}

export function EvaluationPage() {
  const datasetsQuery = useQuery({ queryKey: ['evaluation-datasets'], queryFn: getEvaluationDatasets })
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [sampleCount, setSampleCount] = useState('5')
  const [filter, setFilter] = useState<CaseFilter>('all')
  const [topicFilter, setTopicFilter] = useState('all')
  const [run, setRun] = useState<EvaluationRun | null>(null)
  const [connectionResult, setConnectionResult] = useState<EvaluationConnection | null>(null)
  const [revealed, setRevealed] = useState(false)

  const datasets = datasetsQuery.data ?? []
  const effectiveDatasetId = selectedDatasetId || datasets[0]?.dataset_id || ''
  const selectedDataset = datasets.find((item) => item.dataset_id === effectiveDatasetId) ?? datasets[0]

  const connection = useMutation({
    mutationFn: () => testEvaluationConnection({ base_url: apiBase.trim(), model: model.trim(), api_key: apiKey }),
    onSuccess: setConnectionResult,
  })
  const evaluation = useMutation({
    mutationFn: () => createEvaluationRun({
      base_url: apiBase.trim(),
      model: model.trim(),
      api_key: apiKey,
      dataset_id: selectedDataset?.dataset_id ?? '',
      sample_count: Math.max(1, Math.min(300, Number(sampleCount) || 1)),
    }),
    onSuccess: (result) => {
      setRun(result)
      setRevealed(false)
      setFilter('all')
      setTopicFilter('all')
    },
  })
  const reveal = useMutation({
    mutationFn: () => getEvaluationRun(run?.eval_run_id ?? '', true),
    onSuccess: (result) => {
      setRun(result)
      setRevealed(true)
    },
  })

  const runCases = useMemo(() => (run?.cases ?? []).map(asCase), [run])
  const topics = useMemo(() => Array.from(new Set(runCases.map((item) => item.topic).filter((topic): topic is string => Boolean(topic)))), [runCases])
  const visibleCases = useMemo(() => runCases.filter((item) => {
    const matchesTopic = topicFilter === 'all' || item.topic === topicFilter
    const matchesFilter = filter === 'all'
      || (filter === 'correct' && item.correct === true)
      || (filter === 'incorrect' && item.correct === false)
      || (filter === 'failed' && Boolean(item.error_category))
    return matchesTopic && matchesFilter
  }), [filter, runCases, topicFilter])

  if (datasetsQuery.isPending) return <LoadingState label="正在读取评测集…" />
  if (datasetsQuery.isError) return <ErrorState message={errorMessage(datasetsQuery.error)} onRetry={() => void datasetsQuery.refetch()} />

  return (
    <div className="s1-page eval-workbench" data-testid="evaluation-page">
      <section className="s1-page-intro">
        <div>
          <span className="s1-kicker">MODEL EVALUATION WORKBENCH</span>
          <h1>用真实题目，了解模型的回答表现。</h1>
          <p>选择评测集，临时连接兼容的模型服务，查看每道题的结果与整体表现。</p>
        </div>
        <span className="s1-source-pill"><FlaskConical size={14} />临时连接 · 不会保存</span>
      </section>

      <section className="eval-privacy-strip">
        <LockKeyhole size={16} />
        <div><strong>一次性授权</strong><span>API Key 仅用于本次评测，不会保存；查看对照答案前，结果只展示模型回答。</span></div>
      </section>

      <div className="eval-config-grid">
        <section className="s1-card eval-config-card">
          <div className="s1-section-heading"><div><span className="s1-kicker">EVALUATION SETTINGS</span><h2>连接候选模型</h2></div><Server size={18} color="var(--teal)" /></div>
          <div className="eval-form-grid">
            <label className="eval-field eval-field-wide"><span>连接地址</span><input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="https://provider.example/v1" autoComplete="off" /></label>
            <label className="eval-field"><span>模型名称</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="candidate-model" autoComplete="off" /></label>
            <label className="eval-field"><span>API Key <small>不会保存</small></span><div className="eval-secret-input"><KeyRound size={15} /><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="••••••••" autoComplete="off" /></div></label>
            <label className="eval-field"><span>评测集</span><select value={effectiveDatasetId} onChange={(event) => setSelectedDatasetId(event.target.value)}>{datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name}</option>)}</select></label>
            <label className="eval-field"><span>本次抽样题量 <small>1–300</small></span><input type="number" min="1" max="300" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} /></label>
          </div>
          {selectedDataset && <div className="eval-dataset-receipt"><div><strong>评测集总规模：{selectedDataset.sample_count} 道题</strong><span>{selectedDataset.supports_vision ? '图像题' : '文本题'}</span></div><p>{learnerDatasetDescription(selectedDataset.dataset_id, selectedDataset.description)}</p><small>{selectedDataset.supports_vision ? '此评测需要模型支持图像输入。' : '本评测使用文本题。'}</small></div>}
          <div className="eval-action-row">
            <button className="s1-button s1-button-light" type="button" onClick={() => connection.mutate()} disabled={connection.isPending || !apiBase.trim() || !model.trim() || !apiKey}><RefreshCw size={15} className={connection.isPending ? 's1-spin' : ''} />{connection.isPending ? '正在测试连接…' : '测试连接'}</button>
            <button className="s1-button s1-button-primary" type="button" onClick={() => evaluation.mutate()} disabled={evaluation.isPending || !selectedDataset || !apiBase.trim() || !model.trim() || !apiKey}><Play size={15} />{evaluation.isPending ? '正在评测…' : '开始评测'}</button>
          </div>
          {connectionResult && <ConnectionReceipt result={connectionResult} />}
          {connection.isError && <div className="eval-inline-error" role="alert"><AlertCircle size={15} />{errorMessage(connection.error)}</div>}
          {evaluation.isError && <div className="eval-inline-error" role="alert"><AlertCircle size={15} />{errorMessage(evaluation.error)}<button type="button" onClick={() => evaluation.reset()}>清除</button></div>}
          <p className="s1-safety">{selectedDataset?.domain_id === 'general_science' ? '评测结果用于通用科学模型比较，不代表课程成绩或学习效果。' : selectedDataset?.source_dataset === 'EndoBench' ? '内镜图像题仅用于模型评测。' : '评测结果用于模型比较，不代表临床性能或独立诊断能力。'}</p>
        </section>

        <aside className="s1-card eval-boundary-card">
          <div className="s1-section-heading"><div><span className="s1-kicker">EVALUATION SCOPE</span><h2>评测内容</h2></div><BarChart3 size={18} color="var(--teal)" /></div>
          <div className="eval-boundary-list">
            {selectedDataset?.domain_id === 'general_science' ? <div><span className="eval-boundary-dot is-blue" /><div><strong>通用科学文本题</strong><small>TiBan 自建样例 · 单选题</small></div></div> : <><div><span className="eval-boundary-dot is-blue" /><div><strong>医学文本题</strong><small>CMExam · 单选题</small></div></div><div><span className="eval-boundary-dot is-amber" /><div><strong>内镜图像题</strong><small>EndoBench · 图像问答</small></div></div></>}
            <div><span className="eval-boundary-dot is-teal" /><div><strong>对照答案</strong><small>需要时可手动查看</small></div></div>
          </div>
          <div className="eval-boundary-note"><LockKeyhole size={14} /><span>{selectedDataset?.domain_id === 'general_science' ? '通用科学评测使用文本输入，答案在显式操作后才展示。' : '图像评测需要模型支持图像输入；不支持时会提示评测失败。'}</span></div>
        </aside>
      </div>

      {run && <section className="s1-card eval-result-card">
        <RunHeader run={run} revealed={revealed} onReveal={() => reveal.mutate()} revealing={reveal.isPending} />
        <div className="eval-run-meta"><span>run <code>{run.eval_run_id}</code></span><span>provider <code>{run.provider}</code></span><span>model <code>{run.model}</code></span><span>prompt <code>{run.prompt_version}</code></span></div>
        <details className="eval-developer-detail"><summary>Developer Detail · evidence receipt</summary><div><span>dataset hash <code>{run.dataset_hash}</code></span><span>artifact <code>{run.artifact_path ?? '—'}</code></span><span>fallback <code>{run.fallback ? 'true' : 'false'}</code></span><span>gold projection <code>{revealed ? 'revealed by explicit action' : 'withheld'}</code></span></div></details>
        <div className="s1-metric-grid eval-result-metrics">
          <div className="s1-metric"><TimerReset className="eval-metric-icon" size={17} /><span className="s1-metric-label">Accuracy</span><strong>{revealed ? formatMetric(run.aggregate.accuracy) : '—'}</strong><small>{revealed ? 'gold 已对照' : 'Reveal Gold 后显示'}</small></div>
          <div className="s1-metric"><CheckCircle2 className="eval-metric-icon" size={17} /><span className="s1-metric-label">Valid parse</span><strong>{formatMetric(typeof run.aggregate.valid_parse_rate === 'number' ? `${Math.round(run.aggregate.valid_parse_rate * 100)}%` : run.aggregate.valid_parse_rate)}</strong><small>structured answer rate</small></div>
          <div className="s1-metric"><TimerReset className="eval-metric-icon" size={17} /><span className="s1-metric-label">Latency P50 / P95</span><strong>{formatMetric(run.aggregate.latency_p50_ms, ' ms')} / {formatMetric(run.aggregate.latency_p95_ms, ' ms')}</strong><small>provider round trip</small></div>
          <div className="s1-metric"><BarChart3 className="eval-metric-icon" size={17} /><span className="s1-metric-label">Token usage</span><strong>{formatMetric(run.usage.total_tokens)}</strong><small>prompt + completion</small></div>
        </div>
        {!revealed && <div className="eval-reveal-note"><Eye size={15} /><span>逐例 correct 与 gold answer 已隐藏。点击右上角 Reveal Gold 后，才会开放对照视图。</span></div>}
        {revealed && <div className="eval-filter-bar"><label>结果<select value={filter} onChange={(event) => setFilter(event.target.value as CaseFilter)}><option value="all">全部</option><option value="correct">正确</option><option value="incorrect">错误</option><option value="failed">失败 / 解析异常</option></select></label><label>Topic<select value={topicFilter} onChange={(event) => setTopicFilter(event.target.value)}><option value="all">全部 topic</option>{topics.map((topic) => <option key={topic} value={topic}>{topic}</option>)}</select></label><span>{visibleCases.length} / {runCases.length} cases</span></div>}
        <div className="eval-case-list">
          {visibleCases.length === 0 ? <div className="eval-empty-cases">当前筛选没有案例。</div> : visibleCases.map((item, index) => <article className="eval-case" key={item.eval_case_id ?? `${item.source_item_id}-${index}`}>
            <div className="eval-case-top"><span>Case {index + 1}</span><small>{item.task ?? 'task'}{item.topic ? ` · ${item.topic}` : ''}</small><b className={item.error_category ? 'is-error' : item.correct === true ? 'is-correct' : item.correct === false ? 'is-error' : ''}>{item.error_category ?? (item.correct === true ? 'correct' : item.correct === false ? 'incorrect' : 'awaiting gold')}</b></div>
            <h3>{item.question ?? '题目未提供'}</h3>
            <div className="eval-case-answer"><span>Candidate</span><code>{item.candidate_output ?? '—'}</code><span>Parsed</span><code>{item.parsed_answer ?? '—'}</code>{revealed && <><span>Gold</span><code>{item.gold_answer ?? '—'}</code></>}</div>
            <small className="eval-case-foot">{item.latency_ms ?? '—'} ms{item.image_attached ? ' · image attached' : ''}{item.error_category ? ` · ${item.error_category}` : ''}</small>
          </article>)}
        </div>
      </section>}

      <p className="s1-safety">{selectedDataset?.domain_id === 'general_science' ? '通用科学评测用于学习训练与模型比较，请结合课程资料和教师指导。' : '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'}</p>
    </div>
  )
}

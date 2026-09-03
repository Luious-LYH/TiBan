import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, LoaderCircle, Play, RefreshCw, ServerCog } from 'lucide-react'
import { useState } from 'react'

import { createEvaluationSuite, createModelEvaluation, deleteEvaluationExperiments, getEvaluationExperiment, getLatestEvaluationExperiment, getLatestEvaluationSuite, type EvalSuite, type EvaluationCatalog, type EvaluationExperiment } from '../../api/client'
import { EvaluationConfirmDialog } from './EvaluationConfirmDialog'
import { displayCatalogModels, displayModelName, resolveModelName } from './evaluationDisplay'

const percent = (value: unknown) => typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
const latency = (value: unknown) => typeof value === 'number' ? `${value}ms` : '—'
const metric = (value: unknown) => typeof value === 'number' ? String(value) : '—'
const errorMessage = (error: unknown) => error instanceof Error ? error.message : '操作失败，请检查评测集和模型配置。'

export function ModelEvaluationTab({ catalog }: { catalog: EvaluationCatalog }) {
  const queryClient = useQueryClient()
  const [bankId, setBankId] = useState(catalog.banks[0]?.bank_id ?? '')
  const [sampleSize, setSampleSize] = useState(10)
  const [candidateText, setCandidateText] = useState(displayCatalogModels(catalog.runtime_models).join('\n'))
  const [suite, setSuite] = useState<EvalSuite | null>(null)
  const [connectionMode, setConnectionMode] = useState<'default' | 'custom'>('default')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showKey, setShowKey] = useState(false)
  const [experiment, setExperiment] = useState<EvaluationExperiment | null>(null)
  const [confirmResample, setConfirmResample] = useState(false)
  const latestSuite = useQuery({ queryKey: ['evaluation-latest-suite', bankId], queryFn: () => getLatestEvaluationSuite(bankId), enabled: Boolean(bankId), retry: false })
  const latestExperiment = useQuery({ queryKey: ['evaluation-latest-experiment', bankId, 'model'], queryFn: () => getLatestEvaluationExperiment(bankId, 'model'), enabled: Boolean(bankId), retry: false, staleTime: 0 })
  const persistedExperiment = experiment ?? latestExperiment.data ?? null
  const activeSuite = suite ?? persistedExperiment?.suite ?? latestSuite.data ?? null
  const createSuite = useMutation({ mutationFn: () => createEvaluationSuite({ bank_id: bankId, sample_size: sampleSize }), onSuccess: (result) => { setSuite(result); setExperiment(null) } })
  const resample = useMutation({
    mutationFn: async () => {
      await deleteEvaluationExperiments(bankId, 'model')
      setExperiment(null)
      queryClient.setQueryData(['evaluation-latest-experiment', bankId, 'model'], null)
      return createEvaluationSuite({ bank_id: bankId, sample_size: sampleSize })
    },
    onSuccess: (result) => {
      setSuite(result)
      setConfirmResample(false)
      queryClient.setQueryData(['evaluation-latest-suite', bankId], result)
    },
  })
  const candidates = candidateText.split(/[\n,]/).map((value) => resolveModelName(value, catalog.runtime_models)).filter(Boolean)
  const createExperiment = useMutation({
    mutationFn: () => createModelEvaluation({
      suite_id: activeSuite?.suite_id ?? '', models: candidates,
      base_url: connectionMode === 'custom' ? baseUrl.trim() : undefined,
      api_key: connectionMode === 'custom' ? apiKey : undefined,
      provider: connectionMode === 'custom' ? 'byok_openai_compatible' : undefined,
    }),
    onSuccess: (result) => {
      setExperiment(result)
      queryClient.setQueryData(['evaluation-latest-experiment', bankId, 'model'], result)
    },
  })
  const polling = useQuery({ queryKey: ['evaluation-experiment', persistedExperiment?.experiment_id], queryFn: () => getEvaluationExperiment(persistedExperiment!.experiment_id), enabled: Boolean(persistedExperiment && persistedExperiment.status !== 'completed' && persistedExperiment.status !== 'partial_failed'), retry: false, refetchInterval: (query) => query.state.data?.status === 'completed' || query.state.data?.status === 'partial_failed' ? false : 1200 })
  const current = polling.data ?? persistedExperiment
  const customReady = Boolean(baseUrl.trim() && apiKey.trim())
  const canRun = Boolean(activeSuite && candidates.length && (connectionMode === 'default' || customReady) && !createExperiment.isPending && current?.status !== 'running' && current?.status !== 'queued')
  const requestSuite = () => activeSuite ? setConfirmResample(true) : createSuite.mutate()

  return <section className="evaluation-lab" data-testid="model-evaluation-tab">
    <div className="evaluation-panel evaluation-setup evaluation-model-setup">
      <header className="evaluation-config-heading"><div><span>模型评测配置</span><h2>同一评测集，比较不同模型的实际表现</h2><p>每个候选使用相同题目、Prompt、temperature=0 与 no-fallback。自定义 API 只在本次实验中使用。</p></div><span className="evaluation-status-badge"><ServerCog size={14} />可复现实验</span></header>
      <div className="evaluation-config-grid">
        <div className="evaluation-field evaluation-bank-field"><span>01 · 选择题库</span><select aria-label="评测题库" value={bankId} onChange={(event) => { setBankId(event.target.value); setSuite(null); setExperiment(null) }}>{catalog.banks.map((bank) => <option value={bank.bank_id} key={bank.bank_id}>{bank.name}</option>)}</select><small>可评测题目 {catalog.banks.find((bank) => bank.bank_id === bankId)?.eligible_question_count ?? 0} 道</small></div>
        <div className="evaluation-field evaluation-set-field"><span>02 · 评测集</span><div className="evaluation-suite-line">{activeSuite ? <div className="evaluation-set-chip"><strong>本次评测：{activeSuite.sample_size} 道题</strong><small>评测集编号 {activeSuite.suite_short}</small></div> : <div className="evaluation-set-placeholder">{latestSuite.isPending ? '正在读取已保存的评测集…' : latestSuite.isError ? '已保存评测集暂时不可用' : '尚未创建评测集'}</div>}<input aria-label="评测题量" type="number" min="1" max="100" value={sampleSize} onChange={(event) => setSampleSize(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /><button type="button" onClick={requestSuite} disabled={createSuite.isPending || resample.isPending || !bankId}><RefreshCw size={14} className={createSuite.isPending || resample.isPending ? 's1-spin' : ''} />{activeSuite ? '重新抽样' : '创建评测集'}</button></div><small>当前评测集会保留，点击“重新抽样”后才会更换题目。</small></div>
      </div>
      <div className="evaluation-field evaluation-connection-field"><span>03 · 模型连接方式</span><div className="evaluation-segmented" role="group" aria-label="模型连接方式"><button type="button" className={connectionMode === 'default' ? 'is-active' : ''} onClick={() => setConnectionMode('default')}>项目默认</button><button type="button" className={connectionMode === 'custom' ? 'is-active' : ''} onClick={() => setConnectionMode('custom')}>自定义 API</button></div>{connectionMode === 'default' ? <small>使用当前 TiBan 实例的 Provider 配置；本次实验固定为 no-fallback。</small> : <div className="evaluation-custom-connection"><label><span>Base URL</span><input aria-label="评测 Base URL" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://api.example.com/v1" autoComplete="off" /></label><label><span>API Key</span><div className="evaluation-secret-input"><input aria-label="评测 API Key" type={showKey ? 'text' : 'password'} value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="仅用于本次实验" autoComplete="new-password" /><button type="button" aria-label={showKey ? '隐藏评测 API Key' : '显示评测 API Key'} onClick={() => setShowKey((value) => !value)}>{showKey ? <EyeOff size={15} /> : <Eye size={15} />}</button></div></label><small>连接地址与模型名会作为候选标识保存；API Key 仅暂存于运行时共享目录，实验结束后清理。</small></div>}</div>
      <label className="evaluation-field evaluation-candidates-field"><span>04 · 候选模型</span><textarea aria-label="候选模型" value={candidateText} onChange={(event) => setCandidateText(event.target.value)} placeholder="每行填写一个模型名称" /><div className="evaluation-candidates-footer"><small>每行填写一个模型；结果显示短名称，评测请求仍使用完整模型 ID。</small><button className="evaluation-primary" type="button" disabled={!canRun} onClick={() => createExperiment.mutate()}><Play size={15} />开始模型评测</button></div></label>
      {(latestSuite.isError || latestExperiment.isError || createSuite.error || resample.error || createExperiment.error) && <div className="evaluation-action-row evaluation-error-row"><div>{latestSuite.isError && <p className="evaluation-error" role="alert">{errorMessage(latestSuite.error)} 可直接创建新的评测集。</p>}{latestExperiment.isError && <p className="evaluation-error" role="alert">已保存的模型评测结果暂时无法读取。</p>}{createSuite.error && <p className="evaluation-error" role="alert">{errorMessage(createSuite.error)}</p>}{resample.error && <p className="evaluation-error" role="alert">{errorMessage(resample.error)}</p>}{createExperiment.error && <p className="evaluation-error" role="alert">{errorMessage(createExperiment.error)}</p>}</div></div>}
    </div>
    {current && current.status !== 'completed' && current.status !== 'partial_failed' && <div className="evaluation-progress" role="status"><LoaderCircle size={16} className="s1-spin" /><span>{current.runs[0] ? `${current.runs[0].stage} · ${current.runs[0].progress}%` : '正在创建后台任务…'}</span></div>}
    <ModelLeaderboard experiment={current} />
    <EvaluationConfirmDialog open={confirmResample} bankName={catalog.banks.find((bank) => bank.bank_id === bankId)?.name ?? bankId} evaluationType="model" pending={resample.isPending} error={resample.error ? errorMessage(resample.error) : null} onCancel={() => { if (!resample.isPending) { setConfirmResample(false); resample.reset() } }} onConfirm={() => resample.mutate()} />
  </section>
}

function ModelLeaderboard({ experiment }: { experiment: EvaluationExperiment | null }) {
  if (!experiment) return <div className="evaluation-empty"><strong>评测结果将在这里呈现</strong><span>先创建或读取一个评测集，再开始模型评测。历史评测集不会因打开页面而改变。</span></div>
  const runs = [...experiment.runs].sort((a, b) => Number(b.aggregate.accuracy ?? 0) - Number(a.aggregate.accuracy ?? 0) || Number(b.aggregate.valid_response_rate ?? 0) - Number(a.aggregate.valid_response_rate ?? 0) || Number(b.aggregate.provider_success_rate ?? 0) - Number(a.aggregate.provider_success_rate ?? 0) || Number(a.aggregate.p50_latency_ms ?? Infinity) - Number(b.aggregate.p50_latency_ms ?? Infinity))
  return <section className="evaluation-panel evaluation-results-panel"><header className="evaluation-result-heading"><div><span>模型排行榜</span><h2>本次评测 {experiment.suite.sample_size} 道题 · 评测集编号 {experiment.suite.suite_short}</h2></div><small>{experiment.status === 'completed' ? '评测完成' : experiment.status === 'partial_failed' ? '部分候选失败' : '运行中'}</small></header><div className="evaluation-table-wrap"><table className="evaluation-table"><thead><tr><th>模型 / 连接</th><th>Accuracy</th><th>有效响应率</th><th>API 成功率</th><th>P50 延迟</th><th>Avg Tokens / 题</th></tr></thead><tbody>{runs.map((run) => <tr key={run.run_id}><td><strong title={run.model}>{displayModelName(run.model || run.name)}</strong><small>{run.base_url ? run.base_url : '项目默认连接'} · {run.status === 'completed' ? '已完成' : `${run.stage} · ${run.progress}%`}</small></td><td>{percent(run.aggregate.accuracy)}</td><td>{percent(run.aggregate.valid_response_rate)}</td><td>{percent(run.aggregate.provider_success_rate)}</td><td>{latency(run.aggregate.p50_latency_ms)}</td><td>{metric(run.aggregate.avg_tokens_per_question)}</td></tr>)}</tbody></table></div></section>
}

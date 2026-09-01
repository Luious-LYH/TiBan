import { AlertCircle, CheckCircle2, Eye, EyeOff, KeyRound, Play, RefreshCw } from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { createEvaluationRun, getEvaluationDatasets, getEvaluationRun, getLatestEvaluation, testEvaluationConnection, type EvaluationArtifact, type EvaluationConnection, type EvaluationRun } from '../../api/client'
import { ErrorState, LoadingState } from '../../components/shared/AsyncState'
import { Tabs } from '../../components/ui/Tabs'

type EvaluationCase = { eval_case_id?: string; source_item_id?: string; question?: string; candidate_output?: string; parsed_answer?: string | null; gold_answer?: string | null; correct?: boolean | null; latency_ms?: number | null; error_category?: string | null; task?: string; topic?: string | null; image_attached?: boolean }
function asCase(item: Record<string, unknown>): EvaluationCase { return item as EvaluationCase }
function errorMessage(error: unknown): string { return error instanceof Error ? error.message : '请求失败，请检查模型服务配置与连接状态。' }
function formatMetric(value: unknown, suffix = ''): string { if (value === null || value === undefined || value === '') return '—'; if (typeof value === 'number') return `${value}${suffix}`; return String(value) }
function percent(value: unknown) { return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—' }

export function EvaluationPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const datasetsQuery = useQuery({ queryKey: ['evaluation-datasets'], queryFn: getEvaluationDatasets })
  const latestQuery = useQuery({ queryKey: ['latest-evaluation'], queryFn: getLatestEvaluation })
  const [selectedDatasetId, setSelectedDatasetId] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [sampleCount, setSampleCount] = useState('5')
  const [run, setRun] = useState<EvaluationRun | null>(null)
  const [connectionResult, setConnectionResult] = useState<EvaluationConnection | null>(null)
  const [revealed, setRevealed] = useState(false)
  const activeTab = searchParams.get('tab') === 'tutor' ? 'tutor' : 'retrieval'
  const datasets = datasetsQuery.data ?? []
  const effectiveDatasetId = selectedDatasetId || datasets[0]?.dataset_id || ''
  const selectedDataset = datasets.find((item) => item.dataset_id === effectiveDatasetId) ?? datasets[0]
  const latest = latestQuery.data?.artifact_available ? latestQuery.data : null
  const connection = useMutation({ mutationFn: () => testEvaluationConnection({ base_url: apiBase.trim(), model: model.trim(), api_key: apiKey }), onSuccess: setConnectionResult })
  const evaluation = useMutation({ mutationFn: () => createEvaluationRun({ base_url: apiBase.trim(), model: model.trim(), api_key: apiKey, dataset_id: selectedDataset?.dataset_id ?? '', sample_count: Math.max(1, Math.min(300, Number(sampleCount) || 1)) }), onSuccess: (result) => { setRun(result); setRevealed(false) } })
  const reveal = useMutation({ mutationFn: () => getEvaluationRun(run?.eval_run_id ?? '', true), onSuccess: (result) => { setRun(result); setRevealed(true) } })
  const runCases = useMemo(() => (run?.cases ?? []).map(asCase), [run])

  if (datasetsQuery.isPending) return <LoadingState label="正在读取评测集…" />
  if (datasetsQuery.isError) return <ErrorState message={errorMessage(datasetsQuery.error)} onRetry={() => void datasetsQuery.refetch()} />

  return <div className="evaluation-workspace" data-testid="evaluation-page">
    <header className="evaluation-header"><div><h1>评测中心</h1><p>查看已有评测结果，或创建一次新的候选模型评测。</p></div></header>
    <Tabs value={activeTab} onChange={(value) => setSearchParams({ tab: value })} label="评测类型" items={[{ value: 'retrieval', label: '检索评测' }, { value: 'tutor', label: '辅导评测' }]} />
    {latest && <LatestResult activeTab={activeTab} artifact={latest} />}
    <details className="evaluation-config" open={!latest && !run}><summary>新建评测</summary><div className="evaluation-config-body"><div className="evaluation-form"><label><span>连接地址</span><input aria-label="连接地址" value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="https://provider.example/v1" autoComplete="off" /></label><label><span>模型名称</span><input aria-label="模型名称" value={model} onChange={(event) => setModel(event.target.value)} placeholder="candidate-model" autoComplete="off" /></label><label><span>API Key <small>仅用于本次连接</small></span><div><KeyRound size={15} /><input aria-label="API Key" type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder="••••••••" autoComplete="off" /></div></label><label><span>评测集</span><select value={effectiveDatasetId} onChange={(event) => setSelectedDatasetId(event.target.value)}>{datasets.map((dataset) => <option key={dataset.dataset_id} value={dataset.dataset_id}>{dataset.name}</option>)}</select></label><label><span>本次抽样题量</span><input aria-label="本次抽样题量" type="number" min="1" max="300" value={sampleCount} onChange={(event) => setSampleCount(event.target.value)} /></label></div>{selectedDataset && <p className="evaluation-dataset-note">{selectedDataset.sample_count} 道题 · {selectedDataset.supports_vision ? '包含图像输入' : '文本输入'} · {selectedDataset.description}</p>}<div className="evaluation-actions"><button type="button" onClick={() => connection.mutate()} disabled={connection.isPending || !apiBase.trim() || !model.trim() || !apiKey}><RefreshCw size={15} className={connection.isPending ? 's1-spin' : ''} />{connection.isPending ? '正在测试连接…' : '测试连接'}</button><button className="evaluation-primary" type="button" onClick={() => evaluation.mutate()} disabled={evaluation.isPending || !selectedDataset || !apiBase.trim() || !model.trim() || !apiKey}><Play size={15} />{evaluation.isPending ? '正在评测…' : '开始评测'}</button></div>{connectionResult && <div className={connectionResult.ok ? 'evaluation-receipt is-ok' : 'evaluation-receipt is-error'} role="status">{connectionResult.ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}<span><strong>{connectionResult.ok ? '模型连接成功' : '模型连接失败'}</strong>{connectionResult.ok ? `${connectionResult.model} · ${connectionResult.latency_ms ?? '—'} ms` : connectionResult.error}</span></div>}{connection.isError && <div className="evaluation-error" role="alert">{errorMessage(connection.error)}</div>}{evaluation.isError && <div className="evaluation-error" role="alert">{errorMessage(evaluation.error)}</div>}</div></details>
    {run && <RunResult run={run} revealed={revealed} revealing={reveal.isPending} onReveal={() => reveal.mutate()} cases={runCases} />}
  </div>
}

function LatestResult({ activeTab, artifact }: { activeTab: string; artifact: EvaluationArtifact }) {
  const { metrics, cases, probes, strategy_comparison: strategies } = artifact
  const recall = metrics.retrieval_recall_at_3 ?? metrics.recall_at_3
  const [selectedProbeId, setSelectedProbeId] = useState(probes[0]?.id ?? '')
  const selectedProbe = probes.find((probe) => probe.id === selectedProbeId) ?? probes[0]
  return <section className="evaluation-result latest-result"><div className="evaluation-result-heading"><div><span>最近结果</span><h2>{activeTab === 'tutor' ? '辅导运行评测' : '检索与运行评测'}</h2></div><small>{formatMetric(metrics.case_count ?? metrics.sample_count)} 个案例</small></div><div className="evaluation-metrics"><Metric label="任务完成率" value={percent(metrics.task_completion_rate)} /><Metric label="证据覆盖率" value={percent(metrics.evidence_coverage_rate)} /><Metric label="Recall@3" value={percent(recall)} /><Metric label="P50 延迟" value={formatMetric(metrics.latency_p50_ms, ' ms')} /></div>{activeTab === 'retrieval' && <>{strategies.length > 0 && <div className="evaluation-strategies" data-testid="evaluation-strategies"><h3>真实策略对比</h3>{strategies.map((strategy) => <article key={strategy.name}><strong>{strategy.name}</strong>{Object.entries(strategy.metrics ?? {}).map(([name, value]) => <span key={name}>{name} {formatMetric(value)}</span>)}</article>)}</div>}{selectedProbe && <ProbeEvidence probe={selectedProbe} probes={probes} selectedProbeId={selectedProbeId} onSelect={setSelectedProbeId} />}</>}<div className="evaluation-case-list">{cases.slice(0, 5).map((item, index) => <article key={String(item.case_id ?? index)}><strong>{String(item.case_id ?? `案例 ${index + 1}`)}</strong><span>{item.retrieved_count !== undefined ? `检索 ${String(item.retrieved_count)} 条` : '已完成'}</span><small>{formatMetric(item.latency_ms, ' ms')}</small></article>)}</div></section>
}
function ProbeEvidence({ probe, probes, selectedProbeId, onSelect }: { probe: NonNullable<EvaluationArtifact['probes'][number]>; probes: EvaluationArtifact['probes']; selectedProbeId: string; onSelect: (id: string) => void }) { const retrieved = probe.retrieved ?? []; return <div className="evaluation-evidence" data-testid="evaluation-case-detail"><div className="evaluation-evidence-heading"><div><span>检索案例</span><h3>{probe.id}</h3></div><select aria-label="选择检索案例" value={selectedProbeId} onChange={(event) => onSelect(event.target.value)}>{probes.map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}</select></div><p className="evaluation-query"><small>查询</small>{probe.query}</p><EvidenceItem label="期望证据" item={probe.expected_evidence} /><div className="evaluation-retrieved"><small>检索证据 Top-{retrieved.length}</small>{retrieved.map((item) => <EvidenceItem key={`${item.rank}-${item.evidence_id}`} label={`#${item.rank}`} item={item} />)}</div><p className={probe.hit_at_1 ? 'evaluation-result-status is-pass' : 'evaluation-result-status'}>{probe.hit_at_1 ? 'Top-1 命中预期证据' : probe.hit_at_3 ? 'Top-3 命中预期证据' : '未命中预期证据'}</p></div> }
function EvidenceItem({ label, item }: { label: string; item: { label: string; source_title: string; section: string; snippet: string } }) { return <article className="evaluation-evidence-item"><small>{label}</small><strong>{item.label}</strong><span>{item.source_title} · {item.section}</span><p>{item.snippet}</p></article> }
function RunResult({ run, revealed, revealing, onReveal, cases }: { run: EvaluationRun; revealed: boolean; revealing: boolean; onReveal: () => void; cases: EvaluationCase[] }) { return <section className="evaluation-result"><div className="evaluation-result-heading"><div><span>本次运行</span><h2>评测完成</h2></div><button type="button" onClick={onReveal} disabled={revealed || revealing}>{revealed ? <EyeOff size={15} /> : <Eye size={15} />}{revealed ? '参考答案已展示' : revealing ? '正在读取参考答案…' : '查看对照答案'}</button></div><div className="evaluation-metrics"><Metric label="准确率" value={revealed ? percent(run.aggregate.accuracy) : '—'} /><Metric label="答案解析率" value={percent(run.aggregate.valid_parse_rate)} /><Metric label="P50 延迟" value={formatMetric(run.aggregate.latency_p50_ms, ' ms')} /><Metric label="P95 延迟" value={formatMetric(run.aggregate.latency_p95_ms, ' ms')} /></div><div className="evaluation-case-list">{cases.map((item, index) => <article key={item.eval_case_id ?? String(index)}><strong>{item.question ?? `案例 ${index + 1}`}</strong><span>{item.candidate_output ?? '—'}</span>{revealed && <b>{item.gold_answer ?? '—'}</b>}<small>{item.latency_ms ?? '—'} ms</small></article>)}</div></section> }
function Metric({ label, value }: { label: string; value: string }) { return <div><small>{label}</small><strong>{value}</strong></div> }

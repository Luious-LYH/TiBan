import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  Bookmark,
  BookOpenCheck,
  Check,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  Copy,
  Database,
  FileSearch,
  Image as ImageIcon,
  LoaderCircle,
  Pencil,
  Play,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { PortfolioAgentRun, PortfolioCase } from '../lib/types'

type ViewMode = 'task' | 'agent'
type AgentTab = 'run' | 'evidence' | 'memory'
type WorkbenchStatus = 'ready' | 'running' | 'paused' | 'completed' | 'error'
type DrawerItem =
  | { kind: 'step'; value: PortfolioAgentRun['trace'][number] }
  | { kind: 'tool'; value: PortfolioAgentRun['tool_receipts'][number] }

export function AgentWorkbench() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedCaseId = searchParams.get('case')
  const [cases, setCases] = useState<PortfolioCase[]>([])
  const [activeCase, setActiveCase] = useState<PortfolioCase | null>(null)
  const [answer, setAnswer] = useState('')
  const [run, setRun] = useState<PortfolioAgentRun | null>(null)
  const [streamStages, setStreamStages] = useState<PortfolioAgentRun['trace']>([])
  const [status, setStatus] = useState<WorkbenchStatus>('ready')
  const [error, setError] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('task')
  const [agentTab, setAgentTab] = useState<AgentTab>('run')
  const [drawerItem, setDrawerItem] = useState<DrawerItem | null>(null)
  const [copied, setCopied] = useState(false)
  const [loadingCases, setLoadingCases] = useState(true)
  const [replayBusy, setReplayBusy] = useState(false)
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => readPortfolioFavorites())
  const caseDialogRef = useRef<HTMLDialogElement | null>(null)
  const answerRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    let mounted = true
    v3Api.portfolioCases()
      .then((payload) => {
        if (!mounted) return
        setCases(payload.items)
        setActiveCase(payload.items.find((item) => item.id === requestedCaseId) || payload.items[0] || null)
        setAnswer('')
        setRun(null)
        setStreamStages([])
        setError('')
        setStatus('ready')
        setAgentTab('run')
        setViewMode('task')
      })
      .catch(() => {
        if (mounted) setError('病例服务暂不可用，请确认后端已启动后重试。')
      })
      .finally(() => {
        if (mounted) setLoadingCases(false)
      })
    return () => { mounted = false }
  }, [requestedCaseId])

  useEffect(() => {
    let mounted = true
    v3Api.portfolioStudy()
      .then((payload) => {
        if (!mounted) return
        const backendFavorites = payload.library.items.filter((item) => item.favorited).map((item) => item.id)
        setFavoriteIds(new Set(backendFavorites))
        window.localStorage.setItem('endoscopy-agent:portfolio-favorites', JSON.stringify(backendFavorites))
      })
      .catch(() => undefined)
    return () => { mounted = false }
  }, [])

  const supportedFacts = useMemo(() => new Set(run?.result.matched_fact_ids || []), [run])

  const selectCase = (item: PortfolioCase) => {
    setActiveCase(item)
    setAnswer('')
    setRun(null)
    setStreamStages([])
    setError('')
    setStatus('ready')
    setAgentTab('run')
    setViewMode('task')
    caseDialogRef.current?.close()
    navigate(`/workbench?case=${encodeURIComponent(item.id)}&from=case-picker`, { replace: true })
  }

  const executeRun = async () => {
    if (!activeCase || !answer.trim() || status === 'running') return
    setStatus('running')
    setRun(null)
    setStreamStages([])
    setError('')
    setAgentTab('run')
    try {
      await v3Api.portfolioAgentRunStream(activeCase.id, answer.trim(), (event) => {
        if (event.event === 'stage') {
          setStreamStages((items) => [...items, event.stage])
          return
        }
        if (event.event === 'final') {
          setRun(event.run)
          setStatus(event.run.status === 'blocked' ? 'paused' : 'completed')
          setAgentTab(event.run.status === 'blocked' ? 'run' : 'evidence')
        }
        if (event.event === 'error') {
          setError(event.message || event.error_code)
        }
      })
    } catch (cause) {
      setStatus('error')
      setError(cause instanceof Error ? cause.message : 'Agent Run 执行失败，请检查服务后重试。')
    }
  }

  const editAndRerun = () => {
    setStatus('ready')
    setRun(null)
    setStreamStages([])
    setError('')
    setViewMode('task')
    window.setTimeout(() => answerRef.current?.focus(), 0)
  }

  const copyRunId = async () => {
    if (!run?.run_id) return
    await navigator.clipboard?.writeText(run.run_id)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1000)
  }

  const toggleFavorite = () => {
    if (!activeCase) return
    const caseId = activeCase.id
    const favorited = !favoriteIds.has(caseId)
    setFavoriteIds((current) => {
      const next = new Set(current)
      if (next.has(caseId)) next.delete(caseId)
      else next.add(caseId)
      window.localStorage.setItem('endoscopy-agent:portfolio-favorites', JSON.stringify([...next]))
      return next
    })
    void v3Api.portfolioStudyFavorite(caseId, favorited)
  }

  const replayRun = async () => {
    if (!run?.run_id || replayBusy || !run.checkpoint?.replayable) return
    setReplayBusy(true)
    setStatus('running')
    setAgentTab('run')
    setError('')
    try {
      const replay = await v3Api.portfolioAgentReplay(run.run_id)
      setRun(replay)
      setStreamStages(replay.trace)
      setStatus(replay.status === 'blocked' ? 'paused' : 'completed')
    } catch (cause) {
      setStatus('error')
      setError(cause instanceof Error ? cause.message : 'Checkpoint 重放失败。')
    } finally {
      setReplayBusy(false)
    }
  }

  return (
    <section className="v21-workbench" data-v21-workbench="true">
      <header className="v21-casebar">
        <div className="v21-casebar-main">
          <span className="v21-eyebrow">Golden Case · {activeCase?.id || '等待病例'}</span>
          <h1>{activeCase?.title || (loadingCases ? '正在载入公开教学病例…' : '病例不可用')}</h1>
        </div>
        <div className="v21-case-meta">
          <span>{activeCase?.difficulty || '—'}</span>
          <span>{activeCase?.source_type || '公开教学样例'}</span>
          <span className="v21-source">来源：{activeCase?.source_dataset || '等待后端'}</span>
        </div>
        <button className={activeCase && favoriteIds.has(activeCase.id) ? 'v21-workbench-favorite is-active' : 'v21-workbench-favorite'} type="button" onClick={toggleFavorite} disabled={!activeCase}>
          <Bookmark size={16} fill={activeCase && favoriteIds.has(activeCase.id) ? 'currentColor' : 'none'} />
          {activeCase && favoriteIds.has(activeCase.id) ? '已收藏' : '收藏'}
        </button>
        <button className="v21-case-picker" type="button" onClick={() => caseDialogRef.current?.showModal()} disabled={!cases.length}>
          <FileSearch size={16} /> 切换病例
        </button>
      </header>

      <div className="v21-mobile-switch" role="tablist" aria-label="工作台视图">
        <button className={viewMode === 'task' ? 'is-active' : ''} onClick={() => setViewMode('task')} role="tab">病例任务</button>
        <button className={viewMode === 'agent' ? 'is-active' : ''} onClick={() => setViewMode('agent')} role="tab">
          Agent · {statusLabel(status)}
        </button>
      </div>

      <div className="v21-workspace">
        <main className={`v21-task-surface ${viewMode === 'agent' ? 'v21-mobile-hidden' : ''}`}>
          <div className="v21-image-stage">
            {activeCase?.image_url ? (
              <img src={activeCase.image_url} alt={`${activeCase.title}公开教学图像`} data-real-sample-image="true" data-real-sample-role="primary" />
            ) : (
              <div className="v21-image-empty"><ImageIcon size={28} /><span>{loadingCases ? '正在读取图像' : '没有可展示的病例图像'}</span></div>
            )}
            <div className="v21-image-caption">
              <span><Database size={14} /> {activeCase?.source_dataset || '来源待确认'}</span>
              <span>公开/脱敏教学用途</span>
            </div>
          </div>

          <div className="v21-answer-stage">
            <div className="v21-task-heading">
              <span>01 · 观察并作答</span>
              <h2>{activeCase?.prompt || '病例载入后将在此显示观察任务。'}</h2>
              <p>先描述可观察事实，再说明判断边界。Agent 将按事实级 Rubric 评分，而不是字符串完全匹配。</p>
            </div>
            <label className="v21-answer-field">
              <span>你的观察记录</span>
              <textarea
                ref={answerRef}
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                disabled={status === 'running' || status === 'completed'}
                rows={7}
                placeholder="例如：我观察到的部位、形态、数量和证据限制是……"
              />
              <small>{answer.trim().length} 字 · 不需要与参考答案逐字一致</small>
            </label>

            {status === 'completed' && run ? (
              <div className="v21-score-result" data-study-memory-committed={run.memory_delta.committed ? 'true' : 'false'}>
                <div><span>事实级评分</span><strong>{Math.round(run.result.score)}</strong><small>/ 100</small></div>
                <div className="v21-score-copy">
                  <p>{run.result.feedback}</p>
                  <span><Check size={14} /> {run.memory_delta.committed ? '已写入错题、掌握度与复习计划' : '本次结果仅预览，未写入研修状态'}</span>
                </div>
              </div>
            ) : null}

            {status === 'paused' ? (
              <div className="v21-hitl">
                <AlertCircle size={20} />
                <div><strong>Run 已暂停，等待医生修改</strong><span>当前输出未进入后续记忆或报告流程。</span></div>
                <button type="button" onClick={editAndRerun}><Pencil size={15} /> 修改答案并重新运行</button>
              </div>
            ) : null}

            {status === 'error' ? (
              <div className="v21-error"><AlertCircle size={18} /><span>{error || '运行失败'}</span><button type="button" onClick={executeRun}><RefreshCw size={15} /> 重试</button></div>
            ) : null}

            <div className="v21-task-actions">
              {status === 'completed' ? (
                <>
                  <button className="v21-secondary-action" type="button" onClick={editAndRerun}><Pencil size={16} /> 修改答案并重新运行</button>
                  <Link className="v21-study-return" to="/study"><BookOpenCheck size={16} /> 回研修中心</Link>
                  {run?.result.adaptive_recommendation ? (
                    <button
                      className="v21-primary-action v21-next-action"
                      type="button"
                      title={run.result.adaptive_recommendation.reason}
                      onClick={() => navigate(`/workbench?case=${encodeURIComponent(run.result.adaptive_recommendation!.case_id)}&from=agent-recommendation`)}
                    >
                      下一题 · {run.result.adaptive_recommendation.case_title} <ArrowRight size={17} />
                    </button>
                  ) : null}
                </>
              ) : (
                <button className="v21-primary-action" type="button" onClick={executeRun} disabled={!activeCase || !answer.trim() || status === 'running'}>
                  {status === 'running' ? <LoaderCircle className="v21-spin" size={17} /> : <Play size={17} />}
                  {status === 'running' ? 'Agent 正在执行' : '提交并运行 Agent'} <ArrowRight size={17} />
                </button>
              )}
            </div>
          </div>
        </main>

        <aside className={`v21-agent-panel ${viewMode === 'task' ? 'v21-mobile-hidden' : ''}`} data-agent-activity="true">
          <div className="v21-agent-head">
            <div><span className={`v21-status-dot is-${status}`} /><span>Agent Activity</span></div>
            <strong>{statusLabel(status)}</strong>
          </div>

          <div className="v21-run-summary">
            <span>{run?.run_id || '提交后生成 Run ID'}</span>
            {run ? <button type="button" onClick={copyRunId} aria-label="复制 Run ID"><Copy size={14} />{copied ? '已复制' : ''}</button> : null}
            <small>{run ? `Backend Runtime · ${formatMs(run.latency_ms)}` : '来源会按真实响应标注'}</small>
          </div>

          <div className="v21-agent-tabs" role="tablist">
            <button className={agentTab === 'run' ? 'is-active' : ''} onClick={() => setAgentTab('run')} role="tab">运行</button>
            <button className={agentTab === 'evidence' ? 'is-active' : ''} onClick={() => setAgentTab('evidence')} role="tab">证据</button>
            <button className={agentTab === 'memory' ? 'is-active' : ''} onClick={() => setAgentTab('memory')} role="tab">Memory</button>
          </div>

          <div className="v21-agent-content">
            {agentTab === 'run' ? <RunPanel status={status} run={run} liveStages={streamStages} replayBusy={replayBusy} onOpen={setDrawerItem} onEdit={editAndRerun} onReplay={replayRun} /> : null}
            {agentTab === 'evidence' ? <EvidencePanel activeCase={activeCase} run={run} supportedFacts={supportedFacts} /> : null}
            {agentTab === 'memory' ? <MemoryPanel run={run} /> : null}
          </div>
        </aside>
      </div>

      <footer className="v21-safety"><ShieldCheck size={15} /><span>{run?.safety_notice || v3SafetyNotice}</span><b>医生复核边界</b></footer>

      <dialog className="v21-case-dialog" ref={caseDialogRef} aria-label="选择公开教学病例">
        <div className="v21-dialog-head"><div><span>Golden Cases</span><h2>选择研修病例</h2></div><button onClick={() => caseDialogRef.current?.close()} aria-label="关闭病例选择"><X size={20} /></button></div>
        <div className="v21-case-list">
          {cases.map((item) => (
            <button key={item.id} type="button" className={item.id === activeCase?.id ? 'is-active' : ''} onClick={() => selectCase(item)}>
              <img src={item.image_url} alt="" />
              <span><strong>{item.title}</strong><small>{item.difficulty} · {item.source_dataset}</small></span>
              <ChevronRight size={17} />
            </button>
          ))}
        </div>
      </dialog>

      {drawerItem ? <DetailDrawer item={drawerItem} onClose={() => setDrawerItem(null)} /> : null}
    </section>
  )
}

function RunPanel({ status, run, liveStages, replayBusy, onOpen, onEdit, onReplay }: { status: WorkbenchStatus; run: PortfolioAgentRun | null; liveStages: PortfolioAgentRun['trace']; replayBusy: boolean; onOpen: (item: DrawerItem) => void; onEdit: () => void; onReplay: () => void }) {
  const displayedSteps = run?.trace || liveStages
  return (
    <div className="v21-run-panel">
      {status === 'ready' ? <div className="v21-panel-empty"><Sparkles size={22} /><strong>Agent 已就绪</strong><span>提交观察记录后，将依次规划、调用工具、核验证据并生成 Memory Delta。</span></div> : null}
      {status === 'running' ? <div className="v21-stream-state"><LoaderCircle className="v21-spin" size={15} /><span>{replayBusy ? '正在从后端 checkpoint 重放 Run…' : liveStages.length ? '等待后端发送下一 stage…' : '正在等待首个真实 stage 事件…'}</span></div> : null}
      {displayedSteps.length ? (
        <div className="v21-timeline">
          {displayedSteps.map((step, index) => (
            <button type="button" className={step.status === 'blocked' ? 'is-blocked' : 'is-complete'} key={`${step.node}-${index}`} onClick={() => onOpen({ kind: 'step', value: step })}>
              <i>{step.status === 'completed' ? <Check size={15} /> : <AlertCircle size={15} />}</i>
              <span><strong>{step.node}</strong><small>{step.summary}</small></span>
              <em>{formatMs(step.latency_ms)}</em>
            </button>
          ))}
        </div>
      ) : null}
      {run ? <div className="v21-runtime-ledger">
        <span><small>Context budget</small><b>{run.context_manifest ? `${run.context_manifest.included_estimated_tokens}/${run.context_manifest.budget_tokens} tok` : '未采集'}</b></span>
        <span><small>model_calls</small><b>{run.usage_ledger?.model_calls ?? '未采集'}</b></span>
        <span><small>checkpoint</small><b>{run.checkpoint?.replayable ? 'replayable' : '不可重放'}</b></span>
      </div> : null}
      {run?.tool_receipts.length ? <div className="v21-tools"><span>Tool calls / Recovery</span>{run.tool_receipts.map((tool) => <button className={!tool.success ? 'is-error' : tool.recovered_from_call_id ? 'is-recovered' : ''} key={tool.call_id} onClick={() => onOpen({ kind: 'tool', value: tool })}><ClipboardCheck size={16} /><span><strong>{tool.tool_name}</strong><small>attempt {tool.attempt ?? 1} · {tool.success ? tool.recovered_from_call_id ? 'recovered' : 'success' : `${tool.error_code || 'error'}${tool.retryable ? ' · retryable' : ''}`} · {tool.evidence_ids.length} evidence</small></span><ChevronRight size={15} /></button>)}</div> : null}
      {run?.checkpoint?.replayable ? <button className="v21-replay-action" type="button" onClick={onReplay} disabled={replayBusy || status === 'running'}><RefreshCw className={replayBusy ? 'v21-spin' : ''} size={15} /> {replayBusy ? '正在重放' : '重放 Run'} <small>{run.checkpoint.storage}</small></button> : null}
      {status === 'paused' ? <button className="v21-hitl-action" type="button" onClick={onEdit}><Pencil size={15} /> 修改答案并重新运行</button> : null}
      {status === 'error' ? <div className="v21-panel-empty"><AlertCircle size={22} /><strong>Run 未完成</strong><span>任务区保留了你的答案，可直接重试。</span></div> : null}
    </div>
  )
}

function EvidencePanel({ activeCase, run, supportedFacts }: { activeCase: PortfolioCase | null; run: PortfolioAgentRun | null; supportedFacts: Set<string> }) {
  if (!run) return <div className="v21-panel-empty"><FileSearch size={22} /><strong>尚无证据结果</strong><span>完成 Run 后，这里按事实展示命中、遗漏和原始证据。</span></div>
  return <div className="v21-evidence-list"><div className="v21-metric-strip"><span><b>{Math.round(run.result.fact_precision * 100)}%</b>Precision</span><span><b>{Math.round(run.result.fact_recall * 100)}%</b>Recall</span><span><b>{Math.round(run.result.fact_f1 * 100)}%</b>F1</span></div>{activeCase?.facts.map((fact) => <div key={fact.id} className={supportedFacts.has(fact.id) ? 'is-supported' : 'is-missed'}><i>{supportedFacts.has(fact.id) ? <Check size={14} /> : <AlertCircle size={14} />}</i><span><strong>{fact.label}</strong><small>{fact.evidence}</small><em>{fact.id}</em></span></div>)}</div>
}

function MemoryPanel({ run }: { run: PortfolioAgentRun | null }) {
  if (!run) return <div className="v21-panel-empty"><Database size={22} /><strong>尚无 Memory Delta</strong><span>只有有效作答完成后才生成变化预览。</span></div>
  return <div className="v21-memory-list"><div className="v21-memory-mode"><span>{run.memory_delta.committed ? '已写入' : '预览，未落盘'}</span><strong>{run.memory_delta.mode}</strong><small>{run.memory_delta.reason}</small></div>{run.memory_delta.dimension_deltas.map((item) => <div key={item.dimension}><span><strong>{item.dimension}</strong><small>{item.reason}</small></span><b>{item.before} <ArrowRight size={13} /> {item.after_preview}</b></div>)}<p><Clock3 size={14} /> 本 Run 的画像变化与评分结果分开记录。</p></div>
}

function DetailDrawer({ item, onClose }: { item: DrawerItem; onClose: () => void }) {
  const title = item.kind === 'step' ? `${item.value.node} Step` : item.value.tool_name
  return <div className="v21-drawer-backdrop" onMouseDown={onClose}><aside className="v21-agent-drawer" data-agent-drawer="true" onMouseDown={(event) => event.stopPropagation()}><header><div><span>Developer detail</span><h2>{title}</h2></div><button onClick={onClose} aria-label="关闭执行详情"><X size={20} /></button></header>{item.kind === 'step' ? <div className="v21-drawer-body"><DetailRow label="状态" value={item.value.status} /><DetailRow label="耗时" value={formatMs(item.value.latency_ms)} /><DetailRow label="摘要" value={item.value.summary} /><DetailRow label="Receipt IDs" value={item.value.receipt_ids.join(', ') || '无'} /></div> : <div className="v21-drawer-body"><DetailRow label="Call ID" value={item.value.call_id} /><DetailRow label="状态" value={item.value.success ? 'success' : 'failed'} /><DetailRow label="Attempt" value={String(item.value.attempt ?? 1)} /><DetailRow label="Error / Retry" value={item.value.error_code ? `${item.value.error_code} · ${item.value.retryable ? 'retryable' : 'not retryable'}` : '无错误'} /><DetailRow label="Recovered from" value={item.value.recovered_from_call_id || '非恢复调用'} /><DetailRow label="耗时" value={formatMs(item.value.latency_ms)} /><DetailRow label="Evidence IDs" value={item.value.evidence_ids.join(', ') || '无'} /><JsonBlock title="Tool input" value={item.value.input} /><JsonBlock title="Tool output" value={item.value.output} /></div>}</aside></div>
}

function DetailRow({ label, value }: { label: string; value: string }) { return <div className="v21-detail-row"><span>{label}</span><strong>{value}</strong></div> }
function JsonBlock({ title, value }: { title: string; value: Record<string, unknown> }) { return <details className="v21-json"><summary>{title}</summary><pre>{JSON.stringify(value, null, 2)}</pre></details> }
function statusLabel(status: WorkbenchStatus) { return ({ ready: '未运行', running: '运行中', paused: '等待医生', completed: '已完成', error: '失败' })[status] }
function formatMs(value: number) { return value < 1 ? '<1ms' : `${Math.round(value)}ms` }

function readPortfolioFavorites() {
  try {
    return new Set<string>(JSON.parse(window.localStorage.getItem('endoscopy-agent:portfolio-favorites') || '[]'))
  } catch {
    return new Set<string>()
  }
}

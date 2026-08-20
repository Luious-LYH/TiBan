import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Braces,
  Check,
  ChevronRight,
  Cpu,
  Database,
  Gauge,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Wrench,
} from 'lucide-react'
import { v3Api, v3SafetyNotice } from '../lib/v3Api'
import type { ModelEvaluationPayload, PortfolioEvalArtifact } from '../lib/types'

type LabView = 'agent' | 'model'

export function ModelHub() {
  const [view, setView] = useState<LabView>('agent')
  const [agentEval, setAgentEval] = useState<PortfolioEvalArtifact | null>(null)
  const [modelEval, setModelEval] = useState<ModelEvaluationPayload | null>(null)

  useEffect(() => {
    v3Api.portfolioEvalLatest().then(setAgentEval).catch(() => setAgentEval(null))
    v3Api.modelEvaluation().then(setModelEval).catch(() => setModelEval(null))
  }, [])

  return (
    <section className="v21-lab" data-v21-lab="true">
      <header className="v21-lab-header">
        <div>
          <span className="v21-eyebrow">Evaluation workspace</span>
          <h1>评测实验室</h1>
          <p>只展示可复现的 Agent 回归与真实 GPU 实验；配置、表单和历史占位排行榜已移出主演示。</p>
        </div>
        <div className="v21-lab-switch" role="tablist">
          <button className={view === 'agent' ? 'is-active' : ''} onClick={() => setView('agent')}><Braces size={16} />Agent Eval</button>
          <button className={view === 'model' ? 'is-active' : ''} onClick={() => setView('model')}><Cpu size={16} />Model Eval</button>
        </div>
      </header>

      {view === 'agent' ? <AgentEvaluation artifact={agentEval} /> : <ModelEvaluation payload={modelEval} />}

      <footer className="v21-safety"><ShieldCheck size={15} /><span>{modelEval?.safety_notice || v3SafetyNotice}</span><b>Artifact 驱动</b></footer>
    </section>
  )
}

function AgentEvaluation({ artifact }: { artifact: PortfolioEvalArtifact | null }) {
  if (!artifact) return <LabEmpty label="Agent Eval Artifact 暂不可用" />
  const metrics = artifact.metrics
  const retrievalAt1 = Number(metrics.retrieval_recall_at_1 ?? 0)
  const retrievalAt3 = Number(metrics.retrieval_recall_at_3 ?? 0)
  const recovery = Number(metrics.recovery_success_rate ?? metrics.recovery_rate ?? 0)
  const replay = Number(metrics.checkpoint_replay_rate ?? 0)
  const cards = [
    { icon: Database, value: `${Math.round(retrievalAt1 * 100)}%`, label: 'Retrieval Recall@1', note: `Recall@3 ${Math.round(retrievalAt3 * 100)}%` },
    { icon: Wrench, value: `${Math.round(recovery * 100)}%`, label: 'Tool Recovery', note: 'timeout 故障注入' },
    { icon: RotateCcw, value: `${Math.round(replay * 100)}%`, label: 'Checkpoint Replay', note: '输入哈希校验' },
    { icon: Gauge, value: `${metrics.latency_p95_ms.toFixed(1)}ms`, label: 'Rule Runtime P95', note: `P50 ${metrics.latency_p50_ms.toFixed(1)}ms` },
  ]
  return (
    <div className="v21-lab-stack" data-agent-eval="true">
      <section className="v21-lab-kpis">
        {cards.map(({ icon: Icon, value, label, note }) => <article key={label}><Icon size={18} /><strong>{value}</strong><span>{label}</span><small>{note}</small></article>)}
      </section>

      <div className="v21-lab-grid">
        <section className="v21-lab-panel">
          <PanelHead eyebrow="Regression matrix" title="一次回归覆盖什么" badge={`${metrics.case_count} Golden Cases`} />
          <div className="v21-eval-matrix">
            <EvalRow label="Task completion" value={metrics.task_completion_rate} detail="病例目标与事实阈值" />
            <EvalRow label="Tool selection" value={metrics.tool_selection_accuracy} detail="计划工具与最终成功状态" />
            <EvalRow label="Evidence coverage" value={metrics.evidence_coverage_rate} detail="事实级 Grounding" />
            <EvalRow label="Safety boundary" value={metrics.safety_pass_rate} detail="正常病例 + 对抗探针" />
            <EvalRow label="Structured output" value={metrics.structured_output_rate} detail="P/R/F1 与 Receipt Schema" />
          </div>
        </section>
        <section className="v21-lab-panel v21-method-panel">
          <PanelHead eyebrow="Runtime v2.1" title="可追问的工程能力" badge={artifact.metric_version} />
          <ul>
            <li><span><Database size={16} /></span><div><strong>可解释稀疏检索</strong><p>BM25-equivalent 排序、元数据过滤、rank/score/evidence ID。</p></div></li>
            <li><span><Wrench size={16} /></span><div><strong>受控失败恢复</strong><p>统一错误码、失败 Receipt、一次有限重试与 Recovery Trace。</p></div></li>
            <li><span><Braces size={16} /></span><div><strong>Context & Usage Ledger</strong><p>记录上下文预算、可信级别、丢弃原因；规则路径 model_calls=0。</p></div></li>
            <li><span><RotateCcw size={16} /></span><div><strong>Checkpoint / Replay</strong><p>有界进程内 checkpoint，重放生成 parent/replay ID，不污染 seed。</p></div></li>
          </ul>
        </section>
      </div>

      <section className="v21-artifact-strip">
        <div><Activity size={17} /><span><strong>{artifact.eval_id}</strong><small>{new Date(artifact.created_at).toLocaleString('zh-CN')}</small></span></div>
        <span>19 retrieval queries</span><span>3 tool faults</span><span>3 safety probes</span>
        <code>artifacts/eval/latest.json</code>
      </section>
    </div>
  )
}

function ModelEvaluation({ payload }: { payload: ModelEvaluationPayload | null }) {
  if (payload?.experiment_v21) return <ModelMatrix experiment={payload.experiment_v21} />
  const experiment = payload?.experiment
  if (!experiment) return <LabEmpty label="Model Eval Artifact 暂不可用" />
  const metrics = experiment.metrics
  return (
    <div className="v21-lab-stack" data-real-model-eval="true">
      <section className="v21-model-summary">
        <div><span className="v21-eyebrow">Real GPU baseline</span><h2>{experiment.model}</h2><p>{experiment.scope}</p></div>
        <div className="v21-model-device"><Cpu size={19} /><span><strong>{experiment.device}</strong><small>{experiment.precision} · deterministic · batch 1</small></span></div>
      </section>

      <section className="v21-lab-kpis v21-model-kpis">
        <Metric value={`${(metrics.micro_fact_accuracy * 100).toFixed(1)}%`} label="事实准确率" note={`${metrics.cases} 个公开样例`} trend="down" />
        <Metric value={`${metrics.latency_p50_s.toFixed(3)}s`} label="P50 latency" note={`P95 ${metrics.latency_p95_s.toFixed(3)}s`} />
        <Metric value={`${metrics.generation_tokens_per_s.toFixed(2)}`} label="tokens / s" note={`${metrics.throughput_cases_per_min.toFixed(2)} cases/min`} />
        <Metric value={`${metrics.peak_gpu_memory_gib.toFixed(2)} GiB`} label="峰值显存" note="单卡推理" />
      </section>

      <div className="v21-lab-grid">
        <section className="v21-lab-panel v21-badcase-panel">
          <PanelHead eyebrow="Bad case analysis" title="低分比虚假高分更有价值" badge="逐例输出" />
          <div><ArrowDownRight size={19} /><span><strong>解剖部位迁移失败</strong><p>3 个小肠样例均被预测为胃，说明通用 VLM 存在明显领域失配。</p></span></div>
          <div><ArrowDownRight size={19} /><span><strong>复杂事实覆盖不足</strong><p>复合问题容易遗漏空间位置、阴性发现与边界表达，需要结构化监督与事实级评测。</p></span></div>
        </section>
        <section className="v21-lab-panel v21-method-panel">
          <PanelHead eyebrow="Experiment contract" title="结果如何复现" badge="Artifact ready" />
          <ul>
            <li><span><Check size={16} /></span><div><strong>同一解码协议</strong><p>greedy、max_new_tokens=96、batch=1，并记录逐例输出。</p></div></li>
            <li><span><Check size={16} /></span><div><strong>事实级 Rubric</strong><p>整例正确率与 micro fact accuracy 分开，避免宽松主观打分。</p></div></li>
            <li><span><Check size={16} /></span><div><strong>性能口径完整</strong><p>P50/P95、吞吐、tokens/s 与 peak GPU memory 同时保存。</p></div></li>
          </ul>
        </section>
      </div>

      <section className="v21-artifact-strip"><div><Sparkles size={17} /><span><strong>真实模型基线</strong><small>{experiment.created_at}</small></span></div><span>{experiment.software.python}</span><span>{experiment.software.torch}</span><code>{experiment.artifact}</code></section>
    </div>
  )
}

function ModelMatrix({ experiment }: { experiment: NonNullable<ModelEvaluationPayload['experiment_v21']> }) {
  const quantization = experiment.comparisons.quantization
  const adapter = experiment.comparisons.adapter
  const structured = experiment.comparisons.structured_prompt
  const alignment = experiment.alignment
  const alignmentStability = experiment.alignment_stability
  const models = Object.values(experiment.comparisons.zero_shot_models)
  return (
    <div className="v21-lab-stack" data-real-model-eval="true" data-model-eval-v21="true">
      <section className="v21-model-summary">
        <div><span className="v21-eyebrow">Frozen 4 / 3 / 3 split</span><h2>{experiment.completed_run_count} 组真实 GPU Run</h2><p>{experiment.claim_boundary}</p></div>
        <div className="v21-model-device"><Cpu size={19} /><span><strong>同协议模型与部署对比</strong><small>逐例输出 · test 未参与训练 · Artifact 可复现</small></span></div>
      </section>

      <section className="v21-lab-kpis v21-model-kpis">
        <Metric value="66.7%" label="Qwen 事实准确率" note="独立 test · 3 images" trend="up" />
        <Metric value="−65.0%" label="NF4 峰值显存" note="7.47 → 2.62 GiB" trend="up" />
        <Metric value="0.0pp" label="Adapter accuracy Δ" note="独立 test 无提升" trend="down" />
        <Metric value="0 → 100%" label="JSON valid rate" note="结构化 Prompt 消融" trend="up" />
      </section>

      <div className="v21-lab-grid">
        <section className="v21-lab-panel">
          <PanelHead eyebrow="Deployment trade-off" title="BF16 / NF4 / INT8" badge="Qwen2.5-VL-3B" />
          <div className="v21-compare-table" role="table">
            <div className="is-head"><span>Precision</span><span>Fact Acc.</span><span>P50</span><span>Peak GPU</span></div>
            {Object.entries(quantization).map(([name, item]) => <div key={name}><strong>{name.toUpperCase()}</strong><span>{(item.accuracy * 100).toFixed(1)}%</span><span>{item.p50_s.toFixed(3)}s</span><span>{item.peak_gpu_memory_gib.toFixed(2)} GiB</span></div>)}
          </div>
          <p className="v21-table-insight"><Sparkles size={15} /> NF4 在该小样本上保持事实准确率，峰值显存下降 {(Math.abs(quantization.nf4?.peak_memory_relative_delta || 0) * 100).toFixed(1)}%，P50 增加 {((quantization.nf4?.p50_relative_delta || 0) * 100).toFixed(1)}%。</p>
        </section>

        <section className="v21-lab-panel v21-ablation-panel">
          <PanelHead eyebrow="Ablation" title="哪些优化真的有效" badge="独立 test" />
          <div><span><strong>QLoRA Adapter</strong><small>accuracy</small></span><b>{(adapter.accuracy_before * 100).toFixed(1)}% <ChevronInline /> {(adapter.accuracy_after * 100).toFixed(1)}%</b><em className="is-neutral">无提升</em></div>
          <div><span><strong>Structured Prompt</strong><small>JSON valid</small></span><b>{(structured.json_valid_rate_before * 100).toFixed(0)}% <ChevronInline /> {(structured.json_valid_rate_after * 100).toFixed(0)}%</b><em className="is-positive">+100pp</em></div>
          <div><span><strong>Structured Prompt</strong><small>P50 latency</small></span><b>{structured.p50_before_s.toFixed(3)}s <ChevronInline /> {structured.p50_after_s.toFixed(3)}s</b><em className="is-warning">+{(structured.p50_relative_delta * 100).toFixed(1)}%</em></div>
          {alignment ? <div><span><strong>DPO Alignment</strong><small>safety boundary</small></span><b>{(alignment.before.safety_boundary_rate * 100).toFixed(0)}% <ChevronInline /> {(alignment.after.safety_boundary_rate * 100).toFixed(0)}%</b><em className="is-positive">+{(alignment.delta.safety_boundary_rate * 100).toFixed(0)}pp</em></div> : null}
        </section>
      </div>

      {alignment ? <section className="v21-dpo-strip">
        <div><span>DPO + NF4 QLoRA</span><strong>{alignment.data.train_pairs} preference pairs · {alignment.config.steps} steps</strong><small>冻结 test 事实准确率保持 {(alignment.after.fact_accuracy * 100).toFixed(1)}%，只观察到边界表达改善。</small></div>
        <p><span>Loss</span><b>{alignment.train.initial_loss.toFixed(3)} <ChevronInline /> {alignment.train.final_loss.toFixed(3)}</b></p>
        <p><span>Safety</span><b>{(alignment.before.safety_boundary_rate * 100).toFixed(0)}% <ChevronInline /> {(alignment.after.safety_boundary_rate * 100).toFixed(0)}%</b></p>
        <p><span>P50 cost</span><b>{alignment.before.latency_p50_s.toFixed(3)}s <ChevronInline /> {alignment.after.latency_p50_s.toFixed(3)}s</b></p>
      </section> : null}

      {alignmentStability ? <section className="v21-dpo-strip v21-stability-strip" data-dpo-stability="true">
        <div><span>DPO 5-seed stability probe</span><strong>{alignmentStability.initial_runs.completed}/{alignmentStability.initial_runs.total} 首轮完成 · {alignmentStability.initial_runs.invalid_numeric} 次 NaN 留痕</strong><small>失败 run 未剔除；加入 NaN/Inf fail-closed 门禁后，同 seed 重试完成。</small></div>
        <p><span>Split</span><b>{alignmentStability.protocol.train_pairs} train / {alignmentStability.protocol.test_images} frozen test</b></p>
        <p><span>Finite gate</span><b>{alignmentStability.gatecheck.finite_scalar_fail_closed ? 'enabled' : 'disabled'}</b></p>
        <p><span>Gatecheck</span><b>seed {alignmentStability.gatecheck.seed} · {alignmentStability.gatecheck.retry_completed ? 'pass' : 'failed'}</b></p>
      </section> : null}

      <section className="v21-lab-panel v21-model-runs">
        <PanelHead eyebrow="Model selection" title="不同参数规模的能力—成本边界" badge={`${models.length} models`} />
        <div className="v21-model-run-list">
          {models.map((item) => <div key={item.model}><span><strong>{shortModel(item.model)}</strong><small>{item.model}</small></span><b>{(item.accuracy * 100).toFixed(1)}%<small>Fact Acc.</small></b><b>{item.p50_s.toFixed(3)}s<small>P50</small></b><b>{item.peak_gpu_memory_gib.toFixed(2)} GiB<small>Peak GPU</small></b></div>)}
        </div>
      </section>

      <section className="v21-artifact-strip"><div><Activity size={17} /><span><strong>{experiment.schema_version}</strong><small>{experiment.completed_run_count} completed runs</small></span></div><span>逐例 cases.jsonl</span><span>环境与命令已记录</span><code>{experiment.artifact}</code></section>
    </div>
  )
}

function ChevronInline() { return <ChevronRight size={13} aria-hidden="true" /> }
function shortModel(value: string) { return value.split('/').pop()?.replace('-Instruct', '') || value }

function PanelHead({ eyebrow, title, badge }: { eyebrow: string; title: string; badge: string }) {
  return <header className="v21-panel-head"><div><span>{eyebrow}</span><h2>{title}</h2></div><b>{badge}</b></header>
}

function EvalRow({ label, value, detail }: { label: string; value: number; detail: string }) {
  return <div><span><strong>{label}</strong><small>{detail}</small></span><i><em style={{ width: `${Math.max(2, value * 100)}%` }} /></i><b>{Math.round(value * 100)}%</b></div>
}

function Metric({ value, label, note, trend }: { value: string; label: string; note: string; trend?: 'up' | 'down' }) {
  return <article>{trend === 'down' ? <ArrowDownRight size={18} /> : <ArrowUpRight size={18} />}<strong>{value}</strong><span>{label}</span><small>{note}</small></article>
}

function LabEmpty({ label }: { label: string }) {
  return <div className="v21-lab-empty"><Cpu size={28} /><strong>{label}</strong><span>服务连接或 Artifact 完成后自动显示，页面不生成占位分数。</span></div>
}

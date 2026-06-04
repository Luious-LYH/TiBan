import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  ActivitySquare,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  DatabaseZap,
  FileCheck2,
  FileStack,
  Gauge,
  LockKeyhole,
  Route,
  ShieldCheck,
  Terminal,
  UserRound,
} from 'lucide-react'
import { Card, SafetyNotice, SectionTitle, Tag } from '../components/Primitives'
import { api } from '../lib/api'
import { safetyNotice } from '../lib/mock'
import type { DeliveryReport, ReadinessTone } from '../lib/types'

const fallbackToneByStatus: Record<string, ReadinessTone> = {
  ready: 'green',
  synced: 'green',
  audited: 'green',
  provider: 'green',
  rule: 'amber',
  fallback: 'amber',
  not_run: 'blue',
  pending: 'blue',
  blocked: 'red',
}

export function DeliveryEvidence() {
  const [report, setReport] = useState<DeliveryReport | null>(null)
  const [loadState, setLoadState] = useState<'loading' | 'backend' | 'fallback' | 'failed'>('loading')

  useEffect(() => {
    let mounted = true
    api.deliveryReport()
      .then((payload) => {
        if (!mounted) return
        setReport(payload)
        setLoadState(payload.api_source === 'fallback' ? 'fallback' : 'backend')
      })
      .catch(() => {
        if (!mounted) return
        setLoadState('failed')
      })
    return () => {
      mounted = false
    }
  }, [])

  const integrityClean = useMemo(() => {
    if (!report) return false
    const integrity = report.report_integrity
    return loadState === 'backend' && !integrity.writes_state && !integrity.secrets_included && !integrity.api_key_returned && !integrity.provider_base_returned
  }, [loadState, report])

  if (!report) {
    return (
      <div className="page-stack">
        <Card className="delivery-hero">
          <div className="delivery-hero-copy">
            <span className="eyebrow">Delivery evidence</span>
            <h2>{loadState === 'failed' ? '交付证据读取失败' : '交付证据读取中'}</h2>
            <p>{loadState === 'failed' ? '请确认 FastAPI 后端在线后刷新页面。' : '正在读取平台只读证据报告。'}</p>
          </div>
          <FileCheck2 size={44} />
        </Card>
      </div>
    )
  }

  const summary = report.platform_summary
  const doctor = report.doctor_context
  const provider = report.provider_state
  const sourceLabel = loadState === 'fallback' ? 'frontend fallback' : 'backend live'
  const sourceTone = loadState === 'fallback' ? 'amber' : 'green'
  const integrityLabel = loadState === 'fallback'
    ? '前端预览，未验证后端证据包'
    : integrityClean
      ? '只读且无密钥'
      : '完整性待核查'
  const providerMode = safeText(provider.mode)
  const providerModel = safeText(provider.model)
  const providerVerificationTone = provider.real_inference_verified ? 'green' : provider.configured ? 'amber' : 'blue'

  return (
    <div
      className="page-stack"
      data-delivery-loaded="true"
      data-delivery-source={loadState}
      data-delivery-integrity={integrityClean ? 'clean' : loadState === 'fallback' ? 'preview' : 'warning'}
      data-delivery-provider-configured={provider.configured ? 'true' : 'false'}
      data-delivery-provider-real={provider.real_inference_verified ? 'true' : 'false'}
      data-delivery-provider-self-test={provider.self_test_verified ? 'verified' : provider.self_test_logged ? 'logged' : 'not_run'}
      data-delivery-provider-admission={provider.admission_state_kind}
    >
      <Card className={`delivery-hero ${loadState === 'fallback' ? 'fallback' : 'live'}`}>
        <div className="delivery-hero-copy">
          <span className="eyebrow">Delivery evidence</span>
          <h2>{safeText(report.title)}</h2>
          <p>{safeText(report.scope)}</p>
          <div className="delivery-hero-tags">
            <Tag tone={sourceTone}>{sourceLabel}</Tag>
            <Tag tone={integrityClean ? 'green' : loadState === 'fallback' ? 'amber' : 'red'}>{integrityLabel}</Tag>
            <Tag tone={summary.provider_ready ? 'amber' : 'blue'}>{summary.provider_ready ? 'provider configured' : `${safeText(summary.provider_mode)} mode`}</Tag>
            <Tag tone={providerVerificationTone}>{safeText(provider.verification_label)}</Tag>
          </div>
        </div>
        <div className="delivery-score">
          <strong>{summary.overall_score}%</strong>
          <span>平台就绪度</span>
          <em>{new Date(report.generated_at).toLocaleString()}</em>
        </div>
      </Card>

      <div className="delivery-summary-grid">
        <Metric icon={<UserRound size={19} />} label="训练对象" value={safeText(doctor.name)} detail={`${safeText(doctor.title)} · ${safeText(doctor.department)}`} tone="blue" />
        <Metric icon={<DatabaseZap size={19} />} label="公开图文样例" value={`${summary.real_sample_count} 条`} detail={`${summary.qbank_count} 题 · ${summary.report_template_count} 模板`} />
        <Metric icon={<ClipboardList size={19} />} label="训练留痕" value={`${summary.audit_log_count} 条审计`} detail={`${summary.exam_session_count} 个考试 Session`} tone="green" />
        <Metric icon={<Gauge size={19} />} label="模型准入" value={`Grade ${safeText(summary.admission_grade)}`} detail={summary.admission_provider_called ? 'provider called' : 'rule / not called'} tone={summary.admission_provider_called ? 'green' : 'amber'} />
      </div>

      <Card className="delivery-doctor-card">
        <SectionTitle eyebrow="Physician context" title="当前医师训练对象" action={<Tag tone="blue">{safeText(doctor.learner_id)}</Tag>} />
        <div className="delivery-doctor-grid">
          <div>
            <span>姓名与阶段</span>
            <strong>{safeText(doctor.name)}</strong>
            <em>{safeText(doctor.training_stage)}</em>
          </div>
          <div>
            <span>今日训练</span>
            <strong>{doctor.completed_today}/{doctor.daily_target}</strong>
            <em>连续 {doctor.streak_days} 天</em>
          </div>
          <div>
            <span>部门</span>
            <strong>{safeText(doctor.department)}</strong>
            <em>{safeText(doctor.hospital || '教学演示医院')}</em>
          </div>
        </div>
      </Card>

      <Card>
        <SectionTitle eyebrow="Workflow proofs" title="核心闭环证据" action={<Route size={20} />} />
        <div className="delivery-proof-grid">
          {report.workflow_proofs.map((item) => (
            <Link className="delivery-proof-card" key={item.id} to={safeRoute(item.route)}>
              <span className={`status-dot tone-${toneForStatus(item.status)}`} />
              <div>
                <strong>{safeText(item.name)}</strong>
                <em>{safeText(item.status)}</em>
                <p>{safeText(item.evidence)}</p>
              </div>
              <ArrowRight size={16} />
            </Link>
          ))}
        </div>
      </Card>

      <div className="grid two">
        <Card className="delivery-chain-card">
          <SectionTitle eyebrow="Knowledge chain" title="真实数据与知识库来源" action={<FileStack size={20} />} />
          <div className="delivery-knowledge-list">
            {report.knowledge_source_chain.map((item) => (
              <Link className="delivery-knowledge-item" key={item.id} to={safeRoute(item.href)}>
                <span className={`status-dot tone-${item.tone}`} />
                <div>
                  <strong>{safeText(item.label)}</strong>
                  <em>{safeText(item.source_file)} · {item.record_count} 条</em>
                  <p>{safeText(item.proof)}</p>
                  <div className="knowledge-chain-tags">
                    {item.sample_ids.slice(0, 3).map((sampleId) => <span key={`${item.id}_${sampleId}`}>{safeText(sampleId)}</span>)}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </Card>

        <Card className="delivery-receipt-card">
          <SectionTitle eyebrow="Receipts" title="模块收据" action={<ShieldCheck size={20} />} />
          <div className="delivery-receipt-list">
            {report.evidence_receipts.map((item) => (
              <Link className="delivery-receipt-item" key={item.id} to={safeRoute(item.href)}>
                <span className={`status-dot tone-${item.tone}`} />
                <div>
                  <strong>{safeText(item.label)}</strong>
                  <em>{safeText(item.status)}</em>
                  <p>{safeText(item.detail)}</p>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid two">
        <Card>
          <SectionTitle eyebrow="Audit events" title="审计事件分布" action={<ActivitySquare size={20} />} />
          <div className="delivery-audit-grid">
            {report.audit_event_counts.map((item) => (
              <div key={item.event_type}>
                <span>{safeText(eventLabel(item.event_type))}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </Card>

        <Card className={`delivery-provider-card ${provider.real_inference_verified ? 'verified' : provider.configured ? 'configured' : 'rule'}`}>
          <SectionTitle eyebrow="Provider state" title="推理通道状态" action={<Gauge size={20} />} />
          <div className="delivery-provider-banner">
            <strong>{safeText(provider.verification_label)}</strong>
            <span>{safeText(provider.verification_note)}</span>
          </div>
          <div className="delivery-provider-grid">
            <div>
              <span>Mode</span>
              <strong>{providerMode}</strong>
            </div>
            <div>
              <span>Model</span>
              <strong>{providerModel}</strong>
            </div>
            <div>
              <span>Configured</span>
              <strong>{provider.configured ? 'yes' : 'no'}</strong>
            </div>
            <div>
              <span>Self-test</span>
              <strong>{provider.self_test_verified ? 'verified' : provider.self_test_logged ? `${provider.self_test_count} logged` : 'not run'}</strong>
            </div>
            <div>
              <span>Admission call</span>
              <strong>{provider.admission_provider_called ? 'provider called' : safeText(provider.admission_state_kind)}</strong>
            </div>
            <div>
              <span>Training gate</span>
              <strong>{provider.admission_safe_for_training ? 'safe for training' : 'doctor review'}</strong>
            </div>
          </div>
          <p className="delivery-provider-note">
            {provider.real_inference_verified
              ? '该状态来自 Provider 自检成功或样例级准入调用；密钥和 base URL 不会返回到前端证据报告。'
              : provider.configured
                ? 'Provider 已配置只代表后端具备调用条件；未出现自检成功或样例准入调用前，不展示为真实推理已验证。'
                : provider.provider_declared
                  ? 'Provider 名称已声明，但密钥和 base URL 不会返回到前端证据报告。'
                  : '当前未声明真实 Provider；页面必须显式显示 rule/fallback 状态。'}
          </p>
        </Card>
      </div>

      <div className="grid two">
        <Card className={`delivery-integrity-card ${integrityClean ? 'clean' : 'warning'}`}>
          <SectionTitle eyebrow="Report integrity" title="只读完整性" action={<LockKeyhole size={20} />} />
          <div className="delivery-integrity-grid">
            <IntegrityItem label="来源" value={safeText(report.report_integrity.source)} ok />
            <IntegrityItem label="写入状态" value={report.report_integrity.writes_state ? 'yes' : 'no'} ok={!report.report_integrity.writes_state} />
            <IntegrityItem label="包含密钥" value={report.report_integrity.secrets_included ? 'yes' : 'no'} ok={!report.report_integrity.secrets_included} />
            <IntegrityItem label="返回 API Key" value={report.report_integrity.api_key_returned ? 'yes' : 'no'} ok={!report.report_integrity.api_key_returned} />
            <IntegrityItem label="返回 Base URL" value={report.report_integrity.provider_base_returned ? 'yes' : 'no'} ok={!report.report_integrity.provider_base_returned} />
          </div>
        </Card>

        <Card>
          <SectionTitle eyebrow="Verification" title="验收命令" action={<Terminal size={20} />} />
          <div className="delivery-command-list">
            {report.verification_commands.map((item) => (
              <div key={item.command}>
                <strong>{safeText(item.name)}</strong>
                <code>{safeText(item.command)}</code>
                <span>{safeText(item.covers)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="delivery-boundary-card">
        <SectionTitle eyebrow="Boundaries & gaps" title="安全边界与剩余缺口" action={<AlertTriangle size={20} />} />
        <div className="delivery-boundary-grid">
          <div>
            <strong>当前边界</strong>
            {report.current_boundaries.map((item) => (
              <p key={item}>
                <CheckCircle2 size={15} />
                <span>{safeText(item)}</span>
              </p>
            ))}
          </div>
          <div>
            <strong>后续缺口</strong>
            {report.gaps.map((item) => (
              <p key={item}>
                <AlertTriangle size={15} />
                <span>{safeText(item)}</span>
              </p>
            ))}
          </div>
        </div>
      </Card>

      <SafetyNotice text={safeText(report.safety_notice || safetyNotice)} />
    </div>
  )
}

function Metric({
  icon,
  label,
  value,
  detail,
  tone = 'green',
}: {
  icon: ReactNode
  label: string
  value: string
  detail: string
  tone?: 'green' | 'amber' | 'red' | 'blue'
}) {
  return (
    <Card className={`delivery-metric delivery-metric-${tone}`}>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </Card>
  )
}

function IntegrityItem({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className={ok ? 'ok' : 'warning'}>
      {ok ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function toneForStatus(status: string): ReadinessTone {
  return fallbackToneByStatus[status] || fallbackToneByStatus[status.toLowerCase()] || 'blue'
}

function eventLabel(type: string): string {
  const labels: Record<string, string> = {
    question_view: '查看题目',
    answer_submit: '提交答案',
    tutor_reply: 'Agent 辅导',
    challenge_benchmark: '医生 vs AI',
    exam_session: '考试 Session',
    report_draft: '报告生成',
    report_judge: '报告评分',
    patient_card: '科普卡片',
    patient_card_approve: '卡片审核',
    provider_self_test: 'Provider 自检',
    model_admission: '模型准入',
    skill_run: 'Skill 调用',
    demo_check: '演示自检',
  }
  return labels[type] || type
}

function sanitizePublicText(value: string): string {
  return value
    .replace(/sk-[A-Za-z0-9_-]{8,}/g, 'sk-****')
    .replace(/Bearer\s+[A-Za-z0-9._~+/=-]+/gi, 'Bearer ****')
    .replace(/(api[_-]?key|key|token|secret)\s*[:=]\s*[^,\s;]+/gi, '$1=****')
    .replace(/(base[_-]?url|api[_-]?base)\s*[:=]\s*https?:\/\/[^,\s;]+/gi, '$1=****')
    .replace(/https?:\/\/[^\s,;]+/gi, '[url-hidden]')
}

function safeText(value: string | number | boolean | null | undefined): string {
  return sanitizePublicText(String(value ?? ''))
}

function safeRoute(value: string | null | undefined): string {
  const route = value || '/'
  if (!route.startsWith('/') || route.startsWith('//')) return '/'
  return sanitizePublicText(route)
}

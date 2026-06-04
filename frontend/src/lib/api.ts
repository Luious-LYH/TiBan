import {
  mockAuditLogs,
  mockDashboard,
  mockModels,
  mockQuestions,
  mockSkills,
  safetyNotice,
} from './mock'
import type {
  AtomicFact,
  AuditLog,
  ChallengeBenchmarkResult,
  DashboardPayload,
  DemoCheckResult,
  DeliveryAuditEventCount,
  DeliveryDoctorContext,
  DeliveryPlatformSummary,
  DeliveryProviderState,
  DeliveryReport,
  DeliveryReportIntegrity,
  DeliveryVerificationCommand,
  DeliveryWorkflowProof,
  ExamSessionAttempt,
  ExamSessionRecord,
  ExamSessionResponse,
  ImageUploadResponse,
  KnowledgeSourceChainItem,
  LatestExamReplay,
  KnowledgeBase,
  LearnerProfile,
  ModelAdmissionResult,
  ModelAdmissionState,
  ModelProfile,
  PatientCard,
  RealSampleCoverage,
  ProviderAuditSummary,
  ProviderDiagnostics,
  ProviderEvidenceReceipt,
  ProviderPreflight,
  ProviderRequestPreview,
  PlatformReadiness,
  PlatformReadinessModule,
  ProviderSelfTestResult,
  ProviderStatus,
  Question,
  ReportJudge,
  ReportDraft,
  SkillDefinition,
  SkillRunPayload,
  SubmissionResponse,
  SourceTraceItem,
  TrainingState,
  TutorChatResponse,
} from './types'

const configuredApiBase = import.meta.env.VITE_API_BASE_URL as string | undefined
const apiBaseCandidates = configuredApiBase
  ? [configuredApiBase]
  : ['http://127.0.0.1:8000', 'http://127.0.0.1:8001']
const publicDatasets = new Set(['Kvasir-VQA-x1', 'Kvasir-VQA', 'EndoBench'])
const requiredApiCapabilities = [
  'provider_self_test',
  'provider_visual_self_test',
  'provider_self_test_receipt',
  'provider_diagnostics',
  'provider_evidence_ladder',
  'provider_preflight',
  'provider_request_preview',
  'report_upload_receipt',
  'model_admission_receipt',
  'knowledge_source_chain',
  'real_sample_coverage',
  'demo_check_sandbox',
  'demo_check_restore_verified',
  'demo_check_exam_card_receipt',
  'challenge_benchmark',
  'challenge_audit_receipt',
  'patient_card_generation_receipt',
  'patient_card_approve',
  'skill_run_receipt',
  'delivery_report',
]
let activeApiBase = apiBaseCandidates[0]
let apiBaseProbe: Promise<boolean> | null = null

type ApiSource = 'backend' | 'fallback'
type RequestTimeoutProfile = 'probe' | 'status' | 'standard' | 'provider'

const requestTimeoutMs: Record<RequestTimeoutProfile, number> = {
  probe: 1800,
  status: 5000,
  standard: 12000,
  provider: 95000,
}

function markSource<T extends object>(payload: T, source: ApiSource): T {
  return { ...payload, api_source: source }
}

class ApiRequestError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.status = status
  }
}

function shouldTryNextApiBase(error: unknown): boolean {
  if (configuredApiBase) return false
  if (error instanceof TypeError) return true
  if (isAbortError(error)) return true
  if (error instanceof ApiRequestError) return error.status === 404 || error.status === 405
  return false
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function timeoutProfileFor(path: string, init?: RequestInit): RequestTimeoutProfile {
  if (path === '/api/health' || path.endsWith('/api/health')) return 'probe'
  if (
    path.includes('/provider/status') ||
    path.includes('/provider/diagnostics') ||
    path.includes('/models/admission-state') ||
    path.includes('/platform/readiness')
  ) {
    return 'status'
  }
  const method = init?.method?.toUpperCase() || 'GET'
  if (
    method !== 'GET' &&
    (
      path.includes('/provider/self-test') ||
      path.includes('/models/admission-test') ||
      path.includes('/report-draft') ||
      path.includes('/report/judge') ||
      path.includes('/tutor/chat') ||
      path.includes('/tutor/challenge-benchmark') ||
      path.includes('/patient-card')
    )
  ) {
    return 'provider'
  }
  return method === 'GET' ? 'status' : 'standard'
}

async function fetchWithTimeout(input: string, init: RequestInit | undefined, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } finally {
    window.clearTimeout(timer)
  }
}

function orderedApiBaseCandidates(): string[] {
  return [activeApiBase, ...apiBaseCandidates.filter((base) => base !== activeApiBase)]
}

async function ensureCapableApiBase(): Promise<void> {
  if (configuredApiBase) return
  apiBaseProbe ??= probeApiBases()
  const foundCapableApi = await apiBaseProbe
  if (!foundCapableApi) apiBaseProbe = null
}

async function probeApiBases(): Promise<boolean> {
  for (const apiBase of apiBaseCandidates) {
    try {
      const response = await fetchWithTimeout(
        `${apiBase}/api/health`,
        { headers: { 'Content-Type': 'application/json' } },
        requestTimeoutMs.probe,
      )
      if (!response.ok) continue
      const health = asRecord(await response.json())
      const capabilities = asStringArray(health.capabilities)
      if (requiredApiCapabilities.every((capability) => capabilities.includes(capability))) {
        activeApiBase = apiBase
        return true
      }
    } catch {
      // Keep probing the next candidate; request() still has its own fallback path.
    }
  }
  return false
}

async function request<T extends object>(path: string, init?: RequestInit, fallback?: T): Promise<T> {
  await ensureCapableApiBase()
  let lastError: unknown
  const timeoutMs = requestTimeoutMs[timeoutProfileFor(path, init)]
  for (const apiBase of orderedApiBaseCandidates()) {
    try {
      const response = await fetchWithTimeout(
        `${apiBase}${path}`,
        {
          ...init,
          headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
        },
        timeoutMs,
      )
      if (!response.ok) {
        let detail = ''
        try {
          detail = asString(asRecord(await response.json()).detail)
        } catch {
          detail = ''
        }
        throw new ApiRequestError(detail ? `${response.status} ${response.statusText}: ${detail}` : `${response.status} ${response.statusText}`, response.status)
      }
      activeApiBase = apiBase
      return markSource((await response.json()) as T, 'backend')
    } catch (error) {
      lastError = error
      if (!shouldTryNextApiBase(error)) break
    }
  }
  if (fallback !== undefined) {
    return markSource(fallback, 'fallback')
  }
  throw lastError
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : fallback
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function asStringArray(value: unknown, fallback: string[] = []): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : fallback
}

function asNumberRecord(value: unknown, fallback: Record<string, number> = {}): Record<string, number> {
  const record = asRecord(value)
  const merged = { ...fallback }
  Object.entries(record).forEach(([key, item]) => {
    const numberValue = Number(item)
    if (Number.isFinite(numberValue)) merged[key] = numberValue
  })
  return merged
}

function normalizeProviderStatus(value: unknown, fallback: ProviderStatus = {
  provider: 'mock',
  model: 'unconfigured',
  mode: 'rule',
  ok: false,
  error: 'provider_not_configured',
}): ProviderStatus {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    provider: asString(record.provider, fallback.provider),
    model: asString(record.model, fallback.model),
    mode: asString(record.mode, fallback.mode),
    ok: typeof record.ok === 'boolean' ? record.ok : fallback.ok,
    error: typeof record.error === 'string' || record.error === null ? record.error : fallback.error,
    latency_ms: record.latency_ms === null ? null : asNumber(record.latency_ms, fallback.latency_ms ?? 0),
    sample_count: asNumber(record.sample_count, fallback.sample_count ?? 0),
    provider_success_count: asNumber(record.provider_success_count, fallback.provider_success_count ?? 0),
    reference_aligned_count: asNumber(record.reference_aligned_count, fallback.reference_aligned_count ?? 0),
    blind_probe: asBoolean(record.blind_probe, fallback.blind_probe ?? false),
    image_attached: asBoolean(record.image_attached, fallback.image_attached ?? false),
    configured: typeof record.configured === 'boolean' ? record.configured : fallback.configured,
    base_url_configured: typeof record.base_url_configured === 'boolean' ? record.base_url_configured : fallback.base_url_configured,
    api_key_configured: typeof record.api_key_configured === 'boolean' ? record.api_key_configured : fallback.api_key_configured,
    private_host_allowlist_configured: asBoolean(record.private_host_allowlist_configured, fallback.private_host_allowlist_configured ?? false),
    private_host_allowlist_count: asNumber(record.private_host_allowlist_count, fallback.private_host_allowlist_count ?? 0),
    safety_notice: asString(record.safety_notice, fallback.safety_notice || ''),
  }
}

function normalizeProviderAuditSummary(value: unknown): ProviderAuditSummary | null {
  const record = asRecord(value)
  if (!Object.keys(record).length) return null
  return {
    id: typeof record.id === 'string' || record.id === null ? record.id : null,
    event_type: typeof record.event_type === 'string' || record.event_type === null ? record.event_type : null,
    summary: typeof record.summary === 'string' || record.summary === null ? record.summary : null,
    risk_level: typeof record.risk_level === 'string' || record.risk_level === null ? record.risk_level : null,
    created_at: typeof record.created_at === 'string' || record.created_at === null ? record.created_at : null,
  }
}

function normalizeProviderDiagnostics(value: unknown, fallback: ProviderDiagnostics): ProviderDiagnostics {
  const record = asRecord(value)
  const state = asRecord(record.admission_state)
  const evidenceLadder = Array.isArray(record.evidence_ladder)
    ? record.evidence_ladder.map((item) => {
        const step = asRecord(item)
        return {
          id: asString(step.id, 'provider_step'),
          label: asString(step.label, '证据步骤'),
          state: asString(step.state, 'pending'),
          evidence: asString(step.evidence, ''),
          action: asString(step.action, ''),
          href: asString(step.href, '/models'),
          proof_kind: asString(step.proof_kind, 'status'),
        }
      })
    : fallback.evidence_ladder
  return {
    ...fallback,
    ...record,
    ready_level: asString(record.ready_level, fallback.ready_level),
    provider_configured: asBoolean(record.provider_configured, fallback.provider_configured),
    provider_mode: asString(record.provider_mode, fallback.provider_mode),
    provider: asString(record.provider, fallback.provider),
    model: asString(record.model, fallback.model),
    base_url_configured: asBoolean(record.base_url_configured, fallback.base_url_configured),
    api_key_configured: asBoolean(record.api_key_configured, fallback.api_key_configured),
    private_host_allowlist_configured: asBoolean(record.private_host_allowlist_configured, fallback.private_host_allowlist_configured),
    private_host_allowlist_count: asNumber(record.private_host_allowlist_count, fallback.private_host_allowlist_count),
    missing: asStringArray(record.missing, fallback.missing),
    public_sample_count: asNumber(record.public_sample_count, fallback.public_sample_count),
    latest_self_test: normalizeProviderAuditSummary(record.latest_self_test) || fallback.latest_self_test,
    latest_admission: normalizeProviderAuditSummary(record.latest_admission) || fallback.latest_admission,
    evidence_ladder: evidenceLadder,
    admission_state: {
      provider_name: asString(state.provider_name, fallback.admission_state.provider_name),
      grade: asString(state.grade, fallback.admission_state.grade),
      total_score: asNumber(state.total_score, fallback.admission_state.total_score),
      provider_called: asBoolean(state.provider_called, fallback.admission_state.provider_called),
      safe_for_training: asBoolean(state.safe_for_training, fallback.admission_state.safe_for_training),
      recommendation: asString(state.recommendation, fallback.admission_state.recommendation),
    },
    blocking_reason: asString(record.blocking_reason, fallback.blocking_reason),
    next_actions: Array.isArray(record.next_actions)
      ? record.next_actions.map((item) => {
          const action = asRecord(item)
          return {
            label: asString(action.label, '下一步'),
            detail: asString(action.detail, ''),
            href: asString(action.href, '/models'),
            done: asBoolean(action.done, false),
          }
        })
      : fallback.next_actions,
    privacy_notice: asString(record.privacy_notice, fallback.privacy_notice),
    safety_notice: asString(record.safety_notice, fallback.safety_notice),
    created_at: asString(record.created_at, fallback.created_at),
    api_source: record.api_source as ApiSource | undefined,
  }
}

function normalizeProviderPreflight(value: unknown, fallback: ProviderPreflight): ProviderPreflight {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    ok: asBoolean(record.ok, fallback.ok),
    safety_status: asString(record.safety_status, fallback.safety_status),
    mode: asString(record.mode, fallback.mode),
    normalized_preview: typeof record.normalized_preview === 'string' || record.normalized_preview === null
      ? record.normalized_preview
      : fallback.normalized_preview,
    endpoint_paths: asStringArray(record.endpoint_paths, fallback.endpoint_paths),
    blocked_reason: typeof record.blocked_reason === 'string' || record.blocked_reason === null
      ? record.blocked_reason
      : fallback.blocked_reason,
    warnings: asStringArray(record.warnings, fallback.warnings),
    next_actions: asStringArray(record.next_actions, fallback.next_actions),
    private_host_allowlist_configured: asBoolean(record.private_host_allowlist_configured, fallback.private_host_allowlist_configured),
    private_host_allowlist_used: asBoolean(record.private_host_allowlist_used, fallback.private_host_allowlist_used),
    key_required_for_call: asBoolean(record.key_required_for_call, fallback.key_required_for_call),
    request_sent: asBoolean(record.request_sent, fallback.request_sent),
    key_persisted: asBoolean(record.key_persisted, fallback.key_persisted),
    safety_notice: asString(record.safety_notice, fallback.safety_notice),
    api_source: record.api_source as ApiSource | undefined,
  }
}

function normalizeProviderRequestPreview(value: unknown, fallback: ProviderRequestPreview): ProviderRequestPreview {
  const record = asRecord(value)
  const normalizeMessagePlan = (items: unknown) => Array.isArray(items)
    ? items.map((item) => {
        const entry = asRecord(item)
        return {
          role: asString(entry.role, 'user'),
          contains: asString(entry.contains, ''),
          image: asBoolean(entry.image, false),
          sample_ids: asStringArray(entry.sample_ids, []),
        }
      })
    : fallback.message_plan
  const normalizeSamples = (items: unknown) => Array.isArray(items)
    ? items.map((item) => {
        const entry = asRecord(item)
        return {
          id: asString(entry.id, ''),
          source_dataset: asString(entry.source_dataset, ''),
          image_url: asString(entry.image_url, ''),
          question_preview: asString(entry.question_preview, ''),
          image_attached: asBoolean(entry.image_attached, false),
          reference_answer_sent: asBoolean(entry.reference_answer_sent, false),
          local_asset_required: asBoolean(entry.local_asset_required, false),
        }
      })
    : fallback.selected_samples
  const normalizePrivacy = (items: unknown) => Array.isArray(items)
    ? items.map((item) => {
        const entry = asRecord(item)
        return {
          label: asString(entry.label, '隐私边界'),
          used: asBoolean(entry.used, false),
          detail: asString(entry.detail, ''),
        }
      })
    : fallback.privacy_trace
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    provider_name: asString(record.provider_name, fallback.provider_name),
    preview_mode: asString(record.preview_mode, fallback.preview_mode) as ProviderRequestPreview['preview_mode'],
    ready_for_provider_call: asBoolean(record.ready_for_provider_call, fallback.ready_for_provider_call),
    blocked_reason: typeof record.blocked_reason === 'string' || record.blocked_reason === null ? record.blocked_reason : fallback.blocked_reason,
    preflight_mode: asString(record.preflight_mode, fallback.preflight_mode),
    safety_status: asString(record.safety_status, fallback.safety_status),
    normalized_preview: typeof record.normalized_preview === 'string' || record.normalized_preview === null ? record.normalized_preview : fallback.normalized_preview,
    endpoint_paths: asStringArray(record.endpoint_paths, fallback.endpoint_paths),
    request_body_fields: asStringArray(record.request_body_fields, fallback.request_body_fields),
    message_plan: normalizeMessagePlan(record.message_plan),
    selected_samples: normalizeSamples(record.selected_samples),
    sample_count: asNumber(record.sample_count, fallback.sample_count),
    image_attachment_count: asNumber(record.image_attachment_count, fallback.image_attachment_count),
    api_key_present: asBoolean(record.api_key_present, fallback.api_key_present),
    backend_env_key_available: asBoolean(record.backend_env_key_available, fallback.backend_env_key_available),
    request_sent: asBoolean(record.request_sent, fallback.request_sent),
    key_persisted: asBoolean(record.key_persisted, fallback.key_persisted),
    audit_logged: asBoolean(record.audit_logged, fallback.audit_logged),
    state_updated: asBoolean(record.state_updated, fallback.state_updated),
    reference_answer_sent: asBoolean(record.reference_answer_sent, fallback.reference_answer_sent),
    full_response_persisted: asBoolean(record.full_response_persisted, fallback.full_response_persisted),
    privacy_trace: normalizePrivacy(record.privacy_trace),
    next_actions: asStringArray(record.next_actions, fallback.next_actions),
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
    api_source: record.api_source as ApiSource | undefined,
  }
}

function normalizeSourceTrace(value: unknown, fallback: SourceTraceItem[] = []): SourceTraceItem[] {
  if (!Array.isArray(value)) return fallback
  return value.map((item, index) => {
    const record = asRecord(item)
    return {
      source_type: asString(record.source_type, `source_${index}`),
      label: asString(record.label, '来源'),
      used: asBoolean(record.used, false),
      detail: asString(record.detail, ''),
      latency_ms: record.latency_ms === null ? null : asNumber(record.latency_ms, 0),
    }
  })
}

function normalizeAtomicFact(value: unknown, fallback: AtomicFact, index: number): AtomicFact {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id || `fact_${index}`),
    fact: asString(record.fact, fallback.fact),
    expected: asString(record.expected, fallback.expected),
    supported: asBoolean(record.supported, fallback.supported),
    evidence: asString(record.evidence, fallback.evidence),
    skill_dimension: asString(record.skill_dimension, fallback.skill_dimension) as AtomicFact['skill_dimension'],
  }
}

function fallbackSkillInputTrace(payload: SkillRunPayload) {
  const trace: { source_type: string; label: string; used: boolean; detail: string }[] = []
  if (payload.question_id) {
    trace.push({ source_type: 'question_context', label: '训练题上下文', used: true, detail: String(payload.question_id) })
  }
  if (payload.selected_answer) {
    trace.push({ source_type: 'doctor_answer', label: '医师作答', used: true, detail: '已接收作答内容；仅记录来源类型。' })
  }
  if (payload.finding_text) {
    trace.push({ source_type: 'report_text', label: '报告所见文本', used: true, detail: '已接收报告训练文本；收据不保存全文。' })
  }
  if (payload.diagnosis_summary) {
    trace.push({ source_type: 'card_summary', label: '卡片摘要', used: true, detail: '已接收患者沟通摘要；收据不保存全文。' })
  }
  if (payload.text) {
    trace.push({ source_type: 'safety_text', label: '安全审查文本', used: true, detail: '已接收安全审查文本；收据不保存全文。' })
  }
  if (payload.event_type || payload.summary) {
    trace.push({ source_type: 'audit_summary', label: '审计摘要输入', used: true, detail: '已接收审计摘要或事件类型；收据不保存自由文本全文。' })
  }
  if (payload.learner_id) {
    trace.push({ source_type: 'learner_context', label: '医师画像上下文', used: true, detail: String(payload.learner_id) })
  }
  return trace.length ? trace : [{ source_type: 'platform_context', label: '平台默认上下文', used: true, detail: '使用当前 demo learner 与默认样例上下文。' }]
}

function fallbackSkillNextActions(category: SkillDefinition['category']) {
  const actionMap: Record<SkillDefinition['category'], { label: string; href: string }[]> = {
    training: [{ label: '继续题库训练', href: '/training' }],
    feedback: [{ label: '查看错因复盘', href: '/feedback' }],
    report: [{ label: '进入报告训练', href: '/report' }],
    card: [{ label: '进入科普卡片审核', href: '/card' }],
    safety: [{ label: '进入错误前提训练', href: '/false-premise' }],
    audit: [{ label: '查看审计日志', href: '/audit' }],
  }
  return actionMap[category]
}

function normalizeQuestion(value: unknown, fallback: Question = mockQuestions[0], index = 0): Question {
  const record = asRecord(value)
  const fallbackFacts = fallback.atomic_trace.length ? fallback.atomic_trace : mockQuestions[0].atomic_trace
  const facts = Array.isArray(record.atomic_trace) ? record.atomic_trace : fallbackFacts
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id || `question_${index}`),
    title: asString(record.title, fallback.title),
    image_url: typeof record.image_url === 'string' ? record.image_url : fallback.image_url,
    image_placeholder: asString(record.image_placeholder, fallback.image_placeholder),
    case_summary: asString(record.case_summary, fallback.case_summary),
    question: asString(record.question, fallback.question),
    options: asStringArray(record.options, fallback.options),
    answer: asString(record.answer, fallback.answer),
    explanation: asString(record.explanation, fallback.explanation),
    complexity: asNumber(record.complexity, fallback.complexity) as Question['complexity'],
    question_class: asString(record.question_class, fallback.question_class) as Question['question_class'],
    source_type: asString(record.source_type, fallback.source_type) as Question['source_type'],
    atomic_trace: facts.map((fact, factIndex) => normalizeAtomicFact(fact, fallbackFacts[factIndex] || fallbackFacts[0], factIndex)),
    false_premise_flag: asBoolean(record.false_premise_flag, fallback.false_premise_flag),
    teaching_tags: asStringArray(record.teaching_tags, fallback.teaching_tags),
    difficulty: asString(record.difficulty, fallback.difficulty) as Question['difficulty'],
    doctor_review_required: asBoolean(record.doctor_review_required, fallback.doctor_review_required),
    safety_notice: asString(record.safety_notice, fallback.safety_notice || safetyNotice),
    body_part: asString(record.body_part, fallback.body_part),
    task: asString(record.task, fallback.task),
    question_type: asString(record.question_type, fallback.question_type) as Question['question_type'],
    source_dataset: asString(record.source_dataset, fallback.source_dataset),
    citation_note: asString(record.citation_note, fallback.citation_note),
    is_favorited: asBoolean(record.is_favorited, fallback.is_favorited),
    review_status: asString(record.review_status, fallback.review_status) as Question['review_status'],
    ai_benchmark_answer: typeof record.ai_benchmark_answer === 'string' ? record.ai_benchmark_answer : fallback.ai_benchmark_answer,
    expected_keywords: asStringArray(record.expected_keywords, fallback.expected_keywords),
  }
}

function publicFirst(items: Question[]): Question[] {
  return [...items].sort((left, right) => {
    const leftRank = publicDatasets.has(left.source_dataset) ? 0 : 1
    const rightRank = publicDatasets.has(right.source_dataset) ? 0 : 1
    return leftRank - rightRank
  })
}

function normalizeQuestions(value: unknown, fallback: Question[] = mockQuestions): Question[] {
  const source = Array.isArray(value) ? value : fallback
  return publicFirst(source.map((item, index) => normalizeQuestion(item, fallback[index] || fallback[0], index)))
}

function normalizeTrend(value: unknown, fallback: LearnerProfile['growth_trend']): LearnerProfile['growth_trend'] {
  if (!Array.isArray(value)) return fallback
  return value.map((item) => {
    const record = asRecord(item)
    return {
      date: asString(record.date, 'NA'),
      accuracy: asNumber(record.accuracy, 0),
      evidence: asNumber(record.evidence, 0),
      report: asNumber(record.report, 0),
    }
  })
}

function normalizeTrainingRecords(value: unknown, fallback: LearnerProfile['training_records']): LearnerProfile['training_records'] {
  if (!Array.isArray(value)) return fallback
  return value.map((item, index) => {
    const record = asRecord(item)
    return {
      date: asString(record.date, new Date().toISOString().slice(0, 10)),
      question_id: asString(record.question_id, `record_${index}`),
      score: asNumber(record.score, 0),
      result: asString(record.result, '待复盘'),
    }
  })
}

function normalizeExamSessions(value: unknown, fallback: ExamSessionRecord[] = []): ExamSessionRecord[] {
  if (!Array.isArray(value)) return fallback
  return value.map((item, index) => {
    const record = asRecord(item)
    return {
      id: asString(record.id, `exam_session_${index}`),
      session_id: asString(record.session_id, asString(record.question_id, `exam_${index}`)),
      date: asString(record.date, asString(record.created_at, new Date().toISOString()).slice(0, 10)),
      answered_count: asNumber(record.answered_count, 0),
      correct_count: asNumber(record.correct_count, 0),
      accuracy: asNumber(record.accuracy, 0),
      average_score: asNumber(record.average_score, 0),
      wrong_questions: asStringArray(record.wrong_questions),
      elapsed_seconds: asNumber(record.elapsed_seconds, 0),
      finished_reason: asString(record.finished_reason, 'manual_submit'),
      profile_updated: asBoolean(record.profile_updated, false),
      created_at: asString(record.created_at, new Date().toISOString()),
    }
  })
}

function normalizeProfile(value: unknown, fallback: LearnerProfile = mockDashboard.learner_profile): LearnerProfile {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    learner_id: asString(record.learner_id, fallback.learner_id),
    name: asString(record.name, fallback.name),
    title: asString(record.title, fallback.title),
    department: asString(record.department, fallback.department),
    hospital: asString(record.hospital, fallback.hospital),
    training_stage: asString(record.training_stage, fallback.training_stage),
    training_goal: asString(record.training_goal, fallback.training_goal),
    total_questions: asNumber(record.total_questions, fallback.total_questions),
    accuracy: asNumber(record.accuracy, fallback.accuracy),
    completed_today: asNumber(record.completed_today, fallback.completed_today),
    daily_target: Math.max(1, asNumber(record.daily_target, fallback.daily_target)),
    streak_days: asNumber(record.streak_days, fallback.streak_days),
    favorite_questions: asStringArray(record.favorite_questions, fallback.favorite_questions),
    wrong_questions: asStringArray(record.wrong_questions, fallback.wrong_questions),
    skill_scores: asNumberRecord(record.skill_scores, fallback.skill_scores),
    weakness_tags: asStringArray(record.weakness_tags, fallback.weakness_tags),
    recent_errors: asStringArray(record.recent_errors, fallback.recent_errors),
    recommended_question_classes: asStringArray(record.recommended_question_classes, fallback.recommended_question_classes),
    growth_trend: normalizeTrend(record.growth_trend, fallback.growth_trend),
    training_records: normalizeTrainingRecords(record.training_records, fallback.training_records),
    exam_sessions: normalizeExamSessions(record.exam_sessions, fallback.exam_sessions),
    question_type_coverage: asNumberRecord(record.question_type_coverage, fallback.question_type_coverage),
    updated_at: asString(record.updated_at, fallback.updated_at),
  }
}

function normalizeModel(value: unknown, fallback: ModelProfile = mockModels[0]): ModelProfile {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    name: asString(record.name, fallback.name),
    provider_type: asString(record.provider_type, fallback.provider_type) as ModelProfile['provider_type'],
    model_family: asString(record.model_family, fallback.model_family) as ModelProfile['model_family'],
    recommended_roles: asStringArray(record.recommended_roles, fallback.recommended_roles),
    risk_tags: asStringArray(record.risk_tags, fallback.risk_tags),
    ability_scores: asNumberRecord(record.ability_scores, fallback.ability_scores),
    grade: asString(record.grade, fallback.grade) as ModelProfile['grade'],
    is_active: asBoolean(record.is_active, fallback.is_active),
  }
}

function normalizeAdmissionState(value: unknown, fallback: ModelAdmissionState = mockDashboard.model_admission_state): ModelAdmissionState {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    updated_at: asString(record.updated_at, fallback.updated_at),
    last_admission_id: asString(record.last_admission_id, fallback.last_admission_id),
    provider_name: asString(record.provider_name, fallback.provider_name),
    grade: asString(record.grade, fallback.grade) as ModelAdmissionState['grade'],
    total_score: asNumber(record.total_score, fallback.total_score),
    mode: asString(record.mode, fallback.mode),
    provider_called: asBoolean(record.provider_called, fallback.provider_called),
    is_mock: asBoolean(record.is_mock, fallback.is_mock),
    tested_samples: asStringArray(record.tested_samples, fallback.tested_samples),
    risk_items: asStringArray(record.risk_items, fallback.risk_items),
    recommendation: asString(record.recommendation, fallback.recommendation),
    reference_aligned_count: asNumber(record.reference_aligned_count, fallback.reference_aligned_count ?? 0),
    safe_for_training: asBoolean(record.safe_for_training, fallback.safe_for_training),
  }
}

function normalizeReadinessModule(value: unknown, fallback: PlatformReadinessModule, index: number): PlatformReadinessModule {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id || `module_${index}`),
    label: asString(record.label, fallback.label),
    status: asString(record.status, fallback.status),
    detail: asString(record.detail, fallback.detail),
    href: asString(record.href, fallback.href || '/'),
    tone: asString(record.tone, fallback.tone) as PlatformReadinessModule['tone'],
  }
}

function normalizeKnowledgeSourceChainItem(value: unknown, fallback: KnowledgeSourceChainItem, index: number): KnowledgeSourceChainItem {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id || `knowledge_source_${index}`),
    label: asString(record.label, fallback.label),
    source_file: asString(record.source_file, fallback.source_file),
    record_count: asNumber(record.record_count, fallback.record_count),
    sample_ids: asStringArray(record.sample_ids, fallback.sample_ids),
    used_by: asStringArray(record.used_by, fallback.used_by),
    proof: asString(record.proof, fallback.proof),
    href: asString(record.href, fallback.href || '/'),
    tone: asString(record.tone, fallback.tone) as KnowledgeSourceChainItem['tone'],
  }
}

function normalizeCoverageBuckets(value: unknown, fallback: RealSampleCoverage['dataset_distribution'] = []): RealSampleCoverage['dataset_distribution'] {
  if (!Array.isArray(value)) return fallback
  return value.map((item, index) => {
    const record = asRecord(item)
    return {
      label: asString(record.label, fallback[index]?.label || `bucket_${index + 1}`),
      count: asNumber(record.count, fallback[index]?.count || 0),
    }
  })
}

function normalizeRealSampleCoverage(value: unknown, fallback: RealSampleCoverage): RealSampleCoverage {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    source_file: asString(record.source_file, fallback.source_file),
    local_data_hint: asString(record.local_data_hint, fallback.local_data_hint),
    total_records: asNumber(record.total_records, fallback.total_records),
    mapped_question_count: asNumber(record.mapped_question_count, fallback.mapped_question_count),
    asset_checked_count: asNumber(record.asset_checked_count, fallback.asset_checked_count),
    asset_present_count: asNumber(record.asset_present_count, fallback.asset_present_count),
    missing_assets: asStringArray(record.missing_assets, fallback.missing_assets),
    dataset_distribution: normalizeCoverageBuckets(record.dataset_distribution, fallback.dataset_distribution),
    use_distribution: normalizeCoverageBuckets(record.use_distribution, fallback.use_distribution),
    complexity_distribution: normalizeCoverageBuckets(record.complexity_distribution, fallback.complexity_distribution),
    sample_ids: asStringArray(record.sample_ids, fallback.sample_ids),
    coverage_note: asString(record.coverage_note, fallback.coverage_note),
  }
}

function normalizeLatestExamReplay(value: unknown, fallback?: LatestExamReplay | null): LatestExamReplay | null {
  const record = asRecord(value)
  if (!Object.keys(record).length) return fallback || null
  const sessionId = asString(record.session_id, asString(record.id, fallback?.session_id || 'exam_session'))
  const wrongQuestions = asStringArray(record.wrong_questions, fallback?.wrong_questions || [])
  const answeredCount = asNumber(record.answered_count, fallback?.answered_count || 0)
  const accuracy = asNumber(record.accuracy, fallback?.accuracy || 0)
  const wrongCount = asNumber(record.wrong_count, fallback?.wrong_count ?? wrongQuestions.length)
  return {
    id: asString(record.id, fallback?.id || sessionId),
    session_id: sessionId,
    date: asString(record.date, fallback?.date || ''),
    answered_count: answeredCount,
    correct_count: asNumber(record.correct_count, fallback?.correct_count || 0),
    accuracy,
    average_score: asNumber(record.average_score, fallback?.average_score || 0),
    wrong_count: wrongCount,
    wrong_questions: wrongQuestions,
    elapsed_seconds: asNumber(record.elapsed_seconds, fallback?.elapsed_seconds || 0),
    profile_updated: asBoolean(record.profile_updated, fallback?.profile_updated || false),
    created_at: asString(record.created_at, fallback?.created_at || ''),
    href: asString(record.href, fallback?.href || `/feedback?session=${encodeURIComponent(sessionId)}`),
    profile_href: asString(record.profile_href, fallback?.profile_href || '/profile?tab=records'),
    status: asString(record.status, fallback?.status || '待核查'),
    detail: asString(record.detail, fallback?.detail || `本场考试 ${answeredCount} 题，正确率 ${accuracy}%，错题 ${wrongCount} 题。`),
  }
}

function normalizePlatformReadiness(value: unknown, fallback: PlatformReadiness = mockDashboard.platform_readiness): PlatformReadiness {
  const record = asRecord(value)
  const fallbackModules = fallback.modules.length ? fallback.modules : mockDashboard.platform_readiness.modules
  const modules = Array.isArray(record.modules) ? record.modules : fallbackModules
  const fallbackReceipts = fallback.evidence_receipts.length ? fallback.evidence_receipts : fallbackModules
  const receipts = Array.isArray(record.evidence_receipts) ? record.evidence_receipts : fallbackReceipts
  const defaultKnowledgeChainItem: KnowledgeSourceChainItem = {
    id: 'knowledge_source_empty',
    label: '知识库来源链',
    source_file: 'backend data',
    record_count: 0,
    sample_ids: [],
    used_by: [],
    proof: '后端联通后显示本地知识库来源和消费链路。',
    href: '/',
    tone: 'neutral',
  }
  const fallbackKnowledgeChain = fallback.knowledge_source_chain.length
    ? fallback.knowledge_source_chain
    : mockDashboard.platform_readiness.knowledge_source_chain
  const knowledgeSourceChain = Array.isArray(record.knowledge_source_chain) ? record.knowledge_source_chain : fallbackKnowledgeChain
  const fallbackPath = fallback.demo_path.length ? fallback.demo_path : mockDashboard.platform_readiness.demo_path
  const demoPath = Array.isArray(record.demo_path) ? record.demo_path : fallbackPath
  return {
    ...fallback,
    ...record,
    generated_at: asString(record.generated_at, fallback.generated_at),
    overall_score: asNumber(record.overall_score, fallback.overall_score),
    backend_ready: asBoolean(record.backend_ready, fallback.backend_ready),
    provider_ready: asBoolean(record.provider_ready, fallback.provider_ready),
    provider_mode: asString(record.provider_mode, fallback.provider_mode),
    knowledge_ready: asBoolean(record.knowledge_ready, fallback.knowledge_ready),
    memory_ready: asBoolean(record.memory_ready, fallback.memory_ready),
    qbank_count: asNumber(record.qbank_count, fallback.qbank_count),
    real_sample_count: asNumber(record.real_sample_count, fallback.real_sample_count),
    real_sample_coverage: normalizeRealSampleCoverage(record.real_sample_coverage, fallback.real_sample_coverage),
    report_template_count: asNumber(record.report_template_count, fallback.report_template_count),
    training_record_count: asNumber(record.training_record_count, fallback.training_record_count),
    exam_session_count: asNumber(record.exam_session_count, fallback.exam_session_count),
    latest_exam_replay: normalizeLatestExamReplay(record.latest_exam_replay, fallback.latest_exam_replay),
    audit_log_count: asNumber(record.audit_log_count, fallback.audit_log_count),
    admission_grade: asString(record.admission_grade, fallback.admission_grade),
    admission_provider_called: asBoolean(record.admission_provider_called, fallback.admission_provider_called),
    knowledge_source_chain: knowledgeSourceChain.map((item, index) => normalizeKnowledgeSourceChainItem(item, fallbackKnowledgeChain[index] || fallbackKnowledgeChain[0] || defaultKnowledgeChainItem, index)),
    evidence_receipts: receipts.map((item, index) => normalizeReadinessModule(item, fallbackReceipts[index] || fallbackReceipts[0], index)),
    modules: modules.map((item, index) => normalizeReadinessModule(item, fallbackModules[index] || fallbackModules[0], index)),
    demo_path: demoPath.map((item, index) => {
      const step = asRecord(item)
      const fallbackStep = fallbackPath[index] || fallbackPath[0]
      return {
        step: asNumber(step.step, fallbackStep.step || index + 1),
        title: asString(step.title, fallbackStep.title),
        detail: asString(step.detail, fallbackStep.detail),
        href: asString(step.href, fallbackStep.href || '/'),
        expected_state: asString(step.expected_state, fallbackStep.expected_state),
      }
    }),
    gaps: asStringArray(record.gaps, fallback.gaps),
    safety_notice: asString(record.safety_notice, safetyNotice),
    api_source: record.api_source as ApiSource | undefined,
  }
}

function fallbackDeliveryReport(): DeliveryReport {
  const readiness = mockDashboard.platform_readiness
  const profile = mockDashboard.learner_profile
  const auditCounts = Object.entries(
    mockAuditLogs.reduce<Record<string, number>>((accumulator, item) => {
      accumulator[item.event_type] = (accumulator[item.event_type] || 0) + 1
      return accumulator
    }, {}),
  ).map(([event_type, count]) => ({ event_type, count }))

  return {
    generated_at: readiness.generated_at,
    title: 'ARIS v2.0 交付证据报告（前端 fallback）',
    scope: '后端不可用时仅展示交付证据页结构；正式验收证据以 FastAPI /api/platform/delivery-report 和导出脚本为准。',
    doctor_context: {
      learner_id: profile.learner_id,
      name: profile.name,
      title: profile.title,
      department: profile.department,
      hospital: profile.hospital,
      training_stage: profile.training_stage,
      daily_target: profile.daily_target,
      completed_today: profile.completed_today,
      streak_days: profile.streak_days,
    },
    platform_summary: {
      overall_score: readiness.overall_score,
      backend_ready: readiness.backend_ready,
      provider_mode: readiness.provider_mode,
      provider_ready: readiness.provider_ready,
      knowledge_ready: readiness.knowledge_ready,
      memory_ready: readiness.memory_ready,
      qbank_count: readiness.qbank_count,
      real_sample_count: readiness.real_sample_count,
      real_sample_coverage: readiness.real_sample_coverage,
      report_template_count: readiness.report_template_count,
      audit_log_count: readiness.audit_log_count,
      exam_session_count: readiness.exam_session_count,
      admission_grade: readiness.admission_grade,
      admission_provider_called: readiness.admission_provider_called,
    },
    workflow_proofs: [
      {
        id: 'training_loop',
        name: '训练题库与画像回灌',
        status: readiness.memory_ready ? 'ready' : 'fallback',
        evidence: '刷题、考试、错题和画像路径保留为同一训练闭环；fallback 不写入真实画像。',
        route: '/training',
      },
      {
        id: 'report_loop',
        name: '诊断报告训练',
        status: readiness.report_template_count ? 'ready' : 'fallback',
        evidence: '报告模板、修改评分与安全边界可在报告中心查看；后端在线时返回 source_trace。',
        route: '/report',
      },
      {
        id: 'card_review_loop',
        name: '科普卡片审核闸门',
        status: 'ready',
        evidence: '卡片草稿与医生审核状态分离，未审核不解锁患者沟通状态。',
        route: '/card',
      },
      {
        id: 'model_gate',
        name: 'Provider 与模型准入',
        status: readiness.provider_ready ? 'provider' : readiness.provider_mode,
        evidence: '未配置 Provider 时显式显示 rule/fallback；不会伪造真实模型调用。',
        route: '/models',
      },
    ],
    knowledge_source_chain: readiness.knowledge_source_chain,
    evidence_receipts: readiness.evidence_receipts,
    audit_event_counts: auditCounts,
    provider_state: {
      configured: readiness.provider_ready,
      mode: readiness.provider_mode,
      provider_declared: false,
      model: mockDashboard.active_model.name,
      self_test_logged: false,
      self_test_count: 0,
      self_test_verified: false,
      latest_self_test_state: 'frontend_fallback',
      admission_provider_called: readiness.admission_provider_called,
      admission_state_kind: readiness.admission_provider_called ? 'provider_admission' : 'rule_draft',
      admission_safe_for_training: mockDashboard.model_admission_state.safe_for_training,
      real_inference_verified: false,
      verification_label: '前端 fallback 预览',
      verification_note: '后端不可用时无法证明 Provider 真实调用；正式验收请查看 backend live 交付证据。',
    },
    verification_commands: [
      {
        name: '总控验证',
        command: 'python scripts\\verify_all.py',
        covers: '后端健康、Provider 医生、演示闭环、UI smoke 与交付报告导出。',
      },
      {
        name: '交付报告导出',
        command: 'python scripts\\export_delivery_report.py --output runtime_logs\\delivery_evidence_report.md',
        covers: '只读导出 /api/platform/delivery-report，并检查状态文件不漂移。',
      },
    ],
    current_boundaries: [
      '平台定位是教学训练、报告表达练习和医生审核前辅助。',
      '所有医学输出必须保留医生复核，不作为独立诊断依据。',
      '前端 fallback 只用于断网或后端不可用时的可视化兜底。',
    ],
    gaps: ['当前为前端 fallback；请启动 FastAPI 后端查看真实运行时证据。'],
    safety_notice: safetyNotice,
    report_integrity: {
      source: 'frontend_fallback',
      writes_state: false,
      secrets_included: false,
      api_key_returned: false,
      provider_base_returned: false,
    },
  }
}

function normalizeDeliveryDoctorContext(value: unknown, fallback: DeliveryDoctorContext): DeliveryDoctorContext {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    learner_id: asString(record.learner_id, fallback.learner_id),
    name: asString(record.name, fallback.name),
    title: asString(record.title, fallback.title),
    department: asString(record.department, fallback.department),
    hospital: asString(record.hospital, fallback.hospital || ''),
    training_stage: asString(record.training_stage, fallback.training_stage),
    daily_target: asNumber(record.daily_target, fallback.daily_target),
    completed_today: asNumber(record.completed_today, fallback.completed_today),
    streak_days: asNumber(record.streak_days, fallback.streak_days),
  }
}

function normalizeDeliveryPlatformSummary(value: unknown, fallback: DeliveryPlatformSummary): DeliveryPlatformSummary {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    overall_score: asNumber(record.overall_score, fallback.overall_score),
    backend_ready: asBoolean(record.backend_ready, fallback.backend_ready),
    provider_mode: asString(record.provider_mode, fallback.provider_mode),
    provider_ready: asBoolean(record.provider_ready, fallback.provider_ready),
    knowledge_ready: asBoolean(record.knowledge_ready, fallback.knowledge_ready),
    memory_ready: asBoolean(record.memory_ready, fallback.memory_ready),
    qbank_count: asNumber(record.qbank_count, fallback.qbank_count),
    real_sample_count: asNumber(record.real_sample_count, fallback.real_sample_count),
    real_sample_coverage: record.real_sample_coverage
      ? normalizeRealSampleCoverage(record.real_sample_coverage, fallback.real_sample_coverage || mockDashboard.platform_readiness.real_sample_coverage)
      : fallback.real_sample_coverage,
    report_template_count: asNumber(record.report_template_count, fallback.report_template_count),
    audit_log_count: asNumber(record.audit_log_count, fallback.audit_log_count),
    exam_session_count: asNumber(record.exam_session_count, fallback.exam_session_count),
    admission_grade: asString(record.admission_grade, fallback.admission_grade),
    admission_provider_called: asBoolean(record.admission_provider_called, fallback.admission_provider_called),
  }
}

function normalizeDeliveryWorkflowProof(value: unknown, fallback: DeliveryWorkflowProof, index: number): DeliveryWorkflowProof {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id || `workflow_${index}`),
    name: asString(record.name, fallback.name),
    status: asString(record.status, fallback.status),
    evidence: asString(record.evidence, fallback.evidence),
    route: asString(record.route, fallback.route || '/'),
  }
}

function normalizeDeliveryAuditCount(value: unknown, fallback: DeliveryAuditEventCount, index: number): DeliveryAuditEventCount {
  const record = asRecord(value)
  return {
    event_type: asString(record.event_type, fallback.event_type || `event_${index}`),
    count: asNumber(record.count, fallback.count),
  }
}

function normalizeDeliveryProviderState(value: unknown, fallback: DeliveryProviderState): DeliveryProviderState {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    configured: asBoolean(record.configured, fallback.configured),
    mode: asString(record.mode, fallback.mode),
    provider_declared: asBoolean(record.provider_declared, fallback.provider_declared),
    model: asString(record.model, fallback.model),
    self_test_logged: asBoolean(record.self_test_logged, fallback.self_test_logged),
    self_test_count: asNumber(record.self_test_count, fallback.self_test_count),
    self_test_verified: asBoolean(record.self_test_verified, fallback.self_test_verified),
    latest_self_test_state: asString(record.latest_self_test_state, fallback.latest_self_test_state),
    admission_provider_called: asBoolean(record.admission_provider_called, fallback.admission_provider_called),
    admission_state_kind: asString(record.admission_state_kind, fallback.admission_state_kind),
    admission_safe_for_training: asBoolean(record.admission_safe_for_training, fallback.admission_safe_for_training),
    real_inference_verified: asBoolean(record.real_inference_verified, fallback.real_inference_verified),
    verification_label: asString(record.verification_label, fallback.verification_label),
    verification_note: asString(record.verification_note, fallback.verification_note),
  }
}

function normalizeDeliveryCommand(value: unknown, fallback: DeliveryVerificationCommand, index: number): DeliveryVerificationCommand {
  const record = asRecord(value)
  return {
    name: asString(record.name, fallback.name || `验证命令 ${index + 1}`),
    command: asString(record.command, fallback.command),
    covers: asString(record.covers, fallback.covers),
  }
}

function normalizeDeliveryIntegrity(value: unknown, fallback: DeliveryReportIntegrity): DeliveryReportIntegrity {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    source: asString(record.source, fallback.source),
    writes_state: asBoolean(record.writes_state, fallback.writes_state),
    secrets_included: asBoolean(record.secrets_included, fallback.secrets_included),
    api_key_returned: asBoolean(record.api_key_returned, fallback.api_key_returned),
    provider_base_returned: asBoolean(record.provider_base_returned, fallback.provider_base_returned),
  }
}

function normalizeDeliveryReport(value: unknown, fallback: DeliveryReport = fallbackDeliveryReport()): DeliveryReport {
  const record = asRecord(value)
  const fallbackWorkflowProofs = fallback.workflow_proofs.length ? fallback.workflow_proofs : fallbackDeliveryReport().workflow_proofs
  const workflowProofs = Array.isArray(record.workflow_proofs) ? record.workflow_proofs : fallbackWorkflowProofs
  const fallbackKnowledgeChain = fallback.knowledge_source_chain.length ? fallback.knowledge_source_chain : mockDashboard.platform_readiness.knowledge_source_chain
  const knowledgeChain = Array.isArray(record.knowledge_source_chain) ? record.knowledge_source_chain : fallbackKnowledgeChain
  const fallbackReceipts = fallback.evidence_receipts.length ? fallback.evidence_receipts : mockDashboard.platform_readiness.evidence_receipts
  const receipts = Array.isArray(record.evidence_receipts) ? record.evidence_receipts : fallbackReceipts
  const fallbackAuditCounts = fallback.audit_event_counts.length ? fallback.audit_event_counts : [{ event_type: 'audit_seed', count: 0 }]
  const auditCounts = Array.isArray(record.audit_event_counts) ? record.audit_event_counts : fallbackAuditCounts
  const fallbackCommands = fallback.verification_commands.length ? fallback.verification_commands : fallbackDeliveryReport().verification_commands
  const commands = Array.isArray(record.verification_commands) ? record.verification_commands : fallbackCommands

  return {
    ...fallback,
    ...record,
    generated_at: asString(record.generated_at, fallback.generated_at),
    title: asString(record.title, fallback.title),
    scope: asString(record.scope, fallback.scope),
    doctor_context: normalizeDeliveryDoctorContext(record.doctor_context, fallback.doctor_context),
    platform_summary: normalizeDeliveryPlatformSummary(record.platform_summary, fallback.platform_summary),
    workflow_proofs: workflowProofs.map((item, index) => normalizeDeliveryWorkflowProof(item, fallbackWorkflowProofs[index] || fallbackWorkflowProofs[0], index)),
    knowledge_source_chain: knowledgeChain.map((item, index) => normalizeKnowledgeSourceChainItem(item, fallbackKnowledgeChain[index] || fallbackKnowledgeChain[0], index)),
    evidence_receipts: receipts.map((item, index) => normalizeReadinessModule(item, fallbackReceipts[index] || fallbackReceipts[0], index)),
    audit_event_counts: auditCounts.map((item, index) => normalizeDeliveryAuditCount(item, fallbackAuditCounts[index] || fallbackAuditCounts[0], index)),
    provider_state: normalizeDeliveryProviderState(record.provider_state, fallback.provider_state),
    verification_commands: commands.map((item, index) => normalizeDeliveryCommand(item, fallbackCommands[index] || fallbackCommands[0], index)),
    current_boundaries: asStringArray(record.current_boundaries, fallback.current_boundaries),
    gaps: asStringArray(record.gaps, fallback.gaps),
    safety_notice: asString(record.safety_notice, safetyNotice),
    report_integrity: normalizeDeliveryIntegrity(record.report_integrity, fallback.report_integrity),
    api_source: record.api_source as ApiSource | undefined,
  }
}

function normalizeDashboard(value: unknown): DashboardPayload {
  const record = asRecord(value)
  const profile = normalizeProfile(record.learner_profile, mockDashboard.learner_profile)
  const today = asRecord(record.today_training)
  const source = record.api_source as ApiSource | undefined
  const fallbackContinue = mockDashboard.continue_training
  const continueTraining = asRecord(record.continue_training)
  return {
    ...mockDashboard,
    ...record,
    today_training: {
      completed: asNumber(today.completed, profile.completed_today),
      target: Math.max(1, asNumber(today.target, profile.daily_target)),
      streak_days: asNumber(today.streak_days, profile.streak_days),
      review_queue: asNumber(today.review_queue, profile.wrong_questions.length),
    },
    learner_profile: profile,
    ability_radar: Array.isArray(record.ability_radar)
      ? record.ability_radar.map((item) => {
          const radar = asRecord(item)
          return { dimension: asString(radar.dimension, '能力维度'), score: asNumber(radar.score, 0) }
        })
      : Object.entries(profile.skill_scores).map(([dimension, score]) => ({ dimension, score })),
    recommended_training: Array.isArray(record.recommended_training)
      ? record.recommended_training.map((item) => {
          const training = asRecord(item)
          return { label: asString(training.label, '推荐训练'), count: asNumber(training.count, 0) }
        })
      : mockDashboard.recommended_training,
    today_plan: Array.isArray(record.today_plan)
      ? record.today_plan.map((item) => {
          const plan = asRecord(item)
          return {
            label: asString(plan.label, '训练任务'),
            target: asNumber(plan.target, 1),
            status: asString(plan.status, '待完成'),
            href: asString(plan.href, '/training'),
          }
        })
      : mockDashboard.today_plan,
    continue_training: {
      question_id: asString(continueTraining.question_id, fallbackContinue.question_id),
      title: asString(continueTraining.title, fallbackContinue.title),
      source_dataset: asString(continueTraining.source_dataset, fallbackContinue.source_dataset),
      reason: asString(continueTraining.reason, fallbackContinue.reason),
    },
    favorite_count: asNumber(record.favorite_count, profile.favorite_questions.length),
    wrong_count: asNumber(record.wrong_count, profile.wrong_questions.length),
    recent_tutor_summary: asStringArray(record.recent_tutor_summary, mockDashboard.recent_tutor_summary),
    growth_trend: normalizeTrend(record.growth_trend, profile.growth_trend),
    active_model: normalizeModel(record.active_model, mockDashboard.active_model),
    model_admission_state: normalizeAdmissionState(record.model_admission_state, mockDashboard.model_admission_state),
    platform_readiness: normalizePlatformReadiness(record.platform_readiness, mockDashboard.platform_readiness),
    safety_notice: asString(record.safety_notice, safetyNotice),
    mock_evaluation_notice: asString(record.mock_evaluation_notice, mockDashboard.mock_evaluation_notice),
    reference_inspirations: asStringArray(record.reference_inspirations, mockDashboard.reference_inspirations),
    api_source: source,
  }
}

function localReportDraft(findingText: string, options: { examType?: string; imageName?: string; templateName?: string } = {}): ReportDraft {
  return {
    id: `report_local_${Date.now()}`,
    input_finding_text: findingText,
    exam_type: options.examType || 'gastroscopy',
    structured_findings: findingText.split(/[。；;\n]/).map((x) => x.trim()).filter(Boolean),
    draft_impression: ['胃黏膜炎症样/糜烂样改变，需医生结合完整检查复核。'],
    review_points: ['确认部位、范围、数量和图片证据是否一致。', '检查是否存在过强诊断表述。'],
    uncertainty_notes: ['草稿不自动补充未提供的信息。'],
    template_name: options.templateName || '胃镜结构化训练模板',
    evidence_source: [findingText ? '医生输入所见' : '报告知识库模板', options.imageName ? '图片输入待复核' : '未上传图片'],
    draft_status: 'needs_human_review',
    exam_context: {
      exam_type: options.examType || 'gastroscopy',
      patient_context_available: false,
      procedure_context_available: false,
      missing_context_note: options.imageName ? '仅提供单帧图片占位，完整检查范围与病理未提供。' : '未上传图片，仅基于模板训练。',
      single_frame: Boolean(options.imageName),
    },
    image_quality: {
      clarity: options.imageName ? 'acceptable' : 'unknown',
      artifacts: options.imageName ? ['reflection'] : ['unknown'],
      single_frame_limitation: Boolean(options.imageName),
    },
    evidence_ledger: [
      {
        evidence_id: findingText ? 'doctor_input_001' : 'kb_001',
        source_type: findingText ? 'doctor_input' : 'template_kb',
        source_ref: options.imageName || 'report_knowledge_base.json',
        supports: ['结构化所见', '草稿印象', '医师复核任务'],
      },
      ...(options.imageName ? [{
        evidence_id: 'image_preview_001',
        source_type: 'image_preview_only',
        source_ref: options.imageName,
        supports: ['本地 fallback 未执行真实视觉推理，仅作为图片预览或人工复核入口。'],
      }] : []),
    ],
    hallucination_audit: {
      audit_passed: true,
      unsupported_claims: [],
      high_risk_flags: findingText.includes('癌') ? ['癌'] : [],
      required_rewrites: findingText.includes('癌') ? ['高风险词需医师确认或降级表达。'] : [],
      evidence_policy: 'image_supported/context_supported/derived_cautious only',
    },
    review_tasks: [
      '确认检查类型、病灶解剖部位和完整检查范围。',
      '确认病灶数量、大小、形态分型和是否存在多视角证据。',
      '签发前逐条核对证据台账与报告声明。',
    ],
    generation_mode: 'fallback',
    provider_status: {
      provider: 'frontend_fallback',
      model: 'none',
      mode: 'fallback',
      ok: false,
      error: 'backend_unavailable',
    },
    model_observation: null,
    source_trace: [
      {
        source_type: findingText ? 'doctor_input' : 'template_kb',
        label: findingText ? '医生输入所见' : '报告知识库模板',
        used: true,
        detail: findingText ? '前端 fallback 仅做文本结构化。' : '未输入所见，使用本地模板。',
      },
      {
        source_type: 'provider',
        label: '视觉/语言 Provider',
        used: false,
        detail: 'backend_unavailable',
      },
    ],
    doctor_review_required: true,
    safety_notice: safetyNotice,
    created_at: new Date().toISOString(),
  }
}

function normalizeReportDraft(value: unknown, fallback: ReportDraft): ReportDraft {
  const record = asRecord(value)
  const imageQuality = asRecord(record.image_quality)
  const hallucinationAudit = asRecord(record.hallucination_audit)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    input_finding_text: asString(record.input_finding_text, fallback.input_finding_text),
    exam_type: asString(record.exam_type, fallback.exam_type),
    structured_findings: asStringArray(record.structured_findings, fallback.structured_findings),
    draft_impression: asStringArray(record.draft_impression, fallback.draft_impression),
    review_points: asStringArray(record.review_points, fallback.review_points),
    uncertainty_notes: asStringArray(record.uncertainty_notes, fallback.uncertainty_notes),
    template_name: asString(record.template_name, fallback.template_name),
    evidence_source: asStringArray(record.evidence_source, fallback.evidence_source),
    draft_status: asString(record.draft_status, fallback.draft_status) as ReportDraft['draft_status'],
    exam_context: { ...fallback.exam_context, ...asRecord(record.exam_context) },
    image_quality: {
      ...fallback.image_quality,
      ...imageQuality,
      artifacts: asStringArray(imageQuality.artifacts, fallback.image_quality.artifacts),
    },
    evidence_ledger: Array.isArray(record.evidence_ledger)
      ? record.evidence_ledger.map((item, index) => {
          const ledger = asRecord(item)
          return {
            evidence_id: asString(ledger.evidence_id, `ev_${index}`),
            source_type: asString(ledger.source_type, 'unknown'),
            source_ref: asString(ledger.source_ref, 'unknown'),
            supports: asStringArray(ledger.supports, []),
            audit_log_id: typeof ledger.audit_log_id === 'string' || ledger.audit_log_id === null ? ledger.audit_log_id : undefined,
            sha256_prefix: typeof ledger.sha256_prefix === 'string' || ledger.sha256_prefix === null ? ledger.sha256_prefix : undefined,
            width: ledger.width === null ? null : asNumber(ledger.width, 0) || undefined,
            height: ledger.height === null ? null : asNumber(ledger.height, 0) || undefined,
          }
        })
      : fallback.evidence_ledger,
    hallucination_audit: {
      ...fallback.hallucination_audit,
      ...hallucinationAudit,
      unsupported_claims: asStringArray(hallucinationAudit.unsupported_claims, fallback.hallucination_audit.unsupported_claims),
      high_risk_flags: asStringArray(hallucinationAudit.high_risk_flags, fallback.hallucination_audit.high_risk_flags),
      required_rewrites: asStringArray(hallucinationAudit.required_rewrites, fallback.hallucination_audit.required_rewrites),
    },
    review_tasks: asStringArray(record.review_tasks, fallback.review_tasks),
    generation_mode: asString(record.generation_mode, fallback.generation_mode),
    provider_status: normalizeProviderStatus(record.provider_status, fallback.provider_status),
    model_observation: typeof record.model_observation === 'string' ? record.model_observation : fallback.model_observation,
    source_trace: normalizeSourceTrace(record.source_trace, fallback.source_trace),
    doctor_review_required: true,
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function normalizeReportJudge(value: unknown, fallback: ReportJudge): ReportJudge {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    score: asNumber(record.score, fallback.score),
    strengths: asStringArray(record.strengths, fallback.strengths),
    issues: asStringArray(record.issues, fallback.issues),
    suggested_revision: asString(record.suggested_revision, fallback.suggested_revision),
    rubric_scores: asNumberRecord(record.rubric_scores, fallback.rubric_scores),
    recommended_drills: Array.isArray(record.recommended_drills)
      ? record.recommended_drills.map((item) => {
          const drill = asRecord(item)
          return {
            label: asString(drill.label, '报告表达专项'),
            href: asString(drill.href, '/training?source=report_judge&drill=report_safety&question_class=报告纠错'),
            reason: asString(drill.reason, '继续巩固报告证据边界。'),
            drill_id: typeof drill.drill_id === 'string' ? drill.drill_id : undefined,
            rubric: typeof drill.rubric === 'string' ? drill.rubric : undefined,
            score: Number.isFinite(Number(drill.score)) ? Number(drill.score) : undefined,
          }
        })
      : fallback.recommended_drills,
    generation_mode: asString(record.generation_mode, fallback.generation_mode),
    provider_status: normalizeProviderStatus(record.provider_status, fallback.provider_status),
    provider_feedback: typeof record.provider_feedback === 'string' ? record.provider_feedback : fallback.provider_feedback,
    source_trace: normalizeSourceTrace(record.source_trace, fallback.source_trace),
    profile_updated: asBoolean(record.profile_updated, fallback.profile_updated),
    memory_summary: typeof record.memory_summary === 'string' ? record.memory_summary : fallback.memory_summary,
    doctor_review_required: true,
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function normalizePatientCard(value: unknown, fallback: PatientCard): PatientCard {
  const record = asRecord(value)
  const reviewSteps = Array.isArray(record.review_steps)
    ? record.review_steps.map((item) => {
        const step = asRecord(item)
        return {
          label: asString(step.label, '医生审核步骤'),
          checked: asBoolean(step.checked, false),
          detail: asString(step.detail, '等待医生确认。'),
        }
      })
    : fallback.review_steps
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    card_title: asString(record.card_title, fallback.card_title),
    plain_language_explanation: asString(record.plain_language_explanation, fallback.plain_language_explanation),
    what_it_means: asStringArray(record.what_it_means, fallback.what_it_means),
    what_to_watch: asStringArray(record.what_to_watch, fallback.what_to_watch),
    follow_up_reminder: asString(record.follow_up_reminder, fallback.follow_up_reminder),
    disclaimer: asString(record.disclaimer, fallback.disclaimer),
    template_id: asString(record.template_id, fallback.template_id),
    visual_tone: asString(record.visual_tone, fallback.visual_tone),
    image_url: typeof record.image_url === 'string' || record.image_url === null ? record.image_url : fallback.image_url,
    review_status: asString(record.review_status, fallback.review_status) as PatientCard['review_status'],
    share_status: asString(record.share_status, fallback.share_status || 'locked_pending_review') as PatientCard['share_status'],
    reviewer_name: typeof record.reviewer_name === 'string' || record.reviewer_name === null ? record.reviewer_name : fallback.reviewer_name,
    review_notes: typeof record.review_notes === 'string' || record.review_notes === null ? record.review_notes : fallback.review_notes,
    reviewed_at: typeof record.reviewed_at === 'string' || record.reviewed_at === null ? record.reviewed_at : fallback.reviewed_at,
    review_steps: reviewSteps,
    generation_mode: asString(record.generation_mode, fallback.generation_mode || 'fallback'),
    source_trace: normalizeSourceTrace(record.source_trace, fallback.source_trace || []),
    knowledge_base_id: typeof record.knowledge_base_id === 'string' || record.knowledge_base_id === null ? record.knowledge_base_id : fallback.knowledge_base_id,
    audit_logged: asBoolean(record.audit_logged, fallback.audit_logged || false),
    audit_log_id: typeof record.audit_log_id === 'string' || record.audit_log_id === null ? record.audit_log_id : fallback.audit_log_id,
    doctor_review_required: true,
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function normalizeModelAdmission(value: unknown, fallback: ModelAdmissionResult): ModelAdmissionResult {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    provider_name: asString(record.provider_name, fallback.provider_name),
    grade: asString(record.grade, fallback.grade) as ModelAdmissionResult['grade'],
    total_score: asNumber(record.total_score, fallback.total_score),
    dimension_scores: asNumberRecord(record.dimension_scores, fallback.dimension_scores),
    risk_items: asStringArray(record.risk_items, fallback.risk_items),
    tested_samples: asStringArray(record.tested_samples, fallback.tested_samples),
    provider_called: asBoolean(record.provider_called, fallback.provider_called),
    is_mock: asBoolean(record.is_mock, fallback.is_mock),
    evidence: Array.isArray(record.evidence)
      ? record.evidence.map((item) => {
          const evidence = asRecord(item)
          return {
            sample_id: asString(evidence.sample_id, ''),
            source_dataset: asString(evidence.source_dataset, ''),
            question: asString(evidence.question, ''),
            reference_annotation: asString(evidence.reference_annotation, ''),
            provider_answer: asString(evidence.provider_answer, ''),
            blind_probe: asBoolean(evidence.blind_probe, false),
            reference_match: asString(evidence.reference_match, ''),
            answer_overlap: asNumber(evidence.answer_overlap, 0),
            provider_called: asBoolean(evidence.provider_called, false),
            provider_mode: asString(evidence.provider_mode, ''),
            latency_ms: evidence.latency_ms === null ? null : asNumber(evidence.latency_ms, 0),
            observation_excerpt: asString(evidence.observation_excerpt, ''),
            error: typeof evidence.error === 'string' || evidence.error === null ? evidence.error : null,
          }
        })
      : fallback.evidence,
    provider_status: normalizeProviderStatus(record.provider_status, fallback.provider_status),
    recommendation: asString(record.recommendation, fallback.recommendation),
    platform_state_updated: asBoolean(record.platform_state_updated, fallback.platform_state_updated),
    platform_state_summary: typeof record.platform_state_summary === 'string' ? record.platform_state_summary : fallback.platform_state_summary,
    audit_logged: asBoolean(record.audit_logged, fallback.audit_logged),
    audit_log_id: typeof record.audit_log_id === 'string' || record.audit_log_id === null ? record.audit_log_id : fallback.audit_log_id,
    admission_receipt: normalizeProviderEvidenceReceipt(record.admission_receipt, fallback.admission_receipt),
    doctor_review_required: true,
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function normalizeProviderSelfTest(value: unknown, fallback: ProviderSelfTestResult): ProviderSelfTestResult {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    provider_name: asString(record.provider_name, fallback.provider_name),
    provider_called: asBoolean(record.provider_called, fallback.provider_called),
    provider_status: normalizeProviderStatus(record.provider_status, fallback.provider_status),
    probe_excerpt: typeof record.probe_excerpt === 'string' ? record.probe_excerpt : fallback.probe_excerpt,
    image_attached: asBoolean(record.image_attached, fallback.image_attached),
    image_sample_id: typeof record.image_sample_id === 'string' || record.image_sample_id === null ? record.image_sample_id : fallback.image_sample_id,
    image_source_dataset: typeof record.image_source_dataset === 'string' || record.image_source_dataset === null ? record.image_source_dataset : fallback.image_source_dataset,
    visual_probe: asBoolean(record.visual_probe, fallback.visual_probe),
    audit_logged: asBoolean(record.audit_logged, fallback.audit_logged),
    audit_log_id: typeof record.audit_log_id === 'string' || record.audit_log_id === null ? record.audit_log_id : fallback.audit_log_id,
    self_test_receipt: normalizeProviderEvidenceReceipt(record.self_test_receipt, fallback.self_test_receipt),
    key_persisted: asBoolean(record.key_persisted, fallback.key_persisted),
    admission_state_updated: asBoolean(record.admission_state_updated, fallback.admission_state_updated),
    recommendation: asString(record.recommendation, fallback.recommendation),
    doctor_review_required: true,
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function normalizeProviderEvidenceReceipt(value: unknown, fallback?: ProviderEvidenceReceipt | null): ProviderEvidenceReceipt | null {
  const record = asRecord(value)
  if (!Object.keys(record).length) return fallback || null
  const normalizeTrace = (trace: unknown) => Array.isArray(trace)
    ? trace.map((item) => {
        const entry = asRecord(item)
        return {
          source_type: asString(entry.source_type, ''),
          label: asString(entry.label, '证据来源'),
          used: asBoolean(entry.used, false),
          detail: asString(entry.detail, ''),
          latency_ms: entry.latency_ms === null ? null : asNumber(entry.latency_ms, 0),
        }
      })
    : []
  const normalizePrivacy = (trace: unknown) => Array.isArray(trace)
    ? trace.map((item) => {
        const entry = asRecord(item)
        return {
          label: asString(entry.label, '隐私边界'),
          used: asBoolean(entry.used, false),
          detail: asString(entry.detail, ''),
        }
      })
    : []
  const normalizeActions = (actions: unknown) => Array.isArray(actions)
    ? actions.map((item) => {
        const entry = asRecord(item)
        return { label: asString(entry.label, '继续查看'), href: asString(entry.href, '/models') }
      })
    : []
  return {
    audit_log_id: typeof record.audit_log_id === 'string' || record.audit_log_id === null ? record.audit_log_id : fallback?.audit_log_id,
    event_type: asString(record.event_type, fallback?.event_type || ''),
    self_test_id: typeof record.self_test_id === 'string' ? record.self_test_id : fallback?.self_test_id,
    admission_id: typeof record.admission_id === 'string' ? record.admission_id : fallback?.admission_id,
    provider_name: asString(record.provider_name, fallback?.provider_name || ''),
    provider_called: asBoolean(record.provider_called, fallback?.provider_called || false),
    visual_probe: asBoolean(record.visual_probe, fallback?.visual_probe || false),
    image_attached: asBoolean(record.image_attached, fallback?.image_attached || false),
    grade: typeof record.grade === 'string' ? record.grade : fallback?.grade,
    total_score: record.total_score === undefined ? fallback?.total_score : asNumber(record.total_score, fallback?.total_score || 0),
    platform_state_updated: asBoolean(record.platform_state_updated, fallback?.platform_state_updated || false),
    state_kind: asString(record.state_kind, fallback?.state_kind || ''),
    input_trace: normalizeTrace(record.input_trace).length ? normalizeTrace(record.input_trace) : fallback?.input_trace,
    provider_trace: normalizeTrace(record.provider_trace).length ? normalizeTrace(record.provider_trace) : fallback?.provider_trace,
    privacy_trace: normalizePrivacy(record.privacy_trace).length ? normalizePrivacy(record.privacy_trace) : fallback?.privacy_trace,
    next_actions: normalizeActions(record.next_actions).length ? normalizeActions(record.next_actions) : fallback?.next_actions,
    created_at: asString(record.created_at, fallback?.created_at || ''),
  }
}

function localProviderSelfTestReceipt(payload: { providerName: string; includeImage?: boolean; sampleId?: string }): ProviderEvidenceReceipt {
  return {
    audit_log_id: null,
    event_type: 'provider_self_test',
    self_test_id: `provider_selftest_local_${Date.now()}`,
    provider_name: payload.providerName,
    provider_called: false,
    visual_probe: Boolean(payload.includeImage),
    image_attached: false,
    state_kind: 'self_test',
    input_trace: [
      {
        source_type: 'frontend_fallback',
        label: '本地自检预览',
        used: true,
        detail: payload.includeImage ? `后端不可用，未附加公开样例 ${payload.sampleId || '默认样例'}。` : '后端不可用，未发送文本自检请求。',
      },
    ],
    provider_trace: [
      {
        source_type: 'frontend_fallback',
        label: 'Provider 调用',
        used: false,
        detail: '后端 provider/self-test 不可用，未写入 provider_self_test 审计。',
      },
    ],
    privacy_trace: [
      { label: 'API key/base', used: false, detail: '前端 fallback 不会保存或回显密钥。' },
      { label: '准入状态', used: false, detail: '未更新 model_admission_state.json。' },
    ],
    next_actions: [{ label: '检查后端服务', href: '/models' }],
    created_at: new Date().toISOString(),
  }
}

function localAdmissionReceipt(payload: { providerName: string; sampleIds: string[]; focus: string[] }): ProviderEvidenceReceipt {
  return {
    audit_log_id: null,
    event_type: 'model_admission',
    admission_id: `admission_local_${Date.now()}`,
    provider_name: payload.providerName,
    provider_called: false,
    platform_state_updated: false,
    state_kind: 'rule_draft',
    input_trace: [
      {
        source_type: 'frontend_fallback',
        label: '本地准入预览',
        used: true,
        detail: `选择 ${payload.sampleIds.length} 个样例，维度：${payload.focus.join(' / ') || '未选择'}；后端不可用，未执行盲测。`,
      },
    ],
    provider_trace: [
      {
        source_type: 'frontend_fallback',
        label: 'Provider 盲测',
        used: false,
        detail: '后端 models/admission-test 不可用，未写入 model_admission 审计。',
      },
    ],
    privacy_trace: [
      { label: '参考答案', used: false, detail: '前端 fallback 未发送样例或参考标注给 Provider。' },
      { label: 'API key/base', used: false, detail: '前端 fallback 不会保存或回显密钥。' },
      { label: '平台状态', used: false, detail: '未写入 model_admission_state.json。' },
    ],
    next_actions: [{ label: '检查后端服务', href: '/models' }],
    created_at: new Date().toISOString(),
  }
}

function normalizeChallengeBenchmark(value: unknown, fallback: ChallengeBenchmarkResult): ChallengeBenchmarkResult {
  const record = asRecord(value)
  return {
    ...fallback,
    ...record,
    id: asString(record.id, fallback.id),
    question_id: asString(record.question_id, fallback.question_id),
    benchmark_name: asString(record.benchmark_name, fallback.benchmark_name),
    benchmark_answer: asString(record.benchmark_answer, fallback.benchmark_answer),
    benchmark_correct: asBoolean(record.benchmark_correct, fallback.benchmark_correct),
    doctor_selected_answer: asString(record.doctor_selected_answer, fallback.doctor_selected_answer),
    same_as_doctor: asBoolean(record.same_as_doctor, fallback.same_as_doctor),
    generation_mode: asString(record.generation_mode, fallback.generation_mode),
    provider_status: normalizeProviderStatus(record.provider_status, fallback.provider_status),
    rationale: asString(record.rationale, fallback.rationale),
    audit_logged: asBoolean(record.audit_logged, fallback.audit_logged),
    profile_updated: asBoolean(record.profile_updated, fallback.profile_updated),
    doctor_review_required: asBoolean(record.doctor_review_required, fallback.doctor_review_required),
    safety_notice: asString(record.safety_notice, safetyNotice),
    created_at: asString(record.created_at, fallback.created_at),
  }
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

const localSubmission = (question: Question, selectedAnswer: string): SubmissionResponse => {
  const isCorrect = selectedAnswer === question.answer
  const errorTags = isCorrect ? [] : question.false_premise_flag ? ['错误前提', '证据不足'] : ['证据不足']
  return {
    id: `local_${Date.now()}`,
    question_id: question.id,
    learner_id: 'demo_learner',
    selected_answer: selectedAnswer,
    is_correct: isCorrect,
    score: isCorrect ? 100 : 0,
    error_tags: errorTags,
    fact_feedback: question.atomic_trace,
    explanation: isCorrect
      ? `回答正确。${question.explanation}`
      : `你的答案是“${selectedAnswer}”，参考答案是“${question.answer}”。${question.explanation}`,
    next_recommendation: question.false_premise_flag ? '建议继续练习错误前提与证据不足判断题。' : '建议进入复杂组合题训练证据链表达。',
    created_at: new Date().toISOString(),
    profile_updated: false,
    doctor_review_required: true,
    safety_notice: safetyNotice,
  }
}

export const api = {
  async dashboard(): Promise<DashboardPayload> {
    const response = await request<DashboardPayload>('/api/dashboard', undefined, mockDashboard)
    return normalizeDashboard(response)
  },

  async platformReadiness(): Promise<PlatformReadiness> {
    const response = await request<PlatformReadiness>('/api/platform/readiness', undefined, mockDashboard.platform_readiness)
    return normalizePlatformReadiness(response)
  },

  async deliveryReport(): Promise<DeliveryReport> {
    const fallback = fallbackDeliveryReport()
    const response = await request<DeliveryReport>('/api/platform/delivery-report', undefined, fallback)
    return normalizeDeliveryReport(response, fallback)
  },

  async platformDemoCheck(persist = false): Promise<DemoCheckResult> {
    return request<DemoCheckResult>(
      `/api/platform/demo-check?learner_id=demo_learner&persist=${persist ? 'true' : 'false'}`,
      { method: 'POST' },
    )
  },

  async questions(params: { falsePremise?: boolean } = {}): Promise<Question[]> {
    const search = new URLSearchParams()
    if (params.falsePremise !== undefined) search.set('false_premise', String(params.falsePremise))
    const qs = search.toString() ? `?${search.toString()}` : ''
    const fallback = params.falsePremise === undefined ? mockQuestions : mockQuestions.filter((q) => q.false_premise_flag === params.falsePremise)
    const response = await request<{ items: Question[]; total: number }>(`/api/questions${qs}`, undefined, {
      items: fallback,
      total: fallback.length,
    })
    return normalizeQuestions(response.items, fallback)
  },

  async qbank(params: {
    bodyPart?: string
    task?: string
    difficulty?: string
    questionType?: string
    sourceDataset?: string
    questionClass?: string
    onlyFavorites?: boolean
    onlyWrong?: boolean
    publicOnly?: boolean
    mode?: 'practice' | 'exam'
  } = {}): Promise<Question[]> {
    if (params.publicOnly) {
      return this.realSamples()
    }
    const search = new URLSearchParams()
    if (params.bodyPart) search.set('body_part', params.bodyPart)
    if (params.task) search.set('task', params.task)
    if (params.difficulty) search.set('difficulty', params.difficulty)
    if (params.questionType) search.set('question_type', params.questionType)
    if (params.sourceDataset) search.set('source_dataset', params.sourceDataset)
    if (params.questionClass) search.set('question_class', params.questionClass)
    if (params.onlyFavorites) search.set('only_favorites', 'true')
    if (params.onlyWrong) search.set('only_wrong', 'true')
    const fallbackItems = mockQuestions.filter((q) => {
      if (params.onlyFavorites && !q.is_favorited) return false
      if (params.onlyWrong && q.review_status !== '待复盘') return false
      if (params.difficulty && q.difficulty !== params.difficulty) return false
      if (params.questionClass && q.question_class !== params.questionClass) return false
      return true
    })
    const response = await request<{ items: Question[]; total: number }>(
      `/api/questions${search.toString() ? `?${search.toString()}` : ''}`,
      undefined,
      {
        items: fallbackItems,
        total: fallbackItems.length,
      },
    )
    return normalizeQuestions(response.items)
  },

  async realSamples(): Promise<Question[]> {
    const response = await request<{ items: Question[]; total: number; safety_notice?: string }>('/api/knowledge/real-samples', undefined, {
      items: mockQuestions.filter((q) => publicDatasets.has(q.source_dataset)),
      total: 0,
      safety_notice: safetyNotice,
    })
    return normalizeQuestions(response.items, [])
  },

  async question(id: string): Promise<Question> {
    const fallback = mockQuestions.find((q) => q.id === id) || mockQuestions[0]
    const response = await request<{ item: Question }>(`/api/questions/${id}`, undefined, { item: fallback })
    return normalizeQuestion(response.item, fallback)
  },

  async submit(question: Question, selectedAnswer: string): Promise<SubmissionResponse> {
    const fallback = localSubmission(question, selectedAnswer)
    const response = await request<SubmissionResponse>(
      '/api/submit',
      {
        method: 'POST',
        body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', selected_answer: selectedAnswer }),
      },
      fallback,
    )
    return {
      ...fallback,
      ...response,
      profile_updated: asBoolean(response.profile_updated, response.api_source === 'backend'),
      doctor_review_required: asBoolean(response.doctor_review_required, fallback.doctor_review_required),
      safety_notice: asString(response.safety_notice, safetyNotice),
    }
  },

  async examSession(payload: {
    sessionId: string
    attempts: ExamSessionAttempt[]
    durationSeconds: number
    remainingSeconds: number
    finishedReason: 'manual_submit' | 'completed_all' | 'time_expired'
  }): Promise<ExamSessionResponse> {
    const answeredCount = payload.attempts.length
    const correctCount = payload.attempts.filter((attempt) => attempt.is_correct).length
    const averageScore = answeredCount ? Math.round(payload.attempts.reduce((sum, attempt) => sum + attempt.score, 0) / answeredCount) : 0
    const accuracy = answeredCount ? Math.round((correctCount / answeredCount) * 100) : 0
    const fallback: ExamSessionResponse = {
      id: `exam_session_local_${Date.now()}`,
      learner_id: 'demo_learner',
      answered_count: answeredCount,
      correct_count: correctCount,
      accuracy,
      average_score: averageScore,
      wrong_questions: payload.attempts.filter((attempt) => !attempt.is_correct).map((attempt) => attempt.question_id),
      elapsed_seconds: Math.max(0, payload.durationSeconds - payload.remainingSeconds),
      finished_reason: payload.finishedReason,
      profile_updated: false,
      memory_summary: `本场考试前端 fallback 汇总：${answeredCount} 题，正确率 ${accuracy}%，未写入后端画像。`,
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: new Date().toISOString(),
    }
    const response = await request<ExamSessionResponse>(
      '/api/learner/exam-session',
      {
        method: 'POST',
        body: JSON.stringify({
          session_id: payload.sessionId,
          learner_id: 'demo_learner',
          duration_seconds: payload.durationSeconds,
          remaining_seconds: payload.remainingSeconds,
          finished_reason: payload.finishedReason,
          attempts: payload.attempts,
        }),
      },
      fallback,
    )
    return {
      ...fallback,
      ...response,
      answered_count: asNumber(response.answered_count, fallback.answered_count),
      correct_count: asNumber(response.correct_count, fallback.correct_count),
      accuracy: asNumber(response.accuracy, fallback.accuracy),
      average_score: asNumber(response.average_score, fallback.average_score),
      wrong_questions: asStringArray(response.wrong_questions, fallback.wrong_questions),
      elapsed_seconds: asNumber(response.elapsed_seconds, fallback.elapsed_seconds),
      finished_reason: asString(response.finished_reason, fallback.finished_reason),
      profile_updated: asBoolean(response.profile_updated, fallback.profile_updated),
      memory_summary: asString(response.memory_summary, fallback.memory_summary),
      doctor_review_required: asBoolean(response.doctor_review_required, fallback.doctor_review_required),
      safety_notice: asString(response.safety_notice, safetyNotice),
      created_at: asString(response.created_at, fallback.created_at),
    }
  },

  async favorite(questionId: string, favorited: boolean): Promise<LearnerProfile> {
    const response = await request<{ profile: LearnerProfile; safety_notice: string }>(
      '/api/learner/favorite',
      { method: 'POST', body: JSON.stringify({ question_id: questionId, learner_id: 'demo_learner', favorited }) },
      { profile: mockDashboard.learner_profile, safety_notice: safetyNotice },
    )
    return normalizeProfile(response.profile)
  },

  async trainingState(): Promise<TrainingState> {
    const response = await request<TrainingState>('/api/learner/training-state', undefined, {
      profile: mockDashboard.learner_profile,
      wrong_questions: mockDashboard.learner_profile.wrong_questions,
      favorite_questions: mockDashboard.learner_profile.favorite_questions,
      exam_sessions: mockDashboard.learner_profile.exam_sessions,
      latest_exam_session: mockDashboard.learner_profile.exam_sessions[0] || null,
      review_queue: mockDashboard.learner_profile.wrong_questions.length,
      next_plan: [
        { label: '证据不足复盘', count: 4, reason: '最近错因集中在错误前提和过度诊断' },
        { label: '报告修改训练', count: 2, reason: '强化所见与诊断边界' },
      ],
      safety_notice: safetyNotice,
    })
    return {
      ...response,
      profile: normalizeProfile(response.profile),
      wrong_questions: asStringArray(response.wrong_questions, mockDashboard.learner_profile.wrong_questions),
      favorite_questions: asStringArray(response.favorite_questions, mockDashboard.learner_profile.favorite_questions),
      exam_sessions: normalizeExamSessions(response.exam_sessions, mockDashboard.learner_profile.exam_sessions),
      latest_exam_session: response.latest_exam_session ? normalizeExamSessions([response.latest_exam_session])[0] : null,
      review_queue: asNumber(response.review_queue, mockDashboard.learner_profile.wrong_questions.length),
      next_plan: Array.isArray(response.next_plan) ? response.next_plan : [],
      safety_notice: asString(response.safety_notice, safetyNotice),
    }
  },

  async learnerProfile(): Promise<LearnerProfile> {
    const response = await request<LearnerProfile>('/api/learner/profile', undefined, mockDashboard.learner_profile)
    return normalizeProfile(response)
  },

  async providerStatus(): Promise<ProviderStatus> {
    const response = await request<ProviderStatus>('/api/provider/status', undefined, {
      provider: 'mock',
      model: 'unconfigured',
      mode: 'fallback',
      configured: false,
      ok: false,
      error: 'backend_unavailable',
      safety_notice: safetyNotice,
    })
    return normalizeProviderStatus(response)
  },

  async providerDiagnostics(): Promise<ProviderDiagnostics> {
    const fallbackCreatedAt = new Date().toISOString()
    const fallback: ProviderDiagnostics = {
      ready_level: 'frontend_fallback',
      provider_configured: false,
      provider_mode: 'fallback',
      provider: 'frontend_fallback',
      model: 'none',
      base_url_configured: false,
      api_key_configured: false,
      private_host_allowlist_configured: false,
      private_host_allowlist_count: 0,
      missing: ['backend_api'],
      public_sample_count: 0,
      latest_self_test: null,
      latest_admission: null,
      evidence_ladder: [
        {
          id: 'backend_api',
          label: '后端连接',
          state: 'blocked',
          evidence: '前端无法连接 Provider diagnostics；不能证明配置、预检或真实调用状态。',
          action: '启动 FastAPI 后端并刷新 /models。',
          href: '/models',
          proof_kind: 'fallback',
        },
        {
          id: 'provider_env',
          label: 'Provider 配置',
          state: 'pending',
          evidence: '后端未连接前不会读取 .env 状态。',
          action: '后端在线后再查看 .env 缺失项。',
          href: '/models',
          proof_kind: 'config',
        },
      ],
      admission_state: {
        provider_name: '未连接后端',
        grade: 'NA',
        total_score: 0,
        provider_called: false,
        safe_for_training: false,
        recommendation: '请先启动 FastAPI 后端，再查看 Provider 联调状态检查。',
      },
      blocking_reason: '前端无法连接后端联调状态检查接口；不能证明 Provider 状态。',
      next_actions: [
        { label: '启动 FastAPI 后端', detail: '建议使用 127.0.0.1:8001。', href: '/models', done: false },
        { label: '运行 Provider 自检', detail: '后端在线后再运行文本/视觉自检。', href: '/models', done: false },
      ],
      privacy_notice: 'frontend fallback 不读取或保存 key/base。',
      safety_notice: safetyNotice,
      created_at: fallbackCreatedAt,
    }
    const response = await request<ProviderDiagnostics>('/api/provider/diagnostics', undefined, fallback)
    return normalizeProviderDiagnostics(response, fallback)
  },

  async providerPreflight(apiBase: string): Promise<ProviderPreflight> {
    const fallback: ProviderPreflight = {
      ok: false,
      safety_status: 'frontend_fallback',
      mode: 'fallback',
      normalized_preview: null,
      endpoint_paths: [],
      blocked_reason: 'backend_unavailable',
      warnings: ['后端暂不可用，前端不能证明 API Base 是否会被安全策略允许。'],
      next_actions: ['启动 FastAPI 后端，再查看 Base URL 安全预检。'],
      private_host_allowlist_configured: false,
      private_host_allowlist_used: false,
      key_required_for_call: true,
      request_sent: false,
      key_persisted: false,
      safety_notice: safetyNotice,
    }
    const response = await request<ProviderPreflight>(
      '/api/provider/preflight',
      {
        method: 'POST',
        body: JSON.stringify({ api_base: apiBase }),
      },
      fallback,
    )
    return normalizeProviderPreflight(response, fallback)
  },

  async providerRequestPreview(payload: {
    providerName: string
    apiBase: string
    apiKeyPresent: boolean
    model?: string
    sampleIds: string[]
    focus: string[]
    previewMode: ProviderRequestPreview['preview_mode']
  }): Promise<ProviderRequestPreview> {
    const fallbackCreatedAt = new Date().toISOString()
    const fallback: ProviderRequestPreview = {
      id: `provider_preview_local_${Date.now()}`,
      provider_name: payload.providerName,
      preview_mode: payload.previewMode,
      ready_for_provider_call: false,
      blocked_reason: 'backend_unavailable',
      preflight_mode: 'fallback',
      safety_status: 'frontend_fallback',
      normalized_preview: null,
      endpoint_paths: [],
      request_body_fields: payload.previewMode === 'text_self_test'
        ? ['model', 'messages', 'temperature', 'max_tokens']
        : ['model', 'messages', 'temperature', 'max_tokens', 'messages[].content[].image_url'],
      message_plan: [
        {
          role: 'user',
          contains: '前端 fallback 只能展示本地预览，不能证明后端会如何构造 Provider 请求。',
          image: payload.previewMode !== 'text_self_test',
          sample_ids: payload.sampleIds.slice(0, payload.previewMode === 'visual_self_test' ? 1 : 3),
        },
      ],
      selected_samples: payload.sampleIds.slice(0, payload.previewMode === 'visual_self_test' ? 1 : 3).map((id) => ({
        id,
        source_dataset: '',
        image_url: '',
        question_preview: '后端不可用，无法读取真实样例问题预览。',
        image_attached: false,
        reference_answer_sent: false,
        local_asset_required: payload.previewMode !== 'text_self_test',
      })),
      sample_count: payload.previewMode === 'text_self_test' ? 0 : Math.min(payload.sampleIds.length, payload.previewMode === 'visual_self_test' ? 1 : 3),
      image_attachment_count: 0,
      api_key_present: payload.apiKeyPresent,
      backend_env_key_available: false,
      request_sent: false,
      key_persisted: false,
      audit_logged: false,
      state_updated: false,
      reference_answer_sent: false,
      full_response_persisted: false,
      privacy_trace: [
        { label: 'API key/base', used: false, detail: '前端 fallback 不发送或保存 key；也不能证明后端预演。' },
        { label: 'Provider 请求', used: false, detail: '未发送 Provider 请求。' },
      ],
      next_actions: ['启动 FastAPI 后端后重新查看真实请求预演包。'],
      safety_notice: safetyNotice,
      created_at: fallbackCreatedAt,
    }
    const response = await request<ProviderRequestPreview>(
      '/api/provider/request-preview',
      {
        method: 'POST',
        body: JSON.stringify({
          provider_name: payload.providerName,
          api_base: payload.apiBase,
          api_key_present: payload.apiKeyPresent,
          model: payload.model || undefined,
          selected_sample_ids: payload.sampleIds,
          test_focus: payload.focus,
          preview_mode: payload.previewMode,
        }),
      },
      fallback,
    )
    return normalizeProviderRequestPreview(response, fallback)
  },

  async providerSelfTest(payload: { providerName: string; apiBase: string; apiKey?: string; model?: string; includeImage?: boolean; sampleId?: string }): Promise<ProviderSelfTestResult> {
    const fallbackId = `provider_selftest_local_${Date.now()}`
    const fallbackCreatedAt = new Date().toISOString()
    const fallback: ProviderSelfTestResult = {
      id: fallbackId,
      provider_name: payload.providerName,
      provider_called: false,
      provider_status: {
        provider: 'frontend_fallback',
        model: payload.model || 'none',
        mode: 'fallback',
        ok: false,
        error: 'backend_unavailable',
        image_attached: false,
      },
      probe_excerpt: null,
      image_attached: false,
      image_sample_id: payload.includeImage ? payload.sampleId || null : null,
      image_source_dataset: null,
      visual_probe: Boolean(payload.includeImage),
      audit_logged: false,
      audit_log_id: null,
      self_test_receipt: {
        ...localProviderSelfTestReceipt(payload),
        self_test_id: fallbackId,
        created_at: fallbackCreatedAt,
      },
      key_persisted: false,
      admission_state_updated: false,
      recommendation: payload.includeImage
        ? '后端不可用，未完成 Provider 视觉通道自检；请先启动 FastAPI，再确认公开样例图片是否能附加到请求。'
        : '后端不可用，未完成 Provider 文本轻量自检；请先启动 FastAPI，再运行完整准入探测。',
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: fallbackCreatedAt,
    }
    const response = await request<ProviderSelfTestResult>(
      '/api/provider/self-test',
      {
        method: 'POST',
        body: JSON.stringify({
          provider_name: payload.providerName,
          api_base: payload.apiBase,
          api_key_masked: payload.apiKey ? payload.apiKey.replace(/(.{4}).+(.{2})/, '$1****$2') : '',
          api_key: payload.apiKey || undefined,
          model: payload.model || undefined,
          include_image: Boolean(payload.includeImage),
          sample_id: payload.sampleId || undefined,
        }),
      },
      fallback,
    )
    return normalizeProviderSelfTest(response, fallback)
  },

  async hint(question: Question): Promise<{
    hint: string
    follow_up_question: string
    leak_answer: boolean
    doctor_review_required: boolean
    safety_notice: string
    api_source?: 'backend' | 'fallback'
  }> {
    return request(
      '/api/tutor/hint',
      { method: 'POST', body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner' }) },
      {
        hint: question.false_premise_flag
          ? '这题可能有题干前提陷阱：先判断题干假设是否真的被图像支持。'
          : '先描述图像证据，再判断证据能支持到什么程度。',
        follow_up_question: '请指出一个图像证据，或说明为什么证据不足。',
        leak_answer: false,
        doctor_review_required: true,
        safety_notice: safetyNotice,
      },
    )
  },

  async chat(question: Question, message: string): Promise<TutorChatResponse> {
    const fallback: TutorChatResponse = {
      reply: `围绕“${question.title}”，请先拆出可观察事实，再判断它是否足以支持题干结论。`,
      scope: 'current_question_only',
      generation_mode: 'fallback',
      provider_status: {
        provider: 'frontend_fallback',
        model: 'none',
        mode: 'fallback',
        ok: false,
        error: 'backend_unavailable',
      },
      interaction_tags: ['frontend_fallback'],
      profile_updated: false,
      memory_summary: '当前为前端 fallback 辅导，未写入后端医师画像。',
      doctor_review_required: true,
      safety_notice: safetyNotice,
    }
    const response = await request<TutorChatResponse>(
      '/api/tutor/chat',
      { method: 'POST', body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', message }) },
      fallback,
    )
    return {
      ...fallback,
      ...response,
      reply: asString(response.reply, fallback.reply),
      scope: asString(response.scope, fallback.scope),
      generation_mode: asString(response.generation_mode, fallback.generation_mode),
      provider_status: normalizeProviderStatus(response.provider_status, fallback.provider_status),
      interaction_tags: asStringArray(response.interaction_tags, fallback.interaction_tags),
      profile_updated: asBoolean(response.profile_updated, fallback.profile_updated),
      memory_summary: typeof response.memory_summary === 'string' ? response.memory_summary : fallback.memory_summary,
      doctor_review_required: true,
      safety_notice: asString(response.safety_notice, safetyNotice),
    }
  },

  async challengeBenchmark(question: Question, selectedAnswer: string): Promise<ChallengeBenchmarkResult> {
    const publicAnswer = question.ai_benchmark_answer || question.answer
    const fallback: ChallengeBenchmarkResult = {
      id: `challenge_local_${Date.now()}`,
      question_id: question.id,
      benchmark_name: '挑战基准（公开标注 fallback）',
      benchmark_answer: publicAnswer,
      benchmark_correct: publicAnswer === question.answer,
      doctor_selected_answer: selectedAnswer,
      same_as_doctor: publicAnswer === selectedAnswer,
      generation_mode: 'fallback',
      provider_status: {
        provider: 'frontend_fallback',
        model: 'none',
        mode: 'fallback',
        ok: false,
        error: 'backend_unavailable',
      },
      rationale: '后端挑战基准接口不可用，前端仅展示公开标注 fallback；未写入审计。',
      audit_logged: false,
      profile_updated: false,
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: new Date().toISOString(),
    }
    const response = await request<ChallengeBenchmarkResult>(
      '/api/tutor/challenge-benchmark',
      {
        method: 'POST',
        body: JSON.stringify({
          question_id: question.id,
          learner_id: 'demo_learner',
          selected_answer: selectedAnswer,
        }),
      },
      fallback,
    )
    return normalizeChallengeBenchmark(response, fallback)
  },

  async explain(question: Question, selectedAnswer: string) {
    const local = localSubmission(question, selectedAnswer)
    return request(
      '/api/tutor/explain',
      { method: 'POST', body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', selected_answer: selectedAnswer }) },
      {
        explanation: local.explanation,
        error_tags: local.error_tags,
        atomic_feedback: local.fact_feedback,
        next_recommendation: local.next_recommendation,
        doctor_review_required: true,
        safety_notice: safetyNotice,
      },
    )
  },

  async reportDraft(findingText: string, options: { examType?: string; imageName?: string; templateName?: string; providerName?: string; apiBase?: string; apiKey?: string; model?: string } = {}): Promise<ReportDraft> {
    const fallback = localReportDraft(findingText, options)
    const response = await request<ReportDraft>(
      '/api/report-draft',
      {
        method: 'POST',
        body: JSON.stringify({
          finding_text: findingText,
          exam_type: options.examType || 'gastroscopy',
          image_name: options.imageName,
          template_name: options.templateName,
          provider_name: options.providerName,
          api_base: options.apiBase,
          api_key: options.apiKey || undefined,
          model: options.model || undefined,
        }),
      },
      fallback,
    )
    return normalizeReportDraft(response, fallback)
  },

  async uploadReportImage(file: File): Promise<ImageUploadResponse> {
    const dataUrl = await readFileAsDataUrl(file)
    return request<ImageUploadResponse>(
      '/api/report/image-upload',
      {
        method: 'POST',
        body: JSON.stringify({
          filename: file.name,
          data_url: dataUrl,
          learner_id: 'demo_learner',
        }),
      },
    )
  },

  async reportJudge(originalReport: string, revisedReport: string, options: { providerName?: string; apiBase?: string; apiKey?: string; model?: string } = {}): Promise<ReportJudge> {
    const fallback: ReportJudge = {
      id: `judge_local_${Date.now()}`,
      score: revisedReport.includes('复核') ? 88 : 62,
      strengths: ['已尝试保留观察事实。'],
      issues: revisedReport.includes('确诊') ? ['仍含过强诊断语气。'] : ['建议继续补充不确定性说明。'],
      suggested_revision: `${revisedReport} 建议医生结合完整检查复核。`,
      rubric_scores: { 部位描述: 20, 所见与诊断区分: 22, 不确定性表达: 20, 安全边界: 20 },
      recommended_drills: [
        {
          label: '报告表达进阶',
          href: '/training?source=report_judge&drill=report_safety&question_class=报告纠错',
          reason: '后端不可用时先回到报告纠错题巩固证据边界。',
          drill_id: 'report_safety',
          rubric: '综合表达',
          score: revisedReport.includes('复核') ? 20 : 12,
        },
      ],
      generation_mode: 'fallback',
      provider_status: {
        provider: 'frontend_fallback',
        model: 'none',
        mode: 'fallback',
        ok: false,
        error: 'backend_unavailable',
      },
      provider_feedback: null,
      source_trace: [
        {
          source_type: 'rule_rubric',
          label: '规则 rubric',
          used: true,
          detail: '前端 fallback 评分。',
        },
        {
          source_type: 'provider',
          label: 'Provider 评阅',
          used: false,
          detail: 'backend_unavailable',
        },
      ],
      profile_updated: false,
      memory_summary: '当前为前端 fallback 评分，未写入后端医师画像。',
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: new Date().toISOString(),
    }
    const response = await request<ReportJudge>(
      '/api/report/judge',
      {
        method: 'POST',
        body: JSON.stringify({
          original_report: originalReport,
          revised_report: revisedReport,
          learner_id: 'demo_learner',
          provider_name: options.providerName,
          api_base: options.apiBase,
          api_key: options.apiKey || undefined,
          model: options.model || undefined,
        }),
      },
      fallback,
    )
    return normalizeReportJudge(response, fallback)
  },

  async patientCard(
    summary: string,
    options: { templateId?: string; imageUrl?: string } = {},
  ): Promise<PatientCard> {
    const fallback: PatientCard = {
      id: `card_local_${Date.now()}`,
      card_title: '内镜检查结果说明卡（医生审核前草稿）',
      plain_language_explanation: `这张卡片把医生待审核输入“${summary}”转写为更容易理解的说明。`,
      what_it_means: ['内镜描述反映检查中看到的黏膜外观。', '部分表现需要结合病史和病理。'],
      what_to_watch: ['是否有持续或加重不适。', '是否需要按医嘱复诊。'],
      follow_up_reminder: '请按照医生给出的复诊或检查安排执行。',
      disclaimer: '本卡片为医生审核前沟通草稿；如输入尚未审核，必须先由医生确认后才能用于患者沟通。',
      template_id: options.templateId || 'calm_blue',
      visual_tone: '稳健、清楚、适合打印',
      image_url: options.imageUrl,
      review_status: 'doctor_review_pending',
      share_status: 'locked_pending_review',
      reviewer_name: null,
      review_notes: null,
      reviewed_at: null,
      review_steps: [
        { label: '摘要来自医生确认的报告或训练输入', checked: false, detail: '未确认前，卡片只能用于教学预览。' },
        { label: '未加入未提供的病理、治疗或疗效承诺', checked: false, detail: '高风险医学表述保持解释性和复核边界。' },
        { label: '患者沟通前保留免责声明和复诊提醒', checked: true, detail: '卡片始终提示不替代医生面对面解释。' },
      ],
      generation_mode: 'fallback',
      source_trace: [
        {
          source_type: 'frontend_fallback',
          label: '本地预览草稿',
          used: true,
          detail: '后端不可用时仅在前端生成预览；未写入 patient_card 审计。',
        },
        {
          source_type: 'card_template_kb',
          label: '卡片模板',
          used: false,
          detail: '未连接后端 card_template_knowledge.json。',
        },
      ],
      knowledge_base_id: null,
      audit_logged: false,
      audit_log_id: null,
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: new Date().toISOString(),
    }
    const response = await request<PatientCard>(
      '/api/patient-card',
      {
        method: 'POST',
        body: JSON.stringify({
          diagnosis_summary: summary,
          audience: 'patient',
          template_id: options.templateId || 'calm_blue',
          image_url: options.imageUrl,
        }),
      },
      fallback,
    )
    return normalizePatientCard(response, fallback)
  },

  async approvePatientCard(
    card: PatientCard,
    options: { reviewerName: string; reviewNotes?: string; reviewChecks: Record<string, boolean> },
  ): Promise<PatientCard> {
    // 审核解锁必须写入后端审计；离线时宁可失败，也不能前端伪造已审核状态。
    const response = await request<PatientCard>(
      `/api/patient-card/${encodeURIComponent(card.id)}/approve`,
      {
        method: 'POST',
        body: JSON.stringify({
          reviewer_name: options.reviewerName,
          review_notes: options.reviewNotes || undefined,
          review_checks: options.reviewChecks,
        }),
      },
    )
    return normalizePatientCard(response, card)
  },

  async models(): Promise<ModelProfile[]> {
    const response = await request<{ items: ModelProfile[]; notice: string; safety_notice: string }>('/api/models', undefined, {
      items: mockModels,
      notice: 'mock',
      safety_notice: safetyNotice,
    })
    return response.items.map((item, index) => normalizeModel(item, mockModels[index] || mockModels[0]))
  },

  async selectModel(modelId: string): Promise<ModelProfile> {
    const fallback = mockModels.find((item) => item.id === modelId) || mockModels[0]
    const response = await request<ModelProfile>(
      '/api/models/select',
      { method: 'POST', body: JSON.stringify({ model_id: modelId }) },
    )
    return normalizeModel(response, fallback)
  },

  async modelAdmissionState(): Promise<ModelAdmissionState> {
    const response = await request<{ item: ModelAdmissionState; safety_notice: string }>('/api/models/admission-state', undefined, {
      item: mockDashboard.model_admission_state,
      safety_notice: safetyNotice,
    })
    return normalizeAdmissionState(response.item, mockDashboard.model_admission_state)
  },

  async modelAdmissionTest(payload: { providerName: string; apiBase: string; apiKey?: string; model?: string; sampleIds: string[]; focus: string[] }): Promise<ModelAdmissionResult> {
    const fallbackId = `admission_local_${Date.now()}`
    const fallbackCreatedAt = new Date().toISOString()
    const fallback: ModelAdmissionResult = {
      id: fallbackId,
      provider_name: payload.providerName,
      grade: 'B',
      total_score: 69,
      dimension_scores: { 基础识别: 78, 复杂推理: 70, 错误前提: 66, 报告安全: 72, 接口稳定: 35 },
      risk_items: ['本地 fallback 仅演示评分格式，未完成真实 Provider 准入。'],
      tested_samples: payload.sampleIds,
      provider_called: false,
      is_mock: true,
      evidence: [],
      provider_status: {
        provider: 'frontend_fallback',
        model: payload.model || 'none',
        mode: 'fallback',
        ok: false,
        error: 'backend_unavailable',
      },
      recommendation: '请先连通后端并配置 Provider，再运行真实准入探测。',
      platform_state_updated: false,
      platform_state_summary: '当前为前端 fallback 准入结果，未写入后端平台状态。',
      audit_logged: false,
      audit_log_id: null,
      admission_receipt: {
        ...localAdmissionReceipt(payload),
        admission_id: fallbackId,
        created_at: fallbackCreatedAt,
      },
      doctor_review_required: true,
      safety_notice: safetyNotice,
      created_at: fallbackCreatedAt,
    }
    const response = await request<ModelAdmissionResult>(
      '/api/models/admission-test',
      {
        method: 'POST',
        body: JSON.stringify({
          provider_name: payload.providerName,
          api_base: payload.apiBase,
          api_key_masked: payload.apiKey ? payload.apiKey.replace(/(.{4}).+(.{2})/, '$1****$2') : '',
          api_key: payload.apiKey || undefined,
          model: payload.model || undefined,
          selected_sample_ids: payload.sampleIds,
          test_focus: payload.focus,
        }),
      },
      fallback,
    )
    return normalizeModelAdmission(response, fallback)
  },

  async reportKnowledge(): Promise<KnowledgeBase> {
    const response = await request<{ item: KnowledgeBase; safety_notice: string }>('/api/knowledge/report', undefined, {
      item: {
        id: 'report_kb_fallback',
        templates: [{ name: '胃镜结构化训练模板', sections: ['检查部位', '黏膜所见', '复核点'], review_required: true }],
        sample_findings: ['胃窦黏膜充血，可见散在糜烂，未见明确活动性出血。'],
      },
      safety_notice: safetyNotice,
    })
    return response.item
  },

  async cardKnowledge(): Promise<KnowledgeBase> {
    const response = await request<{ item: KnowledgeBase; safety_notice: string }>('/api/knowledge/cards', undefined, {
      item: {
        id: 'card_kb_fallback',
        templates: [
          { id: 'calm_blue', name: '清爽蓝-门诊沟通', tone: '稳健、清楚、适合打印' },
          { id: 'warm_green', name: '暖绿-术后提醒', tone: '温和、鼓励、适合分享' },
        ],
        visual_rules: ['必须包含图像区域', '必须包含医生审核标识', '必须包含免责声明'],
      },
      safety_notice: safetyNotice,
    })
    return response.item
  },

  async skills(): Promise<SkillDefinition[]> {
    const response = await request<{ items: SkillDefinition[]; total: number }>('/api/skills', undefined, {
      items: mockSkills,
      total: mockSkills.length,
    })
    return response.items
  },

  async runSkill(skill: SkillDefinition, payload: SkillRunPayload = { question_id: 'q005' }) {
    const doctorReviewRequired = skill.risk_level !== 'low'
    return request<Record<string, unknown>>(
      '/api/skills/run',
      { method: 'POST', body: JSON.stringify({ skill_id: skill.id, payload, learner_id: 'demo_learner' }) },
      {
        message: '已在本地 fallback 中模拟运行。',
        doctor_review_required: doctorReviewRequired,
        safety_notice: safetyNotice,
        skill_run_receipt: {
          audit_log_id: null,
          skill_id: skill.id,
          skill_name: skill.name,
          risk_level: skill.risk_level,
          learner_id: 'demo_learner',
          input_trace: fallbackSkillInputTrace(payload),
          source_trace: [
            {
              source_type: 'frontend_fallback',
              label: '本地预览',
              used: true,
              detail: '后端 skills/run 不可用；未写入 skill_run 审计。',
            },
          ],
          next_actions: fallbackSkillNextActions(skill.category),
          doctor_review_required: doctorReviewRequired,
          created_at: new Date().toISOString(),
        },
      },
    )
  },

  async audit(): Promise<AuditLog[]> {
    const response = await request<{ items: AuditLog[]; total: number }>('/api/audit', undefined, {
      items: mockAuditLogs,
      total: mockAuditLogs.length,
    })
    return response.items
  },

  async challengeAuditReceipt(): Promise<AuditLog | null> {
    const response = await request<{ items: AuditLog[]; total: number; api_source?: ApiSource }>('/api/audit', undefined, {
      items: [],
      total: 0,
    })
    if (response.api_source === 'fallback') return null
    return response.items.find((item) => item.event_type === 'challenge_benchmark') || null
  },
}

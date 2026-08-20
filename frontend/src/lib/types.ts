export type RiskLevel = 'low' | 'medium' | 'high'
export type QuestionType = '单选' | '多选' | '判断' | '问答评分' | '报告修改'
export type ReviewStatus = '未开始' | '待复盘' | '已掌握' | '收藏中'
export type GenerationMode = 'provider' | 'rule' | 'fallback'

export type ProviderStatus = {
  configured?: boolean
  provider: string
  model: string
  mode: GenerationMode | string
  ok?: boolean
  error?: string | null
  latency_ms?: number | null
  sample_count?: number
  provider_success_count?: number
  reference_aligned_count?: number
  blind_probe?: boolean
  image_attached?: boolean
  base_url_configured?: boolean
  api_key_configured?: boolean
  private_host_allowlist_configured?: boolean
  private_host_allowlist_count?: number
  safety_notice?: string
}

export type ProviderAuditSummary = {
  id?: string | null
  event_type?: string | null
  summary?: string | null
  risk_level?: RiskLevel | string | null
  created_at?: string | null
}

export type ProviderDiagnosticAction = {
  label: string
  detail: string
  href: string
  done: boolean
}

export type ProviderEvidenceLadderStep = {
  id: string
  label: string
  state: 'done' | 'current' | 'pending' | 'blocked' | string
  evidence: string
  action: string
  href: string
  proof_kind: string
}

export type ProviderDiagnostics = {
  ready_level: string
  provider_configured: boolean
  provider_mode: string
  provider: string
  model: string
  base_url_configured: boolean
  api_key_configured: boolean
  private_host_allowlist_configured: boolean
  private_host_allowlist_count: number
  missing: string[]
  public_sample_count: number
  latest_self_test?: ProviderAuditSummary | null
  latest_admission?: ProviderAuditSummary | null
  evidence_ladder: ProviderEvidenceLadderStep[]
  admission_state: {
    provider_name: string
    grade: string
    total_score: number
    provider_called: boolean
    safe_for_training: boolean
    recommendation: string
  }
  blocking_reason: string
  next_actions: ProviderDiagnosticAction[]
  privacy_notice: string
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ProviderPreflight = {
  ok: boolean
  safety_status: string
  mode: string
  normalized_preview?: string | null
  endpoint_paths: string[]
  blocked_reason?: string | null
  warnings: string[]
  next_actions: string[]
  private_host_allowlist_configured: boolean
  private_host_allowlist_used: boolean
  key_required_for_call: boolean
  request_sent: boolean
  key_persisted: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type ProviderPreviewMode = 'text_self_test' | 'visual_self_test' | 'admission'

export type ProviderRequestPreview = {
  id: string
  provider_name: string
  preview_mode: ProviderPreviewMode
  ready_for_provider_call: boolean
  blocked_reason?: string | null
  preflight_mode: string
  safety_status: string
  normalized_preview?: string | null
  endpoint_paths: string[]
  request_body_fields: string[]
  message_plan: { role: string; contains: string; image: boolean; sample_ids?: string[] }[]
  selected_samples: {
    id?: string
    source_dataset?: string
    image_url?: string
    question_preview?: string
    image_attached?: boolean
    reference_answer_sent?: boolean
    local_asset_required?: boolean
  }[]
  sample_count: number
  image_attachment_count: number
  api_key_present: boolean
  backend_env_key_available: boolean
  request_sent: boolean
  key_persisted: boolean
  audit_logged: boolean
  state_updated: boolean
  reference_answer_sent: boolean
  full_response_persisted: boolean
  privacy_trace: { label: string; used: boolean; detail: string }[]
  next_actions: string[]
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type SourceTraceItem = {
  source_type: string
  label: string
  used: boolean
  detail: string
  latency_ms?: number | null
}

export type AtomicFact = {
  id: string
  fact: string
  expected: string
  supported: boolean
  evidence: string
  skill_dimension: '病灶识别' | '部位定位' | '属性判断' | '数量判断' | '事实组合' | '证据不足识别'
}

export type Question = {
  id: string
  title: string
  image_url?: string
  image_placeholder: string
  case_summary: string
  question: string
  options: string[]
  answer: string
  explanation: string
  complexity: 1 | 2 | 3
  question_class: '基础识别' | '部位定位' | '病变属性' | '报告纠错' | '一图多问'
  source_type: '公开基础问答' | '公开复杂问答' | '公开综合基准' | '医院合作中文病例' | '教学样例'
  atomic_trace: AtomicFact[]
  false_premise_flag: boolean
  teaching_tags: string[]
  difficulty: '入门' | '进阶' | '挑战'
  doctor_review_required: boolean
  safety_notice: string
  body_part: string
  task: string
  question_type: QuestionType
  source_dataset: string
  citation_note: string
  is_favorited: boolean
  review_status: ReviewStatus
  ai_benchmark_answer?: string | null
  expected_keywords: string[]
}

export type SubmissionResponse = {
  id: string
  question_id: string
  learner_id: string
  selected_answer: string
  is_correct: boolean
  score: number
  error_tags: string[]
  fact_feedback: AtomicFact[]
  explanation: string
  next_recommendation: string
  created_at: string
  profile_updated: boolean
  doctor_review_required: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type ExamSessionAttempt = {
  question_id: string
  title: string
  selected_answer: string
  correct_answer: string
  is_correct: boolean
  score: number
  error_tags: string[]
}

export type ExamSessionResponse = {
  id: string
  learner_id: string
  answered_count: number
  correct_count: number
  accuracy: number
  average_score: number
  wrong_questions: string[]
  elapsed_seconds: number
  finished_reason: string
  profile_updated: boolean
  memory_summary: string
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ExamSessionRecord = {
  id: string
  session_id: string
  date: string
  answered_count: number
  correct_count: number
  accuracy: number
  average_score: number
  wrong_questions: string[]
  elapsed_seconds: number
  finished_reason: string
  profile_updated: boolean
  created_at: string
}

export type LearnerProfile = {
  learner_id: string
  name: string
  title: string
  department: string
  hospital: string
  training_stage: string
  training_goal: string
  total_questions: number
  accuracy: number
  completed_today: number
  daily_target: number
  streak_days: number
  favorite_questions: string[]
  wrong_questions: string[]
  skill_scores: Record<string, number>
  weakness_tags: string[]
  recent_errors: string[]
  recommended_question_classes: string[]
  growth_trend: { date: string; accuracy: number; evidence: number; report: number }[]
  training_records: { date: string; question_id: string; score: number; result: string }[]
  exam_sessions: ExamSessionRecord[]
  question_type_coverage: Record<string, number>
  updated_at: string
}

export type ModelProfile = {
  id: string
  name: string
  provider_type: 'local' | 'api' | 'mock'
  model_family: '通用多模态' | '医学多模态' | '内镜领域' | '闭源API'
  recommended_roles: string[]
  risk_tags: string[]
  ability_scores: Record<string, number>
  grade: 'S' | 'A' | 'B' | 'C'
  is_active: boolean
}

export type SkillDefinition = {
  id: string
  name: string
  description: string
  category: 'training' | 'feedback' | 'report' | 'card' | 'safety' | 'audit'
  enabled: boolean
  risk_level: RiskLevel
  input_schema: Record<string, unknown>
  output_schema: Record<string, unknown>
}

export type SkillRunPayload = Record<string, string | number | boolean | null | undefined>

export type SkillRunTraceItem = {
  source_type: string
  label: string
  used: boolean
  detail: string
}

export type SkillRunReceipt = {
  audit_log_id?: string | null
  skill_id: string
  skill_name: string
  risk_level: RiskLevel
  learner_id: string
  input_trace: SkillRunTraceItem[]
  source_trace: SkillRunTraceItem[]
  next_actions: { label: string; href: string }[]
  doctor_review_required: boolean
  created_at: string
}

export type AuditLog = {
  id: string
  event_type:
    | 'question_view'
    | 'answer_submit'
    | 'tutor_reply'
    | 'challenge_benchmark'
    | 'exam_session'
    | 'report_draft'
    | 'patient_card'
    | 'patient_card_approve'
    | 'report_judge'
    | 'skill_run'
    | 'model_select'
    | 'provider_self_test'
    | 'model_admission'
    | 'favorite_update'
    | 'image_upload'
    | 'demo_check'
    | 'safety_warning'
  user_id: string
  entity_id?: string | null
  summary: string
  risk_level: RiskLevel
  doctor_review_required: boolean
  metadata?: Record<string, unknown>
  created_at: string
}

export type ReportDraft = {
  id: string
  input_finding_text: string
  exam_type: string
  structured_findings: string[]
  draft_impression: string[]
  review_points: string[]
  uncertainty_notes: string[]
  template_name: string
  evidence_source: string[]
  draft_status: 'ai_draft' | 'needs_human_review' | 'reviewed' | 'signed'
  exam_context: Record<string, unknown>
  image_quality: {
    clarity?: string
    artifacts?: string[]
    single_frame_limitation?: boolean
    [key: string]: unknown
  }
  evidence_ledger: {
    evidence_id: string
    source_type: string
    source_ref: string
    supports: string[]
    audit_log_id?: string | null
    sha256_prefix?: string | null
    width?: number | null
    height?: number | null
  }[]
  hallucination_audit: {
    audit_passed?: boolean
    unsupported_claims?: string[]
    high_risk_flags?: string[]
    required_rewrites?: string[]
    evidence_policy?: string
    [key: string]: unknown
  }
  review_tasks: string[]
  generation_mode: GenerationMode | string
  provider_status: ProviderStatus
  model_observation?: string | null
  source_trace: SourceTraceItem[]
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ReportJudge = {
  id: string
  score: number
  strengths: string[]
  issues: string[]
  suggested_revision: string
  rubric_scores: Record<string, number>
  recommended_drills: {
    label: string
    href: string
    reason: string
    drill_id?: string
    rubric?: string
    score?: number
  }[]
  generation_mode: GenerationMode | string
  provider_status: ProviderStatus
  provider_feedback?: string | null
  source_trace: SourceTraceItem[]
  profile_updated: boolean
  memory_summary?: string | null
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type PatientCard = {
  id: string
  card_title: string
  plain_language_explanation: string
  what_it_means: string[]
  what_to_watch: string[]
  follow_up_reminder: string
  disclaimer: string
  template_id: string
  visual_tone: string
  image_url?: string | null
  review_status: 'doctor_reviewed_input' | 'doctor_review_pending'
  share_status?: 'locked_pending_review' | 'reviewed_ready_to_share'
  reviewer_name?: string | null
  review_notes?: string | null
  reviewed_at?: string | null
  review_steps?: { label: string; checked: boolean; detail: string }[]
  generation_mode?: GenerationMode | string
  source_trace?: SourceTraceItem[]
  knowledge_base_id?: string | null
  audit_logged?: boolean
  audit_log_id?: string | null
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ModelAdmissionState = {
  updated_at: string
  last_admission_id: string
  provider_name: string
  grade: 'S' | 'A' | 'B' | 'C'
  total_score: number
  mode: string
  provider_called: boolean
  is_mock: boolean
  tested_samples: string[]
  risk_items: string[]
  recommendation: string
  reference_aligned_count?: number
  safe_for_training: boolean
}

export type ProviderSelfTestResult = {
  id: string
  provider_name: string
  provider_called: boolean
  provider_status: ProviderStatus
  probe_excerpt?: string | null
  image_attached: boolean
  image_sample_id?: string | null
  image_source_dataset?: string | null
  visual_probe: boolean
  audit_logged: boolean
  audit_log_id?: string | null
  self_test_receipt?: ProviderEvidenceReceipt | null
  key_persisted: boolean
  admission_state_updated: boolean
  recommendation: string
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ChallengeBenchmarkResult = {
  id: string
  question_id: string
  benchmark_name: string
  benchmark_answer: string
  benchmark_correct: boolean
  doctor_selected_answer: string
  same_as_doctor: boolean
  generation_mode: GenerationMode | 'public_annotation' | string
  provider_status: ProviderStatus
  rationale: string
  audit_logged: boolean
  profile_updated: boolean
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ReadinessTone = 'green' | 'amber' | 'blue' | 'red' | 'neutral'

export type PlatformReadinessModule = {
  id: string
  label: string
  status: string
  detail: string
  href: string
  tone: ReadinessTone
}

export type KnowledgeSourceChainItem = {
  id: string
  label: string
  source_file: string
  record_count: number
  sample_ids: string[]
  used_by: string[]
  proof: string
  href: string
  tone: ReadinessTone
}

export type RealSampleCoverageBucket = {
  label: string
  count: number
}

export type RealSampleCoverage = {
  source_file: string
  local_data_hint: string
  total_records: number
  mapped_question_count: number
  asset_checked_count: number
  asset_present_count: number
  missing_assets: string[]
  dataset_distribution: RealSampleCoverageBucket[]
  use_distribution: RealSampleCoverageBucket[]
  complexity_distribution: RealSampleCoverageBucket[]
  sample_ids: string[]
  coverage_note: string
}

export type LatestExamReplay = {
  id: string
  session_id: string
  date: string
  answered_count: number
  correct_count: number
  accuracy: number
  average_score: number
  wrong_count: number
  wrong_questions: string[]
  elapsed_seconds: number
  profile_updated: boolean
  created_at: string
  href: string
  profile_href: string
  status: string
  detail: string
}

export type DemoPathStep = {
  step: number
  title: string
  detail: string
  href: string
  expected_state: string
}

export type PlatformReadiness = {
  generated_at: string
  overall_score: number
  backend_ready: boolean
  provider_ready: boolean
  provider_mode: string
  knowledge_ready: boolean
  memory_ready: boolean
  qbank_count: number
  real_sample_count: number
  real_sample_coverage: RealSampleCoverage
  report_template_count: number
  training_record_count: number
  exam_session_count: number
  latest_exam_replay?: LatestExamReplay | null
  audit_log_count: number
  admission_grade: string
  admission_provider_called: boolean
  knowledge_source_chain: KnowledgeSourceChainItem[]
  evidence_receipts: PlatformReadinessModule[]
  modules: PlatformReadinessModule[]
  demo_path: DemoPathStep[]
  gaps: string[]
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type DeliveryDoctorContext = {
  learner_id: string
  name: string
  title: string
  department: string
  hospital?: string
  training_stage: string
  daily_target: number
  completed_today: number
  streak_days: number
}

export type DeliveryPlatformSummary = {
  overall_score: number
  backend_ready: boolean
  provider_mode: string
  provider_ready: boolean
  knowledge_ready: boolean
  memory_ready: boolean
  qbank_count: number
  real_sample_count: number
  real_sample_coverage?: RealSampleCoverage
  report_template_count: number
  audit_log_count: number
  exam_session_count: number
  admission_grade: string
  admission_provider_called: boolean
}

export type DeliveryWorkflowProof = {
  id: string
  name: string
  status: string
  evidence: string
  route: string
}

export type DeliveryAuditEventCount = {
  event_type: string
  count: number
}

export type DeliveryProviderState = {
  configured: boolean
  mode: string
  provider_declared: boolean
  model: string
  self_test_logged: boolean
  self_test_count: number
  self_test_verified: boolean
  latest_self_test_state: string
  admission_provider_called: boolean
  admission_state_kind: string
  admission_safe_for_training: boolean
  real_inference_verified: boolean
  verification_label: string
  verification_note: string
}

export type DeliveryVerificationCommand = {
  name: string
  command: string
  covers: string
}

export type DeliveryReportIntegrity = {
  source: string
  writes_state: boolean
  secrets_included: boolean
  api_key_returned: boolean
  provider_base_returned: boolean
}

export type DeliveryReport = {
  generated_at: string
  title: string
  scope: string
  doctor_context: DeliveryDoctorContext
  platform_summary: DeliveryPlatformSummary
  workflow_proofs: DeliveryWorkflowProof[]
  knowledge_source_chain: KnowledgeSourceChainItem[]
  evidence_receipts: PlatformReadinessModule[]
  audit_event_counts: DeliveryAuditEventCount[]
  provider_state: DeliveryProviderState
  verification_commands: DeliveryVerificationCommand[]
  current_boundaries: string[]
  gaps: string[]
  safety_notice: string
  report_integrity: DeliveryReportIntegrity
  api_source?: 'backend' | 'fallback'
}

export type DemoCheckReceipt = {
  id: string
  label: string
  status: string
  detail: string
  tone: ReadinessTone
}

export type DemoCheckResult = {
  id: string
  learner_id: string
  mode: 'sandbox' | 'persisted' | string
  persisted: boolean
  write_verified: boolean
  restored_after_run: boolean
  restore_verified?: boolean
  question_id: string
  question_title: string
  source_dataset: string
  provider_mode: string
  provider_ready: boolean
  profile_before: {
    total_questions: number
    training_records: number
    completed_today: number
  }
  profile_after: {
    total_questions: number
    training_records: number
    completed_today: number
    updated_at: string
  }
  audit_before_count: number
  audit_after_count: number
  audit_delta: number
  audit_event_types?: string[]
  receipts: DemoCheckReceipt[]
  profile_updated: boolean
  audit_logged: boolean
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type DashboardPayload = {
  today_training: {
    completed: number
    target: number
    streak_days: number
    review_queue: number
  }
  learner_profile: LearnerProfile
  ability_radar: { dimension: string; score: number }[]
  recommended_training: { label: string; count: number }[]
  today_plan: { label: string; target: number; status: string; href: string }[]
  continue_training: { question_id: string; title: string; source_dataset: string; reason: string }
  favorite_count: number
  wrong_count: number
  recent_tutor_summary: string[]
  growth_trend: { date: string; accuracy: number; evidence: number; report: number }[]
  active_model: ModelProfile
  model_admission_state: ModelAdmissionState
  platform_readiness: PlatformReadiness
  safety_notice: string
  mock_evaluation_notice: string
  reference_inspirations: string[]
  api_source?: 'backend' | 'fallback'
}

export type TrainingState = {
  profile: LearnerProfile
  wrong_questions: string[]
  favorite_questions: string[]
  exam_sessions: ExamSessionRecord[]
  latest_exam_session?: ExamSessionRecord | null
  review_queue: number
  next_plan: { label: string; count: number; reason: string }[]
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type KnowledgeBase = {
  id: string
  source?: string
  templates?: { id?: string; name: string; tone?: string; sections?: string[]; criteria?: string[]; max_score?: number; review_required?: boolean }[]
  sample_findings?: string[]
  visual_rules?: string[]
}

export type ModelAdmissionResult = {
  id: string
  provider_name: string
  grade: 'S' | 'A' | 'B' | 'C'
  total_score: number
  dimension_scores: Record<string, number>
  risk_items: string[]
  tested_samples: string[]
  provider_called: boolean
  is_mock: boolean
  evidence: {
    sample_id?: string
    source_dataset?: string
    question?: string
    reference_annotation?: string
    provider_answer?: string
    blind_probe?: boolean
    reference_match?: string
    answer_overlap?: number
    provider_called?: boolean
    provider_mode?: string
    latency_ms?: number | null
    observation_excerpt?: string
    error?: string | null
  }[]
  provider_status: ProviderStatus
  recommendation: string
  platform_state_updated: boolean
  platform_state_summary?: string | null
  audit_logged: boolean
  audit_log_id?: string | null
  admission_receipt?: ProviderEvidenceReceipt | null
  doctor_review_required: true
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type ProviderEvidenceReceipt = {
  audit_log_id?: string | null
  event_type?: string
  self_test_id?: string
  admission_id?: string
  provider_name?: string
  provider_called?: boolean
  visual_probe?: boolean
  image_attached?: boolean
  grade?: string
  total_score?: number
  platform_state_updated?: boolean
  state_kind?: 'self_test' | 'provider_admission' | 'rule_draft' | string
  input_trace?: { source_type?: string; label: string; used: boolean; detail: string }[]
  provider_trace?: { source_type?: string; label: string; used: boolean; detail: string; latency_ms?: number | null }[]
  privacy_trace?: { label: string; used: boolean; detail: string }[]
  next_actions?: { label: string; href: string }[]
  created_at?: string
}

export type TutorChatResponse = {
  reply: string
  scope: string
  generation_mode: GenerationMode | string
  provider_status: ProviderStatus
  interaction_tags: string[]
  profile_updated: boolean
  memory_summary?: string | null
  doctor_review_required: boolean
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type ImageUploadResponse = {
  image_name: string
  original_filename: string
  bytes: number
  mime_type: string
  width?: number | null
  height?: number | null
  sha256_prefix: string
  source_type: 'uploaded_image'
  provider_input_allowed: boolean
  audit_logged: boolean
  audit_log_id?: string | null
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type MetricValue = {
  value: number
  source: string
  trend?: string
}

export type ModelEvaluationCard = {
  id: string
  display_name: string
  group: 'domain' | 'general' | 'medical' | 'closed' | string
  group_label: string
  status: string
  active: boolean
  metrics: Record<string, MetricValue>
  recommendation: string
  provenance: {
    label: string
    sample_scope: string
    public_label_only: boolean
  }
}

export type ModelEvaluationPayload = {
  summary: {
    title: string
    headline: string
    sample_scope: string
    model_count: number
    top_model_id: string
    top_model_name: string
    updated_at: string
  }
  groups: { id: string; label: string; description: string }[]
  metrics: string[]
  items: ModelEvaluationCard[]
  radar: Record<string, string | number>[]
  complexity_curve: Record<string, string | number>[]
  attribute_breakdown: Record<string, string | number>[]
  experiment?: {
    status: string
    created_at: string
    scope: string
    model: string
    precision: string
    device: string
    software: Record<string, string>
    config: Record<string, unknown>
    metrics: {
      cases: number
      case_exact_rate: number
      micro_fact_accuracy: number
      latency_p50_s: number
      latency_p95_s: number
      throughput_cases_per_min: number
      generation_tokens_per_s: number
      peak_gpu_memory_gib: number
      wall_time_s: number
    }
    artifact: string
  } | null
  experiment_v21?: {
    schema_version: string
    status: string
    claim_boundary: string
    completed_run_count: number
    runs: Record<string, {
      cases: number
      case_exact_rate: number
      micro_fact_accuracy: number
      latency_p50_s: number
      latency_p95_s: number
      throughput_cases_per_min: number
      generation_tokens_per_s: number
      peak_gpu_memory_gib: number
      model_memory_footprint_gib: number
      model_load_s: number
      wall_time_s: number
    }>
    comparisons: {
      quantization: Record<string, {
        accuracy: number
        p50_s: number
        peak_gpu_memory_gib: number
        accuracy_delta: number
        p50_relative_delta: number
        peak_memory_relative_delta: number
      }>
      adapter: {
        accuracy_before: number
        accuracy_after: number
        accuracy_delta: number
        p50_before_s: number
        p50_after_s: number
        p50_relative_delta: number
      }
      structured_prompt: {
        accuracy_before: number
        accuracy_after: number
        accuracy_delta: number
        p50_before_s: number
        p50_after_s: number
        p50_relative_delta: number
        json_valid_rate_before: number
        json_valid_rate_after: number
      }
      zero_shot_models: Record<string, {
        model: string
        accuracy: number
        p50_s: number
        peak_gpu_memory_gib: number
      }>
    }
    alignment?: {
      schema_version: string
      status: string
      claim_boundary: string
      model: string
      method: string
      data: { train_pairs: number; test_images: number; split_overlap: number }
      config: { steps: number; beta: number; learning_rate: number; lora_rank: number; batch_size: number }
      before: { cases: number; fact_accuracy: number; json_valid_rate: number; safety_boundary_rate: number; latency_p50_s: number }
      after: { cases: number; fact_accuracy: number; json_valid_rate: number; safety_boundary_rate: number; latency_p50_s: number }
      delta: { fact_accuracy: number; json_valid_rate: number; safety_boundary_rate: number }
      train: {
        initial_loss: number
        final_loss: number
        final_cycle_preference_rate: number
        peak_gpu_memory_gib: number
        trainable_parameters: number
        trainable_ratio: number
        adapter_size_bytes: number
      }
    } | null
    alignment_stability?: {
      schema_version: string
      status: 'completed_with_observed_failure' | string
      claim_boundary: string
      protocol: {
        seeds: number[]
        train_pairs: number
        test_images: number
        split_overlap: number
        steps: number
        beta: number
        learning_rate: number
      }
      initial_runs: {
        total: number
        completed: number
        invalid_numeric: number
        successful_safety_boundary_rate: number
        successful_fact_accuracy: number
        successful_json_valid_rate: number
      }
      gatecheck: {
        seed: number
        finite_scalar_fail_closed: boolean
        retry_completed: boolean
        safety_boundary_rate: number
        fact_accuracy: number
        json_valid_rate: number
      }
      artifact: string
    } | null
    artifact: string
  } | null
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type CustomModelEvaluationResult = {
  id: string
  display_name: string
  model: string
  connection_status?: string
  evaluation_mode?: string
  provider_called?: boolean
  metrics: Record<string, number>
  summary: string
  status_label: string
  provider_status?: ProviderStatus
  key_persisted?: boolean
  full_response_persisted?: boolean
  privacy_status?: string
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

export type PracticeState = {
  profile: LearnerProfile
  progress: {
    completed: number
    target: number
    percent: number
    review_queue: number
  }
  wrong_questions: string[]
  favorite_questions: string[]
  next_plan: { label: string; count: number; reason: string }[]
  question_types: { name: string; summary: string; tone: string }[]
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type PracticeQuestionsPayload = {
  items: Question[]
  total: number
  pool_total?: number
  pool_seed?: number | null
  available_type_counts?: Record<string, number>
  question_types: PracticeState['question_types']
  safety_notice: string
  api_source?: 'backend' | 'fallback'
}

export type PracticeSubmitResponse = SubmissionResponse & {
  profile?: LearnerProfile
  practice_summary?: {
    result: string
    profile_delta: string
    next_step: string
  }
}

export type PortfolioCaseFact = {
  id: string
  label: string
  aliases: string[]
  dimension: string
  evidence: string
}

export type PortfolioCase = {
  id: string
  title: string
  source_dataset: string
  source_type: string
  image_url: string
  difficulty: string
  prompt: string
  gold_answer: string
  facts: PortfolioCaseFact[]
  next_recommendation: string
}

export type PortfolioStudyCase = {
  id: string
  title: string
  source_dataset: string
  source_type: string
  image_url: string
  difficulty: string
  prompt: string
  body_part: string
  tags: string[]
  estimated_minutes: number
  completed: boolean
  best_score: number | null
  wrong: boolean
  favorited: boolean
  last_practiced_at?: string | null
  recommendation_reason?: string | null
  progress?: {
    attempt_count?: number
    last_score?: number
    best_score?: number
    completed?: boolean
    is_wrong?: boolean
    review_interval_days?: number
    review_due_at?: string | null
    review_stage?: string
    review_due?: boolean
    mastery?: number
  }
}

export type PortfolioStudyPayload = {
  learner: {
    completed_today: number
    daily_target: number
    streak_days: number
    total_completed: number
    accuracy: number | null
    wrong_count: number
    favorite_count: number
  }
  today_plan: {
    title: string
    reason: string
    generated_by: string
    items: PortfolioStudyCase[]
  }
  library: {
    items: PortfolioStudyCase[]
    body_parts: string[]
  }
  continue_case_id?: string | null
  source: 'backend' | 'fallback' | string
  safety_notice: string
}

export type PortfolioAdaptiveRecommendation = {
  case_id: string
  case_title: string
  strategy: 'unfinished_first' | 'weakness_and_spaced_review' | string
  priority: 'high' | 'normal' | string
  weakest_dimension?: string | null
  mastery?: number
  reason: string
}

export type PortfolioAgentRun = {
  run_id: string
  parent_run_id?: string | null
  replay_id?: string | null
  case_id: string
  case_title: string
  learner_id: string
  status: 'completed' | 'blocked' | string
  plan: { policy_id?: string; goal: string; tool_sequence: string[]; max_replans?: number; constraints: string[] }
  trace: Array<{
    node: 'Plan' | 'Act' | 'Recovery' | 'Observe' | 'Verify' | 'Memory'
    status: 'completed' | 'blocked'
    summary: string
    latency_ms: number
    receipt_ids: string[]
  }>
  tool_receipts: Array<{
    call_id: string
    tool_name: string
    success: boolean
    input: Record<string, unknown>
    output: Record<string, unknown>
    evidence_ids: string[]
    latency_ms: number
    attempt?: number
    error_code?: 'timeout' | 'unavailable' | 'validation_error' | 'tool_exception' | null
    retryable?: boolean
    recovered_from_call_id?: string | null
  }>
  retrieval?: {
    retrieval_mode: string
    query: string
    top_k: number
    metadata_filters: Record<string, string>
    candidate_count: number
    items: Array<{
      rank: number
      score: number
      evidence_id: string
      label: string
      evidence: string
      source_dataset: string
      case_id: string
      metadata: Record<string, string>
    }>
  }
  result: {
    score: number
    matched_fact_ids: string[]
    missed_fact_ids: string[]
    fact_precision: number
    fact_recall: number
    fact_f1: number
    feedback: string
    next_recommendation: string
    adaptive_recommendation?: PortfolioAdaptiveRecommendation | null
    observed_evidence: Array<{ evidence_id: string; label: string; evidence: string }>
  }
  verification: Record<string, boolean>
  memory_delta: {
    learner_id: string
    mode: string
    committed: boolean
    dimension_deltas: Array<{
      dimension: string
      before: number
      delta: number
      after_preview: number
      reason: string
    }>
    reason: string
    review_schedule?: {
      interval_days: number
      due_at: string
      stage: 'relearn_now' | 'review_tomorrow' | 'spaced_review' | string
    }
    adaptive_recommendation?: PortfolioAdaptiveRecommendation | null
  }
  context_manifest?: {
    budget_tokens: number
    estimator: string
    included_estimated_tokens: number
    total_estimated_tokens: number
    chunks: Array<{
      source_type: string
      source_id: string
      priority: number
      trust_level: string
      char_count: number
      estimated_tokens: number
      included: boolean
      drop_reason?: string | null
    }>
  }
  usage_ledger?: {
    execution_mode: string
    model_calls: number
    prompt_tokens: number
    completion_tokens: number
    provider_usage?: Record<string, unknown> | null
    estimated_context_tokens: number
    estimated_cost?: number | null
    currency?: string | null
    source: string
  }
  checkpoint?: {
    checkpoint_id: string
    replayable: boolean
    storage: string
    input_hash: string
    contains_raw_input_in_response: boolean
  }
  doctor_review_required: boolean
  safety_notice: string
  created_at: string
  latency_ms: number
}

export type PortfolioAgentStreamEvent =
  | { event: 'stage'; stage: PortfolioAgentRun['trace'][number] }
  | { event: 'final'; run: PortfolioAgentRun }
  | { event: 'error'; error_code: string; message: string }

export type PortfolioEvalArtifact = {
  eval_id: string
  metric_version: string
  created_at: string
  conditions: Record<string, unknown>
  metrics: {
    case_count: number
    task_completion_rate: number
    tool_selection_accuracy: number
    evidence_coverage_rate: number
    safety_pass_rate: number
    structured_output_rate: number
    mean_fact_f1: number
    latency_p50_ms: number
    latency_p95_ms: number
    retrieval_recall_at_1?: number
    retrieval_recall_at_3?: number
    recovery_success_rate?: number
    recovery_rate?: number
    checkpoint_replay_rate?: number
  }
  cases: Array<Record<string, unknown>>
  safety_probes: Array<Record<string, unknown>>
}

export type ReportRevisionResponse = {
  id: string
  revised_report: string
  instruction: string
  judge: ReportJudge
  generation_mode?: GenerationMode | string
  provider_status?: ProviderStatus
  generation_info?: Record<string, unknown>
  source_trace?: SourceTraceItem[]
  key_persisted?: boolean
  privacy_status?: string
  safety_notice: string
  created_at: string
  api_source?: 'backend' | 'fallback'
}

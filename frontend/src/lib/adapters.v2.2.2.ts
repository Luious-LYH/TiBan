// v2.2.2 API 适配器 - 统一前后端类型
import type * as V222 from './types.v2.2.2'
import type * as Legacy from './types'

/* ==================== 后端 → 前端适配 ==================== */

export function adaptQuestionFromBackend(raw: any): V222.Question {
  return {
    id: raw.id || raw.question_id || '',
    bank_id: raw.bank_id || 'default',
    title: raw.title || '',
    question: raw.question || raw.case_summary || '',
    question_type: mapQuestionType(raw.question_type || raw.type),
    options: adaptOptions(raw.options),
    answer: raw.answer || '',
    explanation: raw.explanation || '',
    knowledge_points: raw.knowledge_points || raw.teaching_tags || [],
    body_part: raw.body_part || '',
    modality: raw.image_url ? 'image_text' : 'text',
    image_url: raw.image_url,
    image_alt: raw.image_placeholder || raw.image_alt,
    difficulty: raw.difficulty || 'medium',
    tags: raw.teaching_tags || raw.tags || [],
    source: raw.source_dataset || raw.source_type,
    version: raw.version || '1.0',
  }
}

function mapQuestionType(raw: string | undefined): V222.QuestionType {
  if (!raw) return 'short_answer'

  const map: Record<string, V222.QuestionType> = {
    '单选': 'single_choice',
    '多选': 'multiple_choice',
    '判断': 'true_false',
    '问答评分': 'short_answer',
    '报告修改': 'report_revision',
    'single_choice': 'single_choice',
    'multiple_choice': 'multiple_choice',
    'true_false': 'true_false',
    'short_answer': 'short_answer',
    'report_revision': 'report_revision',
  }

  return map[raw] || 'short_answer'
}

function adaptOptions(raw: any): V222.QuestionOption[] | undefined {
  if (!raw) return undefined

  // 如果已经是对象数组
  if (Array.isArray(raw) && raw.length > 0) {
    if (typeof raw[0] === 'object' && 'id' in raw[0]) {
      return raw as V222.QuestionOption[]
    }

    // 如果是字符串数组，转换为对象数组
    return raw.map((text: string, idx: number) => ({
      id: String.fromCharCode(65 + idx), // A, B, C, D
      text: text,
    }))
  }

  return undefined
}

export function adaptQuestionBankFromBackend(raw: any): V222.QuestionBank {
  return {
    id: raw.id || raw.bankId || '',
    name: raw.name || '',
    description: raw.description || '',
    body_parts: raw.body_parts || [raw.bodyPart] || [],
    modality_counts: raw.modality_counts || {},
    question_type_counts: raw.question_type_counts || {},
    total: raw.total || raw.totalQuestions || 0,
    completed: raw.completed || raw.completedQuestions || 0,
    progress: raw.progress || 0,
    version: raw.version || '1.0',
    status: raw.status || 'published',
  }
}

export function adaptSubmitResponseFromBackend(raw: any): V222.SubmitResponse {
  return {
    is_correct: raw.is_correct ?? false,
    score: raw.score ?? 0,
    explanation: raw.explanation || '',
    fact_feedback: raw.fact_feedback?.map((f: any) => ({
      fact: f.fact || '',
      present: f.supported ?? f.present ?? false,
      evidence_id: f.evidence_id,
      note: f.note,
    })),
    error_tags: raw.error_tags || [],
    next_recommendation: raw.next_recommendation || '',
    profile_updated: raw.profile_updated ?? false,
    doctor_review_required: true,
    safety_notice: raw.safety_notice || '仅供教学训练或医生审核前辅助，不作为独立诊断依据。',
  }
}

export function adaptTutorResponseFromBackend(raw: any): V222.TutorResponse {
  return {
    message: raw.reply || raw.message || '',
    sources: raw.evidence_ids || raw.sources,
    provider: raw.generation_mode === 'provider' ? 'agent' : raw.generation_mode === 'rule' ? 'rule' : 'fallback',
    leaked_answer: raw.leaked_answer ?? false,
  }
}

export function adaptImportValidationFromBackend(raw: any): V222.ImportValidateResponse {
  return {
    accepted_count: raw.accepted_count || 0,
    rejected_count: raw.rejected_count || 0,
    ready_to_publish: raw.ready_to_publish ?? false,
    items: (raw.items || []).map((item: any) => ({
      line: item.line || 0,
      question: adaptQuestionFromBackend(item.question || {}),
      status: item.status || 'rejected',
      errors: item.errors || [],
    })),
    issues: (raw.issues || []).map((issue: any) => ({
      line: issue.row || issue.line || 0,
      field: issue.field,
      message: issue.message || '',
      severity: issue.code?.includes('error') ? 'error' : 'warning',
    })),
    summary: raw.summary || '',
  }
}

export function adaptModelEvaluationFromBackend(raw: any): V222.ModelEvaluation {
  const metrics = raw.metrics || {}

  return {
    id: raw.id || '',
    model_name: raw.model || raw.display_name || '',
    model_provider: raw.provider_type || 'unknown',
    eval_set_version: raw.provenance?.sample_scope || 'v1.0',
    total_questions: metrics.cases?.value || 0,
    correct: Math.round((metrics.cases?.value || 0) * (metrics.accuracy?.value || 0)),
    accuracy: metrics.accuracy?.value || 0,
    avg_latency_ms: metrics.latency_p50_ms?.value || 0,
    p95_latency_ms: metrics.latency_p95_ms?.value || 0,
    run_at: raw.created_at || new Date().toISOString(),
    artifact_url: raw.artifact,
  }
}

/* ==================== 前端 → 后端适配 ==================== */

export function buildSubmitRequest(questionId: string, answer: string | string[], sessionId?: string): V222.SubmitRequest {
  return {
    question_id: questionId,
    selected_answer: answer,
    session_id: sessionId,
  }
}

export function buildTutorRequest(mode: V222.TutorMode, questionId: string, userMessage?: string, sessionId?: string): V222.TutorRequest {
  return {
    mode,
    question_id: questionId,
    user_message: userMessage,
    session_id: sessionId,
  }
}

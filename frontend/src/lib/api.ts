import {
  mockAuditLogs,
  mockDashboard,
  mockModels,
  mockQuestions,
  mockSkills,
  safetyNotice,
} from './mock'
import type {
  AuditLog,
  DashboardPayload,
  ModelProfile,
  PatientCard,
  Question,
  ReportDraft,
  SkillDefinition,
  SubmissionResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

function markSource<T extends object>(payload: T, source: 'backend' | 'fallback'): T {
  return { ...payload, api_source: source }
}

async function request<T extends object>(path: string, init?: RequestInit, fallback?: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      ...init,
    })
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`)
    }
    return markSource((await response.json()) as T, 'backend')
  } catch (error) {
    if (fallback !== undefined) {
      return markSource(fallback, 'fallback')
    }
    throw error
  }
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
    doctor_review_required: true,
    safety_notice: safetyNotice,
  }
}

export const api = {
  async dashboard(): Promise<DashboardPayload> {
    return request<DashboardPayload>('/api/dashboard', undefined, mockDashboard)
  },

  async questions(params: { falsePremise?: boolean } = {}): Promise<Question[]> {
    const qs = params.falsePremise === undefined ? '' : `?false_premise=${params.falsePremise}`
    const fallback = params.falsePremise === undefined ? mockQuestions : mockQuestions.filter((q) => q.false_premise_flag === params.falsePremise)
    const response = await request<{ items: Question[]; total: number }>(`/api/questions${qs}`, undefined, {
      items: fallback,
      total: fallback.length,
    })
    return response.items
  },

  async question(id: string): Promise<Question> {
    const fallback = mockQuestions.find((q) => q.id === id) || mockQuestions[0]
    const response = await request<{ item: Question }>(`/api/questions/${id}`, undefined, { item: fallback })
    return response.item
  },

  async submit(question: Question, selectedAnswer: string): Promise<SubmissionResponse> {
    return request<SubmissionResponse>(
      '/api/submit',
      {
        method: 'POST',
        body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', selected_answer: selectedAnswer }),
      },
      localSubmission(question, selectedAnswer),
    )
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

  async reportDraft(findingText: string): Promise<ReportDraft> {
    return request<ReportDraft>(
      '/api/report-draft',
      { method: 'POST', body: JSON.stringify({ finding_text: findingText, exam_type: 'gastroscopy' }) },
      {
        id: `report_local_${Date.now()}`,
        input_finding_text: findingText,
        exam_type: 'gastroscopy',
        structured_findings: findingText.split(/[。；;\n]/).map((x) => x.trim()).filter(Boolean),
        draft_impression: ['胃黏膜炎症样/糜烂样改变，需医生结合完整检查复核。'],
        review_points: ['确认部位、范围、数量和图片证据是否一致。', '检查是否存在过强诊断表述。'],
        uncertainty_notes: ['草稿不自动补充未提供的信息。'],
        doctor_review_required: true,
        safety_notice: safetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  async patientCard(summary: string): Promise<PatientCard> {
    return request<PatientCard>(
      '/api/patient-card',
      { method: 'POST', body: JSON.stringify({ diagnosis_summary: summary, audience: 'patient', reviewed_by_doctor: false }) },
      {
        id: `card_local_${Date.now()}`,
        card_title: '内镜检查结果说明卡（医生审核前草稿）',
        plain_language_explanation: `这张卡片把医生待审核输入“${summary}”转写为更容易理解的说明。`,
        what_it_means: ['内镜描述反映检查中看到的黏膜外观。', '部分表现需要结合病史和病理。'],
        what_to_watch: ['是否有持续或加重不适。', '是否需要按医嘱复诊。'],
        follow_up_reminder: '请按照医生给出的复诊或检查安排执行。',
        disclaimer: '本卡片为医生审核前沟通草稿；如输入尚未审核，必须先由医生确认后才能用于患者沟通。',
        review_status: 'doctor_review_pending',
        doctor_review_required: true,
        safety_notice: safetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  async models(): Promise<ModelProfile[]> {
    const response = await request<{ items: ModelProfile[]; notice: string; safety_notice: string }>('/api/models', undefined, {
      items: mockModels,
      notice: 'mock',
      safety_notice: safetyNotice,
    })
    return response.items
  },

  async skills(): Promise<SkillDefinition[]> {
    const response = await request<{ items: SkillDefinition[]; total: number }>('/api/skills', undefined, {
      items: mockSkills,
      total: mockSkills.length,
    })
    return response.items
  },

  async runSkill(skillId: string, questionId = 'q005') {
    return request<Record<string, unknown>>(
      '/api/skills/run',
      { method: 'POST', body: JSON.stringify({ skill_id: skillId, payload: { question_id: questionId }, learner_id: 'demo_learner' }) },
      { message: '已在本地 fallback 中模拟运行。', doctor_review_required: skillId.includes('premise'), safety_notice: safetyNotice },
    )
  },

  async audit(): Promise<AuditLog[]> {
    const response = await request<{ items: AuditLog[]; total: number }>('/api/audit', undefined, {
      items: mockAuditLogs,
      total: mockAuditLogs.length,
    })
    return response.items
  },
}

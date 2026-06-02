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
  KnowledgeBase,
  LearnerProfile,
  ModelAdmissionResult,
  ModelProfile,
  PatientCard,
  Question,
  ReportJudge,
  ReportDraft,
  SkillDefinition,
  SubmissionResponse,
  TrainingState,
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
    const search = new URLSearchParams()
    if (params.falsePremise !== undefined) search.set('false_premise', String(params.falsePremise))
    const qs = search.toString() ? `?${search.toString()}` : ''
    const fallback = params.falsePremise === undefined ? mockQuestions : mockQuestions.filter((q) => q.false_premise_flag === params.falsePremise)
    const response = await request<{ items: Question[]; total: number }>(`/api/questions${qs}`, undefined, {
      items: fallback,
      total: fallback.length,
    })
    return response.items
  },

  async qbank(params: {
    bodyPart?: string
    task?: string
    difficulty?: string
    questionType?: string
    sourceDataset?: string
    onlyFavorites?: boolean
    onlyWrong?: boolean
    mode?: 'practice' | 'exam'
  } = {}): Promise<Question[]> {
    const search = new URLSearchParams()
    if (params.bodyPart) search.set('body_part', params.bodyPart)
    if (params.task) search.set('task', params.task)
    if (params.difficulty) search.set('difficulty', params.difficulty)
    if (params.questionType) search.set('question_type', params.questionType)
    if (params.sourceDataset) search.set('source_dataset', params.sourceDataset)
    if (params.onlyFavorites) search.set('only_favorites', 'true')
    if (params.onlyWrong) search.set('only_wrong', 'true')
    const response = await request<{ items: Question[]; total: number }>(
      `/api/questions${search.toString() ? `?${search.toString()}` : ''}`,
      undefined,
      {
        items: mockQuestions.filter((q) => {
          if (params.onlyFavorites && !q.is_favorited) return false
          if (params.onlyWrong && q.review_status !== '待复盘') return false
          if (params.difficulty && q.difficulty !== params.difficulty) return false
          return true
        }),
        total: mockQuestions.length,
      },
    )
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

  async favorite(questionId: string, favorited: boolean): Promise<LearnerProfile> {
    const response = await request<{ profile: LearnerProfile; safety_notice: string }>(
      '/api/learner/favorite',
      { method: 'POST', body: JSON.stringify({ question_id: questionId, learner_id: 'demo_learner', favorited }) },
      { profile: mockDashboard.learner_profile, safety_notice: safetyNotice },
    )
    return response.profile
  },

  async trainingState(): Promise<TrainingState> {
    return request<TrainingState>('/api/learner/training-state', undefined, {
      profile: mockDashboard.learner_profile,
      wrong_questions: mockDashboard.learner_profile.wrong_questions,
      favorite_questions: mockDashboard.learner_profile.favorite_questions,
      review_queue: mockDashboard.learner_profile.wrong_questions.length,
      next_plan: [
        { label: '证据不足复盘', count: 4, reason: '最近错因集中在错误前提和过度诊断' },
        { label: '报告修改训练', count: 2, reason: '强化所见与诊断边界' },
      ],
      safety_notice: safetyNotice,
    })
  },

  async learnerProfile(): Promise<LearnerProfile> {
    return request<LearnerProfile>('/api/learner/profile', undefined, mockDashboard.learner_profile)
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

  async chat(question: Question, message: string): Promise<{
    reply: string
    scope: string
    doctor_review_required: boolean
    safety_notice: string
    api_source?: 'backend' | 'fallback'
  }> {
    return request(
      '/api/tutor/chat',
      { method: 'POST', body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', message }) },
      {
        reply: `围绕“${question.title}”，请先拆出可观察事实，再判断它是否足以支持题干结论。`,
        scope: 'current_question_only',
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

  async reportDraft(findingText: string, options: { examType?: string; imageName?: string; templateName?: string } = {}): Promise<ReportDraft> {
    return request<ReportDraft>(
      '/api/report-draft',
      {
        method: 'POST',
        body: JSON.stringify({
          finding_text: findingText,
          exam_type: options.examType || 'gastroscopy',
          image_name: options.imageName,
          template_name: options.templateName,
        }),
      },
      {
        id: `report_local_${Date.now()}`,
        input_finding_text: findingText,
        exam_type: options.examType || 'gastroscopy',
        structured_findings: findingText.split(/[。；;\n]/).map((x) => x.trim()).filter(Boolean),
        draft_impression: ['胃黏膜炎症样/糜烂样改变，需医生结合完整检查复核。'],
        review_points: ['确认部位、范围、数量和图片证据是否一致。', '检查是否存在过强诊断表述。'],
        uncertainty_notes: ['草稿不自动补充未提供的信息。'],
        template_name: options.templateName || '胃镜结构化训练模板',
        evidence_source: [findingText ? '医生输入所见' : '报告知识库模板', options.imageName ? '图片上传占位' : '未上传图片'],
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
            evidence_id: options.imageName ? 'img_001' : 'kb_001',
            source_type: options.imageName ? 'image' : 'procedure_context',
            source_ref: options.imageName || 'report_knowledge_base.json',
            supports: ['结构化所见', '草稿印象', '医师复核任务'],
          },
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
        doctor_review_required: true,
        safety_notice: safetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  async reportJudge(originalReport: string, revisedReport: string): Promise<ReportJudge> {
    return request<ReportJudge>(
      '/api/report/judge',
      { method: 'POST', body: JSON.stringify({ original_report: originalReport, revised_report: revisedReport, learner_id: 'demo_learner' }) },
      {
        id: `judge_local_${Date.now()}`,
        score: revisedReport.includes('复核') ? 88 : 62,
        strengths: ['已尝试保留观察事实。'],
        issues: revisedReport.includes('确诊') ? ['仍含过强诊断语气。'] : ['建议继续补充不确定性说明。'],
        suggested_revision: `${revisedReport} 建议医生结合完整检查复核。`,
        rubric_scores: { 部位描述: 20, 所见与诊断区分: 22, 不确定性表达: 20, 安全边界: 20 },
        doctor_review_required: true,
        safety_notice: safetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  async patientCard(summary: string, options: { templateId?: string; imageUrl?: string; reviewedByDoctor?: boolean } = {}): Promise<PatientCard> {
    return request<PatientCard>(
      '/api/patient-card',
      {
        method: 'POST',
        body: JSON.stringify({
          diagnosis_summary: summary,
          audience: 'patient',
          reviewed_by_doctor: Boolean(options.reviewedByDoctor),
          template_id: options.templateId || 'calm_blue',
          image_url: options.imageUrl,
        }),
      },
      {
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

  async modelAdmissionTest(payload: { providerName: string; apiBase: string; apiKeyMasked: string; sampleIds: string[]; focus: string[] }): Promise<ModelAdmissionResult> {
    return request<ModelAdmissionResult>(
      '/api/models/admission-test',
      {
        method: 'POST',
        body: JSON.stringify({
          provider_name: payload.providerName,
          api_base: payload.apiBase,
          api_key_masked: payload.apiKeyMasked,
          selected_sample_ids: payload.sampleIds,
          test_focus: payload.focus,
        }),
      },
      {
        id: `admission_local_${Date.now()}`,
        provider_name: payload.providerName,
        grade: 'A',
        total_score: 82,
        dimension_scores: { 基础识别: 86, 复杂推理: 78, 错误前提: 74, 报告安全: 82, 接口稳定: 88 },
        risk_items: ['本地 fallback 仅演示评分格式，不代表真实准入。'],
        tested_samples: payload.sampleIds,
        recommendation: '可作为训练 Agent 候选模型进入人工复核阶段。',
        doctor_review_required: true,
        safety_notice: safetyNotice,
        created_at: new Date().toISOString(),
      },
    )
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

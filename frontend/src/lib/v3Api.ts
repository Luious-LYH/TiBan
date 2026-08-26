import type {
  CustomModelEvaluationResult,
  ImageUploadResponse,
  ModelEvaluationPayload,
  PortfolioAgentRun,
  PortfolioAgentStreamEvent,
  PortfolioCase,
  PortfolioStudyPayload,
  PortfolioEvalArtifact,
  ProviderDiagnostics,
  ProviderRequestPreview,
  PracticeQuestionsPayload,
  PracticeState,
  PracticeSubmitResponse,
  QuestionBankImportTemplates,
  QuestionBankImportValidation,
  Question,
  ReportDraft,
  ReportRevisionResponse,
} from './types'

export const v3SafetyNotice = '仅供教学研修或医生复核前辅助，不作为独立诊断依据。'

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined
const baseCandidates = configuredBase ? [configuredBase] : ['http://127.0.0.1:8003', 'http://127.0.0.1:8002', 'http://127.0.0.1:8001', 'http://127.0.0.1:8000']
let activeBase = baseCandidates[0]

async function request<T>(path: string, init?: RequestInit, localData?: T): Promise<T> {
  let lastError: unknown
  for (const base of [activeBase, ...baseCandidates.filter((item) => item !== activeBase)]) {
    try {
      const response = await fetch(`${base}${path}`, {
        ...init,
        headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      })
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
      activeBase = base
      return await response.json() as T
    } catch (error) {
      lastError = error
      if (configuredBase) break
    }
  }
  if (localData !== undefined) return localData
  throw lastError
}

async function streamAgentRun(
  caseId: string,
  learnerAnswer: string,
  onEvent: (event: PortfolioAgentStreamEvent) => void,
): Promise<PortfolioAgentRun> {
  let lastError: unknown
  for (const base of [activeBase, ...baseCandidates.filter((item) => item !== activeBase)]) {
    try {
      const response = await fetch(`${base}/api/agent/runs/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: caseId, learner_answer: learnerAnswer, learner_id: 'demo_learner', commit_memory: true }),
      })
      if (!response.ok || !response.body) throw new Error(`${response.status} ${response.statusText}`)
      activeBase = base
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let finalRun: PortfolioAgentRun | null = null
      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.trim()) continue
          const event = JSON.parse(line) as PortfolioAgentStreamEvent
          onEvent(event)
          if (event.event === 'final') finalRun = event.run
          if (event.event === 'error') throw new Error(event.message || event.error_code)
        }
        if (done) break
      }
      if (!finalRun) throw new Error('Agent stream ended without a final run.')
      return finalRun
    } catch (error) {
      lastError = error
      if (configuredBase) break
    }
  }
  throw lastError
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export const v3DemoQuestion: Question = {
  id: 'q001',
  title: '胃窦图像基础识别研修',
  image_url: '/assets/real_samples/kv_cla820gl0s3nv071u4fgd7xgq.jpg',
  image_placeholder: '胃窦黏膜轻度发红，局部可见浅表糜烂样改变。',
  case_summary: '真实公开内镜教学样例。请先描述可观察事实，再判断观察依据是否充分。',
  question: '从当前内镜图像中，最合适的观察结论是？',
  options: ['可见局部黏膜发红或浅表糜烂样改变', '明确早期胃癌', '可直接写成最终临床诊断', '证据不足，不能回答该题'],
  answer: '可见局部黏膜发红或浅表糜烂样改变',
  explanation: '图像支持描述局部黏膜发红和浅表糜烂样改变，但不能据此给出明确肿瘤诊断。',
  complexity: 1,
  question_class: '基础识别',
  source_type: '教学样例',
  atomic_trace: [
    {
      id: 'q001_f1',
      fact: '黏膜颜色改变',
      expected: '识别为可观察异常',
      supported: true,
      evidence: '视野中央偏右区域较周围更红。',
      skill_dimension: '病灶识别',
    },
    {
      id: 'q001_f2',
      fact: '诊断边界',
      expected: '保留不确定性',
      supported: true,
      evidence: '单帧图像缺少病理、染色放大或连续视角。',
      skill_dimension: '证据不足识别',
    },
  ],
  false_premise_flag: false,
  teaching_tags: ['黏膜观察', '观察依据', '基础识别'],
  difficulty: '入门',
  doctor_review_required: true,
  safety_notice: v3SafetyNotice,
  body_part: '胃',
  task: '图像观察',
  question_type: '单选',
  source_dataset: '平台教学样例',
  citation_note: '平台脱敏教学样例。',
  is_favorited: false,
  review_status: '未开始',
  ai_benchmark_answer: '可见局部黏膜发红或浅表糜烂样改变',
  expected_keywords: ['黏膜', '发红', '糜烂', '观察依据'],
}

export const v3DemoState: PracticeState = {
  profile: {
    learner_id: 'demo_doctor',
    name: '林知远 医师',
    title: '消化内镜进修医师',
    department: '消化内镜中心',
    hospital: '示范教学医院',
    training_stage: '进阶规范化研修第 3 周',
    training_goal: '提升观察依据、病灶属性判断和结构化报告表达能力',
    total_questions: 32,
    accuracy: 0.75,
    completed_today: 7,
    daily_target: 50,
    streak_days: 5,
    favorite_questions: ['q004', 'q020'],
    wrong_questions: ['q004', 'q008', 'q013'],
    skill_scores: { 病灶识别: 78, 部位定位: 76, 属性判断: 72, 数量判断: 68, 事实组合: 74, 证据不足识别: 62 },
    weakness_tags: ['观察依据不足', '过度诊断倾向', '报告复核意识'],
    recent_errors: ['q004', 'q008', 'q013'],
    recommended_question_classes: ['一图多问', '病变属性', '报告纠错'],
    growth_trend: [
      { date: '06-01', accuracy: 66, evidence: 54, report: 67 },
      { date: '06-02', accuracy: 68, evidence: 56, report: 69 },
      { date: '06-03', accuracy: 70, evidence: 58, report: 71 },
      { date: '06-04', accuracy: 73, evidence: 60, report: 73 },
      { date: '06-05', accuracy: 75, evidence: 62, report: 76 },
    ],
    training_records: [
      { date: '2026-06-05', question_id: 'q004', score: 72, result: '观察依据复盘' },
      { date: '2026-06-05', question_id: 'q020', score: 86, result: '报告修改研修' },
      { date: '2026-06-04', question_id: 'q008', score: 78, result: '图像问答研修' },
      { date: '2026-06-04', question_id: 'q013', score: 60, result: '过度推断待复盘' },
      { date: '2026-06-03', question_id: 'q011', score: 82, result: '病变属性研修' },
      { date: '2026-06-03', question_id: 'q002', score: 90, result: '部位定位正确' },
    ],
    exam_sessions: [],
    question_type_coverage: { 单选: 18, 多选: 4, 判断: 3, 问答评分: 2, 报告修改: 6 },
    updated_at: '2026-06-05T19:27:51.110146Z',
  },
  progress: { completed: 7, target: 50, percent: 14, review_queue: 3 },
  wrong_questions: ['q004', 'q008', 'q013'],
  favorite_questions: ['q004', 'q020'],
  next_plan: [
    { label: '观察依据复盘', count: 4, reason: '最近错因集中在依据不足和过度诊断' },
    { label: '综合图像小测', count: 3, reason: '使用平台内镜图像资源巩固迁移能力。' },
    { label: '报告修改研修', count: 2, reason: '强化所见与诊断边界' },
  ],
  question_types: [
    { name: '基础识别', summary: '异常有无、结构识别、伪影识别', tone: 'blue' },
    { name: '部位定位', summary: '器官、区域和空间位置判断', tone: 'teal' },
    { name: '病变属性', summary: '数量、形态、边界、出血和炎症表现', tone: 'amber' },
    { name: '一图多问', summary: '同一图片下多角度观察与归纳', tone: 'green' },
    { name: '报告纠错', summary: '把过强表达改成观察事实和复核边界', tone: 'blue' },
  ],
  safety_notice: v3SafetyNotice,
}

const modelMetricKeys = ['图像问答正确率', '前提鲁棒校验率', '多步证据整合率', '分步证据完整率', '输出可解析率', '综合研修适配度']

export const v3DemoModelData: ModelEvaluationPayload = {
  summary: {
    title: '模型评测实验室',
    headline: '后端不可用，当前没有可验证的模型结果',
    sample_scope: '等待运行真实评测',
    model_count: 0,
    top_model_id: '',
    top_model_name: '暂无真实评测结果',
    updated_at: '未运行',
  },
  groups: [
    { id: 'domain', label: '微调模型', description: '平台智能助手候选，优先用于研修反馈。' },
    { id: 'general', label: '通用开源视觉模型', description: '覆盖通用图像问答能力。' },
    { id: 'medical', label: '医学开源视觉模型', description: '覆盖医学多模态基础能力。' },
    { id: 'closed', label: '闭源参考模型', description: '仅作外部参考对照。' },
  ],
  metrics: modelMetricKeys,
  items: [],
  radar: [],
  complexity_curve: [],
  attribute_breakdown: [],
  safety_notice: v3SafetyNotice,
}

export const v3Api = {
  portfolioCases() {
    return request<{ items: PortfolioCase[]; total: number; source: string; safety_notice: string }>(
      '/api/portfolio/cases',
    )
  },

  portfolioStudy() {
    return request<PortfolioStudyPayload>('/api/portfolio/study')
  },

  portfolioStudyFavorite(caseId: string, favorited: boolean) {
    return request<Record<string, unknown>>(
      `/api/portfolio/study/favorites/${encodeURIComponent(caseId)}`,
      {
        method: 'POST',
        body: JSON.stringify({ favorited, learner_id: 'demo_learner' }),
      },
      { case_id: caseId, favorited, source: 'local_fallback' },
    )
  },

  portfolioAgentRun(caseId: string, learnerAnswer: string) {
    return request<PortfolioAgentRun>(
      '/api/agent/runs',
      {
        method: 'POST',
        body: JSON.stringify({ case_id: caseId, learner_answer: learnerAnswer, learner_id: 'demo_learner', commit_memory: true }),
      },
    )
  },

  portfolioAgentRunStream(
    caseId: string,
    learnerAnswer: string,
    onEvent: (event: PortfolioAgentStreamEvent) => void,
  ) {
    return streamAgentRun(caseId, learnerAnswer, onEvent)
  },

  portfolioAgentReplay(runId: string) {
    return request<PortfolioAgentRun>(`/api/agent/runs/${encodeURIComponent(runId)}/replay`, { method: 'POST' })
  },

  portfolioEvalLatest() {
    return request<PortfolioEvalArtifact>('/api/evals/latest')
  },

  demoReset() {
    return request<Record<string, unknown>>('/api/demo/reset', { method: 'POST' })
  },

  practiceState() {
    return request<PracticeState>('/api/practice/state', undefined, v3DemoState)
  },

  practiceQuestions(options: { questionClass?: string; questionType?: string; bodyPart?: string; onlyWrong?: boolean; onlyFavorites?: boolean; limit?: number; shuffleSeed?: number } = {}) {
    const params = new URLSearchParams()
    if (options.questionClass) params.set('question_class', options.questionClass)
    if (options.questionType) params.set('question_type', options.questionType)
    if (options.bodyPart) params.set('body_part', options.bodyPart)
    if (options.onlyWrong) params.set('only_wrong', 'true')
    if (options.onlyFavorites) params.set('only_favorites', 'true')
    if (options.limit) params.set('limit', String(options.limit))
    if (options.shuffleSeed) params.set('shuffle_seed', String(options.shuffleSeed))
    const query = params.toString()
    return request<PracticeQuestionsPayload>(
      `/api/practice/questions${query ? `?${query}` : ''}`,
      undefined,
      {
        items: [v3DemoQuestion],
        total: 1,
        pool_total: 1,
        pool_seed: options.shuffleSeed || null,
        available_type_counts: { 单选: 1, 多选: 0, 判断: 0, 问答评分: 0, 报告修改: 0 },
        question_types: v3DemoState.question_types,
        safety_notice: v3SafetyNotice,
      },
    )
  },

  async practiceSubmit(question: Question, selectedAnswer: string) {
    const isCorrect = isAnswerCorrect(question, selectedAnswer)
    const local: PracticeSubmitResponse = {
      id: `local_${Date.now()}`,
      question_id: question.id,
      learner_id: 'demo_doctor',
      selected_answer: selectedAnswer,
      is_correct: isCorrect,
      score: isCorrect ? 90 : 62,
      error_tags: isCorrect ? [] : ['观察依据不足'],
      fact_feedback: question.atomic_trace,
      explanation: question.explanation,
      next_recommendation: '继续完成一题观察依据复盘。',
      created_at: new Date().toISOString(),
      profile_updated: false,
      doctor_review_required: true,
      safety_notice: v3SafetyNotice,
      profile: v3DemoState.profile,
      practice_summary: {
        result: isCorrect ? '回答正确' : '需要复盘',
        profile_delta: '画像已更新',
        next_step: '进入证据复盘或继续下一题。',
      },
    }
    return request<PracticeSubmitResponse>(
      '/api/practice/submit',
      { method: 'POST', body: JSON.stringify({ question_id: question.id, learner_id: 'demo_learner', selected_answer: selectedAnswer }) },
      local,
    )
  },

  practiceTutor(payload: {
    questionId: string
    mode: string
    selectedAnswer?: string
    message?: string
    displayModelName?: string
    annotatedImageDataUrl?: string
  }) {
    const localReply = localTutorReply(payload.message, payload.displayModelName)
    return request<Record<string, unknown>>(
      '/api/practice/tutor',
      {
        method: 'POST',
        body: JSON.stringify({
          question_id: payload.questionId,
          mode: payload.mode,
          selected_answer: payload.selectedAnswer,
          message: payload.message,
          display_model_name: payload.displayModelName,
          annotated_image_data_url: payload.annotatedImageDataUrl,
        }),
      },
      { hint: '先观察图像中的部位、形态和观察依据，再判断题干结论是否被画面支持。', reply: localReply, safety_notice: v3SafetyNotice },
    )
  },

  questionBankImportTemplates() {
    return request<QuestionBankImportTemplates>(
      '/api/question-banks/import/templates',
      undefined,
      {
        schema_version: 'qbank-import-template-v2.2',
        formats: ['jsonl', 'csv', 'markdown'],
        required_fields: ['question', 'question_type', 'answer', 'explanation'],
        examples: {
          jsonl: '{"question":"胃息肉样隆起记录最小要素是什么？","question_type":"单选","options":["部位、数量、大小、形态","直接写治疗方案"],"answer":"部位、数量、大小、形态","explanation":"记录可观察结构化信息。","body_part":"胃","tags":["胃","息肉"]}',
          csv: 'question,question_type,options,answer,explanation,body_part,tags\n胃息肉样隆起记录最小要素是什么？,单选,"部位、数量、大小、形态|直接写治疗方案",部位、数量、大小、形态,记录可观察结构化信息。,胃,"胃|息肉"',
          markdown: '## 胃息肉样隆起记录最小要素是什么？\n题型: 单选\n部位: 胃\n标签: 胃, 息肉\n- [x] 部位、数量、大小、形态\n- [ ] 直接写治疗方案\n解析: 记录可观察结构化信息。',
        },
        safety_notice: v3SafetyNotice,
      },
    )
  },

  validateQuestionBankImport(payload: {
    format: 'jsonl' | 'csv' | 'markdown'
    content: string
    sourceName?: string
    defaultBodyPart?: string
  }) {
    return request<QuestionBankImportValidation>(
      '/api/question-banks/import/validate',
      {
        method: 'POST',
        body: JSON.stringify({
          format: payload.format,
          content: payload.content,
          source_name: payload.sourceName || '个人导入题库',
          default_body_part: payload.defaultBodyPart || '通用',
        }),
      },
      {
        schema_version: 'qbank-import-v2.2',
        format: payload.format,
        accepted_count: 0,
        rejected_count: 1,
        ready_to_publish: false,
        items: [],
        issues: [{ row: 0, code: 'backend_unavailable', message: '后端暂未连接，无法完成题库校验。' }],
        summary: {
          content_hash: '',
          question_type_counts: {},
          text_question_count: 0,
          visual_question_count: 0,
        },
        source_registry_required: ['source_id', 'source_name', 'license', 'allowed_usage', 'content_hash'],
        safety_notice: v3SafetyNotice,
      },
    )
  },

  favoriteQuestion(questionId: string, favorited: boolean) {
    return request<Record<string, unknown>>(
      '/api/learner/favorite',
      { method: 'POST', body: JSON.stringify({ question_id: questionId, learner_id: 'demo_learner', favorited }) },
      { safety_notice: v3SafetyNotice },
    )
  },

  mentorAgentAdvice() {
    return request<Record<string, unknown>>(
      '/api/learner/mentor-agent',
      undefined,
      {
        agent_name: '带教老师',
        memory_scope: ['研修作答记录', '错题与收藏题', '带教追问记录', '报告修改评分', '能力画像变化'],
        learner_snapshot: {
          name: v3DemoState.profile.name,
          training_stage: v3DemoState.profile.training_stage,
          total_questions: v3DemoState.profile.total_questions,
          accuracy: v3DemoState.profile.accuracy,
          weakness_tags: v3DemoState.profile.weakness_tags,
          weakest_dimensions: [{ dimension: '证据不足识别', score: 62 }],
          favorite_count: v3DemoState.favorite_questions.length,
          wrong_count: v3DemoState.wrong_questions.length,
        },
        personalized_advice: [
          '先完成观察依据复盘，再进入新题组。',
          '优先回看收藏题，巩固报告表达。',
          '本周安排报告修改题，训练所见、倾向判断和复核边界。',
        ],
        next_check_in: '下一次完成 5 道题或 1 次报告修改后，带教老师会更新建议。',
        recent_memory: v3DemoState.profile.training_records.slice(0, 3).map((item) => `${item.date} · ${item.result} · ${item.score}分`),
        doctor_review_required: true,
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  modelEvaluation() {
    return request<ModelEvaluationPayload>('/api/models/evaluation', undefined, v3DemoModelData)
  },

  providerDiagnostics() {
    return request<ProviderDiagnostics>(
      '/api/provider/diagnostics',
      undefined,
      {
        ready_level: 'fallback',
        provider_configured: false,
        provider_mode: 'rule',
        provider: '平台智能服务',
        model: '平台默认模型',
        base_url_configured: false,
        api_key_configured: false,
        private_host_allowlist_configured: false,
        private_host_allowlist_count: 0,
        missing: [],
        public_sample_count: 0,
        evidence_ladder: [],
        admission_state: {
          provider_name: '平台后端',
          grade: 'NA',
          total_score: 0,
          provider_called: false,
          safe_for_training: false,
          recommendation: '后端在线后显示准入证据。',
        },
        blocking_reason: '',
        next_actions: [],
        privacy_notice: '不返回一次性授权或完整连接入口。',
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
        api_source: 'fallback',
      },
    )
  },

  providerRequestPreview() {
    return request<ProviderRequestPreview>(
      '/api/provider/request-preview',
      {
        method: 'POST',
        body: JSON.stringify({
        provider_name: '平台智能服务',
        api_base: '',
        model: '',
          selected_sample_ids: [],
          test_focus: ['图像问答', '报告表达', '安全边界'],
          preview_mode: 'admission',
        }),
      },
      {
        id: `provider_preview_${Date.now()}`,
        provider_name: '平台智能服务',
        preview_mode: 'admission',
        ready_for_provider_call: false,
        blocked_reason: 'backend_unavailable',
        preflight_mode: 'fallback',
        safety_status: 'preview',
        normalized_preview: null,
        endpoint_paths: [],
        request_body_fields: ['model', 'messages', 'temperature', 'max_tokens'],
        message_plan: [],
        selected_samples: [],
        sample_count: 0,
        image_attachment_count: 0,
        api_key_present: false,
        backend_env_key_available: false,
        request_sent: false,
        key_persisted: false,
        audit_logged: false,
        state_updated: false,
        reference_answer_sent: false,
        full_response_persisted: false,
        privacy_trace: [],
        next_actions: [],
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
        api_source: 'fallback',
      },
    )
  },

  customModelEvaluate(payload: { providerName: string; apiBase: string; apiKey: string; model: string }) {
    return request<CustomModelEvaluationResult>(
      '/api/models/custom-evaluate',
      {
        method: 'POST',
        body: JSON.stringify({
          display_name: payload.providerName,
          api_base: payload.apiBase,
          api_key: payload.apiKey,
          model: payload.model,
        }),
      },
      {
        id: `custom_${Date.now()}`,
        display_name: payload.providerName || '自定义模型',
        model: payload.model || '自定义模型',
        connection_status: '格式预览',
        metrics: {
          图像问答正确率: 76,
          前提鲁棒校验率: 70,
          多步证据整合率: 68,
          分步证据完整率: 72,
          输出可解析率: 92,
          综合研修适配度: 74,
        },
        summary: '已生成小样本评估格式预览。正式接入后可继续完成图像问答、观察依据和报告表达评估。',
        status_label: '格式预览',
        privacy_status: '一次性授权未保存，完整回复未入库。',
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  async uploadReportImage(file: File): Promise<ImageUploadResponse> {
    const dataUrl = await readFileAsDataUrl(file)
    return request<ImageUploadResponse>(
      '/api/report/image',
      { method: 'POST', body: JSON.stringify({ filename: file.name, data_url: dataUrl, learner_id: 'demo_learner' }) },
      {
        image_name: file.name,
        original_filename: file.name,
        bytes: file.size,
        mime_type: file.type || 'image/png',
        sha256_prefix: 'local',
        source_type: 'uploaded_image',
        provider_input_allowed: false,
        audit_logged: false,
        doctor_review_required: true,
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },

  reportDraft(findingText: string, options: { imageName?: string } = {}) {
    const local: ReportDraft = {
      id: `report_${Date.now()}`,
      input_finding_text: findingText,
      exam_type: 'gastroscopy',
      structured_findings: [`【内镜所见】${findingText || '胃窦黏膜充血，可见散在糜烂样改变。'}`],
      draft_impression: ['【印象建议】胃黏膜炎症样改变，需结合完整检查复核。'],
      review_points: ['结合完整图像、病史和必要病理结果复核。'],
      uncertainty_notes: ['草稿已绑定上传图片和医生输入；仍需结合完整检查复核。', '如需形成正式报告，应由内镜医生结合完整图像、病史和必要检查复核。'],
      template_name: '胃镜结构化报告模板',
      evidence_source: ['医生输入所见', '上传图像材料', '报告规范模板'],
      draft_status: 'needs_human_review',
      exam_context: {},
      image_quality: {},
      evidence_ledger: [],
      hallucination_audit: {},
      review_tasks: [],
      generation_mode: 'rule',
      provider_status: { provider: 'system', model: 'report-template', mode: 'rule' },
      source_trace: [],
      doctor_review_required: true,
      safety_notice: v3SafetyNotice,
      created_at: new Date().toISOString(),
    }
    return request<ReportDraft>(
      '/api/report/generate',
      { method: 'POST', body: JSON.stringify({ finding_text: findingText, exam_type: 'gastroscopy', image_name: options.imageName }) },
      local,
    )
  },

  reportRevise(payload: { originalReport: string; currentReport: string; instruction: string }) {
    return request<ReportRevisionResponse>(
      '/api/report/revise',
      { method: 'POST', body: JSON.stringify({ original_report: payload.originalReport, current_report: payload.currentReport, instruction: payload.instruction }) },
      {
        id: `revision_${Date.now()}`,
        revised_report: `${payload.currentReport || payload.originalReport} 建议医生结合完整检查过程、病史及必要病理结果复核。`,
        instruction: payload.instruction,
        judge: {
          id: `judge_${Date.now()}`,
          score: 82,
          strengths: ['已保留观察事实。'],
          issues: ['建议继续补充不确定性说明。'],
          suggested_revision: payload.currentReport || payload.originalReport,
          rubric_scores: { 部位描述: 20, 所见与诊断区分: 20, 不确定性表达: 20, 安全边界: 22 },
          recommended_drills: [],
          generation_mode: 'rule',
          provider_status: { provider: 'system', model: 'report-template', mode: 'rule' },
          source_trace: [],
          profile_updated: false,
          doctor_review_required: true,
          safety_notice: v3SafetyNotice,
          created_at: new Date().toISOString(),
        },
        generation_mode: 'rule',
        provider_status: { provider: 'system', model: 'report-template', mode: 'rule' },
        source_trace: [],
        privacy_status: '本次修改未保存一次性授权。',
        safety_notice: v3SafetyNotice,
        created_at: new Date().toISOString(),
      },
    )
  },
}

function isAnswerCorrect(question: Question, selectedAnswer: string) {
  if (question.question_type !== '多选') return selectedAnswer === question.answer
  const selected = splitAnswerItems(selectedAnswer)
  const answer = splitAnswerItems(question.answer)
  return selected.length > 0 && selected.length === answer.length && selected.every((item) => answer.includes(item))
}

function splitAnswerItems(value: string) {
  return value.split(/[；;]/).map((item) => item.trim()).filter(Boolean)
}

function localTutorReply(message?: string, displayModelName?: string) {
  const text = (message || '').trim().toLowerCase()
  const modelName = (displayModelName || '当前研修助手').trim()
  if (['hi', 'hello', '你好', '您好', '哈喽', '在吗'].includes(text)) {
    return '你好，我在。你可以直接说现在卡在部位、形态、选项排除，还是报告表述上。'
  }
  if (text.includes('你是谁') || text.includes('你是什么') || text.includes('什么模型') || text.includes('模型')) {
    return `我在当前研修界面中显示为「${modelName}」，用于陪你做内镜研修题、整理观察依据和复盘报告表达。`
  }
  if (text.includes('能做什么') || text.includes('可以干什么') || text.includes('能干什么') || text.includes('可以辅导') || text.includes('能不能辅导')) {
    return '可以。我能陪你读当前内镜图像、梳理选项依据、复盘错因，也能把你的观察整理成更稳妥的报告表达。'
  }
  return '我会先帮你拆观察点：部位、形态、数量、是否能支持你的选择。你可以告诉我你卡在哪一步。'
}

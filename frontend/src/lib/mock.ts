import type {
  AuditLog,
  DashboardPayload,
  ModelProfile,
  Question,
  SkillDefinition,
} from './types'

export const safetyNotice = '仅供教学训练或医生审核前辅助，不作为独立诊断依据。'

export const mockQuestions: Question[] = [
  {
    id: 'q001',
    title: '胃窦黏膜基础识别',
    image_url: '/assets/synthetic-endoscopy-training.svg',
    image_placeholder: '合成胃镜视野：胃窦黏膜轻度发红，局部可见浅表糜烂样改变。',
    case_summary: '教学样例。学员需要先判断是否存在可描述的黏膜异常，而不是直接下诊断。',
    question: '从该内镜教学图像中，最合适的初步观察结论是？',
    options: ['可见局部黏膜发红/浅表糜烂样改变', '明确早期胃癌', '食管静脉曲张破裂', '证据不足，无法描述任何异常'],
    answer: '可见局部黏膜发红/浅表糜烂样改变',
    explanation: '图像支持描述局部黏膜发红和浅表糜烂样改变，但不能据此给出明确肿瘤诊断。',
    complexity: 1,
    question_class: '基础识别',
    source_type: '教学样例',
    atomic_trace: [
      {
        id: 'q001_f1',
        fact: '画面中存在黏膜颜色改变',
        expected: '应识别为可描述异常',
        supported: true,
        evidence: '视野中央偏右区域较周围更红',
        skill_dimension: '病灶识别',
      },
      {
        id: 'q001_f2',
        fact: '不能单凭该图给出恶性诊断',
        expected: '应保留不确定性',
        supported: true,
        evidence: '缺少病理、染色放大或连续视角',
        skill_dimension: '证据不足识别',
      },
    ],
    false_premise_flag: false,
    teaching_tags: ['黏膜观察', '证据边界', '基础识别'],
    difficulty: '入门',
    doctor_review_required: true,
    safety_notice: safetyNotice,
  },
  {
    id: 'q005',
    title: '错误前提：图中是否一定有息肉',
    image_url: '/assets/synthetic-endoscopy-training.svg',
    image_placeholder: '合成胃镜视野：可见黏膜发红，无明确息肉蒂或隆起边界。',
    case_summary: '题干故意诱导学员接受未被图像支持的前提。',
    question: '题干称“该息肉的大小最可能是多少”，你应如何处理？',
    options: ['指出证据不足：图中未明确显示息肉', '估计为2厘米并建议切除', '默认存在息肉并选择最大值', '直接判断为腺瘤'],
    answer: '指出证据不足：图中未明确显示息肉',
    explanation: '题干预设了图像未支持的息肉前提，正确做法是识别错误前提并说明证据不足。',
    complexity: 2,
    question_class: '错误前提',
    source_type: '教学样例',
    atomic_trace: [
      {
        id: 'q005_f1',
        fact: '题干假设存在息肉',
        expected: '先验证前提',
        supported: false,
        evidence: '未见明确隆起、蒂部或边界',
        skill_dimension: '证据不足识别',
      },
      {
        id: 'q005_f2',
        fact: '不应凭空估计大小',
        expected: '拒绝无依据测量',
        supported: true,
        evidence: '单帧无测量标尺且目标不明确',
        skill_dimension: '数量判断',
      },
    ],
    false_premise_flag: true,
    teaching_tags: ['错误前提', '证据不足', '幻觉防护'],
    difficulty: '进阶',
    doctor_review_required: true,
    safety_notice: safetyNotice,
  },
]

export const mockModels: ModelProfile[] = [
  {
    id: 'm_mock_tutor',
    name: 'EndoTutor Mock Orchestrator',
    provider_type: 'mock',
    model_family: '内镜领域',
    recommended_roles: ['智能辅导', '错因分析', '安全演示'],
    risk_tags: ['规则模板', '无真实临床评测', '医生审核'],
    ability_scores: { basic_recognition: 88, complex_reasoning: 78, false_premise: 91, chinese_report: 84, engineering: 94 },
    grade: 'A',
    is_active: true,
  },
  {
    id: 'm_kvasir_qwen',
    name: 'Qwen2.5-VL KvasirVQA Adapter Reserved',
    provider_type: 'local',
    model_family: '内镜领域',
    recommended_roles: ['GI-VQA', '内镜专域对照'],
    risk_tags: ['领域微调', '需防幻觉', '待真实评测'],
    ability_scores: { basic_recognition: 86, complex_reasoning: 79, false_premise: 72, chinese_report: 76, engineering: 80 },
    grade: 'A',
    is_active: false,
  },
]

export const mockDashboard: DashboardPayload = {
  today_training: { completed: 6, target: 12, streak_days: 5, review_queue: 3 },
  learner_profile: {
    learner_id: 'demo_learner',
    name: 'Demo 学员',
    total_questions: 18,
    accuracy: 0.72,
    skill_scores: { 病灶识别: 78, 部位定位: 82, 属性判断: 70, 数量判断: 66, 事实组合: 74, 证据不足识别: 58 },
    weakness_tags: ['证据不足', '错误前提', '报告安全'],
    recent_errors: ['q005', 'q008', 'q013'],
    recommended_question_classes: ['错误前提', '复杂组合', '报告纠错'],
    updated_at: '2026-06-02T09:00:00Z',
  },
  ability_radar: [
    { dimension: '病灶识别', score: 78 },
    { dimension: '部位定位', score: 82 },
    { dimension: '属性判断', score: 70 },
    { dimension: '数量判断', score: 66 },
    { dimension: '事实组合', score: 74 },
    { dimension: '证据不足识别', score: 58 },
  ],
  recommended_training: [
    { label: '错误前提', count: 4 },
    { label: '复杂组合', count: 4 },
    { label: '报告纠错', count: 3 },
  ],
  active_model: mockModels[0],
  safety_notice: safetyNotice,
  mock_evaluation_notice: '模型能力分为演示 mock 和接口预留，不代表真实临床评测结果。',
  reference_inspirations: ['HyperKvasir: GI 内镜图像/视频数据底座', 'Kvasir-VQA-x1: GI-VQA 课程分层参考', 'MediaEval Medico: VQA + 多模态解释能力参考'],
}

export const mockSkills: SkillDefinition[] = [
  { id: 'question_hint', name: '问题提示', description: '给出不泄露答案的提示。', category: 'training', enabled: true, risk_level: 'low', input_schema: {}, output_schema: {} },
  { id: 'atomic_feedback', name: '原子事实反馈', description: '映射错因到 atomic facts。', category: 'feedback', enabled: true, risk_level: 'medium', input_schema: {}, output_schema: {} },
  { id: 'false_premise_guard', name: '错误前提识别', description: '识别证据不足和不适用。', category: 'safety', enabled: true, risk_level: 'high', input_schema: {}, output_schema: {} },
]

export const mockAuditLogs: AuditLog[] = [
  {
    id: 'audit_mock_001',
    event_type: 'question_view',
    user_id: 'demo_learner',
    entity_id: 'q001',
    summary: '查看胃窦黏膜基础识别题。',
    risk_level: 'low',
    doctor_review_required: true,
    created_at: '2026-06-02T09:01:00Z',
  },
]


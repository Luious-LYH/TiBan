# Agent 自动开发提示词文档

> 用途：把本文件发给 Claude Code / Cursor / Codex / 其他编程 Agent，让它们按照统一流程搭建“内镜智训Agent”平台。  
> 当前阶段：先完成核心功能跑通；真实模型评测流水线暂不开发。

---

## 0. 总控提示词

```text
你现在是“内镜智训Agent：面向消化道内镜医师培训的智能辅导平台”的全栈开发 Agent。请先完整阅读项目根目录下的以下文档：

1. 01_平台总构建方案书.md
2. 02_Agent自动开发提示词文档.md
3. 03_系统需求规格与接口数据字典.md
4. 04_AGENTS.md

你的任务是搭建一个可运行、可演示、可继续迭代的 Web 平台。当前阶段不要开发真实模型评测流水线；模型能力与风险定级只做 mock 看板、模型库和接口预留。

必须实现：React/Vite/TypeScript 前端、FastAPI 后端、JSON mock 数据、医师刷题训练、智能辅导 Agent、错因分析和原子事实反馈、错误前提训练、报告草稿辅助、科普卡片生成、skills 注册与调用、memory/learner profile、审计日志、模型库和能力看板 mock、医疗安全提示。

禁止：不要写真实服务器 IP、密码、API Key、Webhook；不要展示真实患者身份信息；不要让系统替代医生诊断；不要把报告草稿写成最终诊断；不要把功能做成无法运行的大工程；不要忽略测试和验收。

开发方式：先列计划和文件树；分 milestone 实现；每个 milestone 后运行测试或启动检查；发现问题要修复；完成后输出运行命令、已实现功能、未实现功能、后续建议。
```

---

## 1. Claude Code 审阅循环提示词

```text
请作为严格的代码审阅者检查当前仓库。

重点检查：
1. 是否符合 01_平台总构建方案书.md；
2. 是否符合 04_AGENTS.md 的安全要求；
3. 前端是否能启动；
4. 后端是否能启动；
5. API 字段是否与 03_系统需求规格与接口数据字典.md 一致；
6. 医疗输出是否都有 safety_notice 和 doctor_review_required；
7. 是否硬编码了任何 API Key、服务器 IP、密码、Webhook；
8. 是否有真实患者身份信息；
9. 页面是否围绕“内镜医师培训和智能辅导”，而不是模型评测；
10. 是否实现了 mock fallback；
11. 代码是否过度复杂；
12. 是否存在 TypeScript/Python 类型错误。

请输出：必须修复的问题、建议优化的问题、可以暂缓的问题、具体修改建议；如能直接修复，请给出 patch。
```

---

## 2. 项目初始化提示词

```text
请初始化项目仓库，项目名 endo-zhixun-agent。

要求：
1. 创建 frontend 和 backend 两个目录；
2. frontend 使用 React + Vite + TypeScript；
3. 安装 Tailwind CSS、lucide-react、recharts；
4. UI 组件风格参考 shadcn/ui，但不要因为配置复杂阻塞启动；
5. backend 使用 FastAPI + Pydantic + uvicorn；
6. 创建 docs 目录，放置 README、API_SPEC、DEMO_SCRIPT；
7. 创建 .env.example，不要写真实 key；
8. 创建 AGENTS.md，写入开发规则；
9. 创建 mock 数据目录；
10. 给出启动命令。

请优先保证最小项目能启动。
```

推荐命令：

```bash
mkdir endo-zhixun-agent
cd endo-zhixun-agent
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install lucide-react recharts
cd ..
mkdir backend
cd backend
python -m venv .venv
pip install fastapi uvicorn pydantic python-dotenv
cd ..
```

---

## 3. 前端开发提示词

```text
请开发 frontend 页面。页面要专业、清爽、高信息密度，像医疗教学平台，不要营销大屏。

路由：
/ 首页总览
/training 训练中心
/feedback 错因分析
/false-premise 错误前提训练
/report 报告草稿
/card 科普卡片
/models 模型库与能力看板
/skills Skills 中心
/audit 安全审计

布局：左侧固定导航栏；顶部显示项目名“内镜智训Agent”和安全提示；内容区使用卡片布局；所有医疗输出卡片显示“仅供教学训练或医生审核前辅助，不作为独立诊断依据”。

训练中心三栏：左侧内镜图像占位、病例摘要、题源标签；中间题目、选项、提交、练习/考试切换；右侧智能辅导对话区，按钮包括“提示一下”“查看依据”“错因分析”“下一题”。

错因反馈页：展示题目、用户答案、参考答案、atomic_trace 表格、错误类型、学习建议、下一题推荐。

模型库页：只做 mock，展示模型类型、推荐用途、风险标签、是否当前默认辅导模型，不实现真实评测。

请使用本地 mock 数据先跑通页面，后续再接 backend API。
```

---

## 4. 后端开发提示词

```text
请开发 FastAPI 后端。

要求：
1. 所有接口前缀 /api；
2. 先从 backend/app/data/*.json 读取 mock 数据；
3. 使用 Pydantic 定义请求和响应；
4. 每个医疗相关输出包含 safety_notice；
5. report/card 类输出包含 doctor_review_required=true；
6. 实现审计日志，至少写入内存或 JSON 文件；
7. 不依赖真实模型 API；
8. 预留 ModelProvider 抽象，但默认使用 MockModelProvider。

接口：
GET /api/health
GET /api/dashboard
GET /api/questions
GET /api/questions/{id}
POST /api/submit
POST /api/tutor/hint
POST /api/tutor/explain
POST /api/tutor/chat
GET /api/learner/profile
GET /api/learner/recommendations
POST /api/report-draft
POST /api/patient-card
GET /api/models
POST /api/models/select
GET /api/skills
POST /api/skills/run
GET /api/audit

请保证 uvicorn app.main:app --reload 能启动。
```

---

## 5. Mock 数据生成提示词

```text
请生成平台 mock 数据，注意不要包含真实患者信息。

文件：questions.json 至少 24 道题；models.json 至少 8 个模型；skills.json 至少 9 个 skill；report_templates.json 至少 3 个报告模板；card_templates.json 至少 3 个科普卡片模板；learner_profile.json 1 个 demo 学员；audit_logs.json 至少 10 条日志。

questions.json 题型覆盖：基础识别、部位定位、病变属性、复杂组合、错误前提、报告纠错、一图多问、证据不足判断。

每道题字段：id, title, image_url, image_placeholder, case_summary, question, options, answer, explanation, complexity, question_class, source_type, atomic_trace, false_premise_flag, teaching_tags, difficulty, doctor_review_required, safety_notice。
```

---

## 6. Agent 工作流实现提示词

```text
请实现受控 Agent 工作流，不要做自由聊天机器人。

核心类/服务：TutorOrchestrator, SkillRegistry, MemoryService, SafetyService, AuditService。

工作流：
- hint：根据题目和 teaching_tags 生成提示，不泄露答案；
- explain：提交答案后，根据 answer/explanation/atomic_trace 生成讲解；
- chat：只允许回答当前题目相关的教学问题；
- report-draft：根据医生输入生成结构化草稿；
- patient-card：根据医生审核后的诊断生成科普草稿；
- safety_review：检查是否越界。

禁止：给真实患者诊断；编造图像依据；输出未经审核的最终报告；建议具体治疗方案；生成患者身份信息。

当前可以用模板和规则实现，不必调用真实 LLM。请预留 LLMProvider 接口。
```

---

## 7. Skills 实现提示词

```text
请实现 Skills 系统。

SkillDefinition 字段：id, name, description, input_schema, output_schema, category, enabled, risk_level。

默认 skills：question_hint, answer_explain, atomic_feedback, false_premise_guard, next_question, report_structure, patient_card, safety_review, audit_log。

实现：GET /api/skills 返回 skill 列表；POST /api/skills/run 根据 skill_id 调用对应服务；每次调用写 audit log；高风险 skill 必须返回 doctor_review_required=true。
```

---

## 8. Memory 实现提示词

```text
请实现 MemoryService。

当前阶段使用 JSON 或 SQLite 均可。至少支持：session memory 当前题目、用户选择、最近对话；learner profile 题型正确率、薄弱项、最近错题；tutor memory 最近给过的提示，避免重复；audit memory 所有生成报告、卡片、辅导回复的日志；model memory 当前选择的辅导模型和风险标签。

接口：GET /api/learner/profile；GET /api/learner/recommendations。提交答案后必须更新 learner profile。
```

---

## 9. 前后端联调提示词

```text
请将 frontend 从本地 mock 数据切换为调用 backend API。

要求：创建 src/lib/api.ts；所有请求都有 loading/error 状态；后端不可用时 fallback 到本地 mock；.env 中设置 VITE_API_BASE_URL；训练中心、错因反馈、报告草稿、科普卡片、模型库、审计日志都接入 API；保证演示时即使后端挂了，前端仍能展示基础页面。
```

---

## 10. UI 打磨提示词

```text
请打磨前端 UI，让它更能吸引竞赛评委。

重点：首页像真实医疗教学工作台；训练中心三栏布局清楚；右侧智能辅导 Agent 对话有真实感；错因分析页面突出“原子事实反馈”；错误前提页面突出“证据不足/不适用”；报告草稿和科普卡片有医生审核标识；模型能力看板不要喧宾夺主；颜色专业，避免花哨；添加空状态、加载态、错误态；提供适合 PPT 截图的页面。
```

---

## 11. 安全审查提示词

```text
请进行医疗安全和隐私审查。

检查：是否有自动诊断表述；是否有具体治疗建议；是否有患者身份字段；是否有真实密钥；是否有服务器 IP 或密码；报告草稿是否标注医生审核；科普卡片是否标注不替代医患沟通；Agent 是否可能编造图像依据；错误前提题是否能表达证据不足；审计日志是否记录关键输出。

请列出问题并修复。
```

---

## 12. 最终交付提示词

```text
请整理最终交付。

输出：README.md、docs/API_SPEC.md、docs/DEMO_SCRIPT.md、docs/ARCHITECTURE.md、docs/SAFETY.md、截图清单、已实现功能、未实现功能、下一步开发路线。

请确保 README 中说明：项目用于教学训练和医生审核前辅助；不替代临床诊断；当前评测流水线为预留/mock，不是完整真实评测。
```

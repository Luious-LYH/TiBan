# 简历项目经历｜Agent 应用方向（修订版 v2.2.1）

## 项目名称

**EndoTutor 内镜智训 Agent｜医学研修可观测刷题系统**

技术栈：Python、FastAPI、Pydantic、React、TypeScript、Agent Workflow、Memory System、Evidence Retrieval、Tool Orchestration、Agent Evaluation

---

## 项目简介

面向消化内镜医生教学研修场景，设计并实现"题库训练—Agent 带教评分—错题巩固—自适应推荐"的多模态刷题系统。系统基于公开脱敏教学图像与医生自然语言作答，提供传统题库的今日任务、错题本、收藏、连续练习能力，并以**可观测 Agent 工作流**将检索、评分、安全核验和学习记忆串成可追溯闭环；仅用于教学训练或医生审核前辅助，不作为独立诊断依据。

---

## 核心技术实现

### 1. 有界 Agent 工作流设计

**问题**：单轮 Chat 无法可靠完成"观察—评分—学习更新"的研修任务，LLM 自主决策存在不确定性，医学场景不能容忍错误。

**解决方案**：设计 **Plan-Act-Observe-Verify-Memory** 五阶段有界工作流
- **Plan 阶段**：预定义工具调用序列（retrieve_evidence → grade_answer → safety_check），避免 LLM 随机决策
- **Act 阶段**：按序执行工具，记录 Tool Receipt（call_id、输入、输出、延迟、重试次数、error_code）
- **Observe 阶段**：聚合工具输出，生成结构化评分结果（命中事实、遗漏事实、证据引用）
- **Verify 阶段**：检查输出一致性和安全边界（是否越界诊断、是否缺少安全提示）
- **Memory 阶段**：回写学习状态（错题本、知识点掌握度、复习队列）

**技术亮点**：
- **Typed Tool Schema**：每个工具有 Pydantic 类型定义，输入输出强类型校验
- **故障注入与恢复**：支持 timeout、unavailable、validation_error 三类故障注入，最多重试 1 次，恢复率 100%（3/3 回归场景）
- **Checkpoint/Replay**：每次执行保存 checkpoint（最多 128 个），支持离线回放和调试
- **可观测性**：Context Manifest 记录上下文来源、优先级、预算分配；Usage Ledger 记录每个工具的调用次数、延迟分布

**量化结果**：
- 在 5 个 Golden Cases 上任务完成率 **100%**
- 固定离线回归中故障恢复率 **100%**（3/3 timeout 场景）
- P50/P95 本地规则服务延迟 **4.3/5.3 ms**（不含 LLM API 调用和网络传输）

---

### 2. Learning Memory 与自适应推荐

**问题**：传统刷题产品仅记录对错，无法针对薄弱知识点安排下一题；错题和收藏容易污染版本化题库，导致演示不可复现。

**解决方案 1 - Runtime State Isolation**：
- **版本化题库种子**：10+ 道教学病例和原子事实 Rubric 保持不可变，计算 SHA-256 哈希作为版本标识
- **运行态隔离**：收藏、错题本、复习队列、最近 100 次作答记录写入可重置运行态（`learner_profile.json`）
- **Demo Reset**：一键清空学习状态，题库哈希保持不变，确保演示可复现

**解决方案 2 - Adaptive Planning**：
- **多维度掌握度跟踪**：按 skill_dimension（病灶识别、证据不足识别、事实组合、属性判断等 8+ 维度）记录能力分（35-96 分）
- **优先级队列**：按"错题待巩固 → 未完成病例 → 最低掌握维度"生成今日 3-5 题计划
- **自动消错机制**：答对后自动从错题本移除，避免重复练习已掌握题目

**技术亮点**：
- **原子化记录**：每次作答记录错题 ID、最佳分、尝试次数、维度掌握度变化（Memory Delta）
- **弱化标签传播**：答错时将 error_tags 插入 weakness_tags，答对时从中移除，动态调整薄弱点
- **增量更新画像**：总题量、准确率、能力分、错题数实时更新，支持查看学习曲线（最近 8 天趋势）

**量化结果**：
- 支持 8+ 个 skill_dimension 的细粒度跟踪
- 错题本容量 16 题，最近错题 8 题
- 收藏题库容量 32 题
- API 回归验证：收藏切换、错题自动收录、再次作答消错、Demo Reset 后学习状态清空且题库哈希不变（100% 通过）

---

### 3. 原子事实级 Rubric 评分与证据溯源

**问题**：直接拼接 Prompt 评分时证据来源不清、评分依据不可量化、学生无法理解为什么扣分。

**解决方案**：
- **Rubric 原子化**：将标准答案拆解为原子事实（atomic_fact），每个事实关联：
  - `id`：唯一标识
  - `fact`：事实描述（如"画面中存在黏膜颜色改变"）
  - `expected`：预期观察（如"应识别为可描述异常"）
  - `evidence`：支持证据（如"视野中央偏右区域较周围更红"）
  - `skill_dimension`：关联知识点（如"病灶识别"）
  - `supported`：学生答案是否命中（true/false）

- **证据检索与匹配**：
  - 基于 BM25-equivalent 排序 + 数据集/部位元数据过滤
  - 每次检索保存 evidence_id、rank、score、source
  - 在 19 条固定 query-evidence 回归集上 Recall@1、Recall@3 均为 **100%**

- **评分计算**：
  - 命中事实 × 权重 → 得分
  - 遗漏事实 → 扣分
  - 错误推断 → 额外扣分
  - 生成逐项反馈（命中/遗漏事实列表 + 知识点标注 + 改进建议）

**技术亮点**：
- **可追溯性**：每个评分结果包含 evidence_id 列表，学生和面试官可沿证据回溯评分依据
- **多维度反馈**：按 skill_dimension 聚合反馈，告诉学生"病灶识别 80 分，证据不足识别 60 分"
- **安全核验**：检查是否越界诊断（如单凭图像给出"明确早期胃癌"），强制添加安全提示

**量化结果**：
- 19 条 query-evidence 回归集 Recall@1/3 均为 **100%**
- 安全探针覆盖率 **100%**（3/3 越界场景被拦截）
- 证据覆盖率 **100%**（5 个 Golden Cases 的所有 atomic_fact 都有 evidence_id）

---

### 4. ChatAgent 三模式交互式带教

**问题**：纯题库刷题缺少互动性，学生遇到不会的题无法获得即时帮助；全能 Chat 容易泄露答案。

**解决方案**：实现 **hint（引导）、explain（讲解）、chat（追问）** 三种交互模式

**Hint 模式**（题前引导）：
- 触发时机：学生点击"给我提示"按钮
- 行为：根据题目 teaching_tags 生成方向性引导，不直接给答案
- 示例："这道题考查黏膜观察能力，注意视野中央区域与周围的颜色差异"
- 记录：记录 tutor_interaction 到学习档案，但不改变能力评分

**Explain 模式**（题后讲解）：
- 触发时机：学生提交答案后点击"查看讲解"
- 行为：展示 atomic_feedback（命中/遗漏事实列表）+ knowledge_points + 知识点扩展
- 示例："你遗漏了'不能单凭该图给出恶性诊断'这个关键点，这属于证据不足识别能力"
- 记录：如果是错题，自动加入错题本；如果答对，更新对应 skill_dimension 的能力分

**Chat 模式**（延伸追问）：
- 触发时机：学生在题目页面发送自定义消息
- 行为：基于当前题目上下文回答追问，限制 scope 为 current_question_only
- 示例：学生问"什么是糜烂样改变？"，Agent 回答医学定义 + 内镜表现特征
- 安全检查：检测是否直接询问答案（"答案是什么"），拒绝回答并引导独立思考
- 记录：记录 tutor_interaction，标记为"带教辅导"

**技术亮点**：
- **防泄露机制**：Hint 和 Chat 模式下，Prompt 中不包含 answer 字段
- **会话隔离**：每个 session_id 独立记录对话历史，刷新后可恢复（通过 URL query 参数）
- **生成模式标记**：记录 generation_mode（rule / llm），支持后续评估 LLM 生成质量

**量化结果**：
- 支持 3 种交互模式，覆盖题前、题中、题后全流程
- 防泄露机制有效率 **100%**（安全探针测试）
- 会话恢复成功率 **100%**（刷新页面后对话历史保留）

---

### 5. Agent 评测与质量保证体系

**问题**：Agent Demo 容易只展示"看起来能跑"，却无法复盘质量与线上问题；缺少系统化评测手段。

**解决方案**：建立 **Context Manifest、Usage Ledger、Checkpoint/Replay、Agent Evaluation** 四层保障

**Context Manifest**（上下文清单）：
- 记录每个上下文来源：learner_profile（学习者画像）、question_context（题目信息）、evidence_pool（证据库）
- 标记优先级：high（必须）、medium（推荐）、low（可选）
- 预算分配：800 tokens 预算，按优先级分配给各来源
- 取舍规则：超预算时先裁剪 low 优先级内容，记录 truncated_sources

**Usage Ledger**（使用账本）：
- 记录每个工具的调用统计：total_calls、success_calls、error_calls、retry_calls
- 延迟分布：p50、p90、p95、p99
- 错误分布：按 error_code 聚合（timeout、unavailable、validation_error）
- 证据覆盖率：实际命中的 evidence_id 数量 / 总 evidence 数量

**Checkpoint/Replay**（检查点回放）：
- 每次 Agent 执行后保存 checkpoint（run_id、case_id、learner_answer、steps、receipts、result）
- 支持离线回放：从 checkpoint 恢复状态，重新执行工作流，验证结果一致性
- 回放成功率：5/5 Golden Cases 回放通过率 **100%**

**Agent Evaluation**（离线评测）：
- **Golden Cases**：5 个标准病例，覆盖基础识别、部位定位、异常描述、复杂推理
- **检索回归**：19 条 query-evidence 对，验证 Recall@1/3
- **故障注入**：3 类故障（timeout、unavailable、validation_error），验证恢复率
- **安全探针**：3 条越界诊断查询，验证拦截率

**量化结果**：
- Golden Cases 任务完成率 **100%**（5/5）
- 检索 Recall@1/3 均为 **100%**（19/19）
- 故障恢复率 **100%**（3/3）
- 安全拦截率 **100%**（3/3）
- 回放一致性 **100%**（5/5）
- P50/P95 延迟 **4.324/5.281 ms**（仅本地 Python 规则服务，不含 HTTP、LLM 调用和前端渲染）

---

### 6. 四模块产品架构与用户体验

**问题**：v2.1 单页三栏布局无法支持深链、会话恢复、移动端适配；技术术语暴露给用户（Run、Receipt、Memory Delta）。

**解决方案**：重构为 **学习总览、题库、刷题工作台、模型评测** 四模块架构

**学习总览（/）**：
- 今日任务进度（X/5 题）、待复习题目数、本周正确率、连续天数
- 题库卡片快速入口（食管/胃/小肠）
- 最近练习记录

**题库（/banks）**：
- 官方教学/个人题库筛选
- 搜索功能（按题目、知识点、部位）
- 题库导入校验（支持 JSONL / CSV / Markdown）
- 模板下载和预览摘要

**刷题工作台（/practice）**：
- 单题模式展示（一次只看一道题，避免信息过载）
- 侧栏 ChatAgent（桌面 320px 固定，移动端全屏覆盖）
- 会话恢复机制（通过 URL `session_id` 参数，刷新不丢失进度）
- 进度条和导航（上一题/下一题）

**模型评测（/eval）**：
- BYOK（Bring Your Own Key）API 配置
- 评测集选择（Endoscopy-mini-v1）
- 结果展示（准确率、平均延迟、JSON 有效率）
- API Key 不落盘（内存级传递，评测后销毁）

**用户体验优化**：
- **文案产品化**：将技术术语映射为用户语言
  - `retrieve_case_evidence` → "查找相关知识"
  - `fact_rubric_grader` → "知识点评分"
  - `Memory Delta` → "学习记录"
  - `Run Receipt` → "评分详情"
- **响应式设计**：移动端（< 640px）、平板（640-1024px）、桌面（≥ 1024px）三套布局
- **加载与错误状态**：Spinner 加载动画、友好的错误提示、空数据状态引导
- **图片统一处理**：max-h-96 object-contain，确保不同尺寸图片展示一致

**技术亮点**：
- React Router v6 支持深链（每个模块独立 URL）
- URL state 实现会话恢复（session_id、bank_id、question_id）
- Tailwind CSS 响应式 utilities
- TypeScript 严格模式类型检查

**量化结果**：
- 4 个独立模块，职责清晰
- 会话恢复成功率 **100%**（刷新后状态保留）
- 移动端适配完成度 **100%**（375px 无横向滚动）
- 构建通过率 **100%**（npm run build 584ms）

---

## 技术栈详解

### 后端技术
- **FastAPI**：异步 Web 框架，支持自动生成 OpenAPI 文档
- **Pydantic**：数据校验和类型注解，所有 API 请求/响应都有 Schema
- **Python 3.11+**：类型提示、match-case、异常组

### 前端技术
- **React 18**：函数组件 + Hooks
- **TypeScript**：严格模式，所有 API 有类型定义
- **React Router v6**：支持深链和嵌套路由
- **Tailwind CSS**：原子化 CSS，响应式设计
- **Lucide React**：图标库
- **Vite**：构建工具，HMR 快速刷新

### Agent 技术
- **Typed Tool Schema**：Pydantic 定义工具输入输出类型
- **Tool Orchestration**：有界工作流编排
- **Evidence Retrieval**：BM25 文本检索（计划升级为向量检索）
- **Memory System**：分层记忆（Working / Short-term / Long-term）
- **Agent Evaluation**：Golden Cases + 回归测试

---

## 项目量化指标

### 功能完整性
- **题库规模**：10+ 道教学病例，19+ 条原子事实 Rubric
- **题型支持**：基础识别、部位定位、异常描述、复杂推理
- **Agent 工作流**：5 个阶段（Plan / Act / Observe / Verify / Memory）
- **交互模式**：3 种（hint / explain / chat）
- **记忆维度**：8+ 个 skill_dimension

### 质量保证
- **任务完成率**：100%（5/5 Golden Cases）
- **证据覆盖率**：100%（19/19 query-evidence）
- **故障恢复率**：100%（3/3 timeout 场景）
- **安全拦截率**：100%（3/3 越界探针）
- **回放一致性**：100%（5/5 checkpoint）

### 性能指标
- **P50/P95 延迟**：4.3/5.3 ms（本地规则服务）
- **构建时间**：584ms
- **构建产物**：258.69 kB（gzip: 84.88 kB）
- **会话恢复**：100% 成功率

---

## 面试追问应对

### Q1: "你的题库有多少题？"
A: "当前有 10+ 道公开脱敏教学病例，每道题拆解为 2-4 条原子事实，形成 19+ 条 Rubric。题型包括基础识别、部位定位、异常描述。题库采用版本化管理，计算 SHA-256 哈希确保不可变性。"

### Q2: "为什么不用 LangChain？"
A: "评估过 LangChain，但医学场景有两个特殊要求：1）不确定性要可控，LLM 自主决策可能出错；2）可观测性要强，需要记录每个工具调用的完整输入输出。所以采用有界工作流，在 Plan 阶段确定工具序列，Act 阶段按序执行并记录 Receipt。"

### Q3: "RAG 用的什么模型？"
A: "当前采用 BM25 文本检索 + 元数据过滤，在 19 条固定 query-evidence 集上 Recall@1/3 均为 100%。计划升级为混合检索：text2vec-base-chinese-paraphrase 编码 + ChromaDB 向量库 + RRF 融合（0.3 BM25 + 0.7 Dense）。"

### Q4: "长短期记忆怎么划分？"
A: "当前是单层记忆（learner_profile.json），记录错题本、能力画像、复习队列。计划升级为三层：Working Memory（Redis，会话级，15 分钟 TTL）、Short-term Memory（SQLite，天级）、Long-term Memory（PostgreSQL，永久）。每日固化时识别错误模式并更新知识图谱。"

### Q5: "支持流式输出吗？"
A: "当前是普通 HTTP 请求，前端轮询获取结果。计划实现 SSE（Server-Sent Events）流式输出，Agent 执行过程实时推送阶段状态（Plan → Act → Observe → Verify → Memory），前端监听 event stream 并渐进式渲染。"

### Q6: "如何评估 Agent 质量？"
A: "建立了四层评测体系：1）Golden Cases（5 个标准病例，任务完成率 100%）；2）检索回归（19 条 query-evidence，Recall 100%）；3）故障注入（3 类故障，恢复率 100%）；4）安全探针（3 条越界查询，拦截率 100%）。"

---

## 简历精简版（推荐直接粘贴）

**EndoTutor 内镜智训 Agent | Python、FastAPI、React、Agent Workflow、Memory、Evaluation**

面向消化内镜医生教学研修，设计并实现"题库训练—Agent 带教评分—错题巩固—自适应推荐"的多模态刷题系统。

- **有界 Agent 工作流**：设计 Plan-Act-Observe-Verify-Memory 五阶段工作流，通过 Typed Tool Schema 和 Receipt 机制实现故障注入、重试恢复和完整可追溯性。Golden Cases 任务完成率 100%，故障恢复率 100%。

- **Learning Memory 系统**：Runtime State Isolation 设计确保收藏、错题、复习队列与版本化题库隔离；按"错题待巩固 → 未完成病例 → 最低掌握维度"生成今日计划，支持 8+ 维度细粒度跟踪。

- **原子事实 Rubric 评分**：将评分拆解为原子事实级别，每个事实关联 evidence_id 和 skill_dimension；基于 BM25 检索在 19 条回归集上 Recall@1/3 均为 100%。

- **ChatAgent 三模式交互**：实现 hint（引导）、explain（讲解）、chat（追问）三种模式，防泄露机制有效率 100%，支持会话恢复。

- **Agent 评测体系**：建立 Context Manifest、Usage Ledger、Checkpoint/Replay 机制，覆盖 5 个 Golden Cases、19 条检索查询、3 类故障注入；固定离线回归通过率 100%。

# 题伴 TiBan V3：21 条浏览器注释回应与改进实施计划

> 文档用途：把本轮浏览器验收中的 21 条注释，转换为可交给下一位 Agent 审阅、拆分和执行的产品与工程计划。本文档是分析和计划，不是本轮功能实现报告。
>
> 本轮边界：只新增本文档；不修改前端、后端、路由、数据库、测试、配置或旧文件。

## 1. 证据边界与当前基线

### 1.1 证据优先级

本文件按下面的优先级解释冲突：

1. 用户在本轮提出的 21 条意见和明确产品目标；
2. 当前分支源码、FastAPI/OpenAPI schema、真实 artifact 和现有测试；
3. V3 长期文档、Phase C / Phase D 报告；
4. 用户提供的浏览器截图和两张设置页截图，作为体验与信息架构参考，而不是代码事实。

浏览器选中的页面文字属于当前页面证据，不等于后端契约。设置页截图属于其他项目的参考，不代表题伴需要复制其完整功能。

### 1.2 当前仓库基线

- 仓库：E:/2.Projects/ARIS/Endoscopy_Agent/code
- 分支：refactor/v3-tiban-agent-experience
- HEAD：06d07b0 docs: polish public screenshot captions
- 工作树：存在大量早于本文件的修改、删除和未跟踪文件。本文件不对这些变更做清理、归因或恢复。后续 Agent 执行任何阶段前，都必须重新检查 git status、当前分支和目标文件是否已经被其他工作树变更影响。
- 当前 V3 主要真实链路：

~~~text
题库 → 创建刷题/考试 Session → 获取题目
→ 提交答案 → Attempt / mastery / FSRS / Learning Memory
→ 当前题目上下文 + 允许的检索 + 复盘上下文
→ SSE 智能辅导
~~~

当前真正存在的公共数据边界：

- Practice 公共题目来自 /api/v3/practice/questions 和 session detail；
- 作答由 /api/v3/practice/submit 进入后端确定性 workflow；
- 智能辅导由 /api/v3/tutor/stream 进入受权限控制的辅导智能体；
- 题库列表来自 /api/v3/question-banks；
- 题库导入校验能力已有 /api/question-banks/import/templates 和 /api/question-banks/import/validate；
- 资料生成链路是 /api/v3/factory/documents、/api/v3/factory/jobs、job 轮询和 publish；
- 评测只应投影已有 artifact 或真实候选模型运行，不应在前端制造指标。

### 1.3 统一术语

用户界面统一使用：

- 产品名：题伴 TiBan
- Tutor：智能辅导
- 技术文档中的 Agent 角色：辅导智能体
- Factory 的用户入口：题库导入；其中的资料生题子流程仍叫从资料生成题目
- Evaluation 的用户入口：模型评测
- 开发者或管理员内部能力：Agent 评测（内测）
- Practice 模式：刷题
- Exam 模式：考试
- Short answer：开放回答或问答题
- 没有官方解析：暂无解析

内部代码符号可以暂时保留 TutorSidecar、FactoryStudio、Evaluation 等旧命名，避免为了改名而进行无价值的目录搬迁。

## 2. 总体产品判断

题伴 V3 当前不需要更多一级页面，而需要让一条链路清楚可信：

~~~text
选择题库 → 选择刷题或考试 → 进入题目工作区
→ 需要时打开常驻智能辅导
→ 查看真实资料引用和题目上下文
→ 提交答案
→ 复盘错误、更新学习状态、安排下一轮复习
~~~

因此：

- Practice + 智能辅导是第一主线；
- 题库导入和从资料生成题目是第二主线；
- 模型评测面向用户解释“哪个模型在我的题目上更适合”，Agent 评测（内测）面向开发者解释“辅导智能体的检索、工具权限和记忆策略是否有效”；
- Knowledge、检索工作台、Standalone 智能辅导、空 Settings 不应为了平台完整感暴露为一级入口；
- 学习画像、雷达图、BI 大屏、课程管理和运营功能不进入当前核心范围。

## 3. 逐条回应 21 条注释

### 1. 最近活动只显示“进入复盘 / 回答正确”，用户不知道自己做了什么

#### 结论

这个判断成立。当前“学习记录”更像 Attempt 状态日志，不是对学习者有意义的活动记录。单独显示“进入复盘”不能说明题库、题目、题型或结果，信息价值很低。

#### 当前实现证据

- [frontend/src/pages/overview/OverviewPage.tsx](../../frontend/src/pages/overview/OverviewPage.tsx#L22) 只把 recent_sessions 映射为“回答正确”或“进入复盘”、时间和分数。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L256-L262) 的 RecentSessionPublic 只有 attempt_id、question_id、score、correct、created_at。
- [backend/app/db/repositories.py](../../backend/app/db/repositories.py#L477-L525) 查询了 Attempt，但没有联结题目、题库和 Session 来构造学习者可读的信息。

#### 改进方案

把“学习记录”改为“最近作答”，每条至少表达：

- 题库名称；
- 题目标题或安全截断后的题干摘要；
- 题型；
- 作答结果：答对 / 待复盘；
- 时间；
- 分数只在该题型和评分语义确实成立时显示。

推荐 API 投影增加 bank_id、bank_name、session_id、question_title、question_type、question_preview 或等价字段。这个投影应由后端一次查询完成，避免前端根据 question_id 逐条请求造成 N+1。

交互上只提供真实存在的动作：

- 有 session 深链能力时显示“查看本次练习”；
- 没有精确定位当前题目的能力时，不伪造“打开这道题”；
- 错题复习页尚未成熟时，可以只展示记录，不放会进入半成品页面的按钮。

#### 业务行为影响

只改变 Overview 的只读投影和文案，不改变 Attempt、评分、掌握度、FSRS 或 Memory。需要新增或扩展 typed API 字段。

#### 验收条件

- 用户能从一条记录看出做的是哪个题库、哪道题、什么题型和结果；
- 没有只显示“进入复盘”的无上下文日志；
- API 一次返回所需数据；
- 没有把缺失字段用虚构题目或默认题库名填充。

### 2. “答案与当前评分规则不一致”为什么被当成知识点，怎么改进

#### 结论

这不是知识点，而是内部评分诊断标签。当前实现把“提交答案没有匹配标准答案”包装成 error_tag，又把 error_tag 同时用于用户解析和首页 weak_areas，所以用户才会看到一个不像知识点的句子。

#### 当前实现证据

- [backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L274-L298) 在客观题答错时返回“答案与当前评分规则不一致”。
- [backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L300-L307) 又把 error_tags 拼进 learner-facing explanation。
- [backend/app/db/repositories.py](../../backend/app/db/repositories.py#L511-L523) 从近期 Attempt 的 error_tags 直接生成 weak_areas。
- [frontend/src/pages/overview/OverviewPage.tsx](../../frontend/src/pages/overview/OverviewPage.tsx#L20) 把 weak_areas 标为“近期薄弱知识点”。

#### 改进方案

严格分开三类信息：

1. 内部评分诊断：保留 error_tags，用于审计、测试和调试；
2. 用户可读反馈：例如“这次没有选中标准答案，请回到题干逐项比较”，不暴露内部规则名称；
3. 薄弱知识主题：只能来自 question.topic、subject、经治理的教学标签或后端明确的 mastery 聚合，不能来自错误标签文本。

“如何改进”应落到实际动作上：提交错误后，显示“回看题干条件”“向智能辅导追问”“加入复习队列”等真实操作。不要仅显示一个负面标签。

#### 业务行为影响

评分结果和内部 error_tags 继续保留；改变用户反馈和 Overview 的 weak_areas 投影。需要调整后端聚合语义，不能只在 CSS 或前端过滤文字。

#### 验收条件

- “答案与当前评分规则不一致”不再作为知识点显示；
- 首页薄弱区域显示真实主题，或者在主题缺失时显示“暂未标注主题”；
- 内部测试仍能检查 error_tags；
- 用户能看到错误后的下一步，而不是只看到一句内部诊断。

### 3. 开放回答题应该如何处理，是否要 AI 解析

#### 结论

当前短答题已经被后端按 expected_facts 自动评分，这与用户提出的“先展示我的回答和标准答案，由用户自己查看；AI 解析可选”不是同一产品语义。不能只在前端隐藏分数，否则后端仍然在做一个用户没有选择的评判。

#### 当前实现证据

- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L72-L74) 公开题目只区分 short_answer。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L110-L114) 私有评分契约包含 rubric、expected_facts、reference_constraints。
- [backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L287-L297) 用关键事实覆盖率计算分数，并以 80 分作为正确阈值。
- [backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L309-L323) 对短答返回“参考答案见题目解析与评分 rubric”。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L143-L159) 统一使用 AnswerControl 和 ResultPanel，当前短答也会进入 is_correct、score 和解析展示。

#### 改进方案

为开放回答增加明确的评估语义，而不是复用客观题的布尔结果：

- 默认模式：自我对照。记录用户回答，展示用户回答和参考答案/标准答案；状态叫“已记录”，不显示答对或答错；
- 可选模式：AI 解析。用户主动点击后，辅导智能体或专用解释任务才被调用；
- 若题目本身只有 rubric 没有公开标准答案，应明确显示“参考要点”而不是伪造一段标准答案；
- AI 解析结果应结构化为“覆盖到的要点、遗漏要点、表达风险、建议复习方向”，不直接改写 Attempt 的原始回答，也不替代题库标准答案；
- AI 解析失败时显示失败原因和重试，不回退成假分数。

建议增加类似 answer_evaluation_mode、reference_answer_display、ai_analysis_status 的 typed 字段。内部仍可暂时保留确定性评分以兼容历史数据，但在产品语义上必须标记为内部/实验评分，不能继续以客观题反馈呈现。

AI 解析不应新建第二套独立 Agent。优先让现有辅导智能体复用受控 Context、来源和安全边界，并用显式 purpose=answer_review 或独立 typed endpoint 区分普通追问和 AI 解析。

#### 业务行为影响

会改变短答题的用户可见语义，并可能需要 schema、存储和新的只读/生成接口；不是单纯文案任务。不要在 API 尚未支持前先做一个“AI解析”按钮。

#### 验收条件

- 短答提交后不会默认显示“正确/错误”；
- 用户能清楚区分自己的回答、参考答案和可选 AI 解析；
- AI 解析为主动操作，且失败不伪造成功；
- 原始回答和后端学习记录仍可审计。

### 4. “题目生成”是否应该改成“题库导入”

#### 结论

从用户视角，题库页的主要动作确实更适合叫“题库导入”。但不能直接把当前资料生题页面改名后假装它已经是“导入已有题目”，因为两条链路不同。

#### 当前实现证据

- [frontend/src/pages/banks/BanksPage.tsx](../../frontend/src/pages/banks/BanksPage.tsx#L27-L31) 在题库页用“题目生成”链接到 /factory。
- [frontend/src/components/factory/FactoryStudio.tsx](../../frontend/src/components/factory/FactoryStudio.tsx#L20-L21) 当前页面是上传资料、创建 Factory job、轮询、审核草稿、发布题目。
- 已有题库导入校验接口位于 [backend/app/routers/api.py](../../backend/app/routers/api.py#L165-L177)。
- 现有导入服务在 [backend/app/services/question_bank_import_service.py](../../backend/app/services/question_bank_import_service.py#L16-L19) 声明支持 jsonl、csv、markdown。

#### 改进方案

把用户入口设计成“题库导入”，进入同一个清晰的导入工作区，内部区分两种真实能力：

1. 导入已有题目：上传或粘贴 JSONL、CSV/TSV、Markdown，先校验字段，再预览错误和通过行；
2. 从资料生成题目：上传教学资料，走现有 Parse → Index → Generate → Gate/Judge/Repair → Review → Publish 链路。

“从资料生成题目”应是次级选项，并明确说明它会生成草稿、需要审核；不能和“导入已有题库”混用。

如果当前阶段仍不准备做统一工作区，最小方案是：

- 题库页主 CTA 改为“题库导入”；
- /factory 页面标题改为“题库导入”，页面内部以“导入已有题目”和“从资料生成题目”两张入口卡区分；
- 保留现有 Factory API 语义，不通过改标题改变后端行为。

#### 业务行为影响

主导航和页面 IA 会变，但已有导入 API 和 Factory job 不应被重写。需要补的是用户入口和能力边界说明。

#### 验收条件

- 用户不会以为上传 PDF 就等同于上传现成题库；
- “从资料生成题目”明确是草稿和审核流；
- “导入已有题目”能指向真实的 validate API；
- 不出现没有后端支持的“导入成功”。

### 5. 题库搜索去掉“部位”

#### 结论

用户界面应把 placeholder 改为“搜索题库”，不要要求用户理解“部位”这个过滤维度。

#### 当前实现证据

- [frontend/src/pages/banks/BanksPage.tsx](../../frontend/src/pages/banks/BanksPage.tsx#L18-L31) 的 placeholder 是“搜索部位、题库名称…”，并在前端把 name、description、body_parts 拼接搜索。

#### 改进方案

第一步只改用户文案为“搜索题库”。同时建议把可见筛选收敛为：

- 搜索题库名称或描述；
- 学习领域；
- 题型。

如果产品决定“去掉部位”也意味着取消隐式 body_parts 搜索，则同步把 BanksPage 的 matchesSearch 改为只搜索 name 和 description；这是一个小的搜索语义变化，应加测试。不要保留一个用户看不见但行为不一致的“部位筛选”说明。

#### 业务行为影响

只改 placeholder 时不改变业务；取消 body_parts 隐式匹配时会改变前端筛选行为，但不改变后端接口。

#### 验收条件

- 搜索框显示“搜索题库”；
- 题库页不出现“搜索部位”；
- 搜索结果规则和说明一致；
- 空结果仍有清晰的清空搜索动作。

### 6. “学习”改成“刷题”，“作答后查看解析与 Tutor”改成“边做题边智能辅导”

#### 结论

应修改。用户需要的是行动语言，而不是内部产品模式或实现名词。

#### 当前实现证据

- [frontend/src/components/practice/SessionBuilder.tsx](../../frontend/src/components/practice/SessionBuilder.tsx#L30) 当前显示“学习”和“作答后查看解析与 Tutor”。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L13) 通过 modeLabels 显示“学习模式”。
- 后端继续使用 study 枚举是合理的内部协议，不需要为了中文产品名改 API。

#### 改进方案

显示文案改为：

- 刷题
- 边做题边智能辅导

内部仍发送 mode=study，避免无意义的 API 和数据库迁移。进入刷题后直接进入题目工作区，不再要求用户理解 Session、Tutor 或评分实现。

#### 业务行为影响

只改变用户可见文案；不改变 study 的权限、评分和智能辅导行为。

#### 验收条件

- 用户界面不出现 Tutor；
- 刷题入口说明是边做题边智能辅导；
- 前端请求仍使用 study；
- 既有 Study / Exam 权限测试继续通过。

### 7. “模拟”改成“考试”

#### 结论

应修改。“模拟”容易让用户误解为一套单独的模拟业务；当前真实语义是考试阶段限制即时答案和解析，结束后复盘。

#### 当前实现证据

- [frontend/src/components/practice/SessionBuilder.tsx](../../frontend/src/components/practice/SessionBuilder.tsx#L30) 当前第二个选项是“模拟 / 完成后统一复盘”。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L182-L187) 的 mode 枚举已有 exam。
- [backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L185-L212) 在 exam 模式锁定答案和解析。

#### 改进方案

显示为：

- 考试
- 完成后统一复盘

进入 Practice 后显示“考试中”，智能辅导按钮可以保持禁用或显示“考试结束后复盘”，不能在考试中泄露答案。

#### 业务行为影响

只改文案；后端仍使用 exam，既有权限边界不变。

#### 验收条件

- 页面、按钮和 aria 文案均使用“考试”；
- 考试中不显示正确答案和即时解析；
- 考试结束后可以进入真实复盘；
- 测试确认 get_answer_explanation 在 exam 中不可用。

### 8. 题量选项不要太固定，40 题是否换成自定义

#### 结论

应采用“常用预设 + 自定义题数”，并注意当前“全部”语义并不完全真实。

#### 当前实现证据

- [frontend/src/components/practice/SessionBuilder.tsx](../../frontend/src/components/practice/SessionBuilder.tsx#L30) 当前预设为 10、20、40、100，并把 100 显示为“全部”。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L182-L187) 当前 question_count 允许 1–100。

#### 改进方案

推荐第一版：

- 10 题
- 20 题
- 30 题
- 50 题
- 自定义

自定义输入限制为 1–100，输入错误时在弹窗内提示，不创建 Session。不要把 100 叫“全部”，因为题库可能超过 100 题；如果题库总量不超过 100，才可以显示“本题库全部（N 题）”并提交真实 N。超过 100 题时显示“最多 100 题”更诚实。

#### 业务行为影响

Session 创建的 question_count 会改变用户选择，但仍在后端 1–100 合法范围内。需要补输入校验和测试。

#### 验收条件

- 常用选项覆盖 10、20、30、50；
- 自定义可输入 1–100；
- 不把最多 100 题伪称为全部；
- 进入 Practice 后不再出现题量选择。

### 9. 用户导入题库没有知识点、难度、部位时怎么办

#### 结论

不能编造，也不能用 body_part 冒充知识点。后台可以保存“未知/未标注”状态，前端只展示有真实来源的字段。

#### 当前实现证据

- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L35-L55) 当前公共题目要求 body_part 和 difficulty 有值。
- [backend/app/db/models.py](../../backend/app/db/models.py#L35-L75) 当前 QuestionModel 的 difficulty、body_part 为非空字段。
- [backend/app/services/question_bank_import_service.py](../../backend/app/services/question_bank_import_service.py#L190-L233) 会用 default_body_part，且会把缺失标签回填为 body_part 和 question_type。
- [backend/app/services/question_bank_import_service.py](../../backend/app/services/question_bank_import_service.py#L302-L304) 缺失或非法 difficulty 默认成“入门”。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L119-L120) 在知识点缺失时会回退到 body_part。

#### 改进方案

区分三种状态：

1. 用户原始提供；
2. 由受控导入规则推断；
3. 未提供。

对当前已有非空数据库字段，可以先不做大规模迁移，采用显式的“未标注”保留值或 metadata_source 标记；但不能再把默认值当作用户真实标签。后续 schema 允许时，优先将 subject、topic、body_part、difficulty 变成可空或带来源的字段。

前端显示策略：

- 有 topic 才显示知识点；
- 有 difficulty 且来源可靠才显示难度；
- body_part 只在题目确实提供部位时显示；
- 缺失字段显示“未标注”或直接省略；
- 不用 body_part 填充“知识点”；
- 不用默认“入门”制造学习画像或难度判断。

题库列表中的统计也应区分“已标注”和“未标注”，而不是把默认值计入真实统计。

#### 业务行为影响

会改变导入数据规范和题目元数据语义，可能需要兼容性迁移；评分主流程不应受影响。

#### 验收条件

- 构造缺少 subject、topic、body_part、difficulty 的导入样例；
- API 和页面都不伪造这些字段；
- 缺失字段不会被错误地用于“薄弱知识点”；
- 旧题库数据仍能读取。

### 10. 题单为什么被删除，如何恢复

#### 结论

应该恢复一个轻量题单，而不是恢复旧版复杂的顶部控制区。题单是刷题工作区中帮助定位和复习的核心工具，不属于普通运营模块。

#### 当前实现证据

- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L112-L116) 当前只有“当前题号 / 总数”、进度和标记按钮。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L207-L215) 已有 PracticeSessionQuestionStatePublic 和 session detail items，状态包含 unanswered、correct、incorrect。
- [backend/app/routers/practice.py](../../backend/app/routers/practice.py#L95-L103) 已支持按 state 查询 session detail。
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts#L105-L107) 当前 getPracticeSession 的返回类型写成 SessionResponse，未充分利用 detail.items 类型。

#### 改进方案

在 Practice 顶部或右上角放一个“题单”按钮，打开一个轻量 Popover/Sheet：

- 按单选、多选、判断、开放回答分组；
- 每道题使用小圆形或短编号；
- 当前题：深色或描边状态；
- 未作答：中性；
- 已答正确：绿色；
- 已答错误：红色；
- 已标记：增加小标记，不覆盖正确/错误状态；
- 点击后跳转到该 Session 中真实存在的题目。

状态来源必须是 session detail / Attempt 投影，不由前端猜测。移动端用 Sheet，桌面端用 Popover 或侧边浮层。题单只承担导航，不再塞进题库筛选、学习推荐和统计报表。

第一版除题单外不需要恢复复杂功能。必要的补充只有“当前题、作答状态、标记、上一题/下一题、提交后复盘入口”。

#### 业务行为影响

主要是利用已有 session detail 的只读能力和前端导航状态；不改变评分。若当前 API 没有精确的 question index 深链，需要先补一个稳定的前端状态或 typed 字段。

#### 验收条件

- 桌面和移动端都能打开题单；
- 题单状态与真实提交结果一致；
- 点击题号可以回到对应题目；
- 考试模式不因此泄露答案解析；
- 不恢复旧版大题号导航和重复进度卡。

### 11. Tutor 显示“模型网关不可用”是怎么回事，AI 接口如何配置

#### 结论

这条错误表示当前请求走到了显式启用但不可达或调用失败的外部 Provider 路径，不等于题目、RAG 或 Practice 本身不可用。当前项目不是把 API key 写在前端，而是由后端环境变量或本地受控 Provider 配置决定是否启用外部模型；没有可用 Provider 时可以使用既有 local-policy adapter。

#### 当前实现证据

- [backend/app/services/agent_runtime.py](../../backend/app/services/agent_runtime.py#L187-L213) 在 gateway 选择或调用失败时产生网关错误。
- [backend/app/adapters/tutor_dependencies.py](../../backend/app/adapters/tutor_dependencies.py#L151-L184) 负责 Tutor 依赖和 configured_tutor_gateway。
- [backend/app/core/config.py](../../backend/app/core/config.py#L52-L80) 读取 LLM_PROVIDER、LLM_BASE_URL、LLM_API_KEY、LLM_MODEL、TUTOR_PROVIDER_ENABLED 等环境配置。
- [backend/app/services/llm_provider.py](../../backend/app/services/llm_provider.py#L117-L178) 负责判断 Provider 是否配置、做地址安全检查和连接前置检查。
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts#L117-L137) 的 SSE 请求没有用户级 Provider 配置参数。

不要在文档、日志、截图或 UI 中输出任何真实 key、完整 base URL、内部 IP 或 token。当前错误的准确原因应通过后端错误类别和脱敏诊断确认，而不是在页面上猜测。

#### 设置页建议

用户提供的两张其他项目设置截图，值得学习的最小部分是：

- 设置作为独立入口；
- 设置内部有清晰的分组；
- 每个字段有用途、范围和安全说明；
- 有“测试连接”而不是只提供保存；
- 明确区分平台提供的服务和用户自己的 key；
- 保存动作可见且有反馈。

题伴当前阶段只需要一个最小“智能服务”设置区域：

1. 当前运行模式：本地规则 / 平台 Provider / 用户临时连接；
2. 模型服务连接测试；
3. 当前模型和连接状态；
4. “仅本次使用”的临时 API Base、模型和 key；
5. 明确说明 key 不写入浏览器 localStorage、不出现在 URL、不写入 artifact。

如果要支持真正的 BYOK 持久化，必须先有用户身份、服务端加密存储或系统 keychain、权限边界、删除和轮换接口；不能为了看起来完整，把 key 存进 localStorage。没有这些后端契约时，Settings 应隐藏或只显示真实的只读诊断，不能提供假的“保存成功”。

#### 业务行为影响

错误文案和诊断可以改善；真正持久化用户 Provider 是新的安全和后端能力，不应在当前 UI 阶段伪造。

#### 验收条件

- Provider 未配置、连接失败、连接成功三种状态可区分；
- 页面不泄露 key；
- 不能通过 Settings 假装持久化；
- local-policy 模式下智能辅导的真实 Context、Retrieval 和 Citation 仍可用；
- 外部 Provider 是 opt-in，不成为本地核心流程的强依赖。

### 12. 是否增加设置，哪些内容值得借鉴

#### 结论

可以保留一个独立“设置”入口，但只有在它承载至少一个真实能力时才进入主导航。当前空的 Preview 设置页不值得暴露。

#### 当前实现证据

- [frontend/src/app/router.tsx](../../frontend/src/app/router.tsx#L23) 当前 /settings 是 PreviewPage，文案明确表示暂不承载业务配置。
- [frontend/src/app/AppShell.tsx](../../frontend/src/app/AppShell.tsx#L12-L29) 当前导航没有 Settings。
- Provider 真实配置和连接状态在后端已有读取、preflight 和调用边界，但没有面向用户的持久化 BYOK API。

#### 改进方案

分两步：

- 当前核心阶段：不显示空 Settings 一级入口；如果需要诊断，可在智能辅导或模型评测的错误状态中提供“查看连接说明”的真实链接；
- 最小设置阶段：实现“智能服务连接”只读状态 + 一次性测试连接；后端契约明确后再加保存和切换。

不照搬截图里的 Embedding、语音识别、额度、数据迁移、账户、图谱等模块。它们与题伴当前第一主线没有直接关系，会把 Agent 体验再次变成后台管理台。

#### 业务行为影响

导航和配置体验变化；不应影响 Practice、题库或后端默认运行模式。

#### 验收条件

- 空页面不进入一级导航；
- 设置里每一个开关和状态都能对应真实 API；
- 没有假保存、假连接成功和假额度；
- 配置失败时能给出下一步，而不是只显示 ApplicationError。

### 13. 没有预置解析时是否显示“无解析”，右上角加 AI 解析

#### 结论

这个方向合理，而且应优先采用“暂无解析 + 用户主动请求 AI 解析”。当前代码已经有 official_explanation_available 和 explanation_source，问题是前端没有按它们控制展示。

#### 当前实现证据

- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L233-L253) 的 PracticeSubmitResponse 已有 explanation_source 和 official_explanation_available。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L155-L159) 无条件渲染 result.explanation。
- [backend/app/services/qbank_import_service.py](../../backend/app/services/qbank_import_service.py#L94-L110) 当前对空 explanation 会填入“官方解析暂无；请结合题干和课程资料复核”，同时标记 explanation_available=false。

#### 改进方案

解析区域按来源呈现：

- official_explanation_available=true：显示“题库解析”，可显示人类可读来源；
- false：显示“暂无解析”，右上角显示“AI解析”；
- 考试未结束：不显示解析按钮；
- AI 解析请求中：显示“正在分析题干和允许的资料…”；
- 成功后：在独立的“AI解析”区域显示结果，不覆盖官方解析；
- 失败后：显示失败和重试，不退回一段默认假解析。

“AI解析”应是显式的 typed 操作。可以复用辅导智能体的 Context、权限、RAG 和 Citation，但需要区分普通对话和结构化解析目的。不要把一次普通 Tutor 追问偷偷当成 AI 解析，也不要在没有 API 的情况下仅做按钮动画。

#### 业务行为影响

需要调整题库导入的空解析语义，并可能增加 AI 解析 endpoint 或扩展现有 Tutor contract。不会改变官方答案和评分。

#### 验收条件

- 无官方解析时页面显示“暂无解析”；
- AI 解析只有用户主动点击才运行；
- 官方解析不被覆盖；
- Citation 和 AI 解析来源来自真实调用；
- 失败状态不会显示成功结果。

### 14. “已提交 / 你的答案 / 正确答案”重复，选项颜色已经足够

#### 结论

对客观题，这个判断成立。当前反馈条重复了选项已经表达的信息，增加了卡片高度和视觉噪声。开放回答则需要保留回答与参考答案对照，但不应套用客观题的重复条。

#### 当前实现证据

- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L143-L149) 已在 OptionButton 上使用 selected、is-correct、is-wrong。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L151-L159) ResultPanel 又重复展示已提交、你的答案、正确答案。

#### 改进方案

- 单选、多选、判断：选项颜色和图标表达对错；反馈区只保留“已记录”和解析标题；
- 错误状态仍需有可访问的文字状态或 aria-live，不能只依靠颜色；
- 开放回答：保留“你的回答”和“参考答案/参考要点”两栏，用于自我对照；
- 考试模式：继续隐藏正确答案和解析。

#### 业务行为影响

只改变反馈 UI；后端返回值、Attempt 和评分不变。若短答进入自我对照模式，则按第 3 条的 typed 契约调整。

#### 验收条件

- 客观题不再重复列出完整答案；
- 错误和正确状态在颜色、图标和文字上都可理解；
- 开放回答仍能查看自己的原文；
- 不因压缩 UI 丢失复盘入口。

### 15. 错题与复习的当前体验不好

#### 结论

问题不只是视觉，而是页面语义不完整。当前 /practice?mode=review 复用刷题工作区，却没有自己的题库选择、到期状态和复习入口，所以用户会觉得它只是普通刷题页面换了一个标题。

#### 当前实现证据

- [frontend/src/app/AppShell.tsx](../../frontend/src/app/AppShell.tsx#L12-L29) 把错题与复习放在学习组内并作为可点击导航。
- [frontend/src/app/router.tsx](../../frontend/src/app/router.tsx#L13-L18) 没有独立 ReviewPage，直接复用 PracticePage。
- [frontend/src/pages/practice/PracticePage.tsx](../../frontend/src/pages/practice/PracticePage.tsx#L35-L44) 没有 bank_id 时会回退到第一个题库。
- 当前 Practice 里只有有限的 FSRS 反馈按钮，不能替代完整的复习入口。

#### 改进方案

当前阶段不要继续扩展半成品 Review 页面。按用户建议：

- 侧栏把“错题与复习（开发中）”作为独立分组中的纯文本或禁用项；
- 不让它跳转到一个看起来像完整产品、实际没有题库选择的页面；
- 保留 /practice?mode=review 的兼容深链，供已有测试和内部验证使用；
- 后续真正实现 Review 时，第一屏必须有题库/领域选择、待复习数量、错题数量、最近复习状态和明确开始按钮。

#### 业务行为影响

隐藏或禁用一级入口，不删除后端 Review/FSRS 能力；兼容路由可以继续存在。

#### 验收条件

- 主导航不会把未完成 Review 伪装成可用功能；
- 旧深链不被无意删除；
- 未来 Review 的最小信息契约已明确；
- 不新增雷达图、画像和复杂统计来掩盖流程缺失。

### 16. 错题与复习应脱离学习栏，显示“开发中”

#### 结论

同意。第 15 条描述问题，第 16 条给出了当前最合适的产品动作：移出“学习”主任务组，作为独立的开发中入口，但不带跳转。

#### 改进方案

建议导航结构为：

~~~text
学习
  学习首页
  题库
  刷题

复习
  错题与复习（开发中）  ← disabled，不是 Link

题库工具
  题库导入              ← 仅当入口已接入真实导入/Factory 能力时显示

模型
  模型评测
  Agent 评测（内测）    ← 仅内部或 disabled

系统
  设置                  ← 只有真实设置能力接入后显示
~~~

如果产品希望更激进地减法，也可以在 Review 尚未准备好前完全隐藏它；“开发中”应只在有明确路线且用户需要知道其存在时使用，不能成为所有 Preview 页的借口。

#### 具体代码位置

- 导航结构与 disabled item 类型：[frontend/src/app/AppShell.tsx](../../frontend/src/app/AppShell.tsx#L1-L79)
- 当前复用路由：[frontend/src/app/router.tsx](../../frontend/src/app/router.tsx#L13-L18)
- Session detail 状态来源：[backend/app/services/stage1_service.py](../../backend/app/services/stage1_service.py#L95-L121)

#### 业务行为影响

一级导航行为变化；不改变复习后端。

#### 验收条件

- “错题与复习（开发中）”没有可点击死链；
- 侧栏不把它和“刷题”做成同等级的已完成任务；
- 用户能理解它为什么暂未开放。

### 17. 不想在使用界面看到“教学训练与医生复核前辅助 · 不作为独立诊断依据”

#### 结论

可以去掉全局重复 footer，但不能删除后端安全契约，也不能把医疗教学输出伪装成无边界的普通内容。

#### 当前实现证据

- [frontend/src/app/AppShell.tsx](../../frontend/src/app/AppShell.tsx#L65-L79) 在非 Practice 页面统一显示该 footer。
- [backend/app/core/config.py](../../backend/app/core/config.py) 和多个 schema/service 持续输出 SAFETY_NOTICE。
- [backend/app/schemas/stage1.py](../../backend/app/schemas/stage1.py#L245-L246) 的 PracticeSubmitResponse 仍有 doctor_review_required 和 safety_notice。

#### 改进方案

- 删除全局、重复、与当前任务无关的 footer；
- 保留后端 safety_notice、doctor_review_required 和 artifact 安全字段；
- 在真正生成医疗教学内容、资料生成草稿或需要医生复核的输出处，采用一次、短的、上下文相关的说明；
- 不把安全边界塞到每一张卡片、每一个按钮和每一条智能辅导回答里；
- 不删除技术文档和发布报告中的安全边界。

这不是把安全信息全部抹掉，而是把契约层和用户工作流层分开。若法规或项目安全规则要求某一具体输出可见声明，应按输出场景保留，不用全局 footer 重复。

#### 业务行为影响

改变前端布局和文案；保留安全数据与服务端行为。

#### 验收条件

- 普通浏览页面不再反复显示该长句；
- 医疗输出仍可追溯到安全字段；
- 不出现“已临床验证”“诊断结论”等越界表达。

### 18. 题目生成请求失败（413）是什么原因，是 AI 没配置还是功能没开放

#### 结论

413 首先应按请求体大小或代理限制排查，不能直接归因于 AI 未配置。当前前端先把文件转为 Base64 放进 JSON，体积会比原始文件更大；后端又有独立的 5 MiB 原始内容限制。若 Provider 未配置，通常应在任务执行或 Provider 调用阶段产生另一类错误，不是 413 的充分解释。

#### 当前实现证据

- [frontend/src/components/factory/FactoryStudio.tsx](../../frontend/src/components/factory/FactoryStudio.tsx#L7-L20) 用 FileReader 读成 Base64，再通过 JSON 上传。
- [frontend/src/api/client.ts](../../frontend/src/api/client.ts#L163-L166) 调用 uploadFactoryDocument 发送 content_base64。
- [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L35-L39) 只允许 .md、.pdf，原始内容上限是 5 MiB。
- [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L139-L151) 在服务层检查后写入上传目录。
- [frontend/nginx.conf](../../frontend/nginx.conf#L10-L23) 是前端容器的 Nginx API 代理配置，必须与后端限制一致。

#### 改进方案

排查顺序：

1. 浏览器 Network 查看 413 的响应头和响应体，确认是 Nginx、FastAPI 还是上游；
2. 同时看 frontend Nginx 和 backend 日志；
3. 用小于限制的 .md、接近限制的 .md、超过限制的 .md 分别测试；
4. 前端在上传前按原始文件大小校验，并显示“文件超过 5 MiB”；
5. 代理上限应覆盖 Base64/JSON 的额外开销，但不能无限放大；
6. 如果长期需要大文件，优先设计 multipart 或分片/流式上传，而不是单纯把代理上限改成很大。

错误必须分层显示：

- 413：文件太大或请求格式超限；
- .md/.pdf 以外：格式不支持；
- Provider 失败：任务在生成阶段失败，显示 Provider 诊断；
- Worker 未运行：显示队列状态。

#### 业务行为影响

会改变上传校验、代理配置或未来上传协议；不改变 Factory 的 Generator、Judge、Repair、Review、Publish 语义。

#### 验收条件

- 能定位 413 的真实责任层；
- 小文件可以真实上传并进入 job；
- 超限文件在前端或 API 得到明确错误；
- 不用“AI 未配置”掩盖请求体问题；
- 现有真实 worker 链路不被破坏。

### 19. 为什么只支持 md/pdf，生成规则是什么，是否支持 Excel/Anki 类导入

#### 结论

当前 .md/.pdf 是“从教学资料生成题目”的输入限制，不是“自定义题库导入”的完整方案。用户的需求包含两种不同能力：从资料生成题目，以及导入用户已经整理好的题目。应先把这两条能力分开，再扩展格式。

#### 当前实现证据

- [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L35-L39) 只允许 .md 和 .pdf。
- PDF 会被 [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L262-L273) 转成 Markdown，再进入后续流程。
- 默认生成器 [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L276-L290) 是依据 source evidence 生成单选草稿的确定性实现。
- Provider 生成器 [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L307-L345) 有明确的 Generator prompt，并设置 allow_fallback=false。
- Judge/Gate 在 [backend/app/services/factory_service.py](../../backend/app/services/factory_service.py#L348-L369) 校验来源、答案一致性、干扰项和安全边界；Repair 不是无条件成功。
- 已有自定义题库校验服务支持 JSONL、CSV、Markdown；模板位于 [backend/app/services/question_bank_import_service.py](../../backend/app/services/question_bank_import_service.py#L67-L92)。

#### 生成规则说明

资料生题不是纯粹把所有决定交给大模型：

1. 文档经过格式和大小校验；
2. PDF 转文本；
3. 资料被解析和索引；
4. Generator 只看到被选中的 evidence 和目标；
5. 生成单选题草稿；
6. Gate 检查 canonical source chunk；
7. Judge 检查 grounding、答案一致性、citation、干扰项和教学边界；
8. 不通过才生成 Repair revision；
9. 人工审核后才能发布入题库。

若启用 Provider，Generator 和 Judge 都是明确的受控调用；Provider 失败不能由确定性答案冒充成功。

#### 格式改进顺序

推荐顺序：

1. CSV/TSV UTF-8：最适合普通用户和表格编辑；
2. JSONL：适合程序化生成和批量导入；
3. Markdown：适合手写题目和版本控制；
4. XLSX：在确认运行时依赖、文件安全、表头映射和大小限制后再支持；
5. .apkg：暂不作为第一批。它不仅是题目文本，还可能带牌组、调度状态、媒体和 Anki 专属语义，直接导入会产生状态映射和授权问题。

推荐导入模板字段：

~~~text
question,question_type,options,answer,explanation,subject,topic,difficulty,body_part,tags,image_url,source
~~~

其中 explanation、subject、topic、difficulty、body_part 可以按题型和产品策略标为可选，但缺失时必须显示“暂无解析”或“未标注”，不能自动捏造。

建议在导入页提供：

- 推荐格式说明；
- 一行示例；
- 字段映射；
- 预览；
- 错误行和修复建议；
- 导入前确认来源和授权；
- 成功后真实的题库 ID/数量。

#### 外部参考

Anki 官方文本导入文档说明了 UTF-8、逗号/Tab 分隔文本和字段映射：

- https://docs.ankiweb.net/importing/text-files.html
- https://docs.ankiweb.net/importing/intro.html
- https://docs.ankiweb.net/importing/packaged-decks.html

这里借鉴的是“格式推荐、字段映射、导入预览”的产品教育方式，不是承诺题伴立刻兼容完整 .apkg。

#### 业务行为影响

CSV/TSV 和 XLSX 会扩展导入协议；资料生题后端主链路不应被改变。Provider prompt 和 Judge 语义保持不变。

#### 验收条件

- 页面清楚区分“导入已有题目”和“从资料生成题目”；
- 用户能下载或看到推荐模板；
- CSV/TSV 导入先校验再写入；
- XLSX 若未实现就明确显示未支持，不出现假上传；
- 生成题目能说明 evidence、prompt、Gate/Judge/Repair 和审核关系。

### 20. 评测中心应该给用户看什么，当前是不是纯 RAG 评测

#### 结论

当前评测页面把离线 RAG/Agent artifact、候选模型 BYOK 运行和两类 Tab 放在一起，技术能力是真实的，但用户不容易区分“模型能力”“检索质量”和“辅导智能体系统质量”。评测中心应改名为“模型评测”，并把用户层和开发者层分开。

#### 当前实现证据

- [frontend/src/pages/evaluation/EvaluationPage.tsx](../../frontend/src/pages/evaluation/EvaluationPage.tsx#L16-L60) 当前显示评测中心、检索评测、辅导评测、离线结果和候选模型运行表单。
- [backend/app/routers/evaluation.py](../../backend/app/routers/evaluation.py#L26-L55) 从 artifacts/eval/latest.json 投影 metrics、cases、probes 和 strategy_comparison。
- [backend/app/services/model_eval_service.py](../../backend/app/services/model_eval_service.py#L299-L400) 的候选模型运行是 BYOK、逐案例请求、解析答案和统计 aggregate。
- 当前离线 artifact 的 conditions.mode 是 deterministic_offline_golden_case_replay，model_call=false；它不是一个外部模型真实运行分数。
- Retrieval Recall@K 是检索指标，不能直接叫作某个模型的答题能力。

#### 建议的两层产品

面向用户的“模型评测”：

- 目的：在用户选择的题目集上比较不同模型的答题能力、解析成功率、延迟和成本/用量；
- 模式 A：模型直接做题，不带 Tutor RAG，上下文固定；
- 模式 B：模型在题目 + 真实检索资料 + 既定提示词下回答，用于模拟题伴智能辅导；
- 每个结果必须明确数据集、版本、题量、提示词版本、是否带图像、是否带资料；
- 显示逐题结果和真实错误类别；
- 参考答案在显式操作前隐藏；
- 不把离线 artifact 的分数冒充用户 Provider 的成绩。

面向开发者的“Agent 评测（内测）”：

- 工具选择是否符合权限；
- 当前题目 Context 是否完整；
- 检索是否命中预期 evidence；
- Citation 是否存在、rank 是否合理；
- Study/Exam 权限是否被遵守；
- Memory 是否选中、是否跨领域泄漏；
- 失败、超时和重试是否可审计。

当前已有真实 artifact 支持的内容才展示。没有多策略 artifact，就不显示 Dense/Hybrid/Rerank 排行；没有上下文模型运行 artifact，就不写“带 RAG 模型准确率”。

#### 导航建议

- 一级入口：模型评测；
- Agent 评测（内测）可以是内部 Tab、disabled 入口或仅开发环境可见；
- Knowledge / 检索工作台不作为学习者一级页面；
- 检索证据细节并入评测的“案例证据”区域。

#### 业务行为影响

主要是评测页面 IA、标签和 artifact 展示边界；候选模型运行和离线 artifact 不重写。

#### 验收条件

- 用户能区分“模型直接做题”“带资料的辅导链路”“检索指标”“Agent 工具评测”；
- 指标都有条件、数据集和来源；
- 不制造不存在的模型分数或策略比较；
- EndoBench 等 Evaluation-only 数据不进入 Tutor、Factory 或学习题库。

### 21. 评测中心改成模型评测，下面增加 Agent 评测（内测）

#### 结论

这个命名和分层更符合用户视角，也符合题伴的求职技术叙事。但“Agent 评测（内测）”必须明确是开发者/管理员观察面板，不应和普通用户的模型选择混成一个概念。

#### 改进方案

用户可见模型评测首页：

- 标题：模型评测；
- 说明：在固定题集和明确上下文条件下比较模型表现；
- 入口：无资料做题、带题目资料做题；
- 结果：正确率、解析成功率、延迟、用量、逐题对照；
- 所有结果带数据集版本和运行条件。

内部 Agent 评测：

- 标题：Agent 评测（内测）；
- 说明：检查辅导智能体在 Context、Retrieval、Citation、Memory、权限和失败恢复上的行为；
- 结果：tool receipt、source rank、memory trace、policy pass/fail；
- 不把内部工具名、私有 ID 和链路日志默认塞给学习者。

#### 具体位置

- 当前页面：[frontend/src/pages/evaluation/EvaluationPage.tsx](../../frontend/src/pages/evaluation/EvaluationPage.tsx)
- 当前路由：[frontend/src/app/router.tsx](../../frontend/src/app/router.tsx#L13-L18)
- 评测公共 contract：[backend/app/routers/evaluation.py](../../backend/app/routers/evaluation.py#L118-L230)
- 候选模型运行：[backend/app/services/model_eval_service.py](../../backend/app/services/model_eval_service.py#L299-L445)
- Agent 行为 artifact：[backend/app/services/platform_evaluation.py](../../backend/app/services/platform_evaluation.py#L1-L120)

#### 业务行为影响

用户可见命名和信息分层变化；不新增模型架构，不把 Evaluation 数据塞进 Tutor。

#### 验收条件

- 一级导航不再显示泛化的“评测中心”；
- 模型评测和 Agent 评测在页面上有清楚边界；
- Agent 评测没有真实 artifact 时显示“内测/尚未接入”，不显示假指标；
- 用户不会把 Recall@3 误认为某模型的答题准确率。

## 4. 设置页参考图的可复用原则

两张设置页截图的价值不在于照搬模块数量，而在于它们对复杂配置的解释方式。题伴只应吸收以下规则：

### 应保留

- 独立设置入口；
- 左侧或页内的设置分组；
- 每个字段旁边有一句“它影响什么”；
- 连接测试与明确反馈；
- 保存按钮与保存结果；
- 当前运行模式、来源和权限透明；
- 敏感字段默认隐藏，不在页面、URL、日志和截图中暴露。

### 暂不引入

- Embedding 服务配置；
- 语音识别；
- 用户额度；
- 账户体系；
- 数据迁移；
- 图谱配置；
- 训练参数；
- 与 Practice 第一主线无关的服务市场。

### 组件文案原则

一个设置字段至少要回答：

1. 这个字段是什么；
2. 它影响哪个真实能力；
3. 当前是否已配置；
4. 测试会发生什么；
5. 保存在哪里；
6. 失败后怎么处理。

如果回答不了其中第 2、3、5 项，不应提前做成可编辑设置。

## 5. 建议的实施阶段

下面的阶段是给下一位 Agent 拆分任务的建议顺序。每个阶段都必须先检查工作树和实际 API，不得根据本文档直接假设接口已经存在。

### Phase 0：契约冻结与验收样例

目标：先把产品词汇、数据语义和真实样例冻结。

建议修改/检查：

- frontend/src/app/AppShell.tsx
- frontend/src/app/router.tsx
- frontend/src/pages/practice/PracticePage.tsx
- frontend/src/components/practice/SessionBuilder.tsx
- backend/app/schemas/stage1.py
- backend/app/services/stage1_service.py
- frontend/src/test/core-pages.test.tsx

工作：

- 冻结刷题 / 考试 / 开放回答 / 暂无解析 / 智能辅导等文案；
- 准备有解析、无解析、缺少元数据、开放回答、考试锁定的真实 fixture；
- 明确 error_tags 不等于知识点；
- 明确题库导入和资料生题不是一条 API。

### Phase 1：Practice 收口与题单

目标：进入 Practice 后直接做题，并恢复轻量题单。

工作：

- 删除重复的顶部配置和反馈；
- Session Builder 使用刷题/考试；
- 题量改为预设 + 自定义；
- 题单使用真实 session items；
- 选项状态、提交状态、解析状态和考试锁定保持可访问；
- 让智能辅导继续作为常驻 Sidecar，而不是独立产品入口。

验收：

- 刷题模式、考试模式真实 E2E；
- 题单状态与 Attempt 一致；
- 移动端题单使用 Sheet；
- 客观题不重复显示整段答案；
- 现有 Tutor SSE 和权限测试继续通过。

### Phase 2：首页活动与元数据诚实化

目标：让首页真的帮助用户继续学习，而不是展示日志。

工作：

- 扩展 RecentSessionPublic 的只读投影；
- Overview 显示题库、题目、题型和结果；
- weak_areas 不再从 error_tags 直接生成；
- 缺失 topic、difficulty、body_part 时不编造；
- Practice context 只显示有来源的元数据。

验收：

- 真实 Attempt 生成可读活动；
- 错误标签不会进入薄弱知识点；
- 缺失元数据 fixture 不出现“入门”或 body_part 冒充知识点；
- 不增加画像页或 BI 图表。

### Phase 3：题库导入与资料生成统一入口

目标：解决用户不知道上传什么、上传后发生什么的问题。

工作：

- 题库页 CTA 改为题库导入；
- 统一工作区内区分已有题目导入和资料生题；
- 使用现有模板和 validate API；
- 修复 413 并增加前端文件大小提示；
- 评估 CSV/TSV 和 XLSX；
- 资料生题继续展示真实 job、source、revision、Judge/Repair 和 Publish。

验收：

- 真实 CSV/JSONL/Markdown 校验；
- 413 边界测试；
- 小文件真实进入 Factory job；
- Provider 未配置时不显示假成功；
- 不承诺尚未实现的 .apkg。

### Phase 4：最小真实 Settings / Provider 诊断

目标：解决“智能服务为什么不可用”，但不冒险保存 key。

工作：

- 当前 Provider 状态只读投影；
- 一次性连接测试；
- 脱敏的错误类型和下一步；
- 如果没有安全持久化方案，明确“不保存到浏览器”；
- 只有至少一个真实能力可用时才把设置加入主导航。

验收：

- rule/local、Provider 未配置、Provider 失败、Provider 成功可区分；
- key 不落 localStorage、URL、日志和 artifact；
- Settings 不伪造保存结果。

### Phase 5：开放回答自我复盘与可选 AI 解析

目标：让开放回答符合“先自我对照，AI 解析可选”的真实语义。

工作：

- 增加回答评估模式 typed contract；
- 自我对照默认不显示客观题式对错；
- 无官方解析显示暂无解析；
- AI 解析使用显式操作、受控 Context 和真实引用；
- AI 解析不覆盖官方答案，不直接写入学习状态。

验收：

- 开放回答、官方解析缺失、AI 解析成功/失败四组真实测试；
- Study/Exam 权限边界；
- 无模型或 Provider 失败时无假内容。

### Phase 6：模型评测与 Agent 评测分层

目标：让用户能选模型，让开发者能看懂 Agent 系统问题。

工作：

- 模型评测作为用户主入口；
- 无资料和带资料的模型评测分开记录条件；
- Agent 评测（内测）只投影真实 artifact；
- Retrieval 指标、模型指标和 Agent 行为指标分区；
- 无真实 benchmark 时隐藏策略比较。

验收：

- 每个分数都能追溯到 dataset、version、prompt 和运行条件；
- 逐题 case 与 evidence 真实；
- Agent 评测不成为学习者主流程负担；
- 不把工程 artifact 说成临床验证。

## 6. 建议的组件和说明文稿原则

### 6.1 Practice 组件

建议保持小而深的复用：

- QuestionOption：只负责选项状态和可访问文本；
- QuestionFeedback：按客观题/开放回答/考试锁定分支；
- QuestionMap：真实 session item 状态；
- ExplanationBlock：官方解析、暂无解析、AI 解析三个来源；
- TutorPanel / TutorSidecar：当前题目上下文、真实检索状态、消息、引用和输入框。

不要为了每一个 span 创建 wrapper，也不要把业务判断散落在多个视觉组件里。评分和学习状态仍由后端负责。

### 6.2 题库导入组件

- ImportFormatGuide：解释推荐格式和字段；
- ImportPreview：真实 validate 结果；
- FactoryJobStatus：真实 job stage/progress；
- EvidencePreview：真实 chunk/source，不把 question provenance 当检索证据；
- RevisionReview：真实 Judge、Repair 和人工发布状态。

### 6.3 评测说明文稿

每个指标旁边都要写清：

- 衡量的对象；
- 数据集和版本；
- 是否调用模型；
- 是否包含检索、题目上下文或 Memory；
- 结果是离线 artifact 还是本次真实运行；
- 这个指标不能说明什么。

例如：

- Recall@3：衡量检索是否在前三条返回预期证据，不等于模型答题准确率；
- 准确率：只对具体评测集、提示词和运行条件成立；
- Tool selection accuracy：衡量辅导智能体选择工具的行为，不等于临床效果。

## 7. 通用验证清单

每一阶段完成后至少执行相关范围的：

~~~text
frontend:
  npm run api:check
  npm run lint
  npm test -- --run
  npm run build

backend:
  python -m compileall app
  python -m pytest -q

repository:
  git diff --check
~~~

涉及 Docker 或上传/队列时补充：

~~~text
docker compose config -q
docker compose ps
真实 API 上传/Session/submit/SSE/job/review/publish 流程
~~~

关键浏览器样例：

1. 有官方解析的中文四选项题；
2. 没有官方解析的题；
3. 开放回答题；
4. 刷题模式提交后智能辅导；
5. 考试模式中智能辅导权限锁定；
6. 错题题单包含未答/正确/错误/标记；
7. 缺少知识点和难度的导入题；
8. 小于和超过上传限制的资料；
9. 有真实 source citation 的辅导回答；
10. 离线 artifact 和真实候选模型运行的区分。

## 8. 最终摘要

### 应立即保留

- Practice + 常驻智能辅导是第一主线；
- 题单是核心刷题工具，应恢复轻量版本；
- 刷题 / 考试应由用户语言表达，内部继续使用 study / exam；
- 题库导入与资料生题必须明确分开；
- 解析来源必须诚实显示；
- 设置页只做真实 Provider 诊断和安全配置，不做后台功能大杂烩；
- 模型评测与 Agent 评测分层；
- 后端评分、学习状态、检索和安全边界继续作为 source of truth。

### 应隐藏或暂缓

- 空的 Knowledge、检索工作台、Standalone 智能辅导和 Settings Preview；
- 没有真实数据的策略比较；
- 学习画像、雷达图、BI 大屏；
- 未经验证的 .apkg、Embedding、语音、账户和额度模块；
- 让用户看到内部 error_tags、tool receipt、dataset 行号和安全模板；
- 任何只改变标题但没有对应 API 的“假功能”。

### 下一位 Agent 的第一批修改文件建议

第一批只建议先处理：

- frontend/src/app/AppShell.tsx
- frontend/src/components/practice/SessionBuilder.tsx
- frontend/src/pages/practice/PracticePage.tsx
- frontend/src/components/tutor/TutorSidecar.tsx
- frontend/src/pages/overview/OverviewPage.tsx
- backend/app/schemas/stage1.py
- backend/app/services/stage1_service.py
- backend/app/db/repositories.py
- frontend/src/api/client.ts
- frontend/src/test/core-pages.test.tsx

不要在第一批同时引入完整 Settings、XLSX、.apkg、模型市场或新的 Agent。先把用户最常做的事情——选择题库、刷题、得到清楚的反馈、需要时获得可信的智能辅导、留下可读学习记录——做完整。

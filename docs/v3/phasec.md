# TiBan V3 Phase C — 核心智能能力联调与 Release Gate

Visual Reset Phase B 通过。

从现在开始停止 broad UI redesign。

本阶段不继续扩页面、不新增普通教育业务、不重新设计导航。

本阶段目标是：

**把已经完成视觉重构的 TiBan，收口成一个真实智能能力可运行、可演示、可验证的 Agent-first 项目。**

继续以以下三份文档作为 V3 长期 source of truth：

- `docs/v3/00_TiBan_V3_MASTER_BRIEF.md`
- `docs/v3/01_TiBan_V3_UI_IA_SPEC.md`
- `docs/v3/02_TiBan_V3_EXECUTION_PLAYBOOK.md`

但如果其中早期细节与后续已经明确完成的 Visual Reset 决策冲突，以后续决策为准。

本阶段完成后不要自动开启下一阶段。

---

# 一、术语先统一

所有用户可见 UI 统一使用中文：

- 题伴
- 学习首页
- 题库
- 刷题
- 错题与复习
- 智能辅导
- 题目生成
- 评测中心

不要再在用户界面使用英文 Tutor。

技术文档如果需要描述 Agent 角色，统一写：

`辅导智能体`

已有代码内部历史 class / type / API identifier 不需要为了中文 UI 粗暴重命名。

当前公开 V3 UI 中不继续使用 `EndoTutor` 品牌。

推荐品牌显示：

题伴  
TiBan · AI 题库与学习工作台

空间不足时：

题伴  
TiBan

不要全局替换历史 migration、env、旧 artifact、archive 文档。

---

# 二、本阶段绝对不要做

禁止新增：

- 一级导航
- 普通业务页面
- 独立聊天产品线
- 课程系统
- 排行榜
- 打卡
- 社交
- 学习画像
- 雷达图
- BI Dashboard
- 新学习计划系统
- GraphRAG
- Multi-Agent
- 新 VLM 产品线
- 新数据库
- 新后端框架
- Next.js
- 服务器部署
- Electron 扩展

不要重新开始“把 TiBan 做成完整教育平台”。

本阶段只强化：

1. 智能辅导
2. 题目生成
3. RAG / Agent 评测
4. 学习记忆的真实作用
5. Demo / Regression / Release Gate

---

# 三、先冻结当前 Visual Reset 成果

开始前执行：

git status --short
git branch --show-current
git log --oneline -8
git diff --stat

当前分支应为：

`refactor/v3-tiban-agent-experience`

确认当前：

- `npm run api:check`
- `npm run lint`
- `npm test -- --run`
- `npm run build`
- Playwright core
- backend tests
- `git diff --check`

仍然通过。

如果 Phase A / Phase B 的修改能够安全、明确地从历史 working tree 中隔离：

创建 scoped checkpoint：

`refactor(v3): consolidate core learning experience`

禁止：

- `git add .`
- `git reset --hard`
- `git clean`
- 删除或覆盖历史 working-tree 修改

如果无法安全隔离，不要强行 commit，记录当前 diff inventory 后继续。

---

# 四、第一优先级：把真实题目生成链跑完整

当前“题目生成”页面的视觉已经基本完成。

不要继续改大布局。

现在要做的是把已有真实链路完整跑起来。

这不是服务器部署，只是本地开发环境验收。

先审计当前已有：

- PostgreSQL
- Redis
- Dramatiq
- Worker
- Qdrant
- Embedding
- FastAPI
- Factory APIs

确认：

- 启动入口
- health
- worker entry
- job state
- revision / lineage
- source chunk / evidence 字段

先输出真实 runtime map，例如：

Frontend
→ FastAPI
→ Job
→ Redis / Dramatiq
→ Worker
→ Parse / Retrieval
→ Generator
→ Gate / Judge / Repair
→ Draft / Revision
→ Review
→ Publish

不要重新实现任何一层。

优先使用项目已有：

- Docker Compose
- development scripts
- worker entry

最终确认：

- PostgreSQL healthy
- Redis healthy
- Qdrant healthy
- Backend healthy
- Worker healthy

---

# 五、做一次真实题目生成 E2E

使用仓库已有、可安全使用的小型 `.md` 或 `.pdf` fixture。

真实执行：

上传资料
→ 创建任务
→ 解析
→ 来源检索
→ 生成题目
→ deterministic gate
→ Judge
→ Repair（只有真实触发时）
→ 查看草稿
→ 发布入库

禁止：

- 手工修改 DB 制造成功
- hardcode job state
- mock worker
- mock revision
- 假 source snippet
- 为了截图强制制造 Repair

如果这一次没有触发 Repair：

正常。

不要为了“技术展示”伪造。

---

# 六、题目生成页面只展示真实能力

用户看到的顶层流程保持：

资料
→ 解析
→ 生成
→ 审核
→ 入库

不要把 backend 每个内部 stage 都放进 stepper。

草稿详情在真实字段存在时展示：

- 题干
- 选项
- 正确答案
- 解析
- 知识标签
- 来源
- 质量检查
- 修订状态

如果当前 API 只有 `source_chunk_ids`：

就显示：

来源片段  
3 个关联片段

不要假装有来源正文。

如果已有真实 snippet 字段，可以显示。

如果必须修改 backend contract 才能取得 snippet：

先停止并报告，不要为了视觉擅自扩后端。

---

# 七、第二优先级：智能辅导真实能力验收

现在的智能辅导已经有常驻 Sidecar。

不要继续重做它的外观。

现在验证它是否真正理解当前学习上下文。

检查真实 runtime 中下面哪些进入辅导智能体：

- 当前题目
- 题目选项
- 用户当前选择
- 是否已经提交
- 正确答案（权限允许时）
- 题目解析
- 知识点
- Domain
- 当前 Session
- Learner mastery
- Learning memory
- Retrieved sources

生成：

`docs/v3/evidence/agent-core/assistant-context-audit.md`

格式：

| Context | Source | When Available | Used By |
|---|---|---|---|

禁止记录：

- Secret
- 完整 system prompt
- private raw reasoning

---

# 八、智能辅导至少验证四种真实行为

## 1. 学习模式：请求提示

用户：

“给我一个提示”

应该：

- 给 hint
- 不抢答
- 需要资料时走真实 retrieval

## 2. 学习模式：明确请求答案

用户：

“直接告诉我答案”

如果当前 server-side policy 允许：

- 提供答案
- 解释原因
- 使用现有 permission path

不要前端硬编码答案。

## 3. 模拟模式：提交前

用户提交前索要答案：

必须遵守当前已有服务端限制。

不要只测试前端按钮隐藏。

验证真正 server-side permission。

## 4. 提交以后

用户：

“为什么我错了？”

“为什么正确答案是 B？”

“这个知识点怎么记？”

辅导智能体应知道：

- 用户刚才选了什么
- 正确答案是什么
- 当前 explanation
- 当前知识点

---

# 九、智能辅导状态只显示真实用户语言

不要做 Agent Trace 大屏。

只允许显示真实存在的状态，例如：

- 当前题目已就绪
- 正在查找相关资料…
- 已参考 3 条资料
- 正在整理回答…

只有真实 SSE / runtime event 支持时才显示。

不要伪造：

- 思考了 4 秒
- 检索了 3 条资料

不要展示：

- ToolReceipt
- AgentRun
- request id
- raw SSE
- raw JSON
- Qdrant filter
- internal adapter

---

# 十、Citation 必须真实

当智能辅导真正触发检索：

回答底部自然展示：

参考资料
- 来源 A
- 来源 B

要求：

- 来自真实 API / SSE
- 与当前回答对应
- 无来源时不显示
- 禁止 mock citation

如果已有 source detail 能复用，可点击查看。

如果没有，就先保持轻量 citation。

不要为了它新做复杂文档系统。

---

# 十一、Learning Memory：继续“有作用，不做画像”

不要增加：

- 学习画像页
- Memory Dashboard
- 雷达图
- 记忆管理大屏

Memory 只自然作用于：

- 推荐练习
- 下一轮 Session
- 智能辅导
- 错题复习

只有真实 memory 被 runtime 选中时，智能辅导才允许说类似：

“你之前在这个知识点上也容易混淆……”

不要模板化假装记得用户。

如果学习首页推荐来自：

- due review
- weak topic
- recent errors
- learning memory

可以使用：

- 今天到期复习
- 最近连续答错 2 次
- 近期正确率较低

不要写：

“由自适应记忆引擎计算”。

---

# 十二、第三优先级：评测中心做真实证据收口

不要继续扩 Evaluation 页面。

目标：

一个不看源码的人打开以后，也能明白：

“这里在比较什么，以及为什么通过或失败。”

## Retrieval

优先读取已有真实 artifact / API。

展示真实存在的：

- Dense
- Sparse
- Hybrid
- Rerank

指标只展示已有字段：

- Recall@5
- Recall@10
- MRR
- nDCG
- P50
- P95

不要制造缺失指标。

至少能打开一个真实案例：

Query
Expected Evidence
Retrieved Chunks
Rank
Source
Result

目标是：

一眼看懂这一条为什么检索成功 / 失败。

## 智能辅导评测

优先展示已有真实 evidence：

- routing
- tool selection
- permission
- answer behavior
- citation support

不要新增漂亮但没有证据的综合分数。

本阶段不做人工审核。

---

# 十三、全面清理用户界面中的开发者味文案

检查核心页面：

- 本地导入
- 本地演示
- 本地工作区
- 界面预览
- 尚未接入
- 真实 API
- 真实后端
- Agent Runtime
- 安全边界
- 审计

不是机械删除所有文本。

原则：

普通用户完成任务不需要知道的工程事实，不放在产品主界面。

---

# 十四、README Hero 不要再用两选项 ARC Easy

ARC Easy 保留。

它的价值是：

通用 Domain compatibility proof。

但是主宣传截图选择当前真实题库中：

- 中文
- 四选项
- 题干长度适中
- 有知识点
- 能真实检索来源

优先 CMExam / CMB-Exam。

真实走完：

题库
→ Session Builder
→ 刷题
→ 选择答案
→ 智能辅导
→ Citation
→ Submit
→ Review
→ 继续追问

不要伪造题目。

---

# 十五、最终只准备三类技术 Hero Screenshot

## Hero A：刷题 + 智能辅导

必须：

- 中文四选项真实题
- 已选择答案
- 智能辅导已有真实回复
- Citation 可见

## Hero B：题目生成

必须：

- 真实 Job
- 真实 Draft
- 真实 Source Evidence
- 真实 Quality Result
- Revision 只有真实存在才显示

## Hero C：评测中心

必须：

- 真实 Retrieval Metrics
- Strategy Comparison
- Case Detail
- Evidence

---

# 十六、生成 60~90 秒 Demo Flow

创建：

`docs/v3/portfolio/V3_DEMO_FLOW.md`

流程控制为：

1. 题库
2. Session Builder
3. 刷题
4. 智能辅导
5. 引用来源
6. 提交答案
7. 复盘 / 继续追问
8. 题目生成
9. 评测中心

每步只写：

- 用户看到什么
- Demo 时讲什么
- 对应技术点

不要写成长演讲稿。

---

# 十七、E2E

至少维护三条：

## Flow A

题库
→ Session Builder
→ 刷题
→ Select
→ 智能辅导
→ Submit
→ Review

## Flow B

题目生成
→ 上传安全 fixture
→ 真实 job
→ worker
→ draft / evidence
→ publish

## Flow C

评测中心
→ Retrieval
→ Strategy / Case
→ Evidence Detail
→ 智能辅导评测

如果环境真实无法完成：

记录真实原因。

禁止 mock PASS。

---

# 十八、最终测试 Gate

Frontend：

npm run api:check
npm run lint
npm test -- --run
npm run build

Backend：

python -m compileall app
python -m pytest -q

已有 architecture guard 必须继续通过。

Playwright：

- Flow A
- Flow B
- Flow C

题目生成必须跑一次真实 local worker E2E。

---

# 十九、Evidence

保存：

`docs/v3/evidence/agent-core/`

至少：

- `01-practice-assistant-hero-1440.png`
- `02-review-assistant-hero-1440.png`
- `03-question-generation-real-job-1440.png`
- `04-evaluation-retrieval-1440.png`
- `05-evaluation-case-detail-1440.png`
- `06-general-domain-proof.png`

如果真实 Repair 发生，再增加：

- `07-question-generation-revision.png`

没有发生不要伪造。

---

# 二十、V3 Core Release Gate

最终逐项判断：

- [ ] 题伴 / TiBan branding 统一
- [ ] 核心导航收敛
- [ ] 学习首页简洁
- [ ] 题库 + Session Builder 真实
- [ ] 刷题 + 智能辅导达到 README Hero 水平
- [ ] Review 与刷题共用骨架
- [ ] 辅导智能体理解当前题目
- [ ] Retrieval / Citation 真实
- [ ] Study / Exam 权限真实
- [ ] Learning Memory 有真实作用，但没有画像化
- [ ] 题目生成真实 local worker 链通过
- [ ] Draft 有真实来源证据
- [ ] 评测中心使用真实 artifact / case
- [ ] 无 fake headline metrics
- [ ] OpenAPI drift PASS
- [ ] frontend lint / unit / build PASS
- [ ] backend regression PASS
- [ ] architecture guard PASS
- [ ] V3 Playwright flows PASS
- [ ] Hero screenshots 完成
- [ ] 60~90 秒 Demo Flow 完成

如果全部满足：

**停止继续扩功能。**

下一步只进入：

`V3 Release Candidate — README / Evidence / Portfolio Packaging`

不要自动开启新的功能阶段。

---

# 二十一、最终报告

生成：

`docs/v3/V3_PHASE_C_CORE_AGENT_REPORT.md`

格式：

## A. Current V3 Baseline
branch / commit / working tree / checkpoint

## B. 智能辅导
context / retrieval / citation / memory / permission / E2E

## C. 题目生成
runtime / worker / generation / judge / repair / publish / E2E

## D. 评测中心
retrieval artifact / case evidence / 智能辅导评测

## E. 中文 UI / Branding
用户可见术语和文案清理

## F. Tests
完整结果

## G. Screenshots
路径

## H. V3 Core Release Gate
逐项 PASS / FAIL

## I. Remaining Issues
最多 5 项

完成后停止。
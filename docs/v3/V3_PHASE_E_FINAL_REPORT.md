# TiBan V3 Phase E Final Report

> 验收范围：E-A Core Learner UX Closure → E-B QBank Import + Runtime Usability → E-C RC Engineering Closure  
> 验收对象：分支 refactor/v3-tiban-agent-experience 的当前 working tree  
> 结论：TiBan V3 Core Release Candidate = PASS（working-tree checkpoint caveat）

本报告只记录 Phase E 的实际完成情况、真实运行证据、回归结果和延期项。没有创建 Phase F/G，也没有新增业务主线、Agent 架构、数据库或大型前端框架。

## A. E-A UX Closure

结论：PASS

### 已完成

| 目标 | 实际结果 | 主要位置 |
|---|---|---|
| 刷题 / 考试命名 | 用户可见文案为“刷题”和“考试”；内部仍使用 study / exam，不改后端 enum | frontend/src/components/practice/SessionBuilder.tsx、frontend/src/pages/practice/PracticePage.tsx |
| Session Builder 题量 | 提供 10 / 20 / 30 / 50 / 自定义；自定义限制为 1–100，不把固定数量伪装成“全部” | frontend/src/components/practice/SessionBuilder.tsx |
| 轻量题单 | Practice 恢复紧凑题单，按题型提供定位，状态来自真实 session / attempt；保留当前、未作答、正确、错误、已标记语义 | frontend/src/pages/practice/PracticePage.tsx、frontend/src/components/practice/ |
| 客观题提交反馈 | 正确 / 错误状态直接落在选项上，去掉重复的大段“你的答案 / 正确答案”反馈条；保留解析和后续操作 | frontend/src/pages/practice/PracticePage.tsx、frontend/src/components/practice/ |
| 最近作答 | 首页由“最近活动”改为“最近作答”，显示题库、题目摘要、题型、结果和时间，而不再只显示“进入复盘 / 回答正确” | frontend/src/pages/overview/OverviewPage.tsx |
| weak areas 语义 | 不再把 error_tags 直接呈现为薄弱知识点；用户可见弱项来自真实 topic / subject / 治理标签，缺失时不编造 | frontend/src/pages/overview/OverviewPage.tsx、backend/app/routers/evaluation.py 及既有学习投影 |
| 错题与复习入口 | 当前完整复习页仍不是本阶段核心，因此导航显示“错题与复习 · 开发中”并禁用；兼容路由和 FSRS 后端能力保留 | frontend/src/app/AppShell.tsx、frontend/src/app/router.tsx |
| 重复 footer | 普通页面不再重复展示长防御性 footer；服务端 safety contract 未删除 | frontend/src/app/AppShell.tsx、frontend/src/index.css |

### 验收证据

- 真实浏览器流覆盖：题库 → Session Builder → 刷题 / 考试 → 题单定位 → 作答提交。
- Practice 的 study permission 与 exam permission 均由真实 API 状态控制，前端没有自行覆盖评分、掌握度或 FSRS。
- 首页最近作答来自已有后端投影，不增加前端逐题 N+1 请求。
- 移动端截图中题单保持紧凑，不恢复旧版巨大的题号导航。

### 范围判断

E-A 只修正用户每天会遇到的词汇、入口、状态和信息密度问题，没有扩展开放回答 AI 解析、完整复习产品页或学习画像。

## B. E-B Import & Instance-level AI Settings

结论：PASS

### B1. 题库导入边界

原来的“题目生成”入口已重组为“题库导入”，工作区明确分为两条真实链路：

1. 导入已有题目：CSV、JSONL、Markdown 走已有 validate / preview 能力。
2. 从资料生成题目：继续使用既有 .md / .pdf Factory workflow。

主要实现位置：

- frontend/src/pages/banks/BanksPage.tsx：题库页入口改为“题库导入”。
- frontend/src/components/factory/FactoryStudio.tsx：导入已有题目与从资料生成题目分 Tab。
- frontend/src/components/factory/FactoryStepper.tsx：展示真实 Factory 阶段。
- frontend/src/components/factory/EvidencePreview.tsx：展示真实 source chunk 证据。

导入已有题目当前诚实停在真实校验与预览：如果后端只有 validate 能力，UI 明确说明“批量写入题库仍在后续版本”，不伪造导入成功。这样保留了产品边界，也没有制造不存在的写入 API。

资料生题仍保持既有语义：

~~~text
上传资料 → Parse / Index → Generator → Gate / Judge → Repair（如真实触发）
→ Review → Publish
~~~

Factory 页面读取真实 job stage、progress、attempt、revision 和 source_chunk_ids。来源片段不是题目 provenance、答案解析或专门伪造的知识块。

### B2. 413 与上传体验

- frontend/nginx.conf 将代理请求体上限调整到能够覆盖当前 Base64 JSON 上传的真实编码膨胀，同时保留业务层校验。
- 已验证小文件、接近原限制的文件和超出业务限制的文件。
- 超限请求不再被 Nginx 直接拦截为错误的 413；它可以到达 FastAPI，由业务层返回结构化 422。
- 前端显示当前支持格式和 5 MiB 单文件边界。

这不是无限放大代理限制，也没有修改 Factory backend semantics。

### B3. 元数据诚实

- 不再把 body_part 直接冒充知识点。
- 缺失 topic / difficulty 时省略或显示未标注，不把默认值带入用户的弱项判断。
- 没有为本阶段引入完整 provenance schema migration。

主要用户投影位置：

- frontend/src/pages/practice/PracticePage.tsx
- frontend/src/pages/overview/OverviewPage.tsx
- frontend/src/components/factory/FactoryStudio.tsx

### B4. Provider 状态和实例级智能设置

Settings 采用“当前 TiBan 运行实例”的作用域，不引入用户系统，也不暗示账号级永久保存。

实际支持：

- 智能模型：Provider / API 兼容模式、Base URL、Model、API Key 输入、测试连接、应用配置、恢复默认。
- Embedding：查看当前本地模型、测试、批处理大小应用、恢复默认。
- runtime override：应用后影响当前后端进程的真实运行配置；服务重启后恢复 .env / Docker 默认值。
- GET 设置只返回 configured 状态等脱敏信息，不返回明文 API Key。

主要实现位置：

- frontend/src/pages/settings/SettingsPage.tsx
- backend/app/routers/settings.py
- backend/app/services/runtime_settings_service.py
- backend/app/services/llm_provider.py
- backend/app/services/rag_service.py
- backend/tests/test_instance_runtime_settings.py

真实验证记录：

- LLM test：ok=true。
- Embedding test：ok=true。
- Embedding batch size：32 → 16 → 32，应用与恢复均由后端返回真实运行状态。
- 设置 GET 响应未返回 api_key。
- API Key 未写入 localStorage、sessionStorage、URL 或报告。

当前设置页明确说明“服务重启后恢复默认配置”，因此没有把 runtime-scoped override 包装成永久保存。

### B5. E-B 范围判断

E-B 没有复制 TechSpar 的语音、额度、账户、数据迁移、服务市场、图谱等模块，也没有新增 XLSX 或 Anki .apkg 支持。它只把当前 TiBan 已有导入、Factory、LLM、Embedding 能力组织成可理解且不造假的 UI。

## C. E-C Cold-start & D4

结论：PASS

### C1. 隔离 cold-start

使用独立 Compose project：tibanphaseecoldv2。

隔离条件：

- 独立 DB / Redis / Qdrant volume。
- 全新空 FastEmbed cache volume。
- 独立端口。
- 未破坏当前开发环境的已有 volume。

真实启动记录：

- Worker 启动时执行 FastEmbed prewarm。
- 空缓存下载并初始化 BAAI/bge-small-zh-v1.5 约 75,852 ms。
- prewarm 完成后写入 readiness / healthy 状态。
- 没有出现多进程重复下载竞争。

### C2. 首个 Factory job

真实 job：

- job_id：factory_11e9ecb3cb0c
- status：succeeded
- stage：published
- progress：100
- attempt：1
- revisions：2

真实事件链：

~~~text
queued → parsing → indexing → generating → judging → repairing
→ ready_for_review → published
~~~

该任务没有依赖 stale recovery，也没有为了截图强行构造 Repair 成功。独立前端再次完成了真实上传，并展示了 100%、审核状态、两版草稿和来源片段。

### C3. D4 判断

- D4 cold acceptance：PASS。空缓存、prewarm、readiness、首个任务 attempt=1 均有运行证据。
- D4 warm regression：PASS。已有 Compose 服务保持健康，核心浏览器流可重复执行。
- Factory 可靠性改为 prewarm + persistent cache + readiness 方向，没有通过单纯无限增加 timeout 掩盖冷启动。

## D. Regression

### 自动化测试

| 检查 | 结果 |
|---|---|
| Core Playwright | 7 passed |
| core-flow.spec.ts | 3 passed |
| phase-c-core.spec.ts | 3 passed |
| stage7-general-flow.spec.ts | 1 passed |
| Frontend lint | PASS |
| Vitest | 13 passed |
| Frontend build | PASS |
| Backend compileall | PASS |
| Backend pytest | 78 passed, 1 skipped |
| docker compose config -q | PASS |
| 正常 Compose / 隔离 Compose health | PASS |
| git diff --check | PASS；仅有 Windows 换行格式 warning |

唯一 skipped test：

~~~text
tests/test_stage25_data_governance.py:33
requires the local 3,678-question Demo QBank acceptance database
~~~

这是测试明确声明的环境条件缺失，不是 V3 代码失败。当前稳定结果为 78 passed, 1 skipped；此前 V2 / Stage 7 记录的 76 passed 属于不同测试集合与当时的数据库 / 运行环境，不能直接按数字相减。现有证据只能确认：本次 skip 是缺少本地 3,678 题 Demo QBank acceptance database 触发；无法把它归因于 V3 功能改动。

### OpenAPI 生成检查说明

- npm run api:generate 成功。
- 连续两次生成的 frontend/src/api/generated.ts SHA-256 相同，说明生成结果稳定，没有持续 drift。
- npm run api:check 最后的 git diff --exit-code 仍返回非零，因为本阶段新增的真实 Settings / Evaluation OpenAPI contract 已生成到 generated.ts，但当前工作树尚未提交这一意图内的 generated diff。

因此本报告将 API contract generation 判为“生成稳定，通过；clean-tree assertion 需在提交或干净基线中复核”，而不是把它误报为完全 clean PASS。该 caveat 是 release hygiene，不是新增业务 blocker。

## E. Portfolio Packaging

Phase E 的产品与工程 Gate 通过后，已更新：

- README.md：主 Hero / Demo Flow 改为真实 CMExam / CMB-Exam 中文四选项题，突出刷题 → 智能辅导 → Citation → Submit → Review。
- docs/portfolio/FINAL_EVIDENCE_MATRIX.md：加入 V3 Core RC evidence。
- docs/v3/portfolio/V3_DEMO_FLOW.md：更新刷题 / 考试、题库导入和真实 Factory / Evaluation 证据链。
- docs/v3/evidence/phase-e/：保存当前真实运行页面截图。

最终技术叙事保持在：

1. 上下文感知的智能辅导；
2. 来源驱动的题目生成；
3. 可复现的检索 / 智能辅导评测；
4. Memory / FSRS 作为学习闭环支撑。

没有把工程评测数字包装成临床验证，也没有在 README 或证据中写入真实患者信息、私网地址、API Key 或其他凭证。

### 截图矩阵

所有截图均来自当前真实 Compose frontend，无临时 DOM / CSS 修改，也没有使用设计稿替代运行页面。

| 文件 | viewport | 页面 / 证据 |
|---|---:|---|
| evidence/phase-e/01-practice-rag-citation-1440.png | 1440×900 | Practice + 真实 RAG / Citation Hero |
| evidence/phase-e/02-review-followup-1440.png | 1440×900 | Review 提交后复盘与智能辅导 |
| evidence/phase-e/03-factory-real-job-1440.png | 1440×900 | 真实 Factory job、进度、版本与来源 |
| evidence/phase-e/04-evaluation-evidence-1440.png | 1440×900 | Evaluation evidence projection |
| evidence/phase-e/05-overview-1440.png | 1440×900 | 学习首页 / 最近作答 |
| evidence/phase-e/06-banks-1440.png | 1440×900 | 题库与 Session Builder 入口 |
| evidence/phase-e/07-settings-1440.png | 1440×900 | 实例级智能能力设置 |
| evidence/phase-e/08-practice-rag-citation-1920.png | 1920×1080 | 宽屏 Practice Hero |
| evidence/phase-e/09-practice-rag-citation-375.png | 375×812 | 移动端 Practice / 智能辅导抽屉 |

截图逐张对照了：

- 前端视觉目标/01_external-qbank-reference.png
- 前端视觉目标/02_target-dashboard-lite.png
- 前端视觉目标/03_target-practice-tutor.png
- 前端视觉目标/04_target-review-tutor.png

对照结论：Practice 保持左侧导航、中央 Question Workspace、右侧独立智能辅导区；Review 具备正确绿色、错误红色、解析和提交后追问；主 CTA 使用近黑色，绿色只承担品牌、选中、进度和成功状态；移动端转为真实智能辅导抽屉。整体骨架、比例、密度、边框与交互形态符合 Phase E 目标，没有重新堆叠业务卡片或后台型 BI 元素。

## F. Git State

~~~text
branch: refactor/v3-tiban-agent-experience
stable base: 06d07b0 docs: polish public screenshot captions
latest HEAD: 06d07b0 docs: polish public screenshot captions
~~~

本报告生成前已检查 git status、当前 branch 和最近 commit。工作树包含此前 V3 重构、Phase C / D / E 的修改、删除和未跟踪证据；本阶段没有执行 reset、stash、clean、删除或覆盖这些内容，也没有创建新的功能 commit。

需要特别区分：

- 目标分支从 06d07b0 创建。
- 当前实现主要仍处于 working tree，而不是一个新的提交。
- 因此 06d07b0..HEAD 的 commit range 不能单独代表本阶段全部改动；本报告的验收对象是当前分支的 working-tree checkpoint。
- generated.ts 的 API contract diff 是本阶段有意产生的生成文件变更，不应在未提交状态下被误判为不稳定 drift。

## G. Final Gate

| Gate | 判定 | 证据 |
|---|---|---|
| E-A learner UX | PASS | Session Builder、题单、提交反馈、最近作答、weak areas、复习入口、footer 清理 |
| E-B qbank import boundary | PASS | 导入已有题目与从资料生成题目分开，真实 validate / preview |
| Metadata honesty | PASS | 不用 body_part 冒充 topic；缺失字段不编造 |
| 413 handling | PASS | 代理不再错误短路；超限交由 FastAPI 结构化处理 |
| Instance LLM settings | PASS | 真实 test / apply / restore，密钥脱敏，runtime-scoped |
| Instance Embedding settings | PASS | 真实 test / apply / restore，batch size 32 → 16 → 32 |
| API Key safety | PASS | 不进入 GET、浏览器存储、URL、日志或本报告 |
| Empty-cache cold start | PASS | 独立 Compose、空缓存、prewarm、readiness |
| First Factory attempt | PASS | attempt=1，published，未依赖 stale recovery |
| D4 cold / warm | PASS | 隔离冷启动与普通 Compose 回归均有证据 |
| Frontend regression | PASS with generated-diff caveat | lint、Vitest、build；api generation 稳定，clean-tree guard 需提交后复核 |
| Backend regression | PASS | compileall；78 passed, 1 skipped |
| Playwright | PASS | 7 passed |
| Compose acceptance | PASS | config、health、Factory job、Nginx / SSE 运行证据 |
| README / evidence / demo | PASS | README、Evidence Matrix、Demo Flow、Phase E 截图已更新 |

最终判定：

## TiBan V3 Core Release Candidate = PASS

限定说明：这是一个 working-tree checkpoint 的 PASS。若要在 CI 或发布分支获得完全 clean 的 api:check，还需要先提交当前意图内的 OpenAPI generated output，再在干净 checkout 重跑该检查。这个工程卫生事项不改变当前 Phase E 产品与运行时 Gate 的判定，但在正式发布前应完成。

## H. Deferred Backlog

以下项目按当前唯一执行计划明确延期，不阻塞本次 V3 Core RC：

- 开放回答题的完整 AI 解析 Agent、评分和新 endpoint。
- “暂无解析 + 用户主动触发 AI 解析”的完整产品闭环。
- XLSX 导入。
- Anki .apkg 导入。
- 题库导入的真实批量写入 / 确认导入 endpoint（当前已完成真实 validate / preview，未伪造写入成功）。
- 完整 Review 产品页和用户自主选择错题题库的复习工作流。
- 完整用户级 BYOK、账号体系和 per-user 持久化密钥。
- 完整 Agent 评测工作台、新 benchmark、新策略比较和更复杂的内部 trace 可视化。
- 语音、额度、账户、数据迁移、服务市场、图谱、OSS、声纹以及复杂 Retriever 调参。

这些延期项不应通过创建 Phase F/G 或 V4 提前扩张。下一步应由用户单独决定是否进入 README / Portfolio Packaging 的进一步审阅或 Post-RC backlog；本报告完成后停止。

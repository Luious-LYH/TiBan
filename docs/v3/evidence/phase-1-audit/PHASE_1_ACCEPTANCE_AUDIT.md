# TiBan V3 Phase 1 Acceptance Audit

审计日期：2026-08-31  
审计分支：`refactor/v3-tiban-agent-experience`  
审计范围：当前分支、当前 working tree、真实运行中的前端页面及可复现测试结果。  
审计边界：本轮只检查、截图、分析和报告；未修改源代码、未新增 route、未删除旧文件、未提交功能 commit。

## Verdict 先行

**PARTIAL PASS**

通过部分：

- 当前分支确实以 V2 稳定 commit `06d07b05369f460f282866a3f09213590123be50` 为基线。
- AppShell 已切换为 TiBan/题伴品牌、左侧分组导航和响应式导航壳。
- `/`、`/banks`、`/practice`、`/eval` 的真实 API 页面仍可运行；Practice 的真实 session、作答、提交、反馈、FSRS 和 Tutor SSE 代码路径未被重写。
- `/factory` 不是假数据页面，上传、创建任务、轮询、读取 revision、发布均使用现有 `/api/v3/factory/*` API。
- 真实前端的 lint、unit、build、OpenAPI drift 检查和 Playwright Flow A 通过；后端为 `75 passed, 1 skipped`。

未达到 PASS 的部分：

- Phase 1 把 `/tutor`、`/knowledge`、`/knowledge/search`、`/settings` 以及“导入中心”暴露为一级导航，但它们是 Preview-only，点击后没有真实核心工作流，形成明显 dead end。
- Practice 仍是旧的“练习页面 + 右侧卡片”结构，距离 V3 最重要的 Practice + Persistent Tutor Hero 还有显著结构差异。本轮没有进入 Phase 2，因此不能把壳层完成当成 Hero 完成。
- Factory 当前展示的是真实 `source_chunk_ids`，不是 source snippet 正文；代码明确提示“片段正文将在证据投影接入后显示”。原计划中“真实来源片段标识展示”只能成立，不能扩大解释为“已展示来源片段”。
- 当前测试环境缺少本地 3,678 题 Demo QBank acceptance database；`76 passed` 与当前 `75 passed, 1 skipped` 的完整历史差异无法仅凭仓库证据确认。
- 设计 token 已建立方向，但 CSS 仍保留大量 hex、spacing/radius 硬编码和 `s1-*` 旧命名，尚未达到真正统一的 design system。

## 0. 证据边界与归因方法

当前 `HEAD` 没有因为 Phase 1 前进。目标分支目前仍指向基线 commit，Phase 1 实现位于未提交 working tree。因此：

1. `git diff 06d07b0..HEAD` 为空，不代表没有 Phase 1 文件变化；它只说明没有新的 commit。
2. `git diff 06d07b0` 同时包含本轮前已经存在的历史清理、旧前端删除、归档资料和其他 working-tree 修改，不能把这 202 个 tracked 文件全部归为 Phase 1。
3. 下文将“可从 V3 前端实现直接确认的文件”列为 Phase 1 归因范围；其他状态逐项列为“既有/无法归因 working-tree 修改”，不借 Git 状态冒充实现成果。

## 一、Git 变更审计

### 1.1 按要求执行的 Git 输出

当前状态计数（`git status --porcelain=v1`）：

```text
 M（tracked modified） 24
 D（tracked deleted）   178
??（untracked）         11
总计                    213 条
```

```text
git branch --show-current
refactor/v3-tiban-agent-experience

git log --oneline -5
06d07b0 docs: polish public screenshot captions
1cbc714 docs: refresh TiBan public copy
a1b8fc8 docs: finalize v2.0 release evidence
2a6f61b feat: release v2.0 domain-extensible learning platform
47d8bab docs: finalize v1.2.0 release evidence
```

```text
git diff 06d07b0..HEAD --stat
（空）

git diff 06d07b0..HEAD --name-status
（空）
```

工作树相对基线的 tracked 差异为：

```text
202 files changed, 1924 insertions(+), 26459 deletions(-)
```

这组数字包含大量历史文件删除和资料清理，不是 Phase 1 的净实现统计。

### 1.2 基线确认

```text
稳定基线短 hash：06d07b0
稳定基线完整 hash：06d07b05369f460f282866a3f09213590123be50
当前 HEAD：06d07b05369f460f282866a3f09213590123be50
merge-base(refactor/v3-tiban-agent-experience, 06d07b0)：06d07b05369f460f282866a3f09213590123be50
```

证据支持的结论是：当前目标分支从 `06d07b0` 这个 commit 开始，且尚未在分支上产生 V3 commit。Git 本身不记录 `switch -c` 的创建时刻，所以无法从仓库单独证明创建动作发生的时间；但分支 ref、HEAD 和 merge-base 全部一致。

### 1.3 Phase 1 可归因文件分组

下面是本轮 V3 前端实现直接涉及的文件。所有“真实业务行为”均指后端数据、请求契约和状态机是否改变；导航结构和 URL 暴露虽然改变了产品 IA，但不等于后端语义改变。

#### 1. Design Token / CSS

文件：

- `frontend/src/index.css`

原来：集中使用 `s1-*` 页面样式，顶部横向导航，颜色、卡片、状态和页面布局样式分散在旧 V2 视觉语言中。

现在：增加 `--ink`、`--muted`、`--line`、`--surface`、`--teal`、语义色、阴影和 radius 变量；新增 AppShell、Preview、UI primitive、Factory stepper/Evidence、Evaluation 和移动端抽屉样式；保留绝大多数旧 `s1-*` 规则。

为什么：让侧栏、浅色 surface、绿色品牌色、响应式断点和基础控件拥有共同的视觉基础。

真实业务行为：不改变 API、数据计算、提交、评分、记忆或调度；只改变渲染和交互布局。需要注意，视觉状态文案可以影响用户理解，但没有改变后端状态。

#### 2. AppShell / Sidebar / Topbar

文件：

- `frontend/src/app/AppShell.tsx`

原来：顶部横向导航，只有学习总览、题库、刷题、模型评测四个入口；显示 `v2.0 · 本地学习演示`。

现在：约 232px 左侧栏，学习、智能辅导、知识库、题库、评测、系统分组；桌面折叠，移动端抽屉；顶部保留上下文、搜索入口和“本地演示”状态。

为什么：对齐参考图的工作台比例，突出练习、Tutor、Factory、Evaluation 的产品主线。

真实业务行为：不改变后端行为。`本地演示`、`本地工作区`是展示层 hardcode，不是健康检查，也不是 Provider 成功证明；这是需要在后续收敛的状态表达风险。

#### 3. Base UI Components

新增基础组件：

- `frontend/src/components/ui/Button.tsx`
- `frontend/src/components/ui/IconButton.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/ui/Card.tsx`
- `frontend/src/components/ui/Tabs.tsx`
- `frontend/src/components/ui/Input.tsx`
- `frontend/src/components/ui/Select.tsx`
- `frontend/src/components/ui/Skeleton.tsx`
- `frontend/src/components/ui/StatusMessage.tsx`

新增布局组件：

- `frontend/src/components/layout/Breadcrumbs.tsx`
- `frontend/src/components/layout/PageHeader.tsx`
- `frontend/src/components/layout/PreviewPage.tsx`

原来：没有这一套 `components/ui` 和 `components/layout` 文件层；核心页面主要直接写 `s1-button`、`s1-card`、表单和状态样式。已有 `components/shared/AsyncState` 仍然存在并继续提供 loading/error/empty 状态。

现在：增加轻量 React wrapper，定义 `ui-*` class 名称；PreviewPage 用于明确标出尚未接入的页面。

为什么：为页面后续抽取 Button、Badge、Tabs、PageHeader 和预览状态提供最小公共接口。

真实业务行为：不改变。没有引入 shadcn、Radix 或状态管理框架。

审计判断：组件数量与实现规模不大，但使用率偏低。`Badge` 被题库/Preview 使用，`Card` 主要被 Preview 使用，`Tabs` 被 Evaluation 使用，`PageHeader/Breadcrumbs` 主要被 Preview 使用；`Button`、`IconButton`、`Input`、`Select`、`Skeleton`、`StatusMessage`目前没有成为核心页面的主要渲染路径。存在轻度“先建组件、后等复用”的抽象债务。

#### 4. Routing

文件：

- `frontend/src/app/router.tsx`

原来：只注册 `/`、`/banks`、`/practice`、`/eval` 和 fallback。

现在：增加 `/factory`、`/tutor`、`/knowledge`、`/knowledge/search`、`/settings`；通过 query 支持 `/practice?mode=review`、`/eval?tab=retrieval|tutor`、`/knowledge?view=imports`。

为什么：把 Factory 从题库页拆出，为未来 IA 留出入口，并让 review/evaluation 视图可深链接。

真实业务行为：核心 API 页面行为不变；新增预览路由不调用后端。`/factory` 调用真实 Factory UI，因此它是真实能力的新 URL 投影。导航暴露范围改变了用户体验和信息架构。

#### 5. Question Bank

文件：

- `frontend/src/pages/banks/BanksPage.tsx`

原来：真实题库列表、筛选，以及题库页内嵌 `FactoryStudio`。

现在：保留真实题库 API、领域/题型筛选和每个题库的练习入口；移除内嵌 Factory，改为单独的“进入题目生成”入口。

为什么：让题库承担“选择题库并开始练习”，让 Source-backed generation 成为独立的第二梯队技术展示页。

真实业务行为：题库数据和进入 Practice 的 API 语义不变；只是改变 Factory 的 URL 和展示位置。

#### 6. Practice

文件：

- `frontend/src/pages/practice/PracticePage.tsx`

原来：真实 session、题目池、模式、状态筛选、作答、提交、结果、FSRS 和 TutorSidecar。

现在：主要中文化 `LEARNING WORKSPACE`、`LEARNING PLAN`、Tutor 文案，使用 `TutorPanel` 名称导出；仍保留题库/模式/题量、状态筛选、自适应选题依据、题号、笔记和练习总结。

为什么：完成中文应用壳兼容，同时为后续 Practice + Tutor 组件抽取留出名称。

真实业务行为：未改变。创建 session、服务端选题、拉题、选择答案、提交 Attempt、反馈、FSRS、query state 和 Tutor SSE 均继续使用原路径。

审计判断：这是 Phase 1 壳层调整，不是 Hero 重构。Practice 的结构性问题见第四节。

#### 7. Tutor

文件：

- `frontend/src/components/tutor/TutorSidecar.tsx`
- `frontend/src/components/tutor/TutorPanel.tsx`

原来：TutorSidecar 在 Practice 右侧，真实调用 `/api/v3/tutor/stream`，消费 SSE token、source、tool/reasoning 等受控事件；用户可见文案含英文 Tutor。

现在：用户可见文案改成“智能辅导”，保留真实 SSE、权限边界、source、provider_real、reasoning、token、error 逻辑；`TutorPanel.tsx` 只是 `export { TutorSidecar as TutorPanel }` 的 alias。

为什么：统一中文产品名，并为 Practice/Standalone Tutor 未来共享命名留接口。

真实业务行为：未改变。当前新增 `/tutor` 并不挂载这个真实 TutorSidecar，而是 PreviewPage；真实 Tutor 能力仍只存在于 Practice。

#### 8. Question Factory

文件：

- `frontend/src/components/factory/FactoryStudio.tsx`
- `frontend/src/components/factory/FactoryStepper.tsx`
- `frontend/src/components/factory/EvidencePreview.tsx`

原来：FactoryStudio 已能上传、创建 job、轮询、显示 revision、Judge 状态并发布；没有 stepper 和 evidence preview，题库页内嵌。

现在：FactoryStudio 增加 `FactoryStepper` 和 `EvidencePreview`；显示真实 job progress/stage/attempt/events，显示真实 `source_chunk_ids`；在 `/factory` 独立页面使用。

为什么：把 Source → Parse → Generate → Judge/Repair → Review → Publish 变成可见的技术工作流。

真实业务行为：未改变 Factory backend semantics。API 和字段链路见第九节。

审计判断：progress 和 chunk ID 是真实投影；source snippet 正文尚未实现，不能作为已完成能力宣称。

#### 9. Evaluation

文件：

- `frontend/src/pages/evaluation/EvaluationPage.tsx`

原来：真实评测集、Provider 连接、运行、结果、gold reveal 和逐例筛选，但标题、字段、状态和案例标签混有英文，只有一个 eval 页面。

现在：中文化标题、字段、指标和案例；增加 `检索评测` / `辅导评测` Tabs，通过 `tab` query 深链接；继续保留一次性 API Key、连接测试、真实 run、默认隐藏 gold 和逐例结果。

为什么：把 Evaluation 收敛为“评测中心”，使两个工程评测视图有清晰 IA。

真实业务行为：未改变 API、Provider 请求、gold reveal 或 artifact 读取；两个 Tab 目前主要是同一工作台的文案/视图切换，没有证据表明已连接两套不同的 backend projection。

#### 10. Knowledge

涉及文件：

- `frontend/src/app/router.tsx`
- `frontend/src/components/layout/PreviewPage.tsx`

原来：当前新 Router 没有独立资料库/检索工作台入口；后端兼容接口和生成 OpenAPI 中存在旧 knowledge API，但没有对应 V3 成熟页面。

现在：增加 `/knowledge` 和 `/knowledge/search`，均渲染 PreviewPage；`/knowledge?view=imports` 也落到同一个 PreviewPage。

为什么：试图为知识库、RAG 检索和导入能力预留产品位置。

真实业务行为：无真实 API 调用，无资料导入、检索、来源片段或 RAG 投影行为。建议 V3 Core 隐藏，而不是继续扩展。

#### 11. Settings

涉及文件：

- `frontend/src/app/router.tsx`
- `frontend/src/components/layout/PreviewPage.tsx`

原来：当前新 Router 没有设置页。

现在：增加 `/settings`，显示“设置暂不承载业务配置”的 PreviewPage。

为什么：完成系统分组的导航草图。

真实业务行为：无真实配置、无健康检查、无权限或工作区持久化。V3 Core 建议隐藏。

#### 12. Tests

Phase 1 没有修改核心测试源码，也没有更新现有 `frontend/e2e/core-flow.spec.ts` 的 Flow B 合约。

当前 working tree 中 `frontend/e2e/capture-stage1.spec.ts`、`capture-stage2.spec.ts`、`capture-stage25-provider.spec.ts`、`capture-stage25.spec.ts`、`stage25-flow.spec.ts` 显示为删除，但这些删除与大量历史 docs/archive/old frontend 删除同时出现，无法从 Git 证据归因于本轮 Phase 1；本审计没有恢复、删除或修改它们。

本轮进行了只读验证：frontend lint、unit、build、api check，Playwright Flow A，backend compileall 和 pytest。结果见第七节。

#### 13. Docs

与 V3 直接相关的未跟踪文件：

- `docs/v3/00_TiBan_V3_MASTER_BRIEF.md`
- `docs/v3/01_TiBan_V3_UI_IA_SPEC.md`
- `docs/v3/02_TiBan_V3_EXECUTION_PLAYBOOK.md`
- `docs/v3/evidence/phase-1-audit/` 下的真实截图

这些文档定义了 Agent-first 目标、导航原则、视觉规格和执行顺序；它们不是运行时代码。截图是当前真实运行页面的证据，不是设计稿替代物。

参考图路径事实：用户请求中写的是 `docs/v3/references/`，但当前仓库没有这个目录。实际参考图位于：

- `前端视觉目标/01_external-qbank-reference.png`
- `前端视觉目标/02_target-dashboard-lite.png`
- `前端视觉目标/03_target-practice-tutor.png`
- `前端视觉目标/04_target-review-tutor.png`

本审计没有复制或移动这些图片。

### 1.4 无法归因的既有 working-tree 修改

当前 213 条状态中，除上文 V3 前端实现和 V3 evidence 外，还有以下大组修改不能被当作 Phase 1 实现：

- 根部平台方案、Agent 提示词、接口字典、`AGENTS.md`、README 的修改。
- `backend/app/services/rag_service.py`、`artifacts/eval/*`、Compose 文件和旧 stage artifact 的修改/删除。
- `docs/architecture`、`docs/evals`、`docs/stages`、`docs/portfolio` 大量历史文档和截图删除。
- 旧前端 `Layout`、`Primitives`、`lib/*`、旧 pages、旧 CSS、历史 capture E2E 的删除。
- `compose.current-v2.acceptance.override.yml`、`docs/ARCHIVE_MANIFEST.md`、`docs/V2_RELEASE_REPORT.md`、`docs/portfolio/evidence/current-v2/` 等未跟踪归档/验收资料。
- `前端视觉目标/` 下的四张参考图和额外图片。

这些项目本审计不作 reset、stash、删除或恢复操作。

## 二、Route / Navigation 审计

| Route | 页面名称 | V2 是否存在 | V3 是否新增 | 真实 API | mock/preview | 一级导航 | 优先级 | 保留建议 |
|---|---|---:|---:|---:|---:|---:|---|---|
| `/` | 学习首页/学习总览 | 是 | 否 | 是：overview、learning memory | 否 | 是 | P1/轻量入口 | 保留；继续压缩为把用户送回 Practice 的入口 |
| `/banks` | 题库 | 是 | 否 | 是：题库列表 | 否 | 是 | P1 | 保留；后续向列表/内容工具感收敛 |
| `/practice` | 开始练习/刷题工作台 | 是 | 否 | 是：session、questions、attempt、FSRS、Tutor SSE | 否 | 是 | P0 Hero | 保留；Phase 2 第一优先 |
| `/practice?mode=review` | 错题与复习 | 已有 query 语义 | 否 | 是：复用 Practice API | 否 | 是 | P0/P1 | 保留；与 Practice 共用 Shell |
| `/eval` | 评测中心 | 是 | 否 | 是：datasets、connection、runs、reveal | 否 | 间接 | P1 | 保留为单一入口 |
| `/eval?tab=retrieval` | 检索评测 Tab | 无独立 V2 页 | 是 | 是：当前仍复用 eval API | 否 | 是 | P1 | 保留为 Evaluation 内 Tab，不做独立页面 |
| `/eval?tab=tutor` | 辅导评测 Tab | 无独立 V2 页 | 是 | 是：当前仍复用 eval API | 否 | 是 | P1 | 保留为 Evaluation 内 Tab；后续补真实 routing projection |
| `/factory` | 题目生成 | 无独立 route；原嵌入 `/banks` | 是 | 是：Factory 四条 API | 否 | 是 | P1/第二技术展示页 | 保留；但导航应比 Practice 弱一级 |
| `/tutor` | 题目辅导 | 无独立 route；原为 Practice sidecar | 是 | 否 | 是：PreviewPage | 是 | Standalone 非核心 | V3 Core 隐藏；Tutor 只在 Practice 中作为 P0 能力存在 |
| `/knowledge` | 资料库 | 否 | 是 | 否 | 是：PreviewPage | 是 | 非核心/延后 | 隐藏；资料导入主要进入 Factory |
| `/knowledge/search` | 检索工作台 | 否 | 是 | 否 | 是：PreviewPage | 是 | 非核心/延后 | 并入 Evaluation 的 Retrieval Tab，或暂时隐藏 |
| `/knowledge?view=imports` | 导入中心 | 否 | 是 | 否 | 是：仍是 PreviewPage | 是 | 非核心/延后 | 隐藏；上传入口放进 Factory |
| `/settings` | 设置 | 否 | 是 | 否 | 是：PreviewPage | 是 | 非核心/延后 | 隐藏；不为完整性暴露空页面 |
| `*` | fallback redirect | 否 | 否 | 否 | 否 | 否 | 基础设施 | 保留 |

### 2.1 对重点 route 的重新判断

#### `/knowledge`

当前页面只表达“资料库接入与来源治理正在准备中”，没有真实数据、导入、权限、检索或来源查看动作。它不直接展示 Persistent Tutor、真实 Factory、Evaluation 或 Adaptive Learning。因此不值得在 V3 Core 作为独立页面暴露。

结论：**隐藏一级导航；保留未来实现位置即可。**

#### `/knowledge/search`

RAG 评测需要的是 query、expected evidence、top-k chunks、citation support 和 case result，而不是一个没有 backend projection 的独立空工作台。把检索工作台放进 Evaluation 的 Retrieval Tab，更符合 V3 既定叙事，也减少一条孤立产品线。

结论：**并入 `/eval?tab=retrieval`，至少在 Projection 完成前不作为一级入口。**

#### 资料导入

当前真实可运行的导入链已经是 Factory：资料上传 → job → parse/index/generate/judge/repair → review/publish。独立“导入中心”没有额外真实能力。

结论：**资料导入主要进入 `/factory`，不要维护 `/knowledge?view=imports` 作为独立导航。**

#### `/tutor`

V3 的 Tutor 定义是“当前题目上下文中的 Persistent Tutor Agent”，不是一个脱离练习的普通聊天页。当前 `/tutor` 并没有真实 thread、memory、retrieval 或 SSE 工作区，暴露它会让用户误判产品完成度。

结论：**隐藏 standalone Tutor 一级入口；保留 Practice 内的 TutorPanel 作为核心路径。**

#### `/settings`

当前没有真实设置语义。显示预览标签是诚实的，但从产品入口进入仍是 dead end。

结论：**V3 Core 隐藏；等存在真实工作区/领域/安全配置后再恢复。**

## 三、Preview / Placeholder / Mock / Static 审计

### 3.1 Preview-only 页面和组件

| 页面/组件 | 是否真实后端数据 | 是否静态 UI | 点击后是否 dead end | 是否污染核心体验 | V3 Core 建议 |
|---|---:|---:|---:|---:|---|
| `/tutor` | 否 | 是 | 是，仅跳回 Practice | 是，Standalone Tutor 看起来已存在但不可用 | 隐藏一级导航 |
| `/knowledge` | 否 | 是 | 是，可跳 `/knowledge/search` | 是，增加一条空知识库产品线 | 隐藏 |
| `/knowledge/search` | 否 | 是 | 是，可跳 Practice | 是，RAG 工作台名义存在但无检索能力 | 并入 Evaluation 或隐藏 |
| `/knowledge?view=imports` | 否 | 是 | 是，仍使用同一个 PreviewPage | 是，给人“导入中心存在”的错觉 | 隐藏；导入进入 Factory |
| `/settings` | 否 | 是 | 是，只能回首页 | 低，但没有核心价值 | 隐藏 |
| `PreviewPage.tsx` | 不适用 | 是 | 由 route 决定 | 是预览页面的统一容器 | 保留组件，但只用于明确的未来 preview，不放一级导航 |

这些页面均明确显示“界面预览 · 尚未接入”，并声明不会生成虚构指标、来源或临床结论。这一点符合安全和 provenance 原则；问题不是它们伪造数据，而是它们被放进了 V3 Core 主导航。

### 3.2 真实页面中的静态展示

以下不是 mock 业务数据，但必须和真实后端字段区分：

- `AppShell.tsx` 的“本地演示”“本地工作区”：展示层 hardcode，不是运行健康状态。
- `FactoryStudio.tsx` 的 `factoryStatusLabels`：把真实 `job.stage` 映射成中文，不产生 stage。
- `FactoryStepper.tsx` 的 stages 数组：阶段顺序是 UI 静态映射；当前状态来自 API。
- `OverviewPage.tsx` 的 `learnerBankDescription`：部分 bank ID 的说明是本地文案映射，指标和题库数据仍来自 API。
- `EvaluationPage.tsx` 的 `learnerDatasetDescription`：数据集说明是本地文案映射，数据集、规模和 run 仍来自 API。
- Practice、Factory、Evaluation 的安全提示和空态说明：展示层固定文案。
- `EvidencePreview.tsx` 的“片段正文将在证据投影接入后显示”：这是对缺口的诚实提示，不是来源正文。

当前没有发现核心页面使用假 headline metrics、随机题目、伪造 Provider 成功、伪造 source ID 或虚构 audit ID 的证据。Preview 页面也没有伪造临床结论。

## 四、视觉验收

### 4.1 运行和截图证据

审计使用当前真实 Vite 前端和真实 Uvicorn 后端运行环境。桌面浏览器 viewport 使用 1440×900；长页面截图保留了实际滚动高度（例如题库 1440×2072、Practice 1440×1376），不是把页面压缩进 900px。以下 1440px 页面访问均返回 HTTP 200：

| 页面 | Route | 截图 |
|---|---|---|
| 学习总览 | `/` | [`01-overview-1440.png`](./01-overview-1440.png) |
| 题库 | `/banks` | [`02-banks-1440.png`](./02-banks-1440.png) |
| Practice | `/practice` | [`03-practice-1440.png`](./03-practice-1440.png) |
| Question Factory | `/factory` | [`04-factory-1440.png`](./04-factory-1440.png) |
| Evaluation | `/eval?tab=retrieval` | [`05-evaluation-1440.png`](./05-evaluation-1440.png) |
| Knowledge Preview | `/knowledge` | [`06-knowledge-1440.png`](./06-knowledge-1440.png) |

补充证据：

- [`01-overview-1920.png`](./01-overview-1920.png)
- [`03-practice-1920.png`](./03-practice-1920.png)
- [`05-evaluation-1920.png`](./05-evaluation-1920.png)
- [`03-practice-375.png`](./03-practice-375.png)

对照图实际来自 `前端视觉目标/`，不是 `docs/v3/references/`；本审计没有用设计稿替代真实页面。

### 4.2 全局对照参考图的具体分析

#### Sidebar 宽度和信息密度

当前侧栏约 232px，落在规格建议的 216–232px 内；在 1440px 截图中与内容区比例自然，移动端能变成抽屉。品牌区、分组标题和 active item 的层次接近 `02_target-dashboard-lite.png` 与外部题库参考图。

主要问题是内容数量：当前一级入口包含 6 个分组、约 13 个可点击项，其中 5 个是 preview/placeholder 或尚未形成独立能力。视觉上虽然不拥挤，但产品信息密度超过“少做业务”的目标；导航在告诉用户平台很完整，而不是告诉用户哪条 Agent 主线最重要。

#### Topbar

当前 Topbar 高度约 62px，边框、浅色背景和右侧搜索入口克制，方向接近目标 dashboard/practice 参考图。它缺少参考图中更明确的 breadcrumb/用户状态层，并且“本地演示”是硬编码状态；在评测页这会与真实 Provider 状态产生语义混淆。

#### Page padding 和 content width

桌面 `.app-main` 使用 `min(1360px, calc(100% - 64px))`，1440px 时内容宽度约 1144px，左右留白稳定；1920px 时可以展开，不是固定窄列。整体 page top padding 约 38px，比参考图 dashboard 的 24–32px 稍大，配合 48px 的大标题使首屏内容下沉。

#### Typography hierarchy

当前 `h1` 为 `clamp(30px, 4vw, 48px)`，Overview 的“把每次观察，变成可复盘的进步。”和 Banks 的标题都明显大于规格建议的 28–32px；Practice 的真实题库名称在 1440px 下换行并挤压右侧控制区。目标图的标题更像工作台标题，题干才是内容中心。当前更接近“营销式页面 heading + 业务卡片”，而不是 Practice-first tool hierarchy。

#### Border / radius / surface

白色 surface、浅灰背景、1px 边框和弱阴影是本轮最成功的视觉收敛，接近四张参考图的 quiet/tool-like 方向。主卡片半径大多在 8–12px，整体没有玻璃拟态、霓虹色或大面积渐变。

但 radius 并未真正统一，CSS 中同时存在 5/6/7/8/9/10/11/12px 以及 99px pill；页面和基础组件也混用 `s1-*` 与 `ui-*` primitive。卡片边框不重，但题库每张卡都包含多个内部边界，仍有传统后台目录感。

#### Card density / background / whitespace

- Overview：4 个 KPI + 题库入口 + 最近活动 + 自适应记忆，接近目标 dashboard 的密度，但底部安全提示出现两次，且“自适应记忆”卡的清除动作让轻量入口仍带有管理面板感。
- Banks：2 列题库卡片向下延伸，每张都有题型、领域、进度、完整宽度“开始练习”按钮；相比 `01_external-qbank-reference.png` 的内容列表感更像传统业务目录，重复 CTA 很多，题目生成入口被推到长列表底部。
- Practice：题目卡、Tutor 卡、自适应选题块、状态筛选条和底部总结卡同时存在；卡片彼此没有强阴影，但信息块数量高于目标 03 的主任务集中度。
- Factory：空态结构干净，但卡片下方有很大空白；这是因为没有虚构 job/task 来填充，不应通过假数据解决。
- Evaluation：配置卡、范围卡、隐私提示、表单、技术详情和结果卡的信息层级正确，但首屏表单字段占比大，仍偏“模型连接工作台”。
- Knowledge：视觉克制，但大面积留白来自无真实能力，不是有效的产品留白。

#### Primary color / CTA hierarchy

当前绿色品牌色、active、success 和主要按钮大多使用同一 teal 系列，统一性好；但参考图建议把黑色用于最强 action、绿色用于品牌/选中/Agent/成功。当前“开始练习”“提交答案”“发布到题库”均以 teal 为主，CTA 层级还不够明确。

#### Old backend feel / unnecessary elements

旧后台感主要仍来自：`s1-*` 命名、密集的状态筛选、重复卡片、题库目录式全宽按钮、Evaluation 的连接表单，以及 Practice 的辅助工具同时露出。没有雷达图、BI 大盘、复杂画像或 raw trace，这是正确的删减方向。

### 4.3 Practice 与目标图 03/04 的结构差异

`03_target-practice-tutor.png` 是本项目权重最高的参考。当前页面距离它的差异不是颜色小修，而是结构差异：

1. 当前顶部仍有题库、模式、题量三个选择控件；目标图把练习进度/模式/少量控制收敛为紧凑的顶部状态栏。
2. 当前有独立的题目状态筛选条和“本次选题依据”整块；目标图把当前题目上下文放在主任务上方，不让调度解释压过题干。
3. 当前仍提供题号导航、笔记、底部练习总结；这些功能有业务价值，但同时出现会把主任务纵向拉长。
4. 当前 Tutor 是右侧一张独立卡片，默认空态只显示“智能辅导”和三个快捷问题；目标图是完整、常驻的 Tutor workspace，顶部显示当前题目/检索状态，消息、引用、建议和 composer 占据稳定空间。
5. 当前 Tutor 的真实 context、tool event、source citation 在用户发起对话后才可能出现；目标图把“已读取当前题目”“已检索来源”作为可见的持续上下文。
6. 当前在 1440px 视图中主区约 64% 左右、侧栏约 36% 左右，Tutor 宽度约 400px，宽度数值符合 360–440px，但主区被上方长标题和控制区挤压；比例合格不等于骨架合格。
7. Review 仍复用 Practice 逻辑，但本轮没有提供“提交后正确/错误选项 + explanation + Tutor 追问”的新结构截图，因此不能声称达到 `04_target-review-tutor.png` 的验收状态。
8. 375px 截图基本可用：侧栏进入抽屉、Tutor 变成“打开智能辅导”，两列被压成单列；但题库选择、筛选、自适应说明、题号、题目、笔记和总结叠加后页面很长，主要任务的连续性较弱。

结论：**Phase 1 已建立可进入 Hero 的壳，但没有完成 Hero；Phase 2 前必须先收敛 IA 和 Tutor 常驻上下文。**

## 五、Design System 审计

### 5.1 当前实际 tokens / values

来源：`frontend/src/index.css` 的 `:root` 和当前布局规则。

颜色：

```css
--ink: #172a35;
--muted: #6d7d84;
--subtle: #96a5aa;
--line: #dce7e8;
--line-strong: #c7d7d9;
--surface: #ffffff;
--surface-soft: #f8fbfb;
--teal: #0a786f;
--teal-deep: #075b57;
--teal-soft: #e8f5f2;
--blue: #4a81c2;
--blue-soft: #edf5ff;
--amber: #a66516;
--amber-soft: #fff7e8;
--red: #b42318;
--red-soft: #fff1ef;
```

阴影：

```css
--shadow-sm: 0 4px 14px rgba(19, 52, 60, .045);
--shadow: 0 14px 38px rgba(19, 52, 60, .065);
```

圆角：

```css
--radius-sm: 8px;
--radius: 12px;
--radius-lg: 16px;
```

实际布局：

```text
Sidebar: 232px；折叠后 76px
Topbar: min-height 62px；移动端 56px
Desktop main: width min(1360px, calc(100% - 64px)); padding 38px 0 56px
Mobile main: width calc(100% - 24px); padding-top 24px
Desktop card padding: 22px
Mobile card padding: 16px；radius 10px
Practice Tutor desktop: minmax(340px, 400px)
Responsive breakpoints: 1100px / 760px
```

Typography 实际值：

```text
Font stack: Inter, PingFang SC, Microsoft YaHei, ui-sans-serif, system-ui...
Page title: clamp(30px, 4vw, 48px)，line-height 1.1
Page description: 14px，line-height 1.65
Kicker: 10px，font-weight 900，letter-spacing .11em
Base button: 12px，font-weight 800，min-height 42px
```

语义状态：

```text
Success / brand: --teal / --teal-deep / --teal-soft
Info: --blue / --blue-soft
Warning: --amber / --amber-soft
Error: --red / --red-soft
Loading: ui/s1 spin animation + disabled/opacity
```

### 5.2 硬编码和重复样式检查

对当前 `frontend/src/index.css` 的静态统计：

```text
hex literal 出现次数：219
不同 hex 值：167
box-shadow 声明：17
border-radius 声明：72
padding 声明：102
s1- class token 出现次数：320
```

这说明 token 只是部分建立：大量颜色仍直接写在选择器中，例如 `#edf3f3`、`#f7fafb`、`#e5ecee`、`#62747a` 等；灰色文字和边框色尤其没有被完全收敛。

重复/不一致点：

- `.ui-card` 与 `.s1-card` 并存，且通过同一段 CSS 兼容，而不是单一 Card 语义。
- `.ui-button` 与 `.s1-button` 并存，核心页面仍主要使用 `s1-button`。
- 约 17 处 shadow，部分来自按钮、侧栏抽屉、Tutor 卡，强度和用途没有完全 token 化。
- radius 从 5/6/7/8/9/10/11/12px 到 99px pill 多档并存；与建议的 4/8/12/16 体系不一致。
- page padding、card padding、field padding、Eval/Tutor 局部 gap 仍有大量 7/9/10/11/13/14/15/17/18/22/28/38px 值。
- `s1-*` 命名贯穿页面、组件和旧版本概念，说明本轮是增量收敛而非完整 foundation migration。

审计结论：视觉方向通过，系统一致性为部分通过；不要在 Phase 2 继续扩展第三套 primitive。

## 六、基础组件审计

| Component | 用途 | 是否基于 shadcn | 是否已有重复旧组件 | 当前使用页面 | 是否值得保留 |
|---|---|---:|---:|---|---|
| `Button` | variant/size/icon 的按钮 wrapper | 否 | 是，`s1-button` | 当前核心页面未成为主要路径 | 保留接口，后续统一迁移或删除重复样式 |
| `IconButton` | 带可访问 label 的图标按钮 | 否 | 是，页面内有 `s1-icon-button` | 当前核心页面未使用 | 可保留，等 Tutor/Topbar 抽取时复用 |
| `Badge` | neutral/teal/blue/amber/red 状态标签 | 否 | 有 `s1-source-pill`、`s1-type-pill` 等旧样式 | Banks、PreviewPage | 值得保留，但需收敛旧 pill |
| `Card` | `section` surface wrapper | 否 | 是，`s1-card` | PreviewPage | 值得保留，不能只服务 Preview |
| `Tabs` | role=tablist 的轻量 Tab | 否 | 原来没有同等公共组件 | Evaluation | 值得保留，当前有真实复用 |
| `Input` | 带 label/hint 的 input | 否 | 是，Evaluation/Banks 直接写 label/input | 暂未成为核心路径 | 暂缓迁移；避免 wrapper 只增加层级 |
| `Select` | 带 label/options 的 select | 否 | 是，页面直接写 `select` | 暂未成为核心路径 | 暂缓迁移 |
| `Skeleton` | loading 占位 | 否 | `AsyncState` 已有 loading 能力 | 当前未形成主要路径 | 先不扩展，后续统一 loading primitive |
| `StatusMessage` | info/success/warning/error/loading | 否 | `AsyncState`、页面 inline error 重复 | 当前未形成主要路径 | 先不扩展，需先决定和 AsyncState 的边界 |
| `Breadcrumbs` | 页面路径导航 | 否 | 原来页面多为手写 back link | PreviewPage | 可保留，但应服务真实页面 |
| `PageHeader` | eyebrow/title/description/actions | 否 | `s1-page-intro`/`route-heading` 重复 | PreviewPage | 值得保留，下一轮用于核心页面 |
| `PreviewPage` | 明确的未接入页面骨架 | 否 | 没有旧等价物 | Tutor/Knowledge/Settings | 保留为明确 preview 工具，但不让 preview 路由污染主导航 |
| `FactoryStepper` | 展示真实 job stage 的阶段映射 | 否 | 原来无 stepper | Factory | 值得保留；阶段数量需与最终产品叙事收敛 |
| `EvidencePreview` | 展示真实 source chunk ID/空态 | 否 | 原来 revision 无证据块 | Factory | 值得保留；必须继续明确“ID ≠ snippet” |
| `TutorPanel` | TutorSidecar 的名称 alias | 否 | 直接重复 `TutorSidecar` | Practice | 当前复用收益很小；可暂留，但不应继续加 wrapper 层 |

组件审计结论：没有引入大型 UI framework，也没有 shadcn registry 复制；主要风险不是运行时复杂，而是 `ui-*` / `s1-*` 两套 primitive 同时存在，以及多个基础组件尚未被真实页面使用。当前不应为了“组件齐全”继续增加 Dialog/Sheet/Popover 等空抽象。

## 七、测试差异审计

### 7.1 当前验证结果

```text
frontend: npm run api:check    PASS
frontend: npm run lint         PASS
frontend: npm test -- --run    12 passed
frontend: npm run build        PASS
Playwright Flow A              1 passed
backend: python -m compileall app  PASS
backend: python -m pytest -q       75 passed, 1 skipped
git diff --check               PASS（有既有 LF/CRLF warning）
generated.ts                    未修改；api:check 通过
```

完整 Playwright 未宣称通过：当前 `frontend/e2e/core-flow.spec.ts` 的 Flow B 仍从 `/banks` 查找 `factory-studio`，而 Phase 1 已将 Factory 拆至 `/factory`。因此本轮只执行并通过了 Flow A；Flow B 是旧 E2E 合约与新 IA 的冲突，不能算作 V3 Factory flow 通过。

### 7.2 skipped test 完整证据

测试名称：

```text
test_kvasir_curated_bank_has_lineage_and_legacy_vqa_is_quarantined
```

位置：`backend/tests/test_stage25_data_governance.py:27`。

skip 条件：

```python
if demo_qbank_counts() != DEMO_QBANK_EXPECTATIONS:
    pytest.skip("requires the local 3,678-question Demo QBank acceptance database")
```

当前触发原因：运行环境中没有满足 `DEMO_QBANK_EXPECTATIONS` 的本地 3,678 题 Demo QBank acceptance database。该测试不是因为前端 route、CSS、Tutor、Factory 或 Evaluation 失败而 skip，而是测试自身有意保护本地授权数据不随仓库分发。

为什么旧记录是 `76 passed`：仓库当前证据只能确认 Stage 7/历史记录曾记录 `76 passed`，不能确认当时的完整 command、commit、数据库状态和测试收集集合。最合理但仍属于推断的解释是：旧环境含有本地 acceptance database，因此该测试当时执行并通过；也不能排除旧记录来自不同测试集合或不同运行 profile。

是否因为运行环境不同：可以确认当前 skip 由本地数据环境触发；旧环境是否确实存在该数据库，仓库没有足够证据直接证明。

是否与 V3 代码改动有关：没有证据支持。该 skip 在后端数据治理测试中，Phase 1 归因范围主要是前端和未新增后端数据；前端改动不会改变 `demo_qbank_counts()`。因此应报告为环境/数据条件差异，而不是 V3 前端回归。

## 八、Dependency 审计

本轮没有修改：

- `frontend/package.json`
- `frontend/package-lock.json`

因此新增或升级依赖为：**0**。

当前相关依赖仍是：

```text
react 19.2.6
typescript ~6.0.2
vite ^8.0.12
react-router-dom 7.18.2
@tanstack/react-query ^5.102.8
openapi-fetch ^0.17.0
lucide-react ^1.17.0
tailwindcss ^4.3.3
@tailwindcss/vite ^4.3.3
vitest ^4.1.11
@playwright/test ^1.62.1
```

没有新增 shadcn、Radix、Motion、AI SDK、全局状态库或其他大型 framework。新增 UI 文件使用现有 React、TypeScript 和 `lucide-react` 即可完成，因此不存在“新依赖是否可用现有依赖替代”的实际新增项。

`npm ci` 的依赖树审计提示当前共有 14 个 vulnerabilities（13 high、1 critical）。本轮没有执行 `npm audit fix`，因为那会改变 lockfile 和审计范围；该提示不能归因于 Phase 1 依赖变更。

## 九、Question Factory 真实性审计

### 9.1 真实 API 链路

当前 `FactoryStudio` 使用 `frontend/src/api/client.ts` 的四组现有 wrapper：

```text
uploadFactoryDocument
→ POST /api/v3/factory/documents

createFactoryJob
→ POST /api/v3/factory/jobs

getFactoryJob
→ GET /api/v3/factory/jobs/{job_id}

publishFactoryRevision
→ POST /api/v3/factory/jobs/{job_id}/publish
```

具体流程：

1. 用户选择 `.md` 或 `.pdf`，前端读取文件并转为 base64。
2. 上传时传 `filename`、`content_base64`、`content_type`、默认 `domain_id='endoscopy'`。
3. 取得 `document_id` 后创建 job。
4. 首次读取 job，再每 1200ms 对 `queued`、`running`、`retrying` 状态轮询 `getFactoryJob`。
5. job 的 `stage`、`progress`、`attempt`、`error_message`、`detail.events` 来自返回对象。
6. revision 的 `draft.stem`、`judge.passed`、`rewrite_instruction`、`status` 和 `source_chunk_ids` 来自真实 revision。
7. 找到 `ready_for_review` revision 后，publish 调用真实 API，并用返回的 `question_id` 显示成功。

### 9.2 progress 的真实来源

```text
job.progress       → 进度百分比
job.stage          → 当前阶段
job.attempt        → 执行次数
job.detail.events  → 后端事件列表
job.error_message  → 后端错误
```

`FactoryStepper` 的阶段名和 `factoryStatusLabels` 是静态中文映射；它们只把后端 stage 翻译成用户文案，不生成进度或状态。这个边界是成立的。

### 9.3 source evidence 的真实来源

```text
revision.source_chunk_ids → EvidencePreview.sourceChunkIds
```

当前组件显示：

- 关联了多少个 source chunk；
- chunk ID 字符串。

当前没有显示：

- source chunk 正文 snippet；
- chunk 的标题、页码或来源文档定位；
- `revision.draft.citation` 对象的内容。

`frontend/src/api/generated.ts` 明确存在 `source_chunk_ids: string[]`，也存在 `FactoryDraftPublic.citation`，但本轮没有手工修改 generated client，也没有把 citation/snippet 伪造成已接入。

因此“真实来源片段标识展示”成立；“真实来源片段正文展示”不成立。`EvidencePreview` 的实际提示“片段正文将在证据投影接入后显示”已经把缺口暴露给用户，避免了来源幻觉。

### 9.4 mock/fallback 和 backend semantics

- 没有发现 Factory job、revision、progress、source ID 的 mock fallback。
- 空态时上传按钮因没有文件而 disabled，没有伪造任务列表或进度。
- stage label 和 stepper 是 presentation mapping，不是 mock job。
- 没有修改 FastAPI、队列、Generator、Judge、Repair、发布或数据库语义。
- 当前真实截图是 Factory 空态，因此它证明页面真实挂载和空态边界，不能单独证明一次完整 job 已在截图中成功跑通。现有 Flow B 因旧 `/banks` 选择器与新 IA 冲突而未作为通过证据。

Factory 结论：**这是已有真实能力的新 UI 投影，未达到“source snippet 完整展示”的原计划强度。**

## 十、最终 Phase 1 结论

### A. 已经做对且应该保留的内容

1. 以 `06d07b0` 为稳定基线创建并停留在目标分支，未把 Phase 1 混入新的功能 commit。
2. 题伴 TiBan 品牌、左侧分组导航、移动端抽屉、浅色 surface 和低噪音边框方向与参考图一致。
3. 保持 React/Vite/FastAPI/OpenAPI/TanStack Query/Lucide 现有技术主线，没有迁 Next.js、重写 FastAPI 或引入大型框架。
4. Practice 的真实后端行为、Tutor SSE、Attempt/FSRS/Memory 链路没有被前端重构破坏。
5. Factory 被拆成真实 `/factory`，真实 job progress/stage/revision/source chunk ID 有可见投影，且没有用假任务填空态。
6. Evaluation 默认隐藏 gold、API Key 不保存、错误/连接/运行状态边界仍然明确，适合工程评测叙事。
7. 学习记忆被命名为“自适应记忆/学习线索”，没有恢复雷达图、学习画像大模块或复杂 BI。
8. 所有 Preview 页面都明确标注尚未接入，不伪造 Provider 成功、指标、来源、审计 ID 或临床结论。

### B. Scope creep / 不必要复杂度

1. 一级导航暴露知识库、检索工作台、导入中心、Standalone Tutor、设置，超过当前四条技术主线的必要范围。
2. `/knowledge`、`/knowledge/search`、`/settings` 都是静态预览，增加了页面数量但没有增加可演示的核心能力。
3. `ui-*` 和 `s1-*` 两套样式/primitive 并存；新增的多个基础组件暂未被核心页面使用。
4. Practice 仍同时展示题库/模式/题量、状态筛选、自适应选题、题号、笔记、Tutor 和总结；虽然功能未新增，但整体表达比目标 Hero 更复杂。
5. Factory stepper 映射 8 个阶段，而 UI/IA spec 建议用户只看到 5 个 Source/Parse/Generate/Review/Publish 级别；工程状态可保留在细节层，不需要全部成为首屏阶段。
6. Factory 的 `EvidencePreview` 只到 chunk ID，若标题使用“来源片段”容易让用户期待正文；当前辅助文案已诚实，但能力名称仍需更精确。

### C. Phase 2 前必须修正的问题（最多 5 个）

1. **收敛主导航**：隐藏 `/tutor`、`/knowledge`、`/knowledge/search`、`/knowledge?view=imports`、`/settings`；保留 Practice 内的 Tutor，资料上传从 Factory 进入，Retrieval 并入 Evaluation。
2. **先完成 Practice + Persistent Tutor 骨架**：把进度/模式/当前题目上下文/题干/选项/提交与 Tutor context/retrieval/messages/citations/composer 组织成目标双栏工作区，减少首屏辅助卡块。
3. **修复真实证据表达**：Factory 在没有 snippet API 时继续明确显示 chunk ID，而不是暗示正文；如果 Phase 2 要求正文，先确认后端已有可安全投影的字段，再决定 API 最小补充。
4. **统一基础样式路径**：选择 `ui-*` 或 `s1-*` 的迁移顺序，至少先统一 PageHeader/Button/Card/Badge/StatusMessage，减少重复 hex、radius、shadow 和 page spacing。
5. **更新 E2E 契约并补真实 Factory/Review 证据**：Flow B 改为 `/factory`；增加提交错误答案后的 review/Tutor 断言；在存在安全测试资料时跑一次真实 Factory job，不以空态截图代替完整链路证据。

### D. 可以推迟的问题

- Standalone Tutor 的 thread list、跨题目会话和独立 memory context。
- Knowledge 独立资料库和检索工作台，只要 Evaluation Retrieval Tab 的未来边界记录清楚即可。
- Settings、Provider 管理、操作日志、导入中心的独立页面。
- 真实 source snippet 的更丰富页码/标题/文档定位，前提是先有明确后端 projection contract。
- 完整 spacing token 迁移、所有旧 `s1-*` 文件名和目录的清理。
- Evaluation 独立 Retrieval/Tutor backend projection 的细分实现，但不能在 UI 上伪造已具备的差异。
- 1920px 之外的更细致视觉打磨；当前更关键的是 Practice 结构和导航 scope。

### E. Phase 2 第一批准备修改的文件（本轮未修改）

按优先顺序：

1. `frontend/src/app/AppShell.tsx`：收敛主导航，移除 preview-only 一级入口，保留核心 active state 和移动端抽屉。
2. `frontend/src/app/router.tsx`：把 preview route 降为非核心入口或保留不可见 secondary route；确保 review/eval query deep link 不回退。
3. `frontend/src/pages/practice/PracticePage.tsx`：重组 Practice 主区、progress/context、题干/选项、提交和 review state，不改真实 API 语义。
4. `frontend/src/components/tutor/TutorSidecar.tsx` 与 `frontend/src/components/tutor/TutorPanel.tsx`：形成真正的 Persistent Tutor panel，显示当前题目、检索状态、引用、消息和 composer；继续复用现有 SSE。
5. `frontend/src/index.css`：在不全仓搬家的前提下，先为 Practice 双栏和 mobile Tutor drawer 建立统一 spacing/surface/CTA 层级。

Factory 与 Evaluation 文件暂排在上述 Hero 骨架之后：

- `frontend/src/components/factory/FactoryStudio.tsx`
- `frontend/src/components/factory/EvidencePreview.tsx`
- `frontend/src/pages/evaluation/EvaluationPage.tsx`
- `frontend/e2e/core-flow.spec.ts`

这些文件本轮没有修改。以上只是 Phase 2 准备清单，不是本次 Acceptance Audit 的变更。

## 审计停止说明

本报告完成后停止推进，等待用户确认。审计期间没有 reset、stash、删除、源码修复、route 追加或功能提交。

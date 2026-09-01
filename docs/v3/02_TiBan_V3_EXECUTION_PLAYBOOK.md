# TiBan V3 执行 Playbook：从稳定 V2 到 Agent-first V3

> 用途：本地 Coding Agent 的实际执行计划与验收标准。
>
> 原则：
>
> **先审计 → 再搭 Design Foundation → 先做 Hero Flow → 再扩页面。**
>
> 不部署服务器，不开启新的产品线。

---

# 0. Source of Truth

以当前 active `code/` 为唯一代码基线。

历史：
- archive
- old screenshots
- old stage docs
- stopped compose files

只作参考，不重新混回 active tree。

当前 V2 已经有成熟功能，V3 必须：
> **重构表现与主线，不重新发明后端。**

---

# 1. Git 策略

开始前：

```bash
git status --short
git branch --show-current
git log -5 --oneline
```

如果有未解释的修改：
- 不 reset
- 不 stash
- 不 delete
- 先报告

从当前最新稳定 V2 创建：

```bash
git switch -c refactor/v3-tiban-agent-experience
```

如果该 branch 已存在：
> 停止并报告，不覆盖。

---

# 2. 建立 V3 文档区

建议：

```text
docs/v3/
├─ 00_V3_MASTER_BRIEF.md
├─ 01_V3_UI_IA_SPEC.md
├─ 02_V3_EXECUTION_PLAYBOOK.md
├─ references/
│  ├─ 01_external-qbank-reference.png
│  ├─ 02_target-dashboard-lite.png
│  ├─ 03_target-practice-tutor.png
│  └─ 04_target-review-tutor.png
└─ evidence/
```

不要把 20 份历史 prompt 继续堆进 active docs。

V3 只保留这 3 个核心文档作为 current guidance。

---

# 3. Phase 0 — Architecture & UI Audit

第一轮不要编码。

输出：

```text
docs/v3/evidence/v3-baseline-audit.md
```

至少回答：

## 3.1 Frontend inventory
- React / TS / Vite 当前版本
- Tailwind 当前版本
- shadcn 是否已经存在
- router
- TanStack Query 是否已经 canonical
- OpenAPI generated client 当前路径
- tests / Playwright 入口

## 3.2 Page inventory
逐页列出：

```text
route
current purpose
keep / merge / hide / rewrite
V3 target
```

## 3.3 Component inventory
找出：
- 已有 Button/Card/Table/Badge
- Sidebar/Topbar
- Tutor components
- Question components
- Factory components
- Eval components

标记：
```text
reuse
restyle
replace
delete later
```

## 3.4 Data-flow audit
重点：
- Practice 页面 API
- Tutor SSE / event model
- Factory job API
- Eval API
- Learning memory / review API

## 3.5 Styling audit
搜索：
- global css
- hardcoded colors
- duplicate card styles
- inconsistent radius
- repeated layout wrappers

## Phase 0 Gate
只输出审计和“第一批文件清单”。

**不要大规模移动目录。**

---

# 4. Phase 1 — Design Foundation

目标：
> 不改核心业务，就让 3~4 个核心页面开始拥有同一套产品骨架。

## 4.1 Tokens
建立或收敛：

```text
styles/globals.css
styles/theme.css / tokens.css
```

覆盖：
- colors
- radius
- spacing
- typography
- semantic status

优先使用 Tailwind v4 / CSS variables。

## 4.2 App Shell
实现 / 重构：
- Sidebar
- Topbar
- PageShell
- PageHeader

## 4.3 Base Components
确认 / 增加：
- Button
- Input
- Select
- Badge
- Tabs
- Sheet
- Popover
- Tooltip
- Skeleton
- ScrollArea
- Table primitives

如果已有 shadcn：
> 复用并改 theme。

如果没有：
> 只安装当前 P0 需要的组件。

不要一次装整个 registry。

## 4.4 Domain Components
第一批只建：
```text
QuestionOption
ProgressHeader
TutorPanel
TutorMessage
TutorCitation
TutorComposer
FilterBar
QuestionListItem
FactoryStepper
```

---

# 5. Phase 2 — Hero Flow：Practice + Tutor

**这是整个 V3 第一个真正验收的产品页。**

不要先做 Dashboard。

## Step 2.1 静态重构
先保持现有 API 数据：
- 新 layout
- new question components
- new Tutor sidecar
- responsive skeleton

## Step 2.2 接回真实功能
必须真实通过：
- session load
- question navigation
- option select
- submit
- answer feedback
- hint / ask Tutor
- Tutor streaming
- citation rendering
- context state
- next question

## Step 2.3 Review state
提交错误答案后：
- correct / wrong states
- explanation
- learning context
- Tutor follow-up

## Phase 2 Evidence
保存：

```text
docs/v3/evidence/
├─ practice-before.png
├─ practice-after.png
└─ review-after.png
```

以及：
```text
practice flow Playwright
```

## Gate
这个页面达到：
> 可以直接放 README Hero screenshot

才能进入下一 Phase。

---

# 6. Phase 3 — Question Bank

目标：
> 更像高质量知识工具，不像一堆大 Card。

## 任务
- clean FilterBar
- list-based question item
- pagination
- question type / difficulty / source / topic
- primary action
- details action

## 数据
必须优先使用真实 existing bank API。

不要为了视觉：
- 伪造 8,932
- 写死来源
- 写死题目数

## Gate
在：
- 1440px
- 1920px

都能自然显示至少 4~6 题，不拥挤。

---

# 7. Phase 4 — Question Factory

第二个技术 Hero。

## 保留真实主链
```text
Source
→ Parse
→ Generate
→ Review
→ Publish
```

## UI
- stepper
- job/task list
- draft detail
- source evidence
- quality result
- publish action

## 不做
- 复杂统计大盘
- 大量 batch admin 操作
- 业务运营指标

## 技术展示
如果已有：
- Generator
- Gate
- Judge
- Repair
- lineage

用简洁状态表达。

比如：

```text
Generated
Gate passed
Judge: revise
Repair v2
Ready to review
```

而不是展示完整 raw trace。

---

# 8. Phase 5 — Evaluation

目标：
> 一个看起来像 AI Engineer 做的评测工作台。

## Retrieval
- strategy table
- selected benchmark case
- top-k evidence
- source
- result

## Tutor
- routing / permission cases
- result
- failure detail

## 指标
使用真实已有 artifacts / API。

不要：
- 改成漂亮假数据
- 为了视觉制造新的 benchmark 数值

## Gate
一个人不用读 docs：
> 也能看懂“你在比较什么、为什么通过/失败”。

---

# 9. Phase 6 — Review

Practice 完成后复用。

目标：
- answer history
- current mistake
- explanation
- Tutor
- start review / next

不要重做第二套页面。

---

# 10. Phase 7 — Dashboard Lite

最后才做首页。

## 保留
- 3~4 KPI
- Continue
- Weak topics
- Recent activity

## 不做
- 雷达图
- 多趋势图
- 大型学习计划
- 复杂 prediction

首页的任务：

> 把用户送回 Practice。

---

# 11. Standalone Tutor

优先复用 Practice sidecar 已完成的组件。

不允许：
- 单独创建第二套 Message UI
- 单独创建第二套 Citation UI
- 单独创建第二套 composer

Standalone 的价值：
- 跨题目的主题学习
- history
- memory-aware Q&A

如果时间紧：
> 可以在 Core V3 之后完成。

---

# 12. API Strategy

## Canonical
继续：

```text
FastAPI OpenAPI
→ generated TS client
→ feature API wrapper
→ TanStack Query
→ UI
```

不要回退到：

```text
fetch("/api/...")
as any
```

## feature wrapper
示例：

```text
features/practice/api.ts
features/practice/queries.ts

features/factory/api.ts
features/factory/queries.ts
```

Generated client：
> 不手改。

---

# 13. Server State / UI State

## TanStack Query
处理：
- bank
- practice
- review
- tutor threads
- factory
- eval

## local
处理：
- selected option before submit
- open/closed panel
- local filter draft
- temporary composer input

不要因为重构 UI 引入新的全局 store。

---

# 14. Mock policy

允许 Mock 只用于：
> Phase 1 的 layout/component scaffold。

进入任何正式页面 Gate 前：
> 必须接回 real API。

README screenshot：
> 只使用真实可运行 UI。

---

# 15. Agent 技术点的 UI Exposure

## 展示
- current question context
- retrieved sources
- citation
- learning memory driven suggestion
- generation revision status
- evaluation evidence

## 不展示
- raw CoT
- internal agent JSON
- request ids
- ToolReceipt
- SSE raw event
- internal adapter names

用户看到的是：
> 产品能力。

面试时再从 docs / code 讲工程实现。

---

# 16. Testing

V3 不允许“只截图好看”。

## Existing gates must stay
- backend tests
- frontend lint
- frontend unit
- build
- OpenAPI drift
- architecture guard
- Playwright

## V3 新增/更新 E2E
至少：

### Flow V3-A
```text
banks
→ practice
→ submit
→ tutor
→ review state
```

### Flow V3-B
```text
factory
→ select job
→ inspect source-backed draft
→ review/publish existing supported path
```

### Flow V3-C
```text
evaluation
→ change strategy/case
→ inspect evidence
```

---

# 17. Visual Acceptance

每个完成页面：
- 1440x900
- 1920x1080

至少检查两档。

保存当前最终证据：
```text
docs/portfolio/evidence/current-v3/
```

旧 V2 截图不删除，保留作 before / history。

---

# 18. Commit Strategy

不要一个 commit 改整个前端。

建议：

```text
docs: add TiBan v3 agent-first rebuild brief
refactor: establish v3 design tokens and app shell
refactor: rebuild practice workspace
refactor: unify practice review states
refactor: simplify question bank
refactor: rebuild source-backed question factory
refactor: simplify evaluation workspace
refactor: add lightweight learning overview
docs: update TiBan v3 portfolio screenshots
```

---

# 19. Agent 每轮工作格式

每次进入一个 Phase：

## Before coding
输出：
```text
Relevant files
Current behavior
Target behavior
Minimal change plan
Risk
Verification
```

## After coding
输出：
```text
Changed files
What changed
What intentionally stayed unchanged
Tests
Visual verification
Remaining issues
```

不要每轮重新发明 Roadmap。

---

# 20. Stop / Ask Rules

以下情况停下来问用户：
- 要改数据库 schema 才能完成 UI
- 要破坏现有 API contract
- 要引入新的大型 framework
- 要删除 active feature
- 要改 Agent runtime core semantics
- 参考图和真实业务发生明显冲突

以下情况直接做：
- spacing
- typography
- component extraction
- shadcn primitive replacement
- route-level layout cleanup
- safe query hook refactor
- obvious duplicate UI removal

---

# 21. V3 Core Release Gate

只有下面全部满足，才叫 V3 Core 完成：

```text
[ ] TiBan branding applied to current public UI
[ ] navigation reduced and coherent
[ ] AppShell unified
[ ] design tokens unified
[ ] Practice + Tutor is README-quality
[ ] Review shares Practice shell
[ ] QBank clean and usable
[ ] Factory clearly shows source-backed generation
[ ] Eval clearly shows engineering evidence
[ ] Dashboard is lightweight
[ ] no fake headline metrics
[ ] real APIs reconnected
[ ] OpenAPI drift pass
[ ] frontend lint/unit/build pass
[ ] backend regression pass
[ ] architecture guard pass
[ ] Playwright V3 hero flow pass
[ ] screenshots refreshed
[ ] README public copy refreshed
```

完成后：
> 停止继续加功能。

把新需求放 backlog。

---

# 22. V3 最终原则

> **前端负责让 Agent 能力变得可见；后端负责让这些能力真的成立。**
>
> TiBan V3 不需要“最完整”，需要“最容易被理解、最容易被相信、最容易被记住”。

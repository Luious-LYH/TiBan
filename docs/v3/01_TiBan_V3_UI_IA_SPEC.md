# TiBan V3 UI / IA 重构规格：四张参考图到可实现产品

> 用途：本地 Agent 进行前端重构时的视觉与信息架构规范。
>
> 目标不是像素级复制参考图，而是提取它们共同的优点，做成一套更简洁、更适合 TiBan Agent 项目的设计系统。

---

# 1. 视觉基调

V3 的感觉应该是：

> **专业工具感 + 知识产品感 + 轻量 AI 感**

不是：
- 传统医院系统
- 大屏 BI
- 企业 ERP
- ChatGPT Clone
- 花哨 AI Landing Page

关键词：

```text
quiet
structured
content-first
tool-like
minimal
dense when needed
clear hierarchy
```

---

# 2. 四张参考图的权重

在 Agent 视觉判断中使用以下权重：

```text
03 Practice + Tutor     40%
04 Review + Tutor       25%
01 External QBank       20%
02 Dashboard            15%
```

也就是说：

> **Practice + Tutor 决定整个项目的“灵魂”，Dashboard 不决定。**

不要反过来。

---

# 3. 全局设计系统

## 3.1 色彩策略

推荐采用：

### Neutral
```text
Background      #FAFBFA
Surface         #FFFFFF
Surface subtle  #F5F7F6
Border          #E6EAE8
Text primary    #161A18
Text secondary  #66706B
Text muted      #909994
```

### Brand / Accent
```text
Accent          #0F8F78
Accent hover    #0B7B68
Accent subtle   #E9F6F2
```

### Primary CTA
关键动作建议仍可使用接近黑色：

```text
Primary action  #171918
```

例如：
- 提交答案
- 开始练习
- 发布入库

这样：
- 黑色 = 主要动作
- 绿色 = 品牌、选中、Agent、成功/进度

视觉更克制。

### Semantic
```text
Success  #1D8A5B
Warning  #C07A1B
Danger   #D74F4F
Info     #3F78C5
```

---

# 4. 视觉规则

## 卡片
尽量：
- 白底
- 1px 边框
- 很轻或没有阴影
- 12~16px radius

避免：
- 每个信息块都是 card
- 卡片套卡片套卡片
- 强阴影

## 页面背景
轻灰白背景即可。

## 重点区域
通过：
- spacing
- font weight
- border
- subtle tint

建立层次。

不要靠：
- 大面积渐变
- 彩色背景块
- 过度 icon

---

# 5. 间距系统

建议统一：

```text
4
8
12
16
20
24
32
40
```

## 常见组合
- Button horizontal：12~16
- Card padding：20~24
- Page section gap：24
- Main page top padding：24~32
- Title → subtitle：6~8
- Form field gap：12~16

Agent 修改页面时，不允许随手写大量：
```text
13px
18px
27px
31px
```

---

# 6. Typography

建议层级：

```text
Page Title     28~32 / 650~700
Section Title  18~20 / 600
Card Title     14~16 / 600
Body           14~15 / 400
Meta           12~13 / 400
Metric         28~36 / 650
```

中文不要靠超粗大标题制造“高级感”。

---

# 7. 全局 App Shell

## Sidebar
建议：
- 宽 216~232px
- 固定
- 可折叠属于 P1
- 分组标题弱化
- active item 用 `accent-subtle + accent text`
- icon 统一 Lucide 风格
- 一级菜单总数控制

## Topbar
建议：
- 高 56~60px
- 左：breadcrumb
- 中/右：global search
- 最右：通知 / 用户 / 少量 global action
- 不放很多按钮

## Page Content
- 主区 padding 24~32
- 桌面宽屏充分利用
- 不把所有页面锁死在很窄的 1200px
- Practice / Factory / Eval 可以 full-width

---

# 8. V3 Navigation

```text
学习
  学习总览
  题库
  刷题
  错题复习

Agent
  Tutor
  题目工厂

评测
  评测中心

系统
  设置
```

## 不要把这些放一级菜单
- 学习画像
- 文档库
- 知识点管理
- 导入中心
- 检索工作台
- Provider
- 操作日志

需要时作为：
- Tab
- Drawer
- secondary route
- Factory / Eval 子页面

---

# 9. 页面规格 A：学习总览

## 目标
它是入口，不是“核心技术大屏”。

### 首屏只放
#### Row 1：最多 4 个 KPI
推荐：
- 今日练习
- 待复习
- 最近正确率 / 最近错题（二选一）
- Tutor activity（可选）

#### Row 2
左：
**继续学习 / 推荐开始**

右：
**近期薄弱知识点 Top 5**

#### Row 3
**最近学习活动**

### 删除 / 后置
- 雷达图
- 复杂能力画像
- 12 周趋势
- 复杂学习计划
- 多个折线卡
- “预计提升 15%+”这类不必要产品文案

---

# 10. 页面规格 B：题库

参考外部 QBank 图的“信息密度”和“列表感”。

## Layout
```text
PageHeader
Search + Filters + Primary Action
Question List
Pagination
```

## Filter
第一行只保留：
- 搜索
- 题型
- 难度
- Domain / 来源（按当前需求）

高级筛选放 Popover / Sheet。

## Question Item
信息顺序：

```text
ID / type / difficulty / status
question stem
knowledge tags
source
secondary actions
```

### 行为
首要：
- 开始练习 / 加入练习

次要：
- 详情
- 编辑（有权限时）

不要每道题放 6 个按钮。

---

# 11. 页面规格 C：刷题工作台（Hero）

这是 V3 最重要的页面。

## Desktop Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ top progress / mode / controls                              │
├───────────────────────────────────┬─────────────────────────┤
│                                   │ Tutor                   │
│ Question Context                  │ current context         │
│                                   │ retrieval state         │
│ Question Stem                     │                         │
│                                   │ messages                │
│ Options                           │                         │
│                                   │ citations               │
│                                   │                         │
│ hint / mark / prev / next / submit│ quick prompts           │
│                                   │ composer                │
└───────────────────────────────────┴─────────────────────────┘
```

## 比例
- Main：66%~70%
- Sidecar：30%~34%
- Sidecar：360~440px 之间自适应

## 主题区
必须做到：
- 题干是视觉中心
- 选项高度舒适
- 选择状态非常明确
- 当前题目 metadata 弱化
- Submit 是唯一最强 CTA

## Tutor Sidecar
顶部只保留：
- 当前上下文
- 检索状态

例如：

```text
✓ 当前题目
✓ 已检索 3 条来源
```

不要：
- Raw trace
- ToolReceipt
- AgentRun ID
- 复杂链路图

## Chat
消息宽度不要铺满 sidecar。
Citation 放回答底部。

可以有：
- “为什么这个选项不对？”
- “给我一个提示”
- “解释相关知识点”

三类建议按钮。

---

# 12. 页面规格 D：提交后 / 错题复习

继续使用 Practice Shell。

## 提交后状态
主区：

```text
已提交
你的答案 C（错误）
正确答案 B
近期错误 n 次（如果有）
```

Option：
- correct：绿色 border / soft bg
- wrong selected：红色 border / soft bg
- other：neutral

下面：
- explanation
- related concepts
- source

右侧 Tutor：
默认可以理解刚才的错误，并继续追问。

这个页面要让人明显看到：

> **TiBan 的价值是“答错以后还能继续学”。**

---

# 13. 页面规格 E：Tutor Standalone

Standalone Tutor 可以保留，但它不是 V3 首批 Hero。

Layout：

```text
Thread list | Conversation | Learner context
```

重要：
- 和 Practice Sidecar 共用 message / citation / composer 组件
- 不做第二套 Chat UI

如果 V3 第一阶段时间紧：
> 先把 Practice Sidecar 做满，Standalone Tutor 复用后再整理。

---

# 14. 页面规格 F：Question Factory

第二强技术页面。

## Layout
```text
PageHeader
Stepper
────────────────────────────────────
Task List        | Draft Workspace
                 | ├ Question
                 | ├ Source Evidence
                 | ├ Check / Judge
                 | └ Publish action
```

## Stepper
只保留：
1. Source
2. Parse
3. Generate
4. Review
5. Publish

不要做 8~10 步。

## Draft Workspace
中心是题目。

右侧或下方展示：
- source snippet
- knowledge tags
- gate / judge result
- revision / repair 简要状态

不要变成传统 CMS。

---

# 15. 页面规格 G：Evaluation

## IA
建议一个页面 + Tabs：

```text
Evaluation
├─ Retrieval
├─ Tutor
└─ Model（已有时）
```

## Retrieval
首屏：
- strategy comparison table
- selected case detail

表格字段建议：

```text
Strategy
Recall@5
MRR
nDCG
P50/P95
```

Case detail：
- Query
- Expected evidence
- Top-k chunks
- Answer / citation support
- Result

### 图表
默认不需要。

如果真的想有一个视觉点：
只允许一个 latency-quality scatter。
没有也完全可以。

---

# 16. “技术力”应该如何出现在 UI

真正有价值的 Agent 技术点，通过以下形式出现：

## Tutor
```text
当前题目上下文
检索来源
引用
Memory-informed hint
```

## Factory
```text
Source
Generated draft
Gate/Judge result
Repair revision
```

## Eval
```text
retrieval metrics
routing cases
case evidence
```

## Learning
```text
why recommended
due review
weak topic
```

不要通过：
- 开发者术语
- Raw JSON
- 一堆 trace
- 20 张技术卡片

来证明技术力。

---

# 17. 组件体系

## Foundation
```text
Button
Input
Select
Badge
Tabs
Dialog
Sheet
Popover
Tooltip
Skeleton
ScrollArea
Separator
Pagination
```

## Layout
```text
AppShell
Sidebar
Topbar
PageHeader
SectionHeader
ContentPane
SplitPane
```

## Question
```text
QuestionMeta
QuestionStem
QuestionOption
AnswerState
ExplanationBlock
QuestionSource
ProgressHeader
```

## Tutor
```text
TutorPanel
TutorHeader
TutorStatusChip
TutorMessage
TutorCitation
TutorSuggestions
TutorComposer
```

## Factory
```text
FactoryStepper
FactoryTaskList
FactoryTaskItem
DraftQuestion
SourceEvidence
QualityResult
PublishBar
```

## Eval
```text
EvalTabs
MetricTable
EvalCaseList
EvalCaseDetail
EvidenceChunk
```

---

# 18. 组件复用原则

- Practice 和 Review 共用 question components
- Practice sidecar 和 standalone Tutor 共用 tutor components
- Factory 和 Eval 的 evidence card 尽量共享 source primitives
- Dashboard 不自己造一套 MetricCard
- 页面不允许私有化一套 Button / Badge / Table 样式

---

# 19. Responsive

当前优先桌面。

## Desktop
完整 sidecar。

## Tablet
Tutor 可调整到 360px 或 Resizable。

## Mobile
Tutor 使用 Sheet / full-screen drawer。
不要硬挤成两栏。

V3 首轮只要求：
- Desktop 完整
- Tablet 不崩
- Mobile 基本可用

---

# 20. 动画

默认：
- 150~200ms transition
- hover / active
- drawer / dialog
- skeleton

可以：
- message streaming fade
- panel resize
- subtle layout transition

不要：
- 大量 spring
- 每张卡 enter animation
- page scroll effects
- 彩色粒子

---

# 21. UI 验收 checklist

每页完成前回答：

```text
[ ] 这页的主要任务能在 3 秒内看懂
[ ] 只有一个最强 CTA
[ ] 是否至少能删掉 20% 非必要信息
[ ] 是否使用统一 spacing / token
[ ] 是否有多余 Card 套 Card
[ ] 是否出现了不必要图表
[ ] 是否有开发者术语进入用户界面
[ ] 是否真正突出 Agent / learning workflow
[ ] 空态 / 加载 / 错误态是否完整
[ ] 1440px / 1920px 下是否都自然
```

---

# 22. 最终视觉判断

V3 不追求“截图看起来功能最多”。

要追求：

> **截图发出去以后，别人愿意点开仓库。**

而进入仓库以后：

> **核心功能真的能跑。**

# TiBan V3 重构总纲：Agent-first Portfolio Rebuild

> 用途：本地 Coding Agent 的最高优先级上下文。
>
> 这份文档决定 **为什么重构、重构到什么程度、哪些东西值得做、哪些东西现在不值得做**。
> 后续 UI、目录、代码实现都应服从这里的目标。
>
> 当前阶段不讨论服务器部署。

---

# 1. V3 的真正目标

TiBan V3 不是一次“功能扩建”，也不是一次“全栈技术大迁移”。

这次重构只解决三个问题：

1. **让产品第一眼更专业、更有传播力**
2. **把真正能体现 Agent 技术竞争力的能力放到视觉和交互中心**
3. **把现有成熟能力重新组织成一条容易 Demo、容易讲、容易维护的主线**

最终目标：

> **Less product breadth, stronger Agent story.**
>
> 少做业务，核心链路做到位；前端好看但克制；Agent / RAG / Memory / Eval / Generation 的技术价值一眼能看出来。

这不是“做一个完整教育 SaaS”。

这是一个面向大模型应用 / Agent 岗位的 **高完成度作品项目**。

---

# 2. 产品定位统一为 TiBan

## 中文
**题伴 TiBan — AI Tutor 驱动的题库与学习工作台**

## 英文
**TiBan — Agent-native Question Bank & Learning Workspace**

对外第一层只需要让人理解：

> TiBan 把题库、练习、Tutor Agent、知识检索、学习记忆、题目生成和评测串进同一套学习工作流。

不要把项目介绍成：
- 教育管理系统
- 医疗信息系统
- 完整 LMS
- 大型在线教育平台

Medical / Endoscopy 是第一个成熟 Domain，不是 TiBan 的边界。

---

# 3. 面向求职的核心技术叙事

V3 最终只固定 **四个技术亮点**。

## Highlight 1 — Persistent Tutor Agent
Tutor 不是独立聊天页里的普通 Chatbot，而是练习过程中的常驻 Agent：

```text
Current Question
+ Question Context
+ Learner Memory
+ Knowledge Retrieval
+ Tool Policy
        ↓
     Tutor Agent
        ↓
Answer / Hint / Explanation / Citation
```

UI 必须让人自然感知：
- Tutor 知道“我现在正在做哪道题”
- Tutor 可以按需检索知识
- Tutor 能引用来源
- Tutor 能利用已有学习状态
- Tutor 不是一个脱离业务的聊天壳

**这是整个 V3 最重要的 Hero。**

---

## Highlight 2 — Adaptive Learning + Memory
核心不是做复杂学习画像，而是体现：

```text
Answer
→ Attempt
→ Mastery / FSRS
→ Learning Memory
→ Next Session / Tutor Context
```

V3 UI 只展示用户真正需要看到的结果，例如：
- 最近容易错的知识点
- 待复习
- 为什么推荐这组题
- Tutor 对当前薄弱点的辅助

不要为了“画像”造大量雷达图和仪表盘。

---

## Highlight 3 — Source-backed Question Factory
Question Factory 的核心不是后台管理，而是：

```text
Source
→ Parse / Chunk
→ Generate
→ Gate / Judge / Repair
→ Review
→ Publish
```

要让访问者看到：
- 题目从哪里来
- 生成工作流如何运行
- 草稿如何被校验和修正
- 最终如何进入题库

这比“100 个运营配置项”更能体现 Agent Engineering。

---

## Highlight 4 — RAG / Agent Evaluation
评测页体现的是工程能力，而不是 BI 能力。

重点：
- Retriever strategy comparison
- Recall / MRR / nDCG / latency
- Case-level evidence
- Tutor routing / tool-selection cases
- citation support

优先：
**表格 + case detail + evidence**

而不是：
**很多装饰性图表**

---

# 4. 当前只保留 7 个产品页面

V3 第一阶段只围绕下面页面工作。

## P0
1. **学习总览**
2. **题库**
3. **刷题工作台**
4. **错题与复习**
5. **Tutor**
6. **题目工厂**
7. **评测**

其中真正的 Hero 顺序：

```text
刷题工作台 + Tutor
        ↓
题目工厂
        ↓
评测
        ↓
题库
        ↓
错题复习
        ↓
学习总览
```

不是首页优先。

---

# 5. 建议收敛后的导航

不要把所有能力都变成一级菜单。

建议：

```text
学习
├─ 学习总览
├─ 题库
├─ 刷题
└─ 错题复习

Agent
├─ Tutor
└─ 题目工厂

评测
└─ 评测中心

底部
└─ 设置
```

## 暂时不作为一级导航
- 学习画像
- 文档库
- 检索工作台
- 知识点管理
- 导入中心
- Provider 管理
- 操作日志
- 成绩报告

这些能力：
- 能并入已有页面就并入
- 以后需要时再独立
- 不要为了“看起来完整”把菜单堆满

### Retrieval Workbench
建议并入 **评测中心** 的一个 Tab：

```text
评测中心
├─ Retrieval
├─ Tutor
└─ Model / Provider（后续）
```

### 文档导入
优先从 **Question Factory** 进入。

---

# 6. 四张视觉参考图：只学习方向，不照抄

本地只保留这四张。

建议存储为：

```text
docs/v3/references/
├─ 01_external-qbank-reference.png
├─ 02_target-dashboard-lite.png
├─ 03_target-practice-tutor.png
└─ 04_target-review-tutor.png
```

## 01_external-qbank-reference.png
这是外部项目。

重点学习：
- 信息密度控制
- 轻边框 + 大留白
- 单色、低噪音
- 左侧导航很克制
- 题目列表直接展示内容，不靠大量花哨 Card
- 操作集中在同一视觉层级

不要照搬：
- 它偏工具型题库后台
- 没有 TiBan 的 Agent / Tutor / learning loop
- 它的 IA 不是你的 IA

---

## 02_target-dashboard-lite.png
这是目标方向，不是实现清单。

保留：
- Sidebar / Topbar 比例
- 字体层级
- 白底 + 轻边框
- 简洁 KPI
- 推荐学习 / 薄弱知识点 / 最近活动的布局逻辑

删减：
- 指标最多 3~4 个
- 不做复杂学习计划
- 不做太多统计模块
- 不把 Dashboard 做成 V3 的重点

---

## 03_target-practice-tutor.png
**这是 V3 最重要的视觉参考。**

基本方向可以接近：

```text
┌──────────── Main Practice ────────────┬──── Tutor Sidecar ────┐
│ progress                              │ current context        │
│ question context                     │ retrieval status       │
│                                      │                        │
│ question stem                        │ conversation           │
│ options                              │                        │
│                                      │ citations              │
│ hint / skip              submit      │ suggestions / composer │
└───────────────────────────────────────┴────────────────────────┘
```

目标比例：
- Practice：约 66%~70%
- Tutor：约 30%~34%
- Tutor 宽度约 360~440px，按 viewport 自适应

重点：
- 右侧 Tutor 是完整工作区，不是小卡片
- Practice 才是主任务
- Tutor 辅助但持续存在
- 引用来源自然出现在回答里
- 顶部 1~2 个状态 Chip 即可，不做 Agent Trace 大屏

---

## 04_target-review-tutor.png
这是第二重要参考。

重点学习：
- 和 Practice 使用同一骨架
- 提交后只改变内容状态，不换一套页面
- 正确答案 / 用户答案视觉非常明确
- explanation 紧跟题目
- Tutor 继续留在右侧，回答“我为什么错”
- 最近错误信息可以轻量展示

不要增加：
- 复杂复盘图
- 每题分数大卡片
- 大量审计字段

---

# 7. 技术栈决策

## 前端：保留当前 React / Vite 主线
建议：

```text
React
TypeScript
Vite
React Router
Tailwind CSS v4
shadcn/ui
TanStack Query
React Hook Form
Zod
Lucide
```

### 可以引入
- `class-variance-authority`
- `tailwind-merge`
- shadcn/ui 基础组件

### 动画
优先 CSS transition。

只有明确需要 layout / enter-exit 动画时再加 Motion。
不要因为“现代”而让每个组件都有动画。

---

## 为什么不迁 Next.js
当前 TiBan 是典型前后端分离应用：
- FastAPI 已经是 canonical backend
- Tutor / RAG / Factory / Eval 都在 Python backend
- 没有 SEO / SSR 作为当前核心需求

所以迁 Next.js 的收益不足以覆盖重构成本。

V3 重构的核心应该是：
**体验与 Agent 产品表达，不是框架迁移。**

---

## shadcn/ui 的使用原则
用它做：
- Button
- Input
- Select
- Dialog
- Sheet
- Tabs
- Dropdown
- Tooltip
- Table primitives
- Skeleton
- ScrollArea
- Resizable（需要时）

不要把 shadcn default page 直接复制进项目。

TiBan 要有自己的：
- spacing
- typography
- surface
- navigation
- question / tutor / factory 业务组件

---

## TanStack Query
统一管理 server state：
- banks
- questions
- practice sessions
- attempts
- review
- tutor threads
- factory jobs
- eval runs

不要把这些长期塞进全局 Zustand / Redux。

本地 UI state 先用：
- `useState`
- `useReducer`
- URL state
- 必要时 Context

---

## AI Chat UI
可以参考：
- assistant-ui 的 composable chat primitives
- Vercel Chatbot 的 message / composer / streaming UX

**默认不迁入新的 AI SDK。**

TiBan 已经有自己的 FastAPI Agent Runtime / SSE / tool boundary。
前端只需要把它表现得更好。

---

# 8. 后端原则

V3 不做后端大重写。

保留：
- FastAPI
- PostgreSQL
- Qdrant
- Redis / Dramatiq
- existing Agent Runtime
- existing generated OpenAPI client workflow
- Practice / Memory / Factory / Eval 已有核心实现

后端只做两类修改：
1. 前端核心页面确实缺少的 API shape
2. 新 UI 暴露出已有 API 契约不合理的地方

不要因为页面重构重新设计整个 Domain Model。

---

# 9. 目录原则：不要为 V3 再做一次“大搬家”

当前 active code tree 是 source of truth。
历史 archive 只作参考，不重新放回 active tree。

V3 优先在当前结构上增量收敛。

前端内部推荐：

```text
frontend/src/
├─ app/
│  ├─ router/
│  ├─ providers/
│  └─ shell/
├─ components/
│  ├─ ui/
│  ├─ layout/
│  ├─ tutor/
│  ├─ question/
│  ├─ factory/
│  └─ eval/
├─ features/
│  ├─ dashboard/
│  ├─ banks/
│  ├─ practice/
│  ├─ review/
│  ├─ tutor/
│  ├─ factory/
│  └─ evaluation/
├─ lib/
│  ├─ api/
│  ├─ schemas/
│  ├─ utils/
│  └─ design/
├─ routes/
└─ styles/
```

原则：
- route / page：组装
- feature：data + business UI state
- component：渲染
- lib：跨 feature 基础能力

不要先建 monorepo / packages，除非当前仓库已经是这种结构。

---

# 10. V3 分支

建议：

```bash
refactor/v3-tiban-agent-experience
```

它比：
- `v3-ui`
- `v3-redesign`
- `fullstack-rewrite`

更准确。

因为这次不是纯换皮，而是：
> 围绕 Agent 核心体验重新收敛产品。

---

# 11. 第一阶段不做的事情

V3 Core Rebuild 暂不投入：

- Server deployment
- Auth redesign
- Multi-tenant
- Electron
- GraphRAG
- Multi-Agent
- VLM Tutor 新产品线
- 开放题大规模扩展
- 复杂学习画像
- 雷达图 / BI 大盘
- 课程计划系统
- 社交 / 排名 / 打卡
- 新的全局状态框架
- 新的后端框架

这些都不能比：
**Practice + Tutor / Factory / Eval**
更优先。

---

# 12. 判断任何新功能是否值得进入 V3

每提出一个新模块，先回答：

```text
1. 它是否让 Agent 能力更容易被看见？
2. 它是否让核心 Demo 更完整？
3. 它是否能成为面试里有价值的技术 Story？
4. 它是否可以在较短时间内做扎实？
```

满足 0~1 条：
> 不做。

满足 2 条：
> backlog。

满足 3~4 条：
> 才进入 V3。

---

# 13. V3 的成功标准

完成后，第一次打开项目的人：

## 10 秒内
知道：
> TiBan 是 AI 题库 + Tutor Agent 学习工作台。

## 30 秒内
能看到：
- 刷题
- Tutor
- 题目生成
- 评测

## 2 分钟内
能理解：
- Tutor 不是孤立 Chatbot
- RAG 有引用
- 学习历史会进入后续 context / scheduling
- 题目生成是 source-backed workflow
- 有可复现 Eval

## 5 分钟 Demo
可以走完：

```text
题库
→ 开始练习
→ Tutor 提问
→ 提交错误答案
→ 查看解释 / Tutor 纠错
→ 查看错题复习
→ Question Factory
→ Evaluation
```

到这里就是一个非常完整的 Agent 求职项目。

不需要再证明“功能很多”。

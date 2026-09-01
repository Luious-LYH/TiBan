# TiBan V3 RC Human Acceptance & Release Promotion Report

> 验收对象：`refactor/v3-tiban-agent-experience`
>
> 稳定基线：`06d07b0 docs: polish public screenshot captions`
>
> 本报告是 Release Promotion Gate 的收口记录，不开启 Phase F/G，不进入 V4，也不创建正式 `v3.0.0`。

## A. Screenshot-led Human Audit

本轮以当前真实 Compose 页面为准重新检查了首页、题库、Session Builder、Practice、提交后复盘、智能辅导、题库导入、模型评测和 Settings。截图由 Playwright 直接访问 `http://127.0.0.1:5173` 生成，没有修改 DOM/CSS，也没有使用设计稿替代运行页面。

最终截图目录：[`evidence/rc-promotion/`](./evidence/rc-promotion/)

| 文件 | viewport | 验收用途 |
|---|---:|---|
| `01-practice-rag-citation-1440.png` | 1440×900 | Practice + Persistent 智能辅导 + 真实引用 |
| `02-review-followup-1440.png` | 1440×900 | 错误作答、真实解析、提交后复盘追问 |
| `03-factory-real-job-1440.png` | 1440×900 | 题库导入 / 真实 Factory job / 审核稿 |
| `04-evaluation-evidence-1440.png` | 1440×900 | 模型评测 artifact 与检索证据 |
| `05-overview-1440.png` | 1440×900 | 首页今日完成、最近作答、弱项语义 |
| `06-banks-1440.png` | 1440×900 | 题库列表、搜索、进入刷题 |
| `07-settings-1440.png` | 1440×900 | 实例级智能模型与 Embedding 设置 |
| `08-practice-rag-citation-1920.png` | 1920×1080 | 宽屏 Practice 骨架 |
| `09-practice-rag-citation-375.png` | 375×812 | 移动端智能辅导抽屉 |

### 与视觉目标的实际对照

- 对照 `03_target-practice-tutor.png`：当前页面已经保持左侧导航、中央题目工作区、右侧 full-height 智能辅导三栏骨架；题目区与辅导区的比例、近黑色提交按钮、绿色选中/进度状态基本一致。当前仍比目标图更克制、更少装饰，符合题伴“刷题时保持专注”的范围。
- 对照 `04_target-review-tutor.png`：错误选项为红色、正确选项为绿色，解释区位于题目下方，右侧智能辅导可继续追问并显示引用；当前没有恢复重复的大段“你的答案/正确答案”反馈条。
- 对照 `02_target-dashboard-lite.png`：首页保留轻量指标、推荐题库、弱项和最近作答，没有加入画像雷达图、复杂 BI 或学习计划系统。真实页面的 `373` 被明确标为“今日完成 373 题”，不再与日目标拼接成 `373 / 10`。
- 对照 `01_external-qbank-reference.png`：题库采用列表型密度，搜索和筛选在顶部，主要 CTA 是“开始刷题”，题库导入作为独立入口，不把 Factory 内部字段暴露给学习者。

当前真实页面仍有可见的工程化痕迹，例如评测中心的 `Recall@3` 和 Settings 的 `Embedding`，但它们位于技术页面且有清楚中文上下文；没有把 chunk ID、API Key、内部 revision 或“开发中”入口暴露到核心学习路径。

## B. UX / Data Correctness Fixes

### B1. 首页指标与最近作答

- `frontend/src/pages/overview/OverviewPage.tsx` 将指标从含义混乱的 `331 / 10` / `373 / 10` 形式改成单一语义“今日完成 N 题”。后端仍返回真实 `completed_today`，没有前端重算或伪造。
- 最近作答来自 `backend/app/db/repositories.py:overview()` 的真实 Attempt + Question + QuestionBank 联结，显示题库名、题目摘要、题型、结果和时间；不再只显示“进入复盘 / 回答正确”。
- 当前数据库当天真实记录较多，因此首页显示 373 是真实计数，不代表日目标为 373；产品层已避免把累计/日目标拼成一个无解释的分数。

### B2. Practice 进度

- Practice 统一使用当前题号、session 总题数和已提交数量的同一投影，用户可见为“第 N / 总数 题”和“已完成 X / 总数 · Y%”。
- 已有 session 会定位首个未作答题，题单状态来自服务器 session item / Attempt，而不是前端猜测。
- 相关位置：`frontend/src/pages/practice/PracticePage.tsx`、`frontend/src/components/practice/SessionBuilder.tsx`、`backend/app/db/repositories.py`。

### B3. 弱项语义

- `backend/app/db/repositories.py:learner_visible_weak_topics()` 现在优先使用有意义的 topic / teaching tag；过滤“不符合”、模块占位符、import/csv/jsonl 等非知识概念。
- 如果 tag 只是重复 broad subject，不把它提升为知识点；subject 只能以“学科 · X”作为重复错误后的兜底。目前真实首页显示“酸碱”“学科 · 中医科”，不再显示裸“中医科”“妇产科”或“补充章传统医学病证-模块1”。
- 回归测试已覆盖 subject copy 与 placeholder 过滤。

### B4. 客观题解析与引用

- `backend/app/services/stage1_service.py` 在没有官方解析时返回空解析，前端显示“暂无题库解析”并提供“让智能辅导讲解”；评分标签不会伪装成题目知识解释。
- `frontend/src/components/tutor/TutorSidecar.tsx` 对 Citation 按 document + section 去重，默认收纳，snippet 截断，内部 chunk ID 不进入普通界面；真实 source event、链接和技术字段仍保留在后端/Artifact。
- 这两项均是展示层和语义层收口，没有更改评分、RAG、Attempt、FSRS 或 Tutor 权限语义。

### B5. 用户侧工程词

- Factory 生成草稿库映射为“资料生成题库”；题库页面入口统一为“题库导入”。
- 错题与复习不可用入口从一级导航隐藏，兼容 route 和 FSRS 后端保留。
- Factory 来源显示“已关联 N 条资料片段”，不显示内部 chunk ID；Evaluation 的用户侧标签改为“查询 / 期望证据 / 检索证据”。

## C. Settings Runtime Acceptance

Settings 仍是实例级运行时配置，不引入用户账号、per-user 持久化或假保存 API Key。

已完成真实 Settings acceptance：

| 操作 | 结果 |
|---|---|
| GET 当前 Settings | PASS；只返回脱敏的 configured 状态与当前模型信息 |
| LLM test | PASS；真实连接测试返回成功 |
| LLM apply | PASS；runtime override 生效 |
| 智能辅导真实 runtime call | PASS；调用读取 runtime-scoped override，而非只改变表单 |
| LLM restore | PASS；恢复 `.env` / Docker 默认值 |
| Embedding test | PASS；真实本地 Embedding prewarm / 调用成功 |
| Embedding apply 32 → 16 | PASS；真实 runtime batch setting 改为 16 |
| Retrieval after Embedding apply | PASS；真实检索链仍可调用 |
| Embedding restore | PASS；恢复默认 batch size 32 |

验证位置：`backend/app/routers/settings.py`、`backend/app/services/runtime_settings_service.py`、`backend/tests/test_instance_runtime_settings.py`。API Key 没有写入浏览器存储、URL、报告或 GET 明文响应。

## D. Regression

| 检查 | 结果 |
|---|---|
| `npm run api:check` | PASS；在 `db0c371` 提交生成 client 与对应 backend schema 后重新执行，clean drift gate 通过 |
| `npm run lint` | PASS |
| `npm test -- --run` | PASS；16 passed |
| `npm run build` | PASS |
| `python -m compileall app` | PASS |
| `python -m pytest -q` | PASS；81 passed, 1 skipped |
| `npx playwright test core-flow.spec.ts phase-c-core.spec.ts stage7-general-flow.spec.ts --project=chromium` | PASS；7 passed |
| `docker compose config -q` | PASS（前序 Compose acceptance） |
| `docker compose ps` | PASS；backend、frontend、worker、PostgreSQL、Redis、Qdrant healthy |

唯一 skip：`tests/test_stage25_data_governance.py::test_demo_qbank_acceptance_database_is_available`（完整名称以当前仓库测试文件为准），条件是本机存在授权的 3,678 题 Demo QBank acceptance database。当前环境没有该大型本地数据，因此测试明确 skip；它不是 V3 代码失败，也不是由本轮 UI/语义修复触发。此前的 `76 passed` 属于不同测试集合与运行环境，不能与当前 `81 passed, 1 skipped` 直接相减。

## E. Git Inventory & Commits

### 已提交的明确 V3 范围

- 提交：`db0c371 feat(v3): finalize tiban agent learning workspace`
- 包含：V3 frontend shell / Practice / 智能辅导 / Factory / Evaluation / Settings、对应 backend runtime、OpenAPI generated client、回归测试、Compose runtime 配置、真实知识库 fixture 与 UI evidence 脚本。
- 没有使用 `git add .`。
- 没有执行 `git reset --hard`、`git clean -fd`、stash 或删除用户工作树内容。

### 未纳入本次 release commit 的历史工作树内容

仓库中仍有前序整理留下的历史文档、旧阶段证据、旧 Compose override、旧前端页面删除和根目录文档修改。它们没有被本次提交重新处理或覆盖，避免把无法确认归属的历史变更混入 RC commit。新的 RC 截图、报告和 V3 证据仅按明确路径提交。

## F. Clean API Drift Gate

`frontend/src/api/generated.ts` 由 `frontend/scripts/generate-openapi.mjs` 根据当前 FastAPI OpenAPI 重新生成。将 backend schema 与 generated client 一起提交后，执行：

```text
npm run api:check
→ exit code 0
```

因此前一份 Phase E 报告中的 “stable generation but git diff non-zero” caveat 已关闭。OpenAPI check 不依赖未提交的本地 source diff。

## G. Hosted CI

远程分支已推送：

```text
origin/refactor/v3-tiban-agent-experience
```

GitHub Actions workflow 为 `.github/workflows/ci.yml`，仍沿用仓库既有的 backend、frontend、Playwright smoke 和 architecture gate。当前 release commit 已触发 hosted run；最终状态在本报告更新时以 GitHub Actions 实际结果为准，不以本地通过替代 hosted 结果。

## H. Final Screenshot Set

README、Evidence Matrix 和 Demo Flow 已切换到 `docs/v3/evidence/rc-promotion/`：

- README：Practice Hero、首页、Factory、Evaluation 使用 RC 截图。
- `docs/portfolio/FINAL_EVIDENCE_MATRIX.md`：V3 核心能力引用 RC 截图并链接本报告。
- `docs/v3/portfolio/V3_DEMO_FLOW.md`：75 秒 Demo Flow 指向 RC 截图和本报告。

最适合秋招展示的顺序是：

```text
Practice + 智能辅导 + Citation
→ Submit / Review
→ Factory real job
→ Evaluation evidence
→ Settings runtime
```

首页和题库截图作为产品入口，移动端截图作为响应式补充；不建议把所有历史阶段截图放在 README 首屏。

## I. README / Evidence Sync

本轮只更新证据链接和 RC 报告入口，没有新增 Feature 宣传。README 首屏仍然先说明：题伴是什么、为什么是 Agent-native、智能辅导如何使用当前题目与检索证据、题目生成为什么经过 worker / judge / review、评测为什么投影真实 artifact。

## J. Promotion Gate

| Gate | 当前状态 | 证据 |
|---|---|---|
| Human Acceptance H1 — 首页 → 题库 → Session Builder → 刷题 → 题单 → Submit → 智能辅导 | PASS | Playwright Flow V3-A、`01/02/05/06` 截图 |
| Human Acceptance H2 — Resume session / 进度 / 题单状态 | PASS | 持久化 session membership、已有 session 首个未答题定位、Practice 截图与核心回归 |
| Human Acceptance H3 — Wrong answer / explanation / citation | PASS | `02-review-followup-1440.png`、真实提交后智能辅导流 |
| Human Acceptance H4 — Settings test → apply → runtime → restore | PASS | 真实 runtime acceptance 记录、Settings contract tests |
| Human Acceptance H5 — Factory small upload → real job → review / publish | PASS | `03-factory-real-job-1440.png`、Phase C Flow B、真实 job 链路 |
| Human Acceptance H6 — artifact → case → expected/ranked evidence | PASS | `04-evaluation-evidence-1440.png`、Phase C Flow C |
| UX / data correctness | PASS | 首页指标、Practice 进度、weak topics、无解析回退、Citation 收纳、工程词清理 |
| Clean API drift | PASS | `npm run api:check` exit code 0 |
| Hosted GitHub Actions | PENDING | Run triggered for `db0c371`; see Section G |

### 当前 promotion 判定

在 Hosted Actions 对 `db0c371` 返回全绿之前，严格 Gate 状态为：

```text
TiBan V3 RC Promotion Gate = PENDING
```

这不是功能 blocker；本地可展示版本已经完成，剩余是远程 release hygiene。收到 hosted run 的最终结果后，只需更新本节和 Section G，不再重复 Phase E 或重新设计 UI。

## K. Release Commit / Tag Recommendation

- 当前 release commit：`db0c371617db9b0894275d1a341acada100b2b1a`
- 推荐 tag：`v3.0.0-rc1`
- 本轮不创建正式 `v3.0.0`，也不自动创建 / push `v3.0.0-rc1`，等待用户确认。
- Post-RC backlog（开放回答 AI 解析、XLSX、Anki、完整 Agent 评测工作台等）不属于本轮，不进入报告执行范围。

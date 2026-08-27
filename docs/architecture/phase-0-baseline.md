> Phase 0 Recovery / Baseline 记录。快照时间：2026-08-27（Asia/Shanghai）。本文件记录分支、commit、tag、diff 与现有验证结果；Phase 0 未修改业务逻辑。

### 1. Git 基线

| 项目 | 结果 |
|---|---|
| Repository | `E:\\2.Projects\\ARIS\\Endoscopy_Agent\\code` |
| Phase 0 起始分支 | `feat/portfolio-v2.1` |
| Phase 0 目标分支 | `refactor/v3-agent-learning-platform` |
| 当前 HEAD | `9befbe104d2ed165c535e9069b01037ac4a94de6` |
| HEAD 摘要 | `Phase 1 验收通过 - 添加完整验收报告 ✅` |
| 行为对照 tag | `v2.2.1-before-v2.2.2` |
| 对照 tag commit | `4e8825ecc6062e2379b9f757bc76951240be2663` |
| 分支结果 | 已从当前 HEAD 创建 `refactor/v3-agent-learning-platform` |
| 重构状态 | 未开始；不自动进入 Phase 1 |

创建分支时未执行 reset、checkout 覆盖、清理或 stash；工作区中的用户资料和已有修改均保留。

### 2. 创建分支前工作区快照

以下状态在创建重构分支前已经存在，Phase 0 未触碰：

```text
 M artifacts/eval/latest.json
 M artifacts/eval/latest.md
?? docs/portfolio/23_v2.2.2_最新版本评测报告.md
?? docs/portfolio/24_v2.2_ClaudeCode修改前评测报告.md
?? docs/portfolio/25_v2.2.2_Current_State_Technical_Audit.md
?? docs/portfolio/26_v2.2_ClaudeCode修改前_Current_State_Technical_Audit.md
?? docs/portfolio/27_EndoTutor_v3_Architecture_Decision_and_Roadmap.md
```

这些文件不是 Phase 0 的业务实现变更；后续仍需在提交时由用户决定是否分开提交或保留为工作区资料。

### 3. 对照 diff 快照

使用的固定命令：

```powershell
git diff --stat v2.2.1-before-v2.2.2..HEAD
git diff --name-status v2.2.1-before-v2.2.2..HEAD
git diff --stat v2.2.1-before-v2.2.2..HEAD -- backend
git diff --stat v2.2.1-before-v2.2.2..HEAD -- frontend
```

结果摘要：

- 总 diff：13 个文件，`3226 insertions(+), 5 deletions(-)`。
- backend diff：空；当前 `v2.2.2` 没有修改 backend 文件。
- frontend diff：9 个文件，`2197 insertions(+), 5 deletions(-)`，集中于 `App.tsx`、`main.tsx`、v2.2.2 adapters/types、四个 v2.2.2 页面和 `v2.2.2.css`。
- 其余 4 个变更文件是 `docs/portfolio/` 下的 v2.2.2 审查/范围/进度/验收文档。

因此本分支的重构基线是：保留当前 HEAD 的历史和 backend Agent/evaluation 资产；旧 tag 仅做行为回归参照；当前 v2.2.2 前端页面和 adapter 允许在 Contract First / Product Rebuild 阶段重写。

### 4. Phase 0 验证结果

详细命令、环境和输出摘要见 [Phase 0 测试结果](../evals/phase-0-baseline-test-results.md)。结论：

- backend 可编译，现有 pytest 在正确的 `PYTHONPATH` 下通过。
- frontend 可 build，但 lint 基线失败；这是后续 Frontend Product Rebuild 的已知问题，不在 Phase 0 修复。
- frontend 当前没有 test script、Vitest/RTL 用例或 Playwright E2E 用例。

### 5. Phase 0 交付边界

已完成：

- 创建重构分支；
- 固定 HEAD、旧 tag 与两版本 diff 结论；
- 保存 baseline architecture record；
- 运行当前 backend/frontend 可用验证；
- 写入 ADR-000；
- 记录用户批准的 Question Schema、最小 Tutor Harness、确定性 workflow、RAG benchmark、Observability 和逐阶段 evidence 约束。

未做：

- 未修改 backend/frontend 业务逻辑；
- 未安装依赖；
- 未修改 package、schema、API、数据库或运行时数据；
- 未自动进入 Phase 1 Contract First。

### 6. 下一步门禁

Phase 0 在本记录和 ADR-000 完成后暂停。只有用户明确确认 Phase 0 结果，才开始 Phase 1；Phase 1 的第一批实现范围为 discriminated question union、Public/Private schema、`bank_id` 过滤、多选 grading contract、OpenAPI client 和 answer-isolation tests。

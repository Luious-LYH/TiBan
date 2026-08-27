# ADR-000：EndoTutor v3 重构基线与 Phase 0 约束

- Status: Accepted for planning; implementation starts only after Phase 0 confirmation
- Date: 2026-08-27
- Scope: baseline, architecture guardrails, migration order
- Supersedes: any broader or less-specific wording in the first-round roadmap where this ADR defines a stricter v1 boundary

## Context

EndoTutor 当前 HEAD 为 `9befbe104d2ed165c535e9069b01037ac4a94de6`，所在原分支为 `feat/portfolio-v2.1`；行为对照 tag 为 `v2.2.1-before-v2.2.2`（`4e8825ecc6062e2379b9f757bc76951240be2663`）。两者之间的 13 文件 diff 没有 backend 改动，主要是 v2.2.2 前端页面、adapter、types、CSS 与 portfolio 文档。

现有 backend runtime、Tool Receipt、retry/recovery、checkpoint/replay、trace 和离线 eval artifact 有迁移价值；现有 frontend 则存在重复页面/client、字段契约漂移、mock/硬编码与 lint 基线失败。当前公开题目 payload 还会泄漏 `answer`，因此 Contract First 必须先处理安全和类型边界。

用户已批准总体架构和技术路线，并授权 Phase 0 创建重构分支、记录基线、运行现有验证和写 ADR；用户明确要求 Phase 0 完成后暂停，不自动进入 Phase 1。

## Decision

### D1. Baseline

从当前 HEAD 创建并实施：

```text
refactor/v3-agent-learning-platform
```

不回退或覆盖当前 HEAD。`v2.2.1-before-v2.2.2` 只作为行为回归、差异解释和局部恢复参照。创建分支不清理工作区，不覆盖用户已有的 audit/eval 文件或 `artifacts/eval/latest.*` 修改。

### D2. Question schema：MVP 使用 discriminated union

Question 不再由一个包含大量 optional 字段的万能类型承载。服务端至少建立以下公开/私有边界：

```text
QuestionPublic
QuestionForGrading
QuestionAdmin
QuestionDraft
```

其中 MVP 题型由 `question_type` discriminator 区分：

```text
SingleChoiceQuestion
MultipleChoiceQuestion
TrueFalseQuestion
ShortAnswerQuestion
```

`options` 只出现在需要选项的 variant；`answer`、hidden rubric 和 grading target 只存在于服务端 grading/admin/draft 边界；`QuestionPublic` 永不携带 pre-submit answer key。每种 variant 必须拥有与其题型匹配的 grading contract，不能用 `str | string[] | null` 的万能字段掩盖差异。

### D3. Tutor v1：最小 Agent Harness

不把自研 runtime 发展成通用 Agent Framework。Tutor v1 仅实现当前业务需要的最小抽象：

```text
AgentRunner
ToolRegistry
ModelGateway
AgentContext
AgentEvent
AgentResult
```

横切控制只包含 `max_steps`、timeout、cancel、retry、tool permission 和 trace。现有 runtime 中有价值的 receipt、recovery、checkpoint/replay 可迁移到这些边界，但不提前实现通用多 Agent 编排、插件市场、复杂 memory framework 或自由 round-robin 群聊。

### D4. Agent 与确定性业务 workflow 分离

Tutor 第一版只开放少量需要模型选择的工具，例如读取题目上下文、检索知识、澄清术语、比较选项、生成分级 hint，以及提交后读取 grading result 并生成解释。

`update_learning_state`、`schedule_review` 等确定性副作用不交给 LLM 自主决定。用户 submit 成功后，由 application workflow 顺序执行：

```text
grade → attempt → mastery → review scheduling
```

Agent 可以读取结果或提出后续行动建议，但不能绕过服务端业务规则直接写入学习状态。

### D5. RAG：PostgreSQL state + Qdrant index 为默认优先方案

Phase 5 默认采用：

```text
PostgreSQL = relational state / source metadata / benchmark metadata
Qdrant = retrieval index
```

保留一个轻量 ADR 记录 pgvector 备选，但不为二者做长时间平行开发。必须完成四组可复现 benchmark：

```text
sparse
dense
hybrid
hybrid + rerank
```

每组都输出 Recall@K、MRR、nDCG 及数据集版本/参数/失败 case artifact；没有这些证据，不声称 Hybrid RAG 效果提升。

### D6. Observability：先自研事件，后置 OpenTelemetry

前期保留并统一自研 `ToolReceipt` / `AgentEvent`，同时把 Langfuse 作为 prompt、trace、eval 可视化候选。OpenTelemetry 延后至 Phase 9，根据时间、隐私和部署复杂度决定，不作为 Tutor/RAG 主链路的前置依赖。

### D7. Evidence-first delivery

不等到 Phase 10 才收集作品集材料。每个 Phase 在完成当天输出与其真实实现对应的 artifact，按适用性包括：architecture、ADR、test result、benchmark、trace、screenshot、failure case。Phase 10 只负责汇总、筛选和包装，不补写没有证据的能力。

## Options considered

| Decision area | Rejected option | Reason for rejection |
|---|---|---|
| Baseline | hard reset 到旧 tag | 会丢失当前 HEAD 的历史和未破坏的 backend 资产，也不符合保留可追溯性的要求。 |
| Question model | 一个万能 Question + optional fields | 无法在类型层表达 options/answer/grading contract，容易继续造成 answer leakage 和多选契约漂移。 |
| Tutor runtime | 通用 Agent framework / 全面 Multi-Agent | 增加抽象和调试成本，不能直接提升当前 Tutor 主流程可信度。 |
| Learning side effects | 让 LLM 自主调用 update/schedule 工具 | 副作用不可预测且难以审计；submit 后的学习事件应由 application workflow 确定性提交。 |
| RAG vector layer | Phase 5 同时实现 Qdrant 与 pgvector | 产生无效的平行开发；主目标是四组 benchmark，不是基础设施比较本身。 |
| Observability | Phase 1 强制引入 OpenTelemetry | 会把部署/语义规范成本前置到尚未稳定的事件模型；先统一 ToolReceipt/AgentEvent。 |
| Evidence collection | 全部推迟到 Phase 10 | 会导致实现与证据脱节，无法及时发现不可复现或不可宣传的能力。 |

## Consequences

正面影响：

- Question 类型、提交安全和 grading contract 在类型层可检查；
- Tutor 保持小而可测试，确定性学习状态不被模型自由决策污染；
- RAG 目标从“接入向量库”变为四组可量化 benchmark；
- 事件、trace 和 artifact 从第一阶段起可作为作品集证据；
- 当前 HEAD 的 backend 资产得到渐进式迁移，避免重构范围失控。

代价与限制：

- 需要先设计多个 discriminated union schema 和测试 fixture；
- Tutor 的工具数量和自由度受限，第一版不追求通用性；
- Phase 5 仍需维护 Qdrant、本地 fallback adapter 和 benchmark 数据；
- Langfuse、OpenTelemetry、queue 等基础设施按阶段启用，早期可观测性能力以自研事件为主。

## Rollback

- 代码行为回归以 `v2.2.1-before-v2.2.2` 和当前 HEAD 的 commit ref 为准，不执行破坏性 reset。
- Phase 1 以后每个阶段保留 legacy adapter、JSON fixture 或 deterministic baseline，按 feature/module 回退。
- 如果某项新依赖导致主 Demo 不稳定，关闭对应 feature/profile，保留 artifact 和接口记录，不把失败 fallback 计为成功。
- 删除旧模块前必须完成 caller search、测试和 artifact 检查；任何删除或历史清理需要用户另行确认。

## Approval boundary

本 ADR 允许继续执行 Phase 0 的记录和验证工作；不授权 Phase 1 或任何业务代码重构。Phase 0 报告交付后暂停，等待用户确认。

# TiBan V3 Phase C — Core Agent Release Gate

日期：2026-09-01

> 说明：用户指定的 `docs/v3/03_V3_PHASE_C_CORE_AGENT_RELEASE_GATE.md` 在当前分支不存在；本报告以同目录已存在且内容对应的 `docs/v3/phasec.md` 作为 Phase C gate 规范，并同时复核 00/01/02 三份 V3 长期文档。

## A. Current V3 Baseline

- Branch：`refactor/v3-tiban-agent-experience`
- HEAD：`06d07b0 docs: polish public screenshot captions`
- 工作树：存在大量早于本阶段、彼此混合的修改/删除/未跟踪文件；未 reset、stash、clean 或全量 add。无法安全切分出 scoped checkpoint，因此未创建 commit。
- 本阶段本地运行：`docker compose up -d --build`，PostgreSQL、Redis、Qdrant、FastAPI、Dramatiq worker 均健康。
- 真实 runtime map：

```text
React/Vite → FastAPI → PostgreSQL FactoryJob
→ Redis/Dramatiq → app.workers.factory_worker
→ parse → rag_service.index_markdown → Qdrant
→ Generator → deterministic gate → Judge → Repair（实际触发）
→ revision → Publish → canonical QuestionBank
```

## B. 智能辅导

### PASS — 当前题目与提交后上下文

- `get_question_context` 由 `stage1_service.public_question()` 提供当前题目、公开选项、领域、知识点与公开来源，不携带 pre-submit 答案 key。
- 真实 CMExam 四选项题 `cmexam_000009` 使用 Study 模式提交错误选项后，生成 `attempt_c5bcf33ecc88`；post-submit 辅导真实调用 `get_grading_result`，回复包含“本次得分为 0”。
- 完整 context 边界见 [assistant-context-audit.md](evidence/agent-core/assistant-context-audit.md)。

### PASS — Study / Exam 权限

- Study pre-submit “直接告诉我答案”真实选择 `get_answer_explanation`，返回该题的服务端正确答案与官方解析。
- Exam pre-submit 同一请求的实际 SSE receipt 仅含 `get_question_context` 与 `get_learning_profile`；`get_answer_explanation` 不在允许集合，未泄露答案。

### PASS — Learning Memory 有实际作用

- 显式混淆语句创建 `memory_f3e56d235db0`，未保存原始聊天内容。
- 随后同题追问的 SSE trace 真实选中此记录：`selected_memory_ids=[memory_f3e56d235db0]`、`personalization_reason=current_topic_match`。
- 未添加画像页、记忆面板或虚构“记忆引擎”文案。

### FAIL — README Hero 的真实 RAG Citation

- `retrieve_knowledge` 调用确实进入 `rag_service.retrieve()`；但当前 CMExam Hero 没有在受治理 Qdrant collection 中命中相关 chunk。
- 运行时返回的是 CMExam 题目公开来源 fallback（`namespace=question_source`），不是检索结果。Phase C 已修正前端：它不再显示为“已检索知识库”或“参考资料”。
- 因而 `01-practice-assistant-hero-1440.png` 是真实中文四选项、真实 SSE 辅导和真实作答场景，但**不具备真实 RAG citation**，不满足 Hero A 的完整要求。

### UI 术语清理

- 用户可见 Sidecar 已改为“智能辅导”；输入、发送、aria label、状态同样中文化。
- 非真实 Provider 的本地策略 Runtime 也会渲染真实 token，不再错误显示“暂时无法生成回复”。
- 公开 provenance fallback 不再冒充 RAG citation。

## C. 题目生成

### PASS — 真实 local worker E2E

实际安全 fixture：[phase-c-factory-source.md](evidence/agent-core/phase-c-factory-source.md)。

最终浏览器 E2E 创建并发布的任务：

- Job：`factory_67e21f752089`
- Queue message：`26036fe0-aae9-46f2-b57a-14fc65fd5722`
- 状态：`succeeded / published / 100% / attempt 1`
- 初稿：`revision_b33cb32cd77`，Judge `passed=false`
- Repair revision：`revision_b46a6110fee5`，Judge `passed=true`，已发布
- 真实来源 chunk：`chunk-68d4f0ffeb4f-1f777825-180-00-v2`

浏览器真实完成：上传 → Redis/Dramatiq → Parse → PostgreSQL/Qdrant index → Generator → gate → Judge → Repair → Review → Publish。没有手改数据库、假 job、假 revision 或 mock 成功。

### PASS — Draft / source / quality / lineage 投影

- 页面显示两条真实 revision、来源片段关联数量和 canonical chunk id。
- Repair 只因真实 deterministic Judge 要求补齐“医生复核 / 非独立诊断”安全边界而发生；并非为截图强制制造。
- 发布后 Factory revision 真实写入 `factory-generated-endoscopy-v1` 题库。

### 注意事项

- 第一次冷启动任务 `factory_471f8962f9cb` 因首次 FastEmbed 模型下载超过 Dramatiq 120 秒 actor limit 而变 stale；使用仓库既有 `recover_stale_factory_jobs()` 进行服务级恢复后，第二次 attempt 成功并发布。此问题保留在 job 事件日志中，未掩盖。
- Phase C browser E2E 通过预热同一 Worker 的 embedding cache 后，再执行了独立的新 job；最终 E2E 不依赖手工状态修改。

## D. 评测中心

### PASS — 真实 artifact 投影

- 当前 artifact：`artifacts/eval/latest.json`，`portfolio-agent-eval-v2.1`，`deterministic_offline_golden_case_replay`。
- UI 显示实际 `case_count=5`、任务完成率、证据覆盖率、Recall@3、P50 和五条实际 case id。
- 页面与报告明确该 artifact 不代表真实候选模型或临床性能；没有制造新分数。

### FAIL — Strategy Comparison / Case Evidence Detail

- 原 artifact 的 `retrieval_eval.probes` 中有 ranked evidence ids，但现有 `/api/v3/evaluation/latest` 公开 schema 只投影 metrics/cases，未投影 probes、expected evidence 或 retrieval chunk 内容。
- 因 Phase C 不改 FastAPI/API contract，UI 不能诚实展示“Expected Evidence → Retrieved Chunks → Rank → Source”的案例详情，也不能形成真实 Dense/Sparse/Hybrid/Rerank 比较。
- `04/05` 两张截图为当前真实 API projection；`05` 是辅导评测 tab，并不满足“真实 case evidence detail” gate。

## E. 中文 UI / Branding

- PASS：品牌显示为“题伴 / TiBan · AI 题库与学习工作台”；Sidecar 用户可见名称统一为“智能辅导”。
- PASS：主导航收敛为学习、智能能力、评测；Preview-only routes 未出现在一级导航。
- PASS：本阶段未新增页面、一级导航、普通教育业务、GraphRAG、Multi-Agent、数据库、框架或部署配置。

## F. Tests

| Gate | Result |
|---|---|
| `npm run api:check` | PASS |
| `npm run lint` | PASS |
| `npm test -- --run --reporter=verbose` | PASS — 12 passed |
| `npm run build` | PASS |
| `python -m compileall app` | PASS |
| `python -m pytest -q` | PASS — 75 passed, 1 skipped |
| Phase C Flow A | PASS — CMExam Session Builder → 四选项刷题 → 智能辅导 → submit → post-submit review |
| Phase C Flow B | PASS — 实际 worker → draft/source/repair → publish |
| Phase C Flow C | PASS — existing artifact retrieval / tutor tabs |
| General domain regression | PASS — shared practice core |
| `git diff --check` | PASS |

## G. Screenshots

- [01-practice-assistant-hero-1440.png](evidence/agent-core/01-practice-assistant-hero-1440.png) — 中文四选项、已选答案、真实 Sidecar 回复；没有把 provenance fallback 伪装为 RAG citation。
- [02-review-assistant-hero-1440.png](evidence/agent-core/02-review-assistant-hero-1440.png) — 真实错误状态与提交后追问。
- [03-question-generation-real-job-1440.png](evidence/agent-core/03-question-generation-real-job-1440.png) — 真实 job、两版 revision、source chunk、Judge/Repair、发布 CTA。
- [04-evaluation-retrieval-1440.png](evidence/agent-core/04-evaluation-retrieval-1440.png) — 真实 artifact metrics/cases。
- [05-evaluation-case-detail-1440.png](evidence/agent-core/05-evaluation-case-detail-1440.png) — 当前辅导评测 tab 的真实投影；非 case-evidence detail。
- [06-general-domain-proof.png](evidence/agent-core/06-general-domain-proof.png) — 通用科学域复用同一 Practice + 智能辅导骨架。

## H. V3 Core Release Gate

| Release gate | Result | Evidence |
|---|---|---|
| 题伴 / TiBan branding 统一 | PASS | AppShell + screenshots |
| 核心导航收敛 | PASS | 仅学习/智能能力/评测 |
| 学习首页简洁 | PASS | Phase B baseline，Phase C 未扩展 |
| 题库 + Session Builder 真实 | PASS | Phase C Flow A |
| 刷题 + 智能辅导达到 README Hero 水平 | FAIL | 有真实中文四选项与 SSE，但缺真实 RAG citation |
| Review 与刷题共用骨架 | PASS | `02-review-assistant-hero-1440.png` |
| 辅导智能体理解当前题目 | PASS | context audit + SSE receipts |
| Retrieval / Citation 真实 | FAIL | 无 CMExam Hero RAG chunk 命中；provenance 不再被误标 |
| Study / Exam 权限真实 | PASS | runtime SSE receipts + regression tests |
| Learning Memory 有真实作用且不画像化 | PASS | memory audit evidence |
| 题目生成真实 local worker 链通过 | PASS | `factory_67e21f752089` |
| Draft 有真实来源证据 | PASS | revision source_chunk_ids + screenshot 03 |
| 评测中心使用真实 artifact / case | PASS | latest artifact + screenshots 04/05 |
| 无 fake headline metrics | PASS | artifact 声明为离线确定性回放 |
| OpenAPI drift | PASS | `npm run api:check` |
| frontend lint / unit / build | PASS | 见 F |
| backend regression | PASS | 75 passed, 1 skipped |
| architecture guard | PASS | backend regression suite |
| V3 Playwright flows | PASS | Flow A/B/C + general domain regression |
| Hero screenshots 完成 | PARTIAL | 6 张真实截图已生成；Hero A citation 与 Hero C case detail 不达 gate |
| 60–90 秒 Demo Flow 完成 | PASS | [V3_DEMO_FLOW.md](portfolio/V3_DEMO_FLOW.md) |

**V3 Core Release Candidate：FAIL（暂不应进入 README / Portfolio Packaging）。**

## I. Remaining Issues

1. 为中文 CMExam/CMB-Exam Hero 建立受治理、可审计且与题目相关的知识 source/chunk，使真实 retrieval 命中后出现对应 citation；不得用题目 provenance fallback 代替。
2. 在不伪造数据的前提下，为现有评测 artifact 提供 read-only case/probe evidence projection，或明确调整 gate；当前用户无法看到 expected evidence、ranked chunks、rank/source。
3. 若希望任何 provider-backed 辅导作为演示条件，需要配置可用 Provider；本地验收使用的是真实 local-policy runtime，而初始外部 Provider 配置曾返回 `ApplicationError`。
4. 将 Compose frontend 配置成可访问 API（反向代理或正确公开 base URL）；本阶段 E2E 使用项目 Vite proxy，Compose Nginx 静态前端本身无 `/api` proxy。
5. 首次 FastEmbed 下载会超过 Worker 120 秒 actor limit；冷启动需要预热或由后续 release 明确处理该限制，不能依靠静默 stale recovery。

本阶段到此停止；没有自动进入下一阶段。

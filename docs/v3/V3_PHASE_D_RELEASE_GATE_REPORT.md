# TiBan V3 Phase D — Release Gate Closure & Runtime Hardening

日期：2026-09-01  
分支：`refactor/v3-tiban-agent-experience`

> 本报告只记录真实 API、Runtime、artifact 与浏览器运行结果。没有手改业务数据库来制造成功状态，也没有将 question provenance 当作 RAG Citation。

## A. RAG Hero

**PASS**

- Hero 题：真实 learner-facing CMB-Exam `cmb_val_000079`（小肠分节运动，中文四选项）。
- 资料：按既有 corpus manifest/governance 加入并用 `backend/scripts/index_knowledge_corpus_v1.py` 重建；46 份文档、276 个 chunk。
- 真实链路：`rag_service.retrieve(dense)` → Qdrant → `/api/v3/tutor/stream` SSE `source` → Practice 常驻“智能辅导”。
- 首个真实 source：`chunk-ine-motility-bf81c8a1-180-00-v2`，主显示为《小肠运动与消化液混合》· 核心概念；namespace=`endoscopy`，不是 `question_source`。
- 浏览器继续走了错误作答和 post-submit 追问；智能辅导读取真实 `attempt_id` 后输出“这次作答还需要复盘”，并保留同一资料引用。

## B. Evaluation Evidence

**PASS（Case Detail） / N/A（Strategy Comparison）**

- 新增只读 typed contract：`EvaluationEvidencePublic`、`EvaluationRetrievedEvidencePublic`、`EvaluationProbePublic`、`EvaluationStrategyPublic`，并扩展 `EvaluationArtifactResponse.probes` / `strategy_comparison`。
- `/api/v3/evaluation/latest` 仅投影 `artifacts/eval/latest.json` 已有 probe、expected evidence、ranked evidence、rank 和 hit；metadata 从已有 `portfolio_cases.json` 解析为来源、章节和 snippet。
- Compose 容器现在只读挂载根目录 `artifacts/`，因此同源 frontend 获得真实 artifact，而不是错误显示“尚未运行”。
- 当前 artifact 没有真实 multi-strategy 行；UI 和 API 均返回空数组，不制造 Dense/Hybrid/Rerank 表。

## C. Runtime Hardening

### Compose proxy / SSE — PASS

- Nginx `/api/` 转发到 `backend:8000`；关闭 proxy buffering/cache，采用 HTTP/1.1 和长读写超时。
- Compose frontend 的 `VITE_API_BASE_URL` 为空，使用同源 `/api`。
- 实测 `http://127.0.0.1:5173/api/health` 成功；同源 SSE 在真实 CMB Hero 页面流式返回 token 与三条 source。

### Factory warm path — PASS

- Worker 启动阶段实际 FastEmbed prewarm 成功，日志记录 `BAAI/bge-small-zh-v1.5` 约 1–2 秒完成（持久 cache volume）。
- 新任务经真实 UI 上传 `phase-c-factory-source.md` 后到达 `等待审核 / 100% / 第 1 次执行`；显示初始草稿、真实 Judge 要求的修订草稿和真实 source chunk。
- 未触发或强迫 Repair；此任务的 Repair 来自已有 Judge 规则。

### Factory isolated cold-download path — FAIL

- 本轮没有删除/替换既有用户 Docker volume，也没有构造独立 project + 空 FastEmbed cache 的完整 Worker→首个 Factory job 验收。
- 因此不能把持久缓存上的 prewarm 结果宣传为首次外网下载/初始化已经验证。Worker readiness 与 warm path 已闭合，干净 cache 首任务仍是 RC blocker。

### Provider optional path — PASS（本地 adapter）

- Compose 默认值为 `TUTOR_PROVIDER_ENABLED=false`；未配置外部 Key 时使用既有 `local-policy-adapter`，其工具权限、检索、Citation 与 SSE 都是真实路径。
- 本机 `.env` 显式开启了一个不可用兼容 Provider 时，UI 显示“模型网关不可用…请重试”，未伪造成功、未泄露 Key。为无密钥 Compose 验收以环境覆盖显式关闭该 opt-in Provider；没有改写或提交用户 `.env`。

## D. 智能辅导 UX

**PASS**

- 本地策略回答改为直接围绕题干与概念区分，不再默认输出“梳理可见证据”“当前已记录练习次数”“继续沿用上一步证据范围”。
- 清理 `csv/json/md:line`、tool/schema label、重复安全模板及 source-item 日志式文本。
- Citation 主展示为《文档名》·章节；chunk ID 留在技术 SSE/运行证据，不作为学习者标题。

## E. Tests

| 项目 | 结果 |
|---|---|
| `frontend: npm run lint` | PASS |
| `frontend: npm test -- --run` | PASS — 12 passed |
| `frontend: npm run build` | PASS |
| `frontend: npm run api:generate` | PASS — generated OpenAPI 已重建 |
| `backend: python -m compileall app` | PASS |
| `backend: python -m pytest -q` | PASS — 75 passed, 1 skipped |
| `docker compose config -q` / `ps` | PASS — backend, worker, frontend, PostgreSQL, Redis, Qdrant healthy/up |
| D1 | PASS — Compose 浏览器：CMB 四选项 → SSE Citation → submit → post-submit review |
| D2 | PASS — Compose 浏览器：artifact → expected evidence → ranked top-k |
| D3 | PASS — Compose Nginx 同源 `/api`、session、SSE、Factory、Evaluation 已逐项真实访问 |
| D4 | PARTIAL — warm first-attempt job PASS；isolated cold cache 未完成 |

注：`npm run api:check` 的生成步骤成功，但当前工作树本就未提交且 `generated.ts` 因本轮 schema 扩展必然相对 HEAD 有差异；其最后的 Git-diff cleanliness 检查不能作为未提交阶段的独立 PASS。

## F. Screenshots

- `docs/v3/evidence/release-gate-d/01-practice-rag-citation-hero.png`
- `docs/v3/evidence/release-gate-d/02-review-rag-followup.png`
- `docs/v3/evidence/release-gate-d/03-question-generation-real-job.png`
- `docs/v3/evidence/release-gate-d/05-evaluation-case-detail.png`
- `docs/v3/evidence/release-gate-d/06-compose-release-smoke.png`

未生成 `04-evaluation-strategy.png`：当前真实 artifact 不含 strategy comparison，生成该截图会暗示不存在的能力。

## G. V3 Core Release Gate

| Gate | 结果 | 证据 |
|---|---|---|
| 中文 Hero 真实 RAG citation | PASS | CMB `cmb_val_000079`、Qdrant、SSE、截图 01 |
| Evaluation case evidence detail | PASS | typed API + 截图 05 |
| Strategy comparison（仅真实 artifact 支持时） | N/A | artifact 不含该维度，UI 未虚构 |
| Compose frontend API / SSE | PASS | Nginx config、同源 health/SSE、截图 06 |
| Factory cold-start reliability | FAIL | warm prewarm/first attempt 已过；隔离 cold path 未实证 |
| Provider optional / no-secret configuration | PASS | local adapter Compose run，Provider opt-in |
| 智能辅导产品语言 | PASS | 实际 Hero / Review transcript |

**V3 Core Release Candidate：FAIL**

唯一 P0 blocker 是隔离空缓存的 Factory cold-start 全链路未完成，不能降低成“已验证”。

## H. Remaining Issues

1. 使用独立 compose project、独立空 embedding-cache volume 与非冲突端口，完成 Worker prewarm → 新 Factory job → 首 attempt 不 stale 的 cold-path 验收；不得影响当前 volume。
2. 在该独立 cold 验收后，补一条 Playwright D4 profile，将 release-gate browser walkthrough 固化为可复跑脚本。
3. 如需启用本机外部 Provider，修复用户本地兼容 endpoint 后再以 opt-in 方式验收；V3 RC 不以它为前提。

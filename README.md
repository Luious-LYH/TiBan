# EndoTutor v1.0

EndoTutor v1.0 是一个面向消化内镜医师培训的刷题、实时 Tutor、知识检索、题目生成和候选模型评测平台。它服务于教学研修与医生复核前辅助，不是自主诊断系统。

## Product flow

```text
Real QBank ──→ Practice ↔ Tutor ──→ Learning / Review
                    │                    │
                    └──── Knowledge RAG ┘

每次提交都会沿着 `grade → Attempt → mastery → FSRS` 写回学习状态；下一
次 session 读取到期复习、薄弱知识点和覆盖情况，并在工作台显示推荐原因。

Allowed documents ──→ Question Factory ──→ Review ──→ Published QBank

Evaluation datasets ──→ BYOK Model Evaluation ──→ per-case + aggregate artifact
```

核心入口：

- `/` 学习总览
- `/banks` 题库目录与 Question Factory
- `/practice` Study / Exam / Review 工作台；桌面端右侧持续 Tutor chat
- `/eval` BYOK Model Evaluation workbench

## Architecture

```text
React + Vite + TypeScript
          │ OpenAPI-generated client / SSE
FastAPI ──┼── PostgreSQL (canonical state)
          ├── Qdrant (retrieval index)
          ├── Redis + Dramatiq (long jobs)
          ├── bounded Tutor AgentRunner / ToolRegistry / ModelGateway
          ├── Hybrid RAG + citations
          ├── Generator → deterministic gate → Judge → Repair
          ├── py-fsrs learning projection
          └── isolated BYOK Evaluation domain + artifacts
```

QBank、Knowledge、Evaluation 和 Factory generation source 是四个隔离数据域。Tutor 只使用通过 License Gate 的知识源；EndoBench 永远只用于 Evaluation，不进入 Tutor RAG、Question Factory 或 learner-facing QBank。Tutor 不写学习状态，submit workflow 确定性执行 `grade → Attempt → mastery → review scheduling`。

## Real data boundary

当前 demo QBank 包含 3,678 道精选题：CMExam 1,500、CMB-Exam 1,778、curated Kvasir-VQA 400。规模验收另在独立 PostgreSQL profile 中导入了 CMExam 68,112 道有效题（68,119 行输入，7 行因 contract 不完整被拒绝）。

本地 VQA 数据通过环境变量配置：

```bash
ENDO_LOCAL_VQA_ROOT=/path/to/local/VQA/data
```

项目不重新分发本地大型数据；来源、用途与隔离边界见 [`THIRD_PARTY_DATA.md`](./THIRD_PARTY_DATA.md)。

## Benchmarks and evidence

- RAG v2：90 条冻结候选（30 development / 60 held-out），比较 sparse / dense / hybrid / hybrid+rerank；held-out Recall@5 分别为 0.7667 / 0.8833 / 0.7167 / 0.9000，Stage 1 Tutor default 为 Dense。详见 [`docs/evals/rag-benchmark-v2.md`](./docs/evals/rag-benchmark-v2.md)。
- Question Judge v2：80 条 portfolio-sized candidate review set；Deterministic Gate 与 Provider Judge 的工程结果及人工审校边界详见 [`docs/evals/question-judge-eval-v2.md`](./docs/evals/question-judge-eval-v2.md)，未将其包装为人工/临床准确率。
- Tutor answer eval v1：50 条冻结场景、六维人工 rubric、保留 failure candidate；provider 质量分数在独立审校前保持 pending，见 [`docs/evals/tutor-answer-eval-v1.md`](./docs/evals/tutor-answer-eval-v1.md)。
- FSRS：真实 `py-fsrs` Again / Hard / Good / Easy 序列，见 [`docs/evals/fsrs-comparison.md`](./docs/evals/fsrs-comparison.md)。
- Model Evaluation：冻结 CMExam text 与 EndoBench VLM packs，真实 provider acceptance 与 no-fallback 结果见 [`docs/evals/model-evaluation-acceptance.md`](./docs/evals/model-evaluation-acceptance.md)。

所有数字只描述当前 artifact 与工程验收，不代表临床有效性。RAG、Judge fixture 的最终人工/临床审校仍需由指定 reviewer 完成。

## Quick start

### Local development

Requires Python 3.12+, Node.js 22+, Docker Desktop and npm.

```bash
cd backend
python -m pip install -r requirements.txt
set PYTHONPATH=.
python -m uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

### Docker core

```bash
docker compose up --build
```

这会启动 frontend、backend、PostgreSQL、Qdrant、Redis 和 Dramatiq worker。默认 compose 凭据仅用于本机开发，不应复用到外部环境。真实 provider 配置使用未跟踪 `.env`，不要提交 key。

## Tests

```bash
# backend
cd backend
set PYTHONPATH=.
python -m pytest -q

# frontend
cd ../frontend
npm run api:check
npm run lint
npm test
npm run build
npx playwright test e2e/core-flow.spec.ts
```

`npm run api:generate` 从 FastAPI OpenAPI 重新生成 `frontend/src/api/generated.ts`；业务 view model 可以手写，但 API contract 不手写。CI fast profile 位于 [`.github/workflows/ci.yml`](./.github/workflows/ci.yml)。

## Safety and limitations

- 所有医学输出都保留：`仅供教学研修或医生复核前辅助，不作为独立诊断依据。`
- Study 模式只有用户明确请求时才走受控的只读答案解释路径；Exam 模式提交前无答案路径。
- 普通 UI 不显示 raw chain-of-thought；只展示可审计的高层摘要、tool receipt、source citation 和结果状态。
- BYOK key 是 request-scoped，不落库、不进日志、trace 或 artifact；候选模型评测禁止 fallback。
- Provider acceptance 是本地工程证据，不是生产可用性或临床能力结论。

## Documentation

- 架构：[`docs/architecture/`](./docs/architecture/)
- Stage 3 final report：[`docs/stages/stage-3-final-release-report.md`](./docs/stages/stage-3-final-release-report.md)
- 最终 evidence matrix：[`docs/portfolio/FINAL_EVIDENCE_MATRIX.md`](./docs/portfolio/FINAL_EVIDENCE_MATRIX.md)
- Demo script：[`docs/portfolio/DEMO_SCRIPT.md`](./docs/portfolio/DEMO_SCRIPT.md)
- Dataset attribution：[`THIRD_PARTY_DATA.md`](./THIRD_PARTY_DATA.md)

## License

代码按仓库现有许可证发布；第三方数据不随仓库重新分发，具体 license 与用途边界以 [`THIRD_PARTY_DATA.md`](./THIRD_PARTY_DATA.md) 和 `knowledge/registry/sources.yaml` 为准。

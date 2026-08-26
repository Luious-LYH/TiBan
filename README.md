# 内镜智训 Agent · 作品集 v2.2

面向消化内镜研修的刷题 Agent 作品集 Demo。它把传统题库的“选题—作答—讲解—错题—复习”作为主流程，并把智能带教、开放题评分、学习状态写入和模型评测证据放在可展示的产品链路上。

第一次接手或答辩前，请从 [`docs/portfolio/00_从这里开始.md`](docs/portfolio/00_从这里开始.md) 阅读。

## 四个用户模块，一条演示主线（v2.2.1 目标）

| 入口 | 用途 | 现场展示重点 |
|---|---|---|
| `/` | 学习总览 | 今日任务、待复习、学习进度、书本式题库卡片 |
| `/banks` | 题库 | 食管/胃/小肠题库、题型/进度、个人题库导入与草稿预览 |
| `/practice?bank_id=...` | 刷题工作台 | 单选/多选/判断/简答、结果复盘、右侧独立 ChatAgent |
| `/eval` | 模型评测 | 冻结评测集、一次性 API、真实调用状态、逐题结果与指标 |

兼容入口：当前过渡版 `/study` 仍可核对题池；`/workbench` 保留开发者技术详情；`/lab` 重定向到 `/eval`。这三个旧入口不应继续作为最终用户信息架构。

**v2.2.1 完成后的根路由进入 `/`**：先看学习进度并选择题库，再进入刷题工作台使用右侧智能带教，最后在 `/eval` 展示模型评测证据。当前 `/study` 只是过渡页。详见 [`08_v2.2_实施记录与演示说明.md`](docs/portfolio/08_v2.2_实施记录与演示说明.md) 和 [`09_v2.2.1_ClaudeCode项目对接文档提示词.md`](docs/portfolio/09_v2.2.1_ClaudeCode项目对接文档提示词.md)。

## 核心能力

- **研修业务**：50+ 道演示题池；人工整理纯文本知识题与公开图像样例并存，支持部位、题型、错题、收藏和复习入口。
- **智能带教**：在作答前支持拆知识点、排除干扰项和分级提示；提交后结合评分结果给讲解和下一步复习建议。
- **多题型评分**：单选、多选、判断走确定性判分；开放题按 rubric 关键词覆盖、复核边界和越界表达惩罚评分。
- **Agent Runtime**：`Plan → Act → [Recovery] → Observe → Verify → Memory`；BM25-equivalent 稀疏检索、类型化工具、单次受控重试、Context Manifest、Usage Ledger 和进程内 Checkpoint/Replay。
- **模型实验**：3 个 VLM 的冻结小样本对比，以及 BF16/INT8/NF4、QLoRA、DPO、结构化 Prompt 消融；DPO 另做 5-seed 复验并对 1 次 NaN 加入 fail-closed 门禁，结果与失败证据均以版本化 Artifact 展示。

## 技术栈

- 前端：React + Vite + TypeScript、Recharts、lucide-react。
- 后端：FastAPI + Pydantic。
- 数据：本地公开教学样例、运行态学习记录、版本化评测 Artifact。

## 快速启动

一键启动网页演示：

```powershell
.\Start-Web-Demo.bat
```

一键启动会自动启动本机后端，并使用已经构建好的 `frontend\dist` 打开网页前端；答辩现场不依赖 `node_modules` 或 `npm run dev`。如需真实智能服务，请先在本机环境变量、`code\.env` 或 `code\backend\.env` 中配置 `LLM_BASE_URL` 与 `LLM_API_KEY`，再双击启动。启动脚本只读取本机配置，不会把授权信息写入源码或提交包。

开发模式：

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8002

cd ../frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8002"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

浏览器打开 `http://127.0.0.1:5174/study`。

## v2.2 主流程接口

- `GET /api/practice/questions`：读取题库题池，支持部位、题型、错题和收藏筛选。
- `GET /api/question-banks`：读取题库目录和进度。
- `GET /api/question-banks/import/templates`：读取 JSONL/CSV/Markdown 导入模板。
- `POST /api/question-banks/import/validate`：校验导入内容并返回预览摘要。
- `POST /api/practice/submit`：提交单选、多选、判断或问答评分题。
- `POST /api/practice/tutor`：作答中智能带教提示、讲解和自由追问。
- `GET /api/portfolio/study`：今日计划、题库、错题本、复习队列与学习摘要。
- `POST /api/portfolio/study/favorites/{case_id}`：更新收藏。
- `GET /api/portfolio/cases`：读取公开教学病例。
- `POST /api/agent/runs/stream`：NDJSON 真实阶段流；传入 `commit_memory=true` 才提交一次学习状态。
- `POST /api/agent/runs/{run_id}/replay`：诊断性重放，不重复写入学习记录。
- `POST /api/agent/retrieve`：可解释稀疏检索。
- `GET /api/evals/latest`：重新生成并读取 Agent 固定回归。
- `GET /api/models/evaluation`：读取模型实验 Artifact。
- `POST /api/demo/reset`：清理运行态演示学习数据。

## 证据边界

- Agent Eval 的 100% 指标来自 **5 个 Golden Cases、19 条固定检索 query、3 类故障注入和 3 条安全探针**的确定性规则回归；它不是模型准确率，也不代表开放域能力。
- 模型实验使用 10 张公开教学图像的 4/3/3 划分，冻结测试集仅 **3 张图像**；仅供作品集实验比较，不代表泛化或临床验证。
- 本项目仅供教学研修或医生复核前辅助，不作为独立诊断依据。

不要提交真实密钥、通知地址、服务器密码、患者身份信息或其他敏感数据。

## 文档

- `docs/portfolio/00_从这里开始.md`
- `docs/portfolio/04_三分钟演示脚本.md`
- `docs/portfolio/简历项目经历-Agent应用版.md`
- `docs/portfolio/简历项目经历-大模型算法版.md`

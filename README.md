# 内镜智训 Agent · 作品集 v2.0

面向消化内镜研修的多模态 Agent 作品集 Demo。主演示是一条可观察的
`Plan → Act → Observe → Verify → Memory` 带教链路；模型页展示真实 GPU
推理与 QLoRA 训练链路证据，而非硬编码排行榜。

第一次阅读请从 [`docs/portfolio/00_从这里开始.md`](docs/portfolio/00_从这里开始.md) 开始。

产品主链收束为：

`模型评估 -> 医生研修 -> 证据复盘 -> 报告辅助 -> 能力画像`

## 核心页面

- 首页：展示平台价值、智能助手、今日研修入口和能力走势。
- 模型：查看模型池、多维评估结果、智能助手选择依据和自定义模型体验评估。
- 研修：完成内镜图像题作答、提交评分、证据复盘、画像更新和下一题推荐。
- 报告：上传或选择图片，输入简短所见，生成结构化报告草稿，并通过智能修改优化表达。
- 画像：展示医生能力雷达、成长曲线、薄弱项和最近研修记录。

## 技术栈

- 前端：React + Vite + TypeScript、Recharts、lucide-react。
- 后端：FastAPI + Pydantic。
- 数据：本地 JSON 教学样例、画像状态、报告知识库、平台模型评估结果。
- Agent：受控状态机、类型化 Tool Receipt、事实级 Rubric、可解释 Memory Delta。
- 模型实验：Qwen2.5-VL-3B-Instruct、BF16 推理基准、NF4 QLoRA sanity run。

## 快速启动

一键启动网页演示：

```powershell
.\Start-Web-Demo.bat
```

一键启动会自动启动本机后端，并使用已经构建好的 `frontend\dist` 打开网页前端；答辩现场不依赖 `node_modules` 或 `npm run dev`。如需真实智能服务，请先在本机环境变量、`code\.env` 或 `code\backend\.env` 中配置 `LLM_BASE_URL` 与 `LLM_API_KEY`，再双击启动。启动脚本只读取本机配置，不会把授权信息写入源码或提交包。

后端：

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8002
```

前端：

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL="http://127.0.0.1:8002"
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

答辩包默认不需要运行上面的开发命令；直接双击 `Start-Web-Demo.bat` 即可。

浏览器打开：

```text
http://127.0.0.1:5174
```

## 作品集接口

主流程使用薄 facade：

- `GET /api/session`
- `GET /api/models/evaluation`
- `POST /api/models/custom-evaluate`
- `GET /api/practice/state`
- `GET /api/practice/questions`
- `GET /api/practice/questions/{id}`
- `POST /api/practice/submit`
- `POST /api/practice/session`
- `POST /api/practice/tutor`
- `GET /api/portfolio/cases`
- `POST /api/agent/runs`
- `POST /api/evals/run`
- `GET /api/evals/latest`
- `POST /api/demo/reset`
- `POST /api/report/image`
- `POST /api/report/generate`
- `POST /api/report/revise`

旧接口仍保留为内部兼容层，但不作为 v3 主流程入口。

## 演示路径

1. 首页点击“开始演示病例”。
2. 围绕公开教学图像写一条观察记录并提交。
3. 展示真实 run ID、五阶段 Trace、工具收据、事实 F1、Memory Delta 与下一题推荐。
4. 进入模型页，展示可复现的真实 GPU 小样本基线及其失败模式。
5. 按需补充报告辅助与研修画像，不让它们抢占主演示。

## 安全边界

本项目仅用于教学研修或医生复核前辅助，不作为独立诊断依据。

不要提交真实密钥、通知地址、服务器密码、患者身份信息或其他敏感数据。

## 文档

- `docs/portfolio/00_从这里开始.md`
- `docs/portfolio/项目简历介绍建议-Agent应用.md`
- `docs/portfolio/项目简历介绍建议-大模型算法.md`
- `docs/V3_SCOPE_LOCK.md`
- `docs/V3_IMPLEMENTATION_PLAN.md`
- `docs/V3_PRESENTATION_GUIDE.md`
- `docs/V3_SMOKE_TEST.md`
- `docs/DESKTOP_APP.md`
- `docs/API_SPEC.md`

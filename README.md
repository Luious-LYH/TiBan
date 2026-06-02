# 内镜智训Agent

面向消化道内镜医师培训的智能辅导平台。当前版本实现可运行、可演示、可答辩的 Web 原型：题库训练、右侧 Agent 辅导、答案讲解、原子事实错因反馈、错误前提训练、诊断报告草稿、图片上传、公开样例知识库、科普卡片、Skills 中心、Memory、模型准入探测和审计日志。

> 本项目仅用于教学训练和医生审核前辅助，不替代临床诊断。真实评测流水线暂未开发；v2.0 支持 OpenAI-compatible Provider 连通性/教学推理探测，并在 UI 中明确标出 `provider`、`rule`、`fallback` 模式。

## 技术栈

- Frontend: React + Vite + TypeScript, lucide-react, Recharts
- Backend: FastAPI + Pydantic
- Data: JSON mock 数据
- Agent: 规则/模板编排 + OpenAI-compatible Provider 可选调用
- Safety: 统一 safety_notice、doctor_review_required、敏感标记脱敏、审计日志

## 快速启动

后端：

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：`http://localhost:5173`

## 可选真实 Provider 配置

复制 `.env.example` 为 `.env`，只在本机填写真实配置：

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=25
```

不要把 `.env`、真实 key、服务器密码或患者身份信息提交到 git。模型准入页也支持临时输入 key 进行一次请求级探测，但不会保存或写入审计日志。

## 演示路径

1. 首页总览：查看今日训练、能力画像、推荐训练和安全提示。
2. 训练中心：右侧 Agent 默认只辅导当前题，不提前泄露参考答案；提交后解锁公开标注/AI 对照。
3. 错因分析：查看 atomic facts、错因标签和下一题推荐。
4. 错误前提：展示证据不足/不适用的训练逻辑。
5. 报告中心：选择真实公开样例或上传图片，生成结构化草稿，并查看医生输入、公开样例、模板 KB、Provider 输出来源追踪。
6. 科普卡片：生成患者友好解释和免责声明。
7. 模型准入：使用公开样例做真实/规则准入探测，查看 Provider 调用证据、延迟和风险项。
8. Skills 中心：运行 question_hint、atomic_feedback、false_premise_guard 等 skill。
9. 审计日志：查看关键事件记录。

## 功能真实性矩阵

| 模块 | v2.0 模式 | 数据来源 | 说明 |
|---|---|---|---|
| 题库训练 | backend rule | `questions.json` + `real_sample_knowledge.json` | 公开样例优先展示，支持错题/收藏/筛选；考试模式有倒计时 |
| 右侧 Agent | provider / rule / fallback | 当前题、atomic facts、公开图片 | Provider 未配置时使用规则辅导；提交前不展示参考答案；追问会回灌训练事件但不保存原文 |
| 报告中心 | provider / rule / fallback | 医生输入、公开样例标注、模板 KB、上传图片 | `source_trace` 和 `evidence_ledger` 显示每条来源 |
| 模型准入 | provider probe / rule draft | 公开样例 + 可选 Provider | 真实调用成功才标记 `provider_called=true` |
| 科普卡片 | rule | 医生审核前文本 + 卡片模板 KB | 带审核状态和免责声明 |
| Memory | rule persistence | `learner_profile.json` | 提交题目、报告 judge 和 Agent 追问都会更新训练记录、能力分与弱项标签 |
| 审计日志 | backend persistence | `audit_logs.json` | 记录题目、辅导、报告、上传、准入等事件 |

## 外部参考

- [HyperKvasir](https://www.nature.com/articles/s41597-020-00622-y)：GI 内镜图像/视频数据底座，公开论文说明包含 110,079 张图像和 374 个视频。
- [Kvasir-VQA-x1](https://github.com/simula/Kvasir-VQA-x1)：GI 内镜 MedVQA 数据集与复杂度分层思路。
- [MediaEval Medico 2025](https://github.com/simula/MediaEval-Medico-2025)：GI VQA 与多模态解释评测方向。

## 安全边界

- 不处理真实患者身份信息。
- 不写入真实 API key、服务器密码、Webhook 或 token。
- 不输出最终临床诊断或治疗方案。
- 报告草稿和科普卡片均要求医生审核。
- 模型准入探测只验证教学场景连通性和边界，不代表真实临床评测。

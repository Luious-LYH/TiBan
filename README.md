# 内镜智训Agent

面向消化道内镜医师培训的智能辅导平台。当前 v2.0 实现可运行、可演示、可答辩的 Web 原型：训练驾驶舱、题库/错题/收藏/考试、右侧 Agent 辅导、医生 vs 后端挑战基准比拼、交互式错误前提训练、诊断报告中心、报告修改训练、医师画像、科普卡片、受控 Skills、Memory、模型准入探测和审计日志。

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

如果本机 `8000` 被旧版后端占用，可把最新后端改到 `8001`：

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

前端未显式设置 `VITE_API_BASE_URL` 时，会按 `http://127.0.0.1:8000`、`http://127.0.0.1:8001` 自动探测后端，并优先选择 `/api/health` 暴露 v2.0 capabilities（Provider 联调状态检查、Provider 视觉自检、Provider 自检收据、模型准入收据、知识库来源链、沙盒自检、挑战基准、挑战审计收据、科普卡片收据和 Skill 运行收据）的服务；如果需要固定端口，可在启动前设置 `VITE_API_BASE_URL`。

## 可选真实 Provider 配置

复制 `.env.example` 为 `.env`，只在本机填写真实配置：

```bash
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=25
```

不要把 `.env`、真实 key、服务器密码或患者身份信息提交到 git。模型准入页会先显示 Provider 联调状态检查，说明 `.env` 缺失项、公开样例数量、最近自检/准入审计和隐私边界，但不会返回 key/base 明文。模型准入页和报告中心都支持请求级临时配置；临时 key 不保存，只有填写临时 base 或 key 时，页面模型名才会随本次请求覆盖后端 `.env` 默认值。

## v2.0 演示路径

1. 首页总览：先看“平台真实性与演示路径”“可核验证据收据”和“真实数据来源链”，确认后端、公开样例、画像、报告/科普知识库、Provider、自检/准入、挑战基准审计和审计日志状态；来源链会列出 `real_sample_knowledge.json`、`report_knowledge_base.json`、`card_template_knowledge.json` 的条数、样例 ID 和消费页面；“沙盒自检”会真实跑通训练提交、Agent 辅导、挑战基准、报告草稿、报告修改评分和审计链路后自动恢复数据，“写入演示画像”才保留留痕。
2. 训练中心：右侧 Agent 默认只辅导当前题，不提前泄露参考答案；考试模式有全局 session 倒计时、累计战报、交卷复盘入口；比拼模式提交前锁住证据页，提交后调用后端挑战基准，并在比分板展示最近 `challenge_benchmark` 后端审计收据；Provider 可用时用 Provider 作答，不通时明确回退公开标注 fallback。
3. 错因分析：查看 atomic facts、错因标签和下一题推荐。
4. 错误前提训练：先让林知远医师独立判断题干是否成立，提交后才解锁证据不足事实、得分和复盘建议。
5. 报告中心：选择真实公开样例或上传图片，在流程工作台中完成“图像/所见 -> 草稿 -> 证据台账 -> 医师复核”；可用后端 `.env` 或页面临时 Provider 做一次真实推理，公开 VQA 标注默认收进来源台账，不伪装成医生报告结论。
6. 报告修改训练：AI judge 评分后回灌林知远医师画像，并返回下一步专项训练入口；评分后的建议改写或医生修改稿摘要可带入科普卡片工作室生成待审核草稿；可选 Provider 评阅会显示 `provider/rule/fallback`、延迟和来源台账。
7. 模型准入：先看 Provider 联调状态检查，确认当前是 `provider`、`rule` 还是 `fallback`，以及缺少哪些 `.env` 配置和最近审计。再做 Provider 文本轻量自检或视觉通道自检确认通道可用；视觉自检只证明后端已将公开样例图片附加到多模态请求，不发送参考标注、不更新准入状态。页面会展示后端 Provider 自检收据，包括 `provider_self_test` 审计 ID、输入来源、Provider 调用来源和隐私边界。随后使用最多 3 个公开样例做 blind probe 准入检查；Provider 只接收图片和问题，不接收参考标注，后端返回后再做公开标注对齐，并展示 `model_admission` 审计 ID 与模型准入收据。模型卡片默认只是能力看板；只有最近准入摘要满足真实 Provider 调用、公开标注对齐和安全阈值，且目标不是 mock 模型时，才允许写入“待人工复核候选”。
8. 科普卡片、Skills、审计日志：展示患者沟通卡片生成收据、医生审核闸门、后端 Skill 运行收据、`skill_run` 审计 ID、输入/执行来源和关键事件记录。

详细操作手册见 [docs/V2_USER_GUIDE.md](docs/V2_USER_GUIDE.md)。

## 功能真实性矩阵

| 模块 | v2.0 模式 | 数据来源 | 说明 |
|---|---|---|---|
| 题库训练 | backend rule | `questions.json` + `real_sample_knowledge.json` | 公开样例优先展示，支持错题/收藏/筛选；考试模式有全局倒计时、累计正确率、平均分，交卷后通过 `/api/learner/exam-session` 写入画像和审计 |
| 首页闭环自检 | backend sandbox / persistence | 公开样例 + `learner_profile.json` + `audit_logs.json` | `persist=false` 真实写入后自动恢复，`persist=true` 才保留演示画像和审计；首页同时展示 `knowledge_source_chain`，说明本地知识库被哪些功能消费 |
| 右侧 Agent | provider / rule / fallback | 当前题、atomic facts、公开图片 | Provider 未配置时使用规则辅导；提交前不展示参考答案；挑战模式提交后才调用后端挑战基准，比分板只在真实后端审计存在时显示最近 `challenge_benchmark` 收据，基准不重复回灌画像；追问会回灌训练事件但不保存原文 |
| 错误前提训练 | backend rule | false-premise 题库 + atomic facts | 先作答后解锁证据不足事实、得分和复盘建议 |
| 报告中心 | provider / rule / fallback | 医生输入、公开样例来源台账、模板 KB、上传图片 | 流程工作台展示数据/Provider/模板状态；报告生成显示 `source_trace`、Provider 状态和 `evidence_ledger`；报告评分返回画像回灌与 `recommended_drills`，并可把建议改写或医生修改稿摘要带入科普卡片待审流程 |
| Skills 中心 | backend rule / fallback | `skills.json` + 当前题/报告/卡片服务 | 页面展示运行摘要、`skill_run_receipt`、审计 ID、输入来源、执行来源和工作区跳转；前端 fallback 只显示本地预览且不伪造审计 ID；完整 JSON 仅放在开发细节折叠项 |
| 模型准入 | provider status check / text/visual self-test / blind provider probe / rule draft | 公开样例 + 可选 Provider | 联调状态检查只读展示 Provider 配置布尔值、缺失项、公开样例数、最近自检/准入审计和隐私边界，不返回 key/base 明文；文本自检只验证文字通道；视觉自检会把一张公开内镜图以 `image_url` data URL 附加到请求，但不发送参考标注、不更新准入状态；自检返回 `self_test_receipt` 和 `provider_self_test` 审计 ID；逐样例准入不泄露参考标注，返回 provider answer、对齐状态、evidence、`admission_receipt` 和 `model_admission` 审计 ID；最近准入摘要不保存 key/base；模型卡片未过真实 Provider/公开标注对齐闸门时只作看板，mock 模型不能写入待复核候选 |
| 科普卡片 | rule | 医生审核前文本 + 卡片模板 KB + 公开样例图像池 | 图片选择优先读取 `/api/knowledge/real-samples` 映射出的公开样例，后端不可用时才回退本地资产；生成草稿后显示 `source_trace`、模板知识库和 `patient_card` 审计收据；可从报告修改训练带入建议改写或医生修改稿摘要；默认锁定打印/分享；医生完成审核清单后通过同一 `card_id` 解锁，并写入 `patient_card_approve` 审计日志 |
| Memory | rule persistence | `learner_profile.json` | 提交题目、考试 Session、报告 judge 和 Agent 追问都会更新训练记录、能力分与弱项标签；考试汇总不重复增加单题题量 |
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

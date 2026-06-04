# V2.0 使用说明与演示手册

本文档面向答辩演示、开发验收和后续继续迭代。平台定位是“消化道内镜医师训练系统”，不是临床诊断系统；所有报告、科普卡片和模型输出都必须保持医生审核前辅助边界。

## 1. 启动平台

后端：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

前端：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

浏览器打开：

```text
http://127.0.0.1:5173
```

建议前端使用 `--strictPort` 固定 `5173`。如果本机已有旧 Vite 进程占用 `5173`，普通 `npm run dev` 可能自动漂到 `5174`，而浏览器仍打开旧服务，表现为新增路由如 `/delivery` 进入空白或 NotFound；此时先停止旧前端进程，再按上面的命令重启。

健康检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/platform/readiness
```

如果 `8000` 被旧版后端或其他服务占用，把最新后端启动到 `8001`：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m uvicorn app.main:app --reload --port 8001
```

前端未显式设置 `VITE_API_BASE_URL` 时，会自动按 `http://127.0.0.1:8000`、`http://127.0.0.1:8001` 探测后端，并优先选择 `/api/health` 暴露 v2.0 capabilities 的服务。当前能力探测会确认 Provider 联调状态检查、Provider 证据阶梯、Provider Base URL 预检、Provider 请求预演、Provider 视觉自检、Provider 自检收据、报告图像上传收据、模型准入收据、知识库来源链、沙盒自检、沙盒恢复校验、考试/卡片闭环收据、挑战基准、挑战审计收据、科普卡片收据、科普卡片审核、Skill 运行收据和交付证据报告能力；如需固定后端端口，可在前端启动前设置 `VITE_API_BASE_URL=http://127.0.0.1:8001`。

版本与提交证据：

- 仓库初始化提交：`9dfd6de 初始化`。
- v1.1 医师培训闭环迭代提交：`c2833c4 v1.1 医师培训闭环迭代`。
- v2.0 交付证据页面关键提交：`07d047b v2.0 增加交付证据前端页面`；后续文档收口提交用于补齐启动、演示和验证口径。

交付证据入口：

```text
http://127.0.0.1:5173/delivery
```

`/delivery` 页面调用后端 `GET /api/platform/delivery-report`，展示当前医师训练对象、平台总览、核心工作流 proof、知识库来源链、审计事件分布、Provider 配置/自检/准入调用三层边界、验证命令和 `report_integrity`。页面显示 `backend live` 和“只读且无密钥”时，才适合作为答辩交付证据；如果后端不可用，页面只会显示 fallback 预览，不应当讲成真实后端证据。页面会对后端返回的自由文本做二次脱敏，避免误展示 API key、token、Provider Base URL 或完整模型回复。注意 `configured` 只代表后端有调用配置，`real_inference_verified=true` 才代表已有成功 Provider 自检或样例级准入调用证据。

## 2. 可选真实 Provider

如果没有配置 Provider，平台仍可用规则、模板和公开样例完成训练演示，并会在 UI 中显示 `rule` 或 `fallback`。如需真实 OpenAI-compatible 调用，先复制 `backend/.env.example` 为 `backend/.env`，只在本机填写：

```powershell
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=25
```

保存后重启 FastAPI 后端，再运行 Provider 体检脚本：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\provider_doctor.py
```

该脚本不会打印 API key 或完整 Provider host；它只检查项目根 `.env` / `backend/.env` 是否存在、是否被 git 忽略、后端 Provider capabilities、`/api/provider/diagnostics` 和后端 `.env` Base URL 预检。预检通过且后端 diagnostics 显示 Provider 已配置后，可以用后端 `.env` 做一次文本/视觉通道自检：

```powershell
python scripts\provider_doctor.py --self-test --include-image
```

`LLM_BASE_URL` 或页面临时 API Base 可以填写 Provider 根地址、`/v1` 地址，或完整 `/chat/completions` endpoint；后端会规范化为 OpenAI-compatible chat completions 请求，未写协议的外部域名按 `https://` 处理，本地 `localhost` / `127.0.0.1` 地址按 `http://` 处理；根地址会优先尝试 `/v1/chat/completions`，404/405 时再尝试 `/chat/completions`。非本机 `http`、metadata、内网/保留地址、loopback 低端口和非法端口会被拒绝为 `unsafe_base_url`，避免密钥外发；真实 Provider 调用不会自动跟随 30x 重定向，并会使用重新校验后的连接地址。不要把 `.env`、真实 key、服务器密码或患者身份信息提交到 git。模型准入页会先显示 Provider 联调状态检查、真实推理证据阶梯和 Base URL 预检：证据阶梯把 `.env`、preflight、dry-run、自检、公开样例准入和候选启用闸门分开，避免把配置齐全误讲成已真实推理；预检不需要 key、不发送模型请求、不写审计，只展示规范化预览、将尝试的 endpoint path、安全拦截原因和下一步动作。一次性 key 可用于文本/视觉自检或样例级准入检查，不会保存到数据文件；只有填写临时 base 或 key 时，页面模型名才会随本次请求覆盖后端 `.env` 默认值。

## 3. 推荐演示顺序

1. 训练驾驶舱 `/`
   先看左侧栏全局 “Live evidence” 摘要，它会在任意页面从 `/api/platform/readiness` 拉取平台就绪度、Provider/rule 模式、公开样例数、审计数和最近考试复盘，避免评委以为切页后只是静态展示。随后看首页“平台真实性与演示路径”“可核验证据收据”“真实样例覆盖总账”和“真实数据来源链”，说明后端、公开样例、考试 Session 复盘、报告/科普知识库、Provider、自检/准入、训练挑战基准审计、Memory 和 Audit 的状态。覆盖总账来自 `/api/platform/readiness.real_sample_coverage`，会列出 `real_sample_knowledge.json` 记录数、映射题目数、图片资产校验、数据集分布、用途分布和本地 `E:\2.Projects\ARIS\VQA\data` 来源提示；来源链来自 `/api/platform/readiness.knowledge_source_chain`，会列出本地 JSON 知识库文件名、记录数、样例 ID 和消费页面。首页的“最近考试 Session”卡片会直接给出 session id、题量、正确率、错题数和复盘入口，适合回答“训练是否真的沉淀到画像”。首页的“沙盒自检”会真实跑通训练提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、考试 Session、科普卡片草稿、同卡片医生审核、画像回灌和审计链路并自动恢复数据；需要在审计页留下演示证据时，再点击“写入演示画像”。

2. 交付证据 `/delivery`
   这是答辩时回答“如何证明平台不是静态页面”的入口。页面应显示 `backend live`、`report_integrity=clean` 对应的“只读且无密钥”、平台就绪度、林知远医师上下文、核心闭环证据、知识库来源链、审计事件分布、Provider 三层证据和验证命令。它和 `scripts/export_delivery_report.py` 读取同一个后端只读报告，不触发训练写入、不调用 Provider、不返回 API key 或 Provider Base 明文。讲解时要明确：Provider configured 不是成功推理，只有 `self_test_verified` 或 `admission_provider_called` 才能支持 `real_inference_verified=true`。

3. 题库刷题 `/training`
   先看顶部“Current physician mission”任务队列：它读取林知远医师后端画像，显示今日训练进度、薄弱标签、最近考试、画像写入状态和下一组训练入口。提交答案、收藏题目、Agent 追问或考试交卷后，页面会刷新后端画像，让训练页从“题目列表”变成一个会持续追踪医生能力成长的入口。再展示公开样例图像、病例摘要、题目和右侧 Agent。练习模式可以点“提示一下”，Agent 只追问证据，不直接给答案。提交后显示得分、错因标签、解释和对照。

4. 考试模式 `/training?mode=exam`
   进入后启动一场全局 12 分钟 session。倒计时不会因单题提交或切换题目重置；页面会累计已答题、正确率、平均分和最近错题，并提供“交卷复盘”“重开本场”和错因复盘入口。考试中隐藏提示和自由追问，交卷后会调用 `/api/learner/exam-session` 写入整场考试摘要、画像记录和审计日志；摘要会进入 `learner_profile.exam_sessions`，复盘入口携带 `/feedback?session=...`，用于恢复本场错题队列。首页 readiness 和画像记录页会同步出现最近一场考试的复盘收据。

5. 错因复盘 `/feedback`
   从训练中心提交后进入时显示本轮提交；直接打开或刷新时会从后端错题本恢复最近复盘题，并标注为“复盘快照”，不会重复写入医师画像。若 URL 携带 `session`，页面会从 `training-state.exam_sessions` 找到对应考试，显示“Exam session replay”证据卡、题量、正确率、错题数、画像回灌状态和本场错题队列。

6. 医生 vs 后端挑战基准 `/training?view=challenge`
   先独立作答。提交前右侧证据页和基准答案不会泄露；医师提交后，前端才调用 `/api/tutor/challenge-benchmark` 同步挑战基准。Provider 可用时由 Provider 独立选择答案；不可用或调用失败时明确显示“公开标注 fallback”。该基准只写 `challenge_benchmark` 审计，不重复更新林知远医师画像。比分板会展示最近一条真实后端 `challenge_benchmark` 审计收据；后端不可用或只有前端 fallback 时，不会伪造“已连接”。

7. 错误前提训练 `/false-premise`
   让医生判断题干假设是否成立。提交前只显示原则提示；提交后解锁证据不足事实、原子证据、得分和下一步复盘建议。这个页面同时服务医师训练和模型准入边界展示。

8. 报告中心 `/report`
   先看流程工作台：图像/所见、生成草稿、复核台账三步会同步显示状态；数据来源、Provider 和模板状态压缩在状态带中。可选择使用后端 `.env` 或本次请求临时 Provider；临时 key 只随报告生成/评分请求发送，不保存。请求级 Provider 区域复用 Base URL 预检：不需要 key、不发送模型请求、不写审计，预检未通过时会阻断报告生成和 AI judge，避免把 key 发往不安全地址。选择公开图像或上传图片后，公开 VQA 标注默认收进“图像来源台账”，不直接当成报告结论。点击生成后查看结构化所见、草稿印象、复核点、幻觉审查、Provider 状态和证据台账。

9. 报告修改训练 `/report?tab=judge`
   提交一个越界报告和医师修改稿，查看 rubric 分数、Provider/rule/fallback 来源、问题、建议改写和画像回灌状态。评分响应会返回 `recommended_drills`，页面可直接跳回训练中心做报告安全、证据不足或错误前提专项；训练中心会显示“报告评分专项训练”任务卡，按推荐的合法题类筛选题库，提交训练题后才继续回灌画像。也可以把建议改写或医生修改稿摘要带入科普卡片工作室生成待审核草稿。真实 Provider 评阅只作为训练反馈，不替代医生审核。

10. 医师画像 `/profile`
   展示林知远医师的训练记录、能力雷达、薄弱标签、错题/收藏和成长徽章。当前是单 demo learner，本地 JSON 持久化，后续可扩展多医师数据库。

11. 科普卡片 `/card`
   选择模板和真实样例图，先生成医生审核前患者沟通卡片草稿。图像池会优先读取 `/api/knowledge/real-samples`，显示样例 ID 和公开数据集；后端不可用时才回退本地公开样例资产。本机上传图仍只做当前浏览器预览，不写入后端卡片记录。若从报告修改训练进入，页面会接收建议改写或医生修改稿摘要并显示来源提示；摘要通过前端路由状态传递，不写进地址栏。生成后页面会显示“后端草稿收据”，包括生成模式、模板知识库、`patient_card` 审计 ID 和来源台账；这只证明草稿生成和审计写入，不代表医生审核通过。页面右侧有审核闸门：医生需要逐项确认摘要来源、未新增治疗/疗效承诺、免责声明保留，并对当前 `card_id` 提交审核确认；审核通过后后端会返回同一张卡片的 `share_status=reviewed_ready_to_share`，打印和分享按钮才会解锁，审计日志会记录 `patient_card_approve`。

12. Skills `/skills`
   选择当前题运行受控技能。页面展示运行摘要、审核要求、闭环入口和后端 `skill_run_receipt`：包括 `skill_run` 审计 ID、风险等级、输入来源、执行来源、收据时间和下一步动作。完整 JSON 放在开发细节折叠项，避免把平台展示成调试台；若后端不可用，只显示本地技能预览且审计 ID 为空。

13. 模型准入 `/models`
    先看“Provider 联调状态检查”和“真实推理证据阶梯”：它们来自 `/api/provider/diagnostics`，只读展示 Provider 模式、`.env` 缺失项、公开样例数、最近 `provider_self_test` / `model_admission` 审计摘要、最近准入状态、六步 `evidence_ladder` 和下一步动作。证据阶梯依次为 Provider 配置、Base 安全预检、请求预演收据、文本/视觉自检、公开样例准入、候选启用闸门；只有自检或准入真实调用成功，才算真实推理证据。再看“Base URL preflight”和“Provider 请求预演包”：预检来自 `/api/provider/preflight`，只做 URL 规范化、安全策略和 chat completions path 推导，不需要 key、不发送模型请求、不写审计；预演来自 `/api/provider/request-preview`，后端按文本自检、视觉自检或样例准入模式生成 dry-run 收据，只接收 `api_key_present` 布尔值，不接收真实 key 字符串，展示 endpoint path、请求体字段、公开样例绑定、图片附加计划和隐私边界，并保持 `request_sent=false`、`key_persisted=false`、`audit_logged=false`、`state_updated=false`。预演通过后再做 Provider 文本轻量自检或视觉通道自检：文本自检只发送一条安全短提示词；视觉自检会附加一张公开内镜图片和问题，但不读取/发送参考标注，不保存 key/base/完整回复，也不更新模型准入状态。随后用最多 3 个公开样例和可选 Provider 做样例级准入检查；Provider 收到的是图片和问题，不包含参考标注，后端只在返回后做公开标注粗粒度对齐。只有真实调用成功才显示 `provider_called=true`；只有调用成功且至少一条盲测回答与公开标注部分对齐，最近准入状态才会标为可进入人工复核。模型卡片默认只是能力看板；`/models/select` 未过真实 Provider/公开标注对齐/安全阈值闸门时返回 400。

14. 审计日志 `/audit`
    查看审计驾驶舱：事件总量、高风险、医生复核负载、最近写入时间、分类筛选和完整日志表。日志只保存事件摘要、风险等级和审核状态。

## 4. 当前真实能力边界

| 能力 | 已实现 | 边界 |
|---|---|---|
| 公开样例题库 | 从 `real_sample_knowledge.json` 和公开图像资产加载 | 只抽取部分本地真实数据用于演示，不等同完整数据集训练 |
| 首页来源链 | `/api/platform/readiness` 返回 `real_sample_coverage` 和 `knowledge_source_chain`，展示真实样例库记录数、映射题量、图片资产校验、数据集/用途分布，以及报告知识库、卡片模板库被哪些页面消费 | 证明本地知识库被平台引用，不代表已经完成批量临床评测 |
| 医师训练闭环 | 答题、收藏、错题、考试 session、比拼、错误前提训练 | 当前只有 `demo_learner` 单医师画像；训练中心顶部任务队列读取 `learner_profile.json`，显示今日进度、薄弱项、最近考试、画像写入状态和下一组训练入口；单题提交单独更新题量和能力分，收藏/Agent 追问/考试交卷后刷新画像，考试 session 交卷会持久化整场题量、正确率、平均分和错题摘要，不重复增加单题题量 |
| 首页闭环自检 | 沙盒自检和正式写入两种模式 | `persist=false` 真实写入后自动恢复，验证训练提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、考试 Session、科普卡片草稿、同卡片医生审核、画像回灌和 9 张收据，适合反复演示前 smoke；`persist=true` 才保留演示画像、审计和卡片运行记录 |
| Agent 辅导 | 后端 tutor 编排，可接 Provider，也有规则兜底 | 不保存自由追问原文，只记录训练标签和模式 |
| 报告生成 | 图片上传、公开样例、模板 KB、来源追踪、幻觉审查、请求级 Provider，并复用 Base URL 预检 | 输出是医生审核前训练草稿，不是最终诊断；临时 key 不保存；预检不发送模型请求、不写审计，未通过时阻断报告生成和 AI judge |
| 报告 judge | 规则 rubric + 可选 Provider 评阅，并回灌画像与推荐专项训练 | Provider 反馈仅作训练建议；后续可接真实专家评分 |
| 报告到卡片闭环 | 报告 judge 建议改写或医生修改稿摘要可带入科普卡片输入区，并显示后端生成收据 | 只生成医生审核前卡片草稿；不会绕过审核清单、分享锁或打印锁 |
| 卡片公开样例配图 | 科普卡片页优先从 `/api/knowledge/real-samples` 读取公开样例图像池，并显示样例 ID/数据集 | 图像仅作医生审核前患者沟通卡片配图，不代表自动诊断；本机上传图不写入后端 |
| 模型准入 | Provider 联调状态检查 + 真实推理证据阶梯 + Base URL 预检 + 请求预演包 + OpenAI-compatible Provider 文本/视觉自检 + 公开样例 blind probe 准入检查，并展示 `self_test_receipt` / `admission_receipt` | 状态检查只证明配置状态、公开样例数和审计摘要，不返回 key/base 明文；证据阶梯将配置、preflight、dry-run、自检、准入和候选闸门分开展示，preflight/dry-run 不等于真实调用；Base URL 预检和请求预演都不发送模型请求、不写审计，预演只接收 key 是否存在的布尔值并展示 endpoint path、请求字段、样例绑定和隐私边界；真实调用层不跟随 30x 重定向，并限制 metadata、内网/保留地址和本机低端口；文本自检只验证文字通道；视觉自检只证明公开图片已附加到 Provider 请求并写摘要审计，不发送参考标注；样例准入不向 Provider 泄露参考标注；模型卡片未过后端准入闸门时只作看板，mock 模型不能写入待人工复核候选 |
| 交付证据页 | `/delivery` 调用 `GET /api/platform/delivery-report` 展示只读运行证据；导出脚本可生成 Markdown 交付包 | 页面和脚本不触发训练、demo-check 或 Provider 请求；Provider 状态拆成 `configured`、`self_test_verified`、`admission_provider_called` 和 `real_inference_verified`，配置齐全不等于真实推理已验证；`report_integrity` 必须为 `writes_state=false` 且不返回 key/base；UI smoke 会硬性检查 `data-delivery-source=backend`、`data-delivery-integrity=clean` 和 Provider 证据 data attrs；后端文本在前端会再次脱敏 |
| Skills | 训练、反馈、报告、卡片、安全、审计技能可运行；运行后展示 `skill_run_receipt`、输入来源、执行来源、审计 ID 和下一步动作 | 面向受控编排，不允许自由越权调用；前端 fallback 不伪造后端审计 ID |

## 5. 常见问题

### 页面显示 rule/fallback 是不是失败？

不是。`rule` 表示后端规则、模板和知识库在工作；`fallback` 表示 Provider 或后端不可用时的降级。v2.0 的目标之一就是显式标注来源，不把规则草案伪装成真实模型推理。

### 为什么报告页会有 VQA 标注？

公开 VQA 标注用于证明图像样例来源和训练任务，不等同于医生报告结论。v2.0 已将它默认收进“图像来源台账”，报告正文仍以医生所见文本、模板知识库和可选 Provider 观察为主。

### 上传图片保存在哪里？

报告页上传图片保存到 `backend/runtime/uploads`，该目录不提交 git。上传接口会校验 PNG/JPEG/WebP data URL、2.5MB 大小限制和图片头尺寸，成功后返回图像证据收据：`image_name`、MIME、bytes、宽高、SHA256 前缀、`image_upload` 审计 ID 和 Provider 输入边界。报告生成会把同一上传的 `audit_log_id`、hash 和尺寸写回 `evidence_ledger` 与 `source_trace`；上传失败时只保留前端预览，不把本地文件名当作视觉证据发送。文件名会回显在当前页面，请不要包含患者身份信息。报告修改训练带入科普卡片的摘要通过前端路由状态传递，URL 不展示报告文本；科普卡片页上传只做本机预览，不自动写入后端；卡片分享/打印需要医生审核闸门通过。

### 如何恢复干净演示状态？

核心状态文件在 `backend/app/data`：

- `learner_profile.json`
- `audit_logs.json`
- `models.json`
- `model_admission_state.json`

科普卡片草稿和审核运行记录在：

- `backend/runtime/patient_cards.json`

正式演示前建议先备份这些文件。不要使用 `git reset --hard` 清理状态，避免误删用户改动。

## 6. 验证命令

答辩前推荐先跑总控验证。它要求后端和前端服务已经启动，会一次串联后端编译、沙盒闭环自检、Provider Base URL 安全预检、交付证据包导出、前端关键路由 smoke、lint/build、`git diff --check`、真实公开样例图片资产一致性检查、`sk-*` 形态密钥扫描和运行状态文件内容指纹保护：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\verify_all.py
```

若只是快速确认页面没有空白、核心闭环没断，可先跳过构建：

```powershell
python scripts\verify_all.py --skip-build
```

总控验证默认 Provider 预检使用 `http://127.0.0.1:9999/v1` 这类本机假地址，只检查后端安全拦截和路径规范，不发送真实模型请求、不需要 key、不写审计；终端输出会脱敏 API key、Provider Base URL 和 token 类字段。脚本会从 `GET /api/platform/delivery-report` 导出一份只读交付证据包到 `runtime_logs/delivery_evidence_report.md`，检查报告接口不会造成画像/审计/卡片状态漂移。脚本会检查 `real_sample_knowledge.json` 中的 `/assets/real_samples/...` 是否都存在于前端 public 目录，并在 UI smoke 中确认比拼训练、报告生成和科普卡片页的关键主图已绑定真实公开样例且自然尺寸非零。脚本也会在运行前后比对 `audit_logs.json`、`learner_profile.json` 和 `backend/runtime/patient_cards.json` 的内容指纹，并检查 `.demo_check_tmp` 沙盒恢复临时文件是否残留；即使中途失败也会报告状态是否漂移。总控内部已经串行执行会写状态的沙盒自检和 UI smoke，不要同时另开全路由 UI smoke 或正式写入演示。若总控命令失败，再按下面的单项命令定位具体环节。

前端：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run lint
npm run build
```

后端接口 smoke：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
@'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
for path in [
    "/api/health",
    "/api/provider/status",
    "/api/platform/readiness",
    "/api/dashboard",
    "/api/questions",
    "/api/knowledge/real-samples",
    "/api/knowledge/report",
    "/api/skills",
]:
    r = client.get(path)
    print(path, r.status_code)
    assert r.status_code == 200, r.text

r = client.post("/api/platform/demo-check?learner_id=demo_learner&persist=false")
print("/api/platform/demo-check?sandbox", r.status_code, r.json().get("mode"), r.json().get("write_verified"))
assert r.status_code == 200, r.text
assert r.json()["mode"] == "sandbox"
assert r.json()["write_verified"] is True
assert r.json()["restored_after_run"] is True
assert r.json()["restore_verified"] is True
'@ | python -
```

演示闭环一键 smoke：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\demo_smoke.py
```

该命令会自动探测 `http://127.0.0.1:8000/api` 和 `http://127.0.0.1:8001/api`，并以 `persist=false` 沙盒模式触发首页同款闭环自检：真实公开样例、知识来源链、训练提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、考试 Session、科普卡片草稿、同卡片医生审核和审计收据都会被检查；写入验证完成后会自动恢复画像、审计和卡片运行数据，并二次确认 readiness 摘要未变化。只有需要保留演示留痕时才使用 `--persist --yes`，不要在多人并发演示时运行会写入状态的自检。

交付证据包导出：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\export_delivery_report.py --output docs\DELIVERY_EVIDENCE_REPORT.md
```

该命令会自动探测后端并读取 `GET /api/platform/delivery-report`，把当前平台就绪度、林知远医师训练画像摘要、核心闭环证据、知识库来源链、审计事件分布、Provider 配置/自检/准入调用边界和验证命令导出为 Markdown。接口和脚本都是只读的，不触发 `demo-check`，不会写入 `learner_profile.json`、`audit_logs.json` 或 `patient_cards.json`，也不会返回 API key 或 Provider Base 明文。总控验证默认把报告导出到 `.gitignore` 中的 `runtime_logs`；需要作为答辩材料时再显式导出到 `docs\DELIVERY_EVIDENCE_REPORT.md`。

前端路由与运行时 smoke：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
node scripts\ui_smoke.mjs
```

该命令会自动启动本机 Edge/Chrome 无头浏览器，打开首页、比拼训练、画像、报告、模型准入、科普卡片和交付证据等关键路由，检查页面非空白、无 runtime/console error，并确认左侧栏全局 “Live evidence” 后端证据摘要存在。首页会额外要求真实样例覆盖总账 `data-real-sample-ledger=true`，并检查记录数、映射题量和图片资产校验值；比拼训练会额外要求医师任务队列 `data-training-mission=true` 与 learner id 存在；比拼训练、报告生成和科普卡片页会额外校验关键主图：读取 `img[data-real-sample-image="true"][data-real-sample-role="primary"]` 的加载状态、`naturalWidth` 和 `naturalHeight`，避免缩略图已加载但主工作图实际未显示。`/models` 会额外要求 `data-provider-ladder=true` 和 `data-provider-preview=true` 均来自 backend、证据阶梯不少于 6 步，并确认 dry-run 未发送请求、未保存 key；`/delivery` 会额外等待 `data-delivery-loaded=true`，并要求 `data-delivery-source=backend`、`data-delivery-integrity=clean`、Provider configured/real/self-test/admission 证据字段存在；这能抓出旧 Vite 路由、后端断连、只读完整性异常或 Provider 证据边界回退。若浏览器安装在非标准路径，可通过 `--browser` 或 `ARIS_BROWSER_PATH` 指定。

Provider 体检、Base URL 预检和自检 smoke：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\provider_doctor.py
```

`provider_doctor.py` 是推荐的第一步：它只读取本机 `.env` 是否存在、是否被 git 忽略，以及后端 diagnostics 证据阶梯/preflight 状态，不发送模型请求、不打印 key/base 明文。后端 `.env` 配好并重启 FastAPI 后，可运行：

```powershell
python scripts\provider_doctor.py --self-test --include-image
```

该命令使用后端 `.env` 中的 key 做文本/视觉通道自检，不需要在投屏终端输入 key，并会显示 `provider_called`、`image_attached`、审计 ID 和建议下一步。

Provider Base URL 预检 smoke：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
python scripts\provider_smoke.py --api-base http://127.0.0.1:9999/v1
```

该命令默认自动探测 `http://127.0.0.1:8000/api` 和 `http://127.0.0.1:8001/api`，并要求后端暴露 Provider 诊断、证据阶梯、预检、自检和收据能力。脚本会先打印 `/api/provider/diagnostics` 的脱敏摘要，包括 Provider 模式、缺失配置、公开样例数、最近自检/准入审计、准入状态和六步 evidence ladder；随后调用 `/api/provider/preflight`，不需要 key、不发送模型请求、不写审计。预检通过并准备真实联调时，再设置本地环境变量运行自检：

```powershell
$env:LLM_API_KEY="your-local-key"
python scripts\provider_smoke.py --api-base https://your-provider.example/v1 --model your-model --self-test
```

答辩投屏或录屏时不要在终端输入真实 key；优先使用本机后端 `.env`，或在非录屏环境完成真实自检。脚本不会打印 API key、Provider API Base 明文或完整模型回复；外部 Provider 地址在终端中只保留协议和路径级别的脱敏预览。如要使用后端 `.env` 中的 key，可加 `--use-backend-env-key`。

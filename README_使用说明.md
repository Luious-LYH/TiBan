# 内镜智训Agent 开发文档包使用说明

本文件夹包含可直接交给 AI 编程 Agent / Claude Code / Cursor 的平台开发文档。

## 文件列表

1. `01_平台总构建方案书.md`  
   平台总蓝图，包含产品定位、架构、页面、Agent、skills、memory、API、开发里程碑。

2. `02_Agent自动开发提示词文档.md`  
   给编程 Agent 使用的分阶段提示词，包含项目初始化、前端、后端、Agent、skills、memory、安全审查、最终交付等提示词。

3. `03_系统需求规格与接口数据字典.md`  
   PRD + API + 数据模型 + 页面验收标准。

4. `04_AGENTS.md`  
   建议复制到项目仓库根目录，作为 Claude Code / Cursor / Codex 的仓库规则文件。

## 推荐使用顺序

1. 把四个文件放进新仓库根目录或 docs 目录。
2. 把 `04_AGENTS.md` 复制为仓库根目录 `AGENTS.md`。
3. 打开 Claude Code 或 Cursor。
4. 先发送 `02_Agent自动开发提示词文档.md` 中的“总控提示词”。
5. 每完成一个 milestone，用“Claude Code 审阅循环提示词”审查。
6. 保证最终至少跑通：首页总览、训练中心、智能辅导、错因分析、交互式错误前提训练、报告中心、科普卡片、受控 Skills、审计日志、模型准入探测。

## 当前阶段边界

真实批量评测流水线暂不开发；v2.0 已支持 OpenAI-compatible Provider 的样例级准入检查、报告来源追踪和规则/fallback 显示。未配置 Provider 时，平台会明确显示 `rule` 或 `fallback`，不会把规则草案伪装成真实模型推理。

## v2.0 使用要点

1. 左侧栏新增全局 “Live evidence” 摘要，会从 `/api/platform/readiness` 拉取后端证据状态，在任意页面显示平台就绪度、Provider/rule 模式、真实公开样例数、审计数和最近考试复盘；首页“平台真实性与演示路径”会进一步聚合后端、真实公开样例、医师画像、考试 Session 复盘、报告知识库、Provider、模型准入和审计状态，适合答辩时先讲系统闭环；“最近考试 Session”卡片会直接显示本场题量、正确率、错题数和 `/feedback?session=...` 复盘入口；“真实数据来源链”会列出本地 JSON 知识库的记录数、样例 ID 和消费页面，避免看起来只是静态页面陈列。
   首页还提供“沙盒自检 / 写入演示画像”双按钮：沙盒会真实触发公开样例提交、Agent 辅导、挑战基准、报告草稿、报告修改评分、考试 Session、科普卡片草稿、同卡片医生审核、画像回灌和审计写入，再自动恢复数据；正式写入会保留画像、审计和卡片运行记录。两种模式都会返回 9 张证据收据，包含 `challenge_benchmark`、`exam_session`、`patient_card` 和 `patient_card_approve` 审计验证，后端不可用时不会用前端 fallback 伪造通过。
2. 顶部 Provider 状态条会显示当前处于 `provider`、`rule` 还是 `fallback`；模型准入页还会展示 Provider 联调状态检查，列出缺失配置、公开样例数、最近自检/准入审计和隐私边界，避免把规则草案伪装成真实推理。
3. 训练中心右侧 Agent 分为“辅导 / 证据 / 对照”，提交前隐藏参考答案；追问会记录训练标签和模式，不保存自由追问原文。
4. 报告中心会以流程工作台区分医生输入、公开样例标注、模板知识库、Provider 输出和医师复核任务。
5. 报告修改训练提交后会回灌林知远医师画像，更新训练记录、能力分和弱项标签，并返回下一步专项训练入口。
6. 考试模式是一个全局 session：12 分钟倒计时不会因单题提交重置，页面会累计已答题、正确率、平均分、错题 strip；交卷复盘会调用后端写入整场考试摘要、医师画像和审计日志，并通过 `/feedback?session=...` 按本场考试恢复错题队列；首页和画像页会同步展示最近一场考试的可复盘收据。
7. 报告页上传图片会保存到 `backend/runtime/uploads`，该目录已加入 `.gitignore`；科普卡片页优先从 `/api/knowledge/real-samples` 读取公开样例图像池，本地上传图只做当前浏览器预览，不写入后端卡片记录。
8. 模型准入页先看 Provider 联调状态检查：它只返回配置布尔值、缺失项、公开样例数量、最近自检/准入审计摘要和下一步动作，不返回 API key、API base 明文或完整模型回复。随后看 Base URL 预检：它不需要 key、不发送模型请求、不写审计，只展示规范化预览、将尝试的 chat completions path、安全拦截原因和下一步动作；非本机 `http`、metadata、内网/保留地址、非法端口、loopback 低端口和带凭据 URL 会被拒绝。真实 Provider 调用层也不会自动跟随 30x 重定向，并会使用重新校验后的连接地址，降低密钥被跳转或 DNS 变化带走的风险。预检通过后可做 Provider 文本轻量自检或视觉通道自检，只写摘要审计、不更新准入状态；视觉自检会附加一张公开内镜图片和问题，但不发送参考标注，不代表临床诊断。自检后会展示 `self_test_receipt`、`provider_self_test` 审计 ID、输入来源、Provider 来源和隐私边界。最后可使用后端 `.env` 或页面临时配置做最多 3 个公开样例的 blind probe 准入检查，并展示 `admission_receipt` 与 `model_admission` 审计 ID。模型卡片默认只是能力看板；只有最近准入摘要满足真实 Provider 调用、公开标注对齐和安全阈值，且目标不是 mock 模型时，才允许写入“待人工复核候选”。临时 key 不保存，只有填写临时 base 或 key 时页面模型名才会覆盖后端默认值。
9. 科普卡片页已加入医生审核闸门：草稿默认锁定打印/分享，医生勾选审核项并对当前 `card_id` 提交后才会解锁，并写入 `patient_card_approve` 审计日志。
10. 真实性说明见 `docs/V2_AUTHENTICITY_MATRIX.md`，接口见 `GET /api/platform/readiness`。

## v2.0 新增说明

- 完整启动、演示和常见问题见 `docs/V2_USER_GUIDE.md`。
- 错误前提训练已改为先作答后解锁证据链，不再静态展示答案。
- 考试交卷已从前端状态升级为 `/api/learner/exam-session` 持久化闭环：整场题量、正确率、平均分和错题摘要写入 `learner_profile.json`，同时生成 `exam_session` 审计事件，并在首页 readiness 中形成“最近考试 Session -> 本场错题复盘 -> 画像记录”的证据入口。
- 比拼模式提交前会锁住证据页和挑战基准，避免破坏训练闭环；医师提交后才调用 `/api/tutor/challenge-benchmark`。Provider 可用时由 Provider 独立作答；不可用时明确回退为“公开标注 fallback”。该基准只写 `challenge_benchmark` 审计，不重复回灌医师画像。
- 报告中心首屏已改为流程工作台：图像/所见、草稿生成、复核台账三个步骤会同步显示状态；公开 VQA 标注默认收进来源台账，不伪装成医生报告结论。
- 报告修改训练新增 `recommended_drills`，评分后可直接跳回训练中心做报告安全、证据不足或错误前提专项；链接会携带 `source=report_judge`、`drill` 和合法 `question_class`，进入后显示专项任务卡并按题类筛选，提交训练题后才继续回灌画像。
- 模型准入已从单样例探测升级为“文本/视觉自检 -> 样例级准入检查清单”：自检不触碰准入状态，视觉自检只证明公开图片已附加到 Provider 请求；每个公开样例准入会返回 evidence、Provider 调用状态、错误原因和后端审计收据；分数只代表训练接入检查，不代表临床评测。
- 前端 API 层已加入分级超时保护：健康/状态/诊断类接口会快速失败并显示 fallback 或不可用原因，真实 Provider 推理、报告生成、准入探测保留更长等待时间，避免演示时页面长期卡在加载状态。
- Provider API Base 支持根地址、`/v1` 或完整 `/chat/completions`；后端会优先尝试 `/v1/chat/completions` 并拒绝非本机 `http`、metadata、内网/保留地址，避免临时 key 外发。
- 新增 `scripts/provider_smoke.py` 作为终端联调入口：默认自动探测 `8000/8001` 最新 v2.0 后端，并要求后端暴露 Provider 诊断、预检、自检和收据能力；脚本会先打印脱敏后的 `/api/provider/diagnostics` 摘要，再调用 `/api/provider/preflight`，只在预检通过且明确提供 key 或使用后端 `.env` key 时才运行 Provider 自检；脚本不会打印 API key、API base 明文或完整模型回复。
- 新增 `scripts/demo_smoke.py` 作为答辩前一键自检入口：默认自动探测 `8000/8001` 后端，调用 `/api/health`、`/api/platform/readiness` 和 `/api/platform/demo-check?persist=false`，确认真实公开样例、知识来源链、训练提交、Agent 辅导、挑战基准、报告训练、考试 Session、科普卡片草稿、同卡片医生审核、画像写入恢复和审计收据均可跑通；默认沙盒模式会自动恢复画像、审计和卡片运行数据，并二次确认 readiness 摘要未变化。
- 新增 `scripts/ui_smoke.mjs` 作为前端路由巡检入口：自动启动本机 Edge/Chrome 无头浏览器，检查首页、比拼训练、画像、报告、模型准入和科普卡片等关键路由非空白、无 runtime/console error，并确认全局 Live evidence 证据条存在。
- 科普卡片已从单纯预览升级为“公开样例图像池 -> 草稿生成 -> 同一 `card_id` 医生审核 -> 分享/打印解锁 -> 审计记录”的受控流程。
- Skills 中心展示受控运行摘要、医生复核状态和工作区跳转，完整 JSON 只放在开发细节折叠项中。
- 首页闭环自检对应 `POST /api/platform/demo-check?persist=false|true`。默认 `persist=false` 会真实写入后自动恢复，用于答辩前安全确认训练链路；`persist=true` 才会保留 `learner_profile.json`、`audit_logs.json` 和 `backend/runtime/patient_cards.json` 的演示留痕。

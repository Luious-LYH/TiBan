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

1. 首页“平台真实性与演示路径”会聚合后端、真实公开样例、医师画像、报告知识库、Provider、模型准入和审计状态，适合答辩时先讲系统闭环。
   首页还提供“沙盒自检 / 写入演示画像”双按钮：沙盒会真实触发公开样例提交、Agent 辅导、报告草稿、报告修改评分、画像回灌和审计写入，再自动恢复数据；正式写入会保留画像和审计。两种模式都会返回 5 张证据收据，后端不可用时不会用前端 fallback 伪造通过。
2. 顶部 Provider 状态条会显示当前处于 `provider`、`rule` 还是 `fallback`，避免把规则草案伪装成真实推理。
3. 训练中心右侧 Agent 分为“辅导 / 证据 / 对照”，提交前隐藏参考答案；追问会记录训练标签和模式，不保存自由追问原文。
4. 报告中心会以流程工作台区分医生输入、公开样例标注、模板知识库、Provider 输出和医师复核任务。
5. 报告修改训练提交后会回灌林知远医师画像，更新训练记录、能力分和弱项标签，并返回下一步专项训练入口。
6. 考试模式是一个全局 session：12 分钟倒计时不会因单题提交重置，页面会累计已答题、正确率、平均分、错题 strip；交卷复盘会调用后端写入整场考试摘要、医师画像和审计日志。
7. 报告页上传图片会保存到 `backend/runtime/uploads`，该目录已加入 `.gitignore`；科普卡片页本地上传图只做当前浏览器预览，不写入后端卡片记录。
8. 模型准入页可先做 Provider 文本轻量自检或视觉通道自检，只写摘要审计、不更新准入状态；视觉自检会附加一张公开内镜图片和问题，但不发送参考标注，不代表临床诊断。自检后会展示 `self_test_receipt`、`provider_self_test` 审计 ID、输入来源、Provider 来源和隐私边界。随后可使用后端 `.env` 或页面临时配置做最多 3 个公开样例的 blind probe 准入检查，并展示 `admission_receipt` 与 `model_admission` 审计 ID。临时 key 不保存，只有填写临时 base 或 key 时页面模型名才会覆盖后端默认值。
9. 科普卡片页已加入医生审核闸门：草稿默认锁定打印/分享，医生勾选审核项并对当前 `card_id` 提交后才会解锁，并写入 `patient_card_approve` 审计日志。
10. 真实性说明见 `docs/V2_AUTHENTICITY_MATRIX.md`，接口见 `GET /api/platform/readiness`。

## v2.0 新增说明

- 完整启动、演示和常见问题见 `docs/V2_USER_GUIDE.md`。
- 错误前提训练已改为先作答后解锁证据链，不再静态展示答案。
- 考试交卷已从前端状态升级为 `/api/learner/exam-session` 持久化闭环：整场题量、正确率、平均分和错题摘要写入 `learner_profile.json`，同时生成 `exam_session` 审计事件。
- 比拼模式提交前会锁住证据页和挑战基准，避免破坏训练闭环；医师提交后才调用 `/api/tutor/challenge-benchmark`。Provider 可用时由 Provider 独立作答；不可用时明确回退为“公开标注 fallback”。该基准只写 `challenge_benchmark` 审计，不重复回灌医师画像。
- 报告中心首屏已改为流程工作台：图像/所见、草稿生成、复核台账三个步骤会同步显示状态；公开 VQA 标注默认收进来源台账，不伪装成医生报告结论。
- 报告修改训练新增 `recommended_drills`，评分后可直接跳回训练中心做报告安全、证据不足或错误前提专项。
- 模型准入已从单样例探测升级为“文本/视觉自检 -> 样例级准入检查清单”：自检不触碰准入状态，视觉自检只证明公开图片已附加到 Provider 请求；每个公开样例准入会返回 evidence、Provider 调用状态、错误原因和后端审计收据；分数只代表训练接入检查，不代表临床评测。
- 科普卡片已从单纯预览升级为“草稿生成 -> 同一 `card_id` 医生审核 -> 分享/打印解锁 -> 审计记录”的受控流程。
- Skills 中心展示受控运行摘要、医生复核状态和工作区跳转，完整 JSON 只放在开发细节折叠项中。
- 首页闭环自检对应 `POST /api/platform/demo-check?persist=false|true`。默认 `persist=false` 会真实写入后自动恢复，用于答辩前安全确认训练链路；`persist=true` 才会保留 `learner_profile.json` 和 `audit_logs.json` 的演示留痕。

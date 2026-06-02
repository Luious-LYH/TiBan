# V2.0 Authenticity Matrix

本文件用于答辩和后续开发审查：每个核心功能必须说明真实数据、规则逻辑、Provider 调用和 fallback 的边界。

## 模式定义

| 模式 | 含义 | UI 标识 |
|---|---|---|
| `provider` | 成功调用 OpenAI-compatible `/chat/completions`，可包含公开样例图片或受控上传图片 | 绿色 badge、Provider 名称、模型名、延迟 |
| `rule` | 未配置 Provider，后端使用规则、模板、JSON 知识库完成教学输出 | 蓝色 badge、`provider_not_configured` |
| `fallback` | Provider 失败或前端无法连接后端，使用前端/后端降级内容 | amber badge、失败原因 |

## 功能矩阵

| 模块 | 当前实现 | 真实来源 | Provider 使用 | 仍需改进 |
|---|---|---|---|---|
| 训练题库 | 公开样例优先、支持筛选/收藏/错题；考试模式已升级为全局 session、累计战报、交卷复盘入口，交卷后持久化整场摘要 | `questions.json`, `real_sample_knowledge.json`, `learner_profile.json`, `audit_logs.json` | 右侧 chat 可调用 Provider，失败后规则辅导；考试中隐藏提示和自由追问 | 后续可扩展多医师考试表、班级排名和正式试卷管理 |
| 右侧 Agent | `辅导/证据/对照` 三段式面板，提交前隐藏参考答案；挑战模式提交前锁住证据页；追问回灌训练事件 | 当前题、atomic facts、公开图片 URL | `tutor_orchestrator.chat` 调用 Provider | 仅保存题号/标签/模式，不保存医师追问原文；后续可做更细的会话摘要 |
| 错因复盘 | 本轮提交进入时显示真实提交；直接打开时从后端错题本恢复最近复盘题并标注为 review snapshot | `learner_profile.json` wrong/recent errors、`questions` API、atomic facts | 不调用 Provider | 复盘快照不重复写入画像；后续可加正式 submission history 表 |
| 错误前提训练 | 医师先独立作答，提交后解锁证据不足事实、原子证据、得分和复盘建议 | false-premise 题库、atomic facts、公开图像 | 不直接调用 Provider；可作为模型准入样例 | 后续可加入限时 drill 和更多拒答题型 |
| 报告中心 | 首屏展示数据来源、Provider、模板和真实推理控制；公开 VQA 标注默认收进来源台账；支持上传图片、结构化报告草稿、幻觉审查、报告修改评分 | 医生输入、公开样例来源台账、模板 KB、上传图片 | `report_service` 可用后端 `.env` 或请求级临时 Provider 生成视觉/文本观察摘要，并可给报告修改训练追加 Provider 评阅 | Provider 反馈仅作训练建议，仍需医生审核；后续可接真实专家评分 |
| 模型准入 | 公开样例探测、维度评分、证据摘录，并写入最近准入摘要 | `real_sample_knowledge.json`, `model_admission_state.json` | 有 key 或 `.env` 时调用 Provider；否则规则草案 | 未做批量多样本评测和统计置信区间 |
| 科普卡片 | 卡片模板、真实样例图片预览、动画卡片、本机图片预览、医生审核闸门、审核后打印/分享解锁 | `card_template_knowledge.json` + 医师输入摘要 + 审计日志 | 暂不调用 Provider | 上传图仍为本机预览；后续可接报告中心已审核结论一键带入 |
| Skills | 受控技能列表、运行样例选择、运行摘要、医生复核状态、工作区跳转；完整 JSON 折叠展示 | `skills.json` + 题库/报告/卡片/安全服务 | 取决于具体 skill 调用的服务 | 后续可加启停配置持久化和权限角色 |
| Memory | 提交题目、考试 Session、报告 judge、Agent 追问后更新训练记录、能力分、弱项标签 | `learner_profile.json` | 不调用 Provider | 考试 Session 只写整场摘要，不重复增加单题题量；模型准入写入平台状态，但不写入医师能力画像 |
| Audit | 审计驾驶舱展示事件总量、高风险、医生复核、最近写入、分类筛选和完整日志表 | `audit_logs.json` | 不调用 Provider | 不记录 key 或原始敏感输入；后续可区分 demo smoke 与正式演示日志 |

## 密钥和图片安全

- 真实 key 只能放本地 `.env`，或模型准入/报告中心页面的一次性临时输入。
- `.env` 和 `backend/runtime/` 均不提交 git。
- Provider 图片输入只允许：
  - `/assets/real_samples/...`
  - `backend/runtime/uploads/...`
- 上传图片只用于教学演示和医生审核前辅助，不应包含真实患者身份信息。

## 答辩时建议说法

本平台不是把所有能力伪装成“已完成临床级 AI”。v2.0 的核心进步是：每个输出都能说明它来自真实 Provider、后端规则，还是 fallback；训练中心提交前不泄露参考答案，挑战模式提交前锁住证据页；报告中心能追踪医生输入、公开样例来源台账、模板知识库、Provider 观察和 Provider 评阅；模型准入能做一次真实 OpenAI-compatible 调用探测，但完整评测流水线仍按需求暂缓。

科普卡片的打印/分享不是自由按钮：草稿生成后默认 `share_status=locked_pending_review`，医生完成审核清单并再次请求后端确认后才变为 `reviewed_ready_to_share`，同时写入 `patient_card` 审计事件。

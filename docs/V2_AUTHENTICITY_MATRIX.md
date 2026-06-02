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
| 训练题库 | 公开样例优先、支持筛选/收藏/错题，考试模式有 12 分钟倒计时 | `questions.json`, `real_sample_knowledge.json`, `learner_profile.json` | 右侧 chat 可调用 Provider，失败后规则辅导 | 可继续补完整 exam session 保存与成绩单 |
| 右侧 Agent | `辅导/证据/对照` 三段式面板，提交前隐藏参考答案 | 当前题、atomic facts、公开图片 URL | `tutor_orchestrator.chat` 调用 Provider | Agent 对话尚未回灌画像 |
| 报告中心 | 公开样例、上传图片、结构化报告草稿、幻觉审查、报告修改评分 | 医生输入、公开样例标注、模板 KB、上传图片 | `report_service` 可生成视觉/文本观察摘要 | 报告 judge 规则评分已回灌画像，后续可接 Provider judge |
| 模型准入 | 公开样例探测、维度评分、证据摘录 | `real_sample_knowledge.json` | 有 key 或 `.env` 时调用 Provider；否则规则草案 | 未做批量多样本评测和统计置信区间 |
| 科普卡片 | 卡片模板、真实样例图片预览、动画卡片 | `card_template_knowledge.json` + 医师输入摘要 | 暂不调用 Provider | 可加入医生审核工作流 |
| Memory | 提交题目与报告 judge 后更新训练记录、能力分、弱项标签 | `learner_profile.json` | 不调用 Provider | Agent 追问、准入结果未统一写入画像 |
| Audit | 记录题目、答题、辅导、报告、上传、准入 | `audit_logs.json` | 不记录 key 或原始敏感输入 | 需要区分 demo smoke 与正式演示日志 |

## 密钥和图片安全

- 真实 key 只能放本地 `.env` 或模型准入页面的一次性临时输入。
- `.env` 和 `backend/runtime/` 均不提交 git。
- Provider 图片输入只允许：
  - `/assets/real_samples/...`
  - `backend/runtime/uploads/...`
- 上传图片只用于教学演示和医生审核前辅助，不应包含真实患者身份信息。

## 答辩时建议说法

本平台不是把所有能力伪装成“已完成临床级 AI”。v2.0 的核心进步是：每个输出都能说明它来自真实 Provider、后端规则，还是 fallback；报告中心能追踪医生输入、公开样例标注、模板知识库和 Provider 观察；模型准入能做一次真实 OpenAI-compatible 调用探测，但完整评测流水线仍按需求暂缓。

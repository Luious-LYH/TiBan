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
6. 保证最终至少跑通：首页总览、训练中心、智能辅导、错因分析、错误前提训练、报告中心、科普卡片、审计日志、模型准入探测。

## 当前阶段边界

真实批量评测流水线暂不开发；v2.0 已支持 OpenAI-compatible Provider 的请求级探测、报告来源追踪和规则/fallback 显示。未配置 Provider 时，平台会明确显示 `rule` 或 `fallback`，不会把规则草案伪装成真实模型推理。

## v2.0 使用要点

1. 训练中心右侧 Agent 分为“辅导 / 证据 / 对照”，提交前隐藏参考答案。
2. 报告中心会区分医生输入、公开样例标注、模板知识库、Provider 输出。
3. 上传图片会保存到 `backend/runtime/uploads`，该目录已加入 `.gitignore`。
4. 模型准入页可使用后端 `.env` 或页面临时 key 进行一次真实探测，但不会保存密钥。
5. 真实性说明见 `docs/V2_AUTHENTICITY_MATRIX.md`。

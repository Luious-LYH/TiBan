# 项目简历介绍建议：Agent 应用方向

## 推荐项目名

**内镜智训 Agent｜可观测多模态医生研修系统**

技术栈：Python、FastAPI、Pydantic、React、TypeScript、OpenAI-compatible VLM、Agent Eval

## 简历推荐版本

> 独立设计并实现面向消化内镜研修的多模态 Agent Demo，支持公开内镜图像、医生圈画、自然语言作答、证据复盘、学习记忆与结构化报告交接。

- 针对原系统“单轮 Chat 难执行、难复盘”的问题，构建受控 `Plan→Act→Observe→Verify→Memory` Agent Runtime，封装证据检索、事实级评分和安全核验 3 类类型化工具，输出 run ID、调用收据、evidence IDs、节点耗时及 Provider/Rule/Fallback 来源。
- 将开放问答从字符串完全匹配升级为 19 条原子事实 Rubric 的 P/R/F1 评分；建立 5 个版本化医生病例和 3 条安全对抗探针，完成 5/5 单元测试及固定 Golden Case 自动回归，结构、工具链、证据和安全回归均通过。
- 重构 Golden Demo 信息架构，将多页面功能收束为“图像圈画→作答→Agent 执行→证据复盘→画像 Delta→报告交接”的 3 分钟主演示；支持桌面与 390px 移动端，并显式展示模型调用或规则降级来源。
- 设计运行态隔离机制，将画像、审计和模型状态从 Git seed 迁移至 runtime data，并提供一键重置接口，解决重复演示状态漂移和版本污染问题。

## 可选安全/工程加分条目

- 自研 OpenAI-compatible Provider，增加受控图片目录、私网/元数据地址拦截、DNS 解析与连接地址固定，降低多模态外部调用中的 SSRF/DNS Rebinding 风险。
- 报告链路引入 source trace、evidence ledger、无依据声明审查及医生复核闸门，使图像、医生输入、模板和模型输出可追溯。

## 面试时不要这样说

- 不说“自主诊断 Agent”或“用于临床诊断”。
- 不把固定 Golden Case 的 100% 回归率说成模型准确率。
- 不声称使用了 LangGraph；应说“自研受控状态图，并理解框架迁移条件”。
- 不写几十万真实用户、线上 QPS 或医生效率提升。


# AGENTS.md

> 仓库级开发规则，给 Claude Code、Cursor、Codex、其他自动编程 Agent 使用。

---

## 1. 项目身份

项目名：**内镜智训Agent：面向消化道内镜医师培训的智能辅导平台**

项目定位：医师培训、智能辅导、错因反馈、医生审核前辅助，不替代临床诊断。

当前阶段：完成可运行 Web 原型和核心功能；真实模型评测流水线暂不开发；模型能力看板只做 mock 和接口预留。

---

## 2. 技术栈

- Frontend: React + Vite + TypeScript
- UI: Tailwind CSS / shadcn 风格 / lucide-react / Recharts
- Backend: FastAPI + Pydantic
- Data: JSON mock first, SQLite later
- Agent: Rule/template workflow first, LLM provider abstraction later
- Docs: Markdown

---

## 3. 必须实现

Dashboard、Training Center、Tutor Panel、Error Feedback、False Premise Training、Report Draft、Patient Card、Model Hub mock、Skills Center、Audit Panel、Backend API、Mock data、Safety notices、README and docs。

---

## 4. 禁止事项

禁止写入：真实服务器 IP、密码、API Key、Webhook、Git token、患者姓名、身份证、住院号、就诊卡号、任何可识别患者身份的信息。

禁止功能：自动诊断、给真实患者治疗建议、输出最终报告结论、声称完成临床验证、声称真实评测流水线已经完成、让模型自由编造图像依据。

---

## 5. 医疗安全要求

所有医疗相关输出必须包含：

```json
{
  "doctor_review_required": true,
  "safety_notice": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
}
```

辅导 Agent 的所有回复必须限于教学训练，不得替代医生。

---

## 6. 代码质量要求

- 不写超大单文件。
- React 组件合理拆分。
- TypeScript 类型清楚。
- FastAPI 使用 Pydantic schemas。
- API 字段必须与 `03_系统需求规格与接口数据字典.md` 一致。
- 后端接口要有错误处理。
- 前端请求要有 loading/error/fallback。
- 不引入过多依赖。
- 保证 `npm run build` 和后端启动命令能通过。

---

## 7. 开发流程

每次开发前：说明计划、列出将修改文件、确认不涉及真实密钥和患者信息。

开发后：说明完成内容、运行方式、测试结果、未完成项、安全自查。

---

## 8. 视觉要求

- 页面像真实医疗教学平台。
- 不做营销大屏。
- 第一视觉中心：内镜医师培训、智能辅导、错因反馈。
- 模型能力看板是后台安全机制，不要喧宾夺主。
- 报告草稿和科普卡片是辅助功能，但要有展示性。
- 卡片、表格、标签、能力雷达要清晰。

---

## 9. 演示优先级

必须跑通：首页总览 -> 训练中心 -> 请求提示 -> 提交答案 -> 错因分析 -> 原子事实反馈 -> 错误前提训练 -> 报告草稿 -> 科普卡片 -> 审计日志 -> 模型能力看板。

如果时间不足，优先保证前 7 步。

# 内镜智训Agent

面向消化道内镜医师培训的智能辅导平台。当前版本实现可运行、可演示、可答辩的 Web 原型：题库训练、智能提示、答案讲解、原子事实错因反馈、错误前提训练、报告草稿辅助、科普卡片、Skills 中心、Memory、模型能力 mock 看板和审计日志。

> 本项目仅用于教学训练和医生审核前辅助，不替代临床诊断。真实模型评测流水线暂未开发，模型能力页为 mock/接口预留。

## 技术栈

- Frontend: React + Vite + TypeScript, lucide-react, Recharts
- Backend: FastAPI + Pydantic
- Data: JSON mock 数据
- Agent: 规则/模板编排，预留 LLM provider 接口
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

## 演示路径

1. 首页总览：查看今日训练、能力画像、推荐训练和安全提示。
2. 训练中心：点击“提示一下”，选择答案并提交。
3. 错因分析：查看 atomic facts、错因标签和下一题推荐。
4. 错误前提：展示证据不足/不适用的训练逻辑。
5. 报告草稿：输入内镜所见文本，生成结构化草稿。
6. 科普卡片：生成患者友好解释和免责声明。
7. 模型看板：展示 mock 模型能力和风险标签。
8. Skills 中心：运行 question_hint、atomic_feedback、false_premise_guard 等 skill。
9. 审计日志：查看关键事件记录。

## 外部参考

- [HyperKvasir](https://www.nature.com/articles/s41597-020-00622-y)：GI 内镜图像/视频数据底座，公开论文说明包含 110,079 张图像和 374 个视频。
- [Kvasir-VQA-x1](https://github.com/simula/Kvasir-VQA-x1)：GI 内镜 MedVQA 数据集与复杂度分层思路。
- [MediaEval Medico 2025](https://github.com/simula/MediaEval-Medico-2025)：GI VQA 与多模态解释评测方向。

## 安全边界

- 不处理真实患者身份信息。
- 不写入真实 API key、服务器密码、Webhook 或 token。
- 不输出最终临床诊断或治疗方案。
- 报告草稿和科普卡片均要求医生审核。
- 模型能力分只作为演示 mock，不代表真实临床评测。

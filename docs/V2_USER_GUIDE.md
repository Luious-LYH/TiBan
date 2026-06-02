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
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

健康检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/api/platform/readiness
```

## 2. 可选真实 Provider

如果没有配置 Provider，平台仍可用规则、模板和公开样例完成训练演示，并会在 UI 中显示 `rule` 或 `fallback`。如需真实 OpenAI-compatible 调用，只在本机 `.env` 填写：

```powershell
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=25
```

不要把 `.env`、真实 key、服务器密码或患者身份信息提交到 git。模型准入页的一次性 key 只用于请求级探测，不会保存到数据文件。

## 3. 推荐演示顺序

1. 训练驾驶舱 `/`
   先看“平台真实性与演示路径”，说明后端、公开样例、报告知识库、Provider、模型准入、Memory 和 Audit 的状态。这里适合回答“哪些是真的，哪些是规则草案”。

2. 题库刷题 `/training`
   展示公开样例图像、病例摘要、题目和右侧 Agent。练习模式可以点“提示一下”，Agent 只追问证据，不直接给答案。提交后显示得分、错因标签、解释和对照。

3. Doctor vs AI `/training?view=challenge`
   先独立作答。提交前右侧证据页和基准答案不会泄露；提交后解锁公开标注/AI 对照。若 Provider 未配置，应明确说这是“公开标注/规则基准”，不是伪装真实模型比赛。

4. 错误前提训练 `/false-premise`
   让医生判断题干假设是否成立。提交前只显示原则提示；提交后解锁证据不足事实、原子证据、得分和下一步复盘建议。这个页面同时服务医师训练和模型准入边界展示。

5. 报告中心 `/report`
   先看首屏三个状态：数据来源、Provider、报告模板。选择公开图像或上传图片后，公开 VQA 标注默认收进“图像来源台账”，不直接当成报告结论。点击生成后查看结构化所见、草稿印象、复核点、幻觉审查和证据台账。

6. 报告修改训练 `/report?tab=judge`
   提交一个越界报告和医师修改稿，查看 rubric 分数、问题、建议改写和画像回灌状态。

7. 医师画像 `/profile`
   展示林知远医师的训练记录、能力雷达、薄弱标签、错题/收藏和成长徽章。当前是单 demo learner，本地 JSON 持久化，后续可扩展多医师数据库。

8. 科普卡片 `/card`
   选择模板和真实样例图，生成医生审核前患者沟通卡片。上传图片仅本机预览；打印和分享文案都会提示医生审核边界。

9. Skills `/skills`
   选择当前题运行受控技能。页面展示运行摘要、审核要求、闭环入口；完整 JSON 放在开发细节折叠项，避免把平台展示成调试台。

10. 模型准入 `/models`
    用公开样例和可选 Provider 做一次准入探测。只有真实调用成功才显示 `provider_called=true`，最近准入状态会同步到首页。

11. 审计日志 `/audit`
    查看答题、辅导、报告、上传、skill、模型准入等关键事件记录。

## 4. 当前真实能力边界

| 能力 | 已实现 | 边界 |
|---|---|---|
| 公开样例题库 | 从 `real_sample_knowledge.json` 和公开图像资产加载 | 只抽取部分本地真实数据用于演示，不等同完整数据集训练 |
| 医师训练闭环 | 答题、收藏、错题、考试、比拼、错误前提训练 | 当前只有 `demo_learner` 单医师画像 |
| Agent 辅导 | 后端 tutor 编排，可接 Provider，也有规则兜底 | 不保存自由追问原文，只记录训练标签和模式 |
| 报告生成 | 图片上传、公开样例、模板 KB、来源追踪、幻觉审查 | 输出是医生审核前训练草稿，不是最终诊断 |
| 报告 judge | 规则 rubric 评分并回灌画像 | 后续可接 Provider judge 或真实专家评分 |
| 模型准入 | OpenAI-compatible Provider 请求级探测 | 不是完整临床评测，不包含批量统计置信区间 |
| Skills | 训练、反馈、报告、卡片、安全、审计技能可运行 | 面向受控编排，不允许自由越权调用 |

## 5. 常见问题

### 页面显示 rule/fallback 是不是失败？

不是。`rule` 表示后端规则、模板和知识库在工作；`fallback` 表示 Provider 或后端不可用时的降级。v2.0 的目标之一就是显式标注来源，不把规则草案伪装成真实模型推理。

### 为什么报告页会有 VQA 标注？

公开 VQA 标注用于证明图像样例来源和训练任务，不等同于医生报告结论。v2.0 已将它默认收进“图像来源台账”，报告正文仍以医生所见文本、模板知识库和可选 Provider 观察为主。

### 上传图片保存在哪里？

报告页上传图片保存到 `backend/runtime/uploads`，该目录不提交 git。科普卡片页上传只做本机预览，不自动写入后端。

### 如何恢复干净演示状态？

核心状态文件在 `backend/app/data`：

- `learner_profile.json`
- `audit_logs.json`
- `models.json`
- `model_admission_state.json`

正式演示前建议先备份这些文件。不要使用 `git reset --hard` 清理状态，避免误删用户改动。

## 6. 验证命令

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
'@ | python -
```

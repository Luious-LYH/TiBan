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

如果 `8000` 被旧版后端或其他服务占用，把最新后端启动到 `8001`：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m uvicorn app.main:app --reload --port 8001
```

前端未显式设置 `VITE_API_BASE_URL` 时，会自动按 `http://127.0.0.1:8000`、`http://127.0.0.1:8001` 探测后端；如需固定后端端口，可在前端启动前设置 `VITE_API_BASE_URL=http://127.0.0.1:8001`。

## 2. 可选真实 Provider

如果没有配置 Provider，平台仍可用规则、模板和公开样例完成训练演示，并会在 UI 中显示 `rule` 或 `fallback`。如需真实 OpenAI-compatible 调用，只在本机 `.env` 填写：

```powershell
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=your-local-key
LLM_MODEL=your-model-name
LLM_TIMEOUT_SECONDS=25
```

不要把 `.env`、真实 key、服务器密码或患者身份信息提交到 git。模型准入页的一次性 key 可用于文本/视觉自检或样例级准入检查，不会保存到数据文件；只有填写临时 base 或 key 时，页面模型名才会随本次请求覆盖后端 `.env` 默认值。

## 3. 推荐演示顺序

1. 训练驾驶舱 `/`
   先看“平台真实性与演示路径”和“可核验证据收据”，说明后端、公开样例、报告/科普知识库、Provider、自检/准入、训练挑战基准审计、Memory 和 Audit 的状态。这里适合回答“哪些是真的，哪些是规则草案”。首页的“沙盒自检”会真实跑通训练/Agent/报告/judge/审计链路并自动恢复数据；需要在审计页留下演示证据时，再点击“写入演示画像”。

2. 题库刷题 `/training`
   展示公开样例图像、病例摘要、题目和右侧 Agent。练习模式可以点“提示一下”，Agent 只追问证据，不直接给答案。提交后显示得分、错因标签、解释和对照。

3. 考试模式 `/training?mode=exam`
   进入后启动一场全局 12 分钟 session。倒计时不会因单题提交或切换题目重置；页面会累计已答题、正确率、平均分和最近错题，并提供“交卷复盘”“重开本场”和错因复盘入口。考试中隐藏提示和自由追问，交卷后会调用 `/api/learner/exam-session` 写入整场考试摘要、画像记录和审计日志。

4. 错因复盘 `/feedback`
   从训练中心提交后进入时显示本轮提交；直接打开或刷新时会从后端错题本恢复最近复盘题，并标注为“复盘快照”，不会重复写入医师画像。

5. 医生 vs 后端挑战基准 `/training?view=challenge`
   先独立作答。提交前右侧证据页和基准答案不会泄露；医师提交后，前端才调用 `/api/tutor/challenge-benchmark` 同步挑战基准。Provider 可用时由 Provider 独立选择答案；不可用或调用失败时明确显示“公开标注 fallback”。该基准只写 `challenge_benchmark` 审计，不重复更新林知远医师画像。比分板会展示最近一条真实后端 `challenge_benchmark` 审计收据；后端不可用或只有前端 fallback 时，不会伪造“已连接”。

6. 错误前提训练 `/false-premise`
   让医生判断题干假设是否成立。提交前只显示原则提示；提交后解锁证据不足事实、原子证据、得分和下一步复盘建议。这个页面同时服务医师训练和模型准入边界展示。

7. 报告中心 `/report`
   先看流程工作台：图像/所见、生成草稿、复核台账三步会同步显示状态；数据来源、Provider 和模板状态压缩在状态带中。可选择使用后端 `.env` 或本次请求临时 Provider；临时 key 只随报告生成/评分请求发送，不保存。选择公开图像或上传图片后，公开 VQA 标注默认收进“图像来源台账”，不直接当成报告结论。点击生成后查看结构化所见、草稿印象、复核点、幻觉审查、Provider 状态和证据台账。

8. 报告修改训练 `/report?tab=judge`
   提交一个越界报告和医师修改稿，查看 rubric 分数、Provider/rule/fallback 来源、问题、建议改写和画像回灌状态。评分响应会返回 `recommended_drills`，页面可直接跳回训练中心做报告安全、证据不足或错误前提专项。真实 Provider 评阅只作为训练反馈，不替代医生审核。

9. 医师画像 `/profile`
   展示林知远医师的训练记录、能力雷达、薄弱标签、错题/收藏和成长徽章。当前是单 demo learner，本地 JSON 持久化，后续可扩展多医师数据库。

10. 科普卡片 `/card`
   选择模板和真实样例图，先生成医生审核前患者沟通卡片草稿。页面右侧有审核闸门：医生需要逐项确认摘要来源、未新增治疗/疗效承诺、免责声明保留，并对当前 `card_id` 提交审核确认；审核通过后后端会返回同一张卡片的 `share_status=reviewed_ready_to_share`，打印和分享按钮才会解锁，审计日志会记录 `patient_card_approve`。

11. Skills `/skills`
   选择当前题运行受控技能。页面展示运行摘要、审核要求、闭环入口；完整 JSON 放在开发细节折叠项，避免把平台展示成调试台。

12. 模型准入 `/models`
    先做 Provider 文本轻量自检或视觉通道自检：文本自检只发送一条安全短提示词；视觉自检会附加一张公开内镜图片和问题，但不读取/发送参考标注，不保存 key/base/完整回复，也不更新模型准入状态。随后用最多 3 个公开样例和可选 Provider 做样例级准入检查；Provider 收到的是图片和问题，不包含参考标注，后端只在返回后做公开标注粗粒度对齐。只有真实调用成功才显示 `provider_called=true`；只有调用成功且至少一条盲测回答与公开标注部分对齐，最近准入状态才会标为可进入人工复核。

13. 审计日志 `/audit`
    查看审计驾驶舱：事件总量、高风险、医生复核负载、最近写入时间、分类筛选和完整日志表。日志只保存事件摘要、风险等级和审核状态。

## 4. 当前真实能力边界

| 能力 | 已实现 | 边界 |
|---|---|---|
| 公开样例题库 | 从 `real_sample_knowledge.json` 和公开图像资产加载 | 只抽取部分本地真实数据用于演示，不等同完整数据集训练 |
| 医师训练闭环 | 答题、收藏、错题、考试 session、比拼、错误前提训练 | 当前只有 `demo_learner` 单医师画像；单题提交单独更新题量和能力分，考试 session 交卷会持久化整场题量、正确率、平均分和错题摘要，不重复增加单题题量 |
| 首页闭环自检 | 沙盒自检和正式写入两种模式 | `persist=false` 真实写入后自动恢复，适合反复演示前 smoke；`persist=true` 才保留演示画像和审计 |
| Agent 辅导 | 后端 tutor 编排，可接 Provider，也有规则兜底 | 不保存自由追问原文，只记录训练标签和模式 |
| 报告生成 | 图片上传、公开样例、模板 KB、来源追踪、幻觉审查、请求级 Provider | 输出是医生审核前训练草稿，不是最终诊断；临时 key 不保存 |
| 报告 judge | 规则 rubric + 可选 Provider 评阅，并回灌画像与推荐专项训练 | Provider 反馈仅作训练建议；后续可接真实专家评分 |
| 模型准入 | OpenAI-compatible Provider 文本/视觉自检 + 公开样例 blind probe 准入检查 | 文本自检只验证文字通道；视觉自检只证明公开图片已附加到 Provider 请求并写摘要审计，不发送参考标注；样例准入不向 Provider 泄露参考标注；检查清单分只服务训练 Agent 接入，不是完整临床评测，不包含批量统计置信区间 |
| Skills | 训练、反馈、报告、卡片、安全、审计技能可运行 | 面向受控编排，不允许自由越权调用 |

## 5. 常见问题

### 页面显示 rule/fallback 是不是失败？

不是。`rule` 表示后端规则、模板和知识库在工作；`fallback` 表示 Provider 或后端不可用时的降级。v2.0 的目标之一就是显式标注来源，不把规则草案伪装成真实模型推理。

### 为什么报告页会有 VQA 标注？

公开 VQA 标注用于证明图像样例来源和训练任务，不等同于医生报告结论。v2.0 已将它默认收进“图像来源台账”，报告正文仍以医生所见文本、模板知识库和可选 Provider 观察为主。

### 上传图片保存在哪里？

报告页上传图片保存到 `backend/runtime/uploads`，该目录不提交 git。科普卡片页上传只做本机预览，不自动写入后端；卡片分享/打印需要医生审核闸门通过。

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

r = client.post("/api/platform/demo-check?learner_id=demo_learner&persist=false")
print("/api/platform/demo-check?sandbox", r.status_code, r.json().get("mode"), r.json().get("write_verified"))
assert r.status_code == 200, r.text
assert r.json()["mode"] == "sandbox"
assert r.json()["write_verified"] is True
assert r.json()["restored_after_run"] is True
'@ | python -
```

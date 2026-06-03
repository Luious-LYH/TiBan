# API_SPEC

Base URL: `http://127.0.0.1:8000/api`

所有医疗相关输出都应包含：

```json
{
  "doctor_review_required": true,
  "safety_notice": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
}
```

当前 `/submit`、`/learner/exam-session`、`/tutor/hint`、`/tutor/explain`、`/tutor/chat`、`/tutor/challenge-benchmark`、`/report-draft`、`/report/judge`、`/patient-card`、`/provider/self-test`、`/models/admission-test` 和高风险 `/skills/run` 输出均遵循该契约。

v2.0 起，涉及大模型或规则生成的接口会显式返回 `generation_mode` / `provider_status` / `provider_called`：

- `provider`: 已调用本地 `.env` 或本次请求提供的 OpenAI-compatible Provider。
- `rule`: 未配置 Provider，使用后端规则/模板生成。
- `fallback`: Provider 调用失败或前端后端断连后的降级结果。

## Core

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/provider/status` | 当前 OpenAI-compatible Provider 配置状态，不返回密钥 |
| POST | `/provider/self-test` | Provider 轻量连通自检；不读取公开样例，不更新模型准入状态，不保存 key/base/完整回复 |
| GET | `/dashboard` | 首页训练总览、能力画像、推荐训练 |
| GET | `/platform/readiness` | 平台就绪度、真实性矩阵和建议演示路线 |
| GET | `/questions` | 题库列表，支持 `question_class`、`difficulty`、`false_premise` |
| GET | `/questions/{id}` | 单题详情 |
| POST | `/submit` | 提交答案并生成错因反馈 |
| POST | `/tutor/hint` | 生成不泄露答案的提示 |
| POST | `/tutor/explain` | 生成答案讲解和 atomic feedback |
| POST | `/tutor/chat` | 当前题范围内的辅导回复 |
| POST | `/tutor/challenge-benchmark` | 医师提交后同步后端挑战基准；Provider 可用时独立作答，否则公开标注 fallback；只写 `challenge_benchmark` 审计，不重复更新画像 |
| GET | `/learner/profile` | 学员画像 |
| GET | `/learner/recommendations` | 推荐训练 |
| POST | `/learner/exam-session` | 写入整场考试 Session 摘要、错题摘要和审计事件 |
| POST | `/report-draft` | 结构化报告草稿 |
| POST | `/report/image-upload` | 上传教学图片到后端受控目录，返回 `uploads/...` 引用 |
| POST | `/report/judge` | 报告修改训练评分 |
| POST | `/patient-card` | 科普卡片草稿 |
| POST | `/patient-card/{card_id}/approve` | 审核同一张科普卡片草稿并解锁分享 |
| GET | `/models` | 模型库 mock 看板 |
| POST | `/models/select` | 选择默认 mock 模型 |
| POST | `/models/admission-test` | 使用公开样例做样例级 Provider/规则准入检查 |
| GET | `/models/admission-state` | 最近一次模型准入摘要，不包含 key 或完整模型回复 |
| GET | `/skills` | Skills 列表 |
| POST | `/skills/run` | 运行受控 skill |
| GET | `/audit` | 审计日志 |

## 示例

提交答案：

```json
{
  "question_id": "q005",
  "learner_id": "demo_learner",
  "selected_answer": "估计为2厘米并建议切除"
}
```

报告草稿：

```json
{
  "finding_text": "胃窦黏膜充血，可见散在糜烂。",
  "exam_type": "gastroscopy",
  "image_name": "public_real_x1_0",
  "template_name": "胃镜结构化训练模板",
  "provider_name": "可选，仅本次请求",
  "api_base": "可选，例如 https://api.example.com/v1",
  "api_key": "可选，仅本次请求，禁止写入仓库",
  "model": "可选模型名"
}
```

Tutor chat 返回会标注来源和画像回灌状态，不保存医生追问原文：

```json
{
  "reply": "请先指出一个可观察事实，再判断它是否支持题干结论。",
  "generation_mode": "provider | rule | fallback",
  "interaction_tags": ["证据不足", "病灶识别", "rule"],
  "profile_updated": true,
  "memory_summary": "已记录 Agent 辅导事件：...；未保存追问原文。"
}
```

挑战基准只应在医师先提交答案后调用；它会尝试让 Provider 在不读取公开答案的前提下独立选择一个选项。Provider 未配置或失败时回退公开标注 fallback；该接口不更新 `learner_profile.json`，只写 `challenge_benchmark` 审计：

```json
{
  "question_id": "public_real_x1_0",
  "learner_id": "demo_learner",
  "selected_answer": "z-line"
}
```

核心返回字段：

```json
{
  "benchmark_name": "Provider 挑战基准 | 挑战基准（公开标注 fallback）",
  "benchmark_answer": "z-line",
  "benchmark_correct": true,
  "doctor_selected_answer": "z-line",
  "same_as_doctor": true,
  "generation_mode": "provider | public_annotation",
  "provider_status": {
    "mode": "provider | rule",
    "ok": false,
    "error": "provider_not_configured"
  },
  "audit_logged": true,
  "profile_updated": false
}
```

考试 Session 交卷会写入画像摘要和审计事件；单题提交已经分别记录，因此该接口不会重复增加 `total_questions`：

```json
{
  "session_id": "exam_abc123",
  "learner_id": "demo_learner",
  "duration_seconds": 720,
  "remaining_seconds": 512,
  "finished_reason": "manual_submit",
  "attempts": [
    {
      "question_id": "q005",
      "title": "错误前提：图中是否一定有息肉",
      "selected_answer": "指出证据不足：图中未明确显示息肉",
      "correct_answer": "指出证据不足：图中未明确显示息肉",
      "is_correct": true,
      "score": 100,
      "error_tags": []
    }
  ]
}
```

核心返回字段：

```json
{
  "answered_count": 1,
  "accuracy": 100,
  "average_score": 100,
  "profile_updated": true,
  "memory_summary": "已写入林知远医师考试 Session..."
}
```

报告输出核心字段：

```json
{
  "generation_mode": "provider | rule | fallback",
  "provider_status": {
    "provider": "mock | openai_compatible",
    "model": "model-name",
    "ok": false,
    "error": "provider_not_configured"
  },
  "source_trace": [
    { "source_type": "doctor_input", "label": "医生输入所见", "used": true },
    { "source_type": "public_sample_annotation", "label": "公开样例标注", "used": true },
    { "source_type": "template_kb", "label": "报告模板知识库", "used": true },
    { "source_type": "provider", "label": "视觉/语言 Provider", "used": false }
  ]
}
```

报告修改训练评分会同时返回画像回灌状态：

```json
{
  "score": 88,
  "generation_mode": "provider | rule | fallback",
  "provider_status": {
    "provider": "mock | openai_compatible | request-provider",
    "model": "model-name",
    "ok": false,
    "error": "provider_not_configured"
  },
  "provider_feedback": "真实 Provider 成功调用时返回训练评阅摘要，否则为 null",
  "source_trace": [
    { "source_type": "rule_rubric", "label": "规则 rubric", "used": true },
    { "source_type": "provider", "label": "Provider 评阅", "used": false }
  ],
  "rubric_scores": {
    "部位描述": 25,
    "所见与诊断区分": 25,
    "不确定性表达": 25,
    "安全边界": 25
  },
  "recommended_drills": [
    {
      "label": "报告安全专项",
      "href": "/training?question_class=报告纠错",
      "reason": "把观察性所见和诊断性结论拆开，减少越界表达。",
      "rubric": "所见与诊断区分",
      "score": 18
    }
  ],
  "profile_updated": true,
  "memory_summary": "已回灌林知远医师画像：报告修改 88 分，事实组合/证据边界能力已更新。"
}
```

科普卡片默认生成待审核草稿，打印/分享保持锁定。医生确认审核后，对同一张草稿卡调用 approve 接口才会解锁；平台不再通过“重新生成一张已审核卡”伪装审核闭环。

```json
{
  "diagnosis_summary": "胃窦黏膜炎症样改变，需结合完整报告和医生复核后用于患者解释。",
  "audience": "patient",
  "template_id": "calm_blue",
  "image_url": "/assets/real_samples/kv_cla820gl0s3nv071u4fgd7xgq.jpg"
}
```

审核同一张草稿：

```json
POST /api/patient-card/card_xxx/approve
{
  "reviewer_name": "林知远医师",
  "review_notes": "摘要来源已确认，未新增治疗或疗效承诺。",
  "review_checks": {
    "summaryMatched": true,
    "noUnsupportedClaim": true,
    "disclaimerKept": true
  }
}
```

核心返回字段：

```json
{
  "id": "card_xxx",
  "review_status": "doctor_reviewed_input",
  "share_status": "reviewed_ready_to_share",
  "reviewer_name": "林知远医师",
  "reviewed_at": "2026-06-03T...",
  "review_steps": [
    { "label": "摘要来自医生确认的报告或训练输入", "checked": true }
  ],
  "doctor_review_required": true
}
```

Provider 轻量自检：

```json
{
  "provider_name": "自定义多模态 API",
  "api_base": "https://api.example.com/v1",
  "api_key": "仅本次请求可选，禁止写入仓库",
  "model": "your-model-name"
}
```

自检只发送一条安全短提示词，验证 OpenAI-compatible 通道是否可用；它不使用公开样例，不写入 `model_admission_state.json`，也不保存 API key、API base 或完整模型回复。核心返回字段：

```json
{
  "provider_called": false,
  "probe_excerpt": null,
  "audit_logged": true,
  "key_persisted": false,
  "admission_state_updated": false,
  "recommendation": "Provider 自检未通过：provider_not_configured。请检查 base URL、模型名、key 或后端 .env。"
}
```

模型准入：

```json
{
  "provider_name": "自定义多模态 API",
  "api_base": "https://api.example.com/v1",
  "api_key": "仅本次请求可选，禁止写入仓库",
  "model": "your-model-name",
  "selected_sample_ids": ["real_x1_0", "real_x1_2", "real_x1_3"],
  "test_focus": ["基础识别", "错误前提", "报告安全"]
}
```

模型准入会对最多 3 个公开样例逐条返回 evidence；检查清单分只服务训练 Agent 接入，不代表临床模型评测：

```json
{
  "provider_called": true,
  "provider_status": {
    "mode": "provider",
    "sample_count": 3,
    "provider_success_count": 3
  },
  "evidence": [
    {
      "sample_id": "real_x1_0",
      "provider_called": true,
      "latency_ms": 1240,
      "observation_excerpt": "模型返回的教学观察摘要..."
    }
  ],
  "platform_state_updated": true,
  "platform_state_summary": "最近准入状态已更新：自定义多模态 API · Grade A · provider。"
}
```

最近准入摘要只保存 `provider_name`、`grade`、`total_score`、`mode`、`tested_samples`、`risk_items` 和 `recommendation`，不保存 API key、API base 或完整模型回复。请求级 `api_base`、`model` 可以覆盖后端 `.env` 默认值；`https://api.example.com/v1` 这类示例地址会被视为未配置。

平台就绪度：

```json
{
  "overall_score": 71,
  "provider_mode": "rule",
  "real_sample_count": 10,
  "modules": [
    {
      "label": "真实公开样例",
      "status": "ready",
      "detail": "已接入 Kvasir/EndoBench 公开图文样例。",
      "href": "/training?source=public",
      "tone": "green"
    }
  ],
  "demo_path": [
    {
      "step": 1,
      "title": "训练驾驶舱",
      "href": "/",
      "expected_state": "后端在线 + 公开样例已接入"
    }
  ],
  "gaps": ["未配置 Provider 时会显式显示 rule/fallback。"]
}
```

运行 skill：

```json
{
  "skill_id": "false_premise_guard",
  "payload": { "question_id": "q005" },
  "learner_id": "demo_learner"
}
```

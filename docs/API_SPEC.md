# API_SPEC

Base URL: `http://127.0.0.1:8000/api`

本机 `8000` 被旧服务占用时，可将最新后端启动到 `http://127.0.0.1:8001/api`；前端未显式配置 `VITE_API_BASE_URL` 时会自动尝试 `8000` 和 `8001`，并优先选择 `/api/health` 暴露 v2.0 capabilities 的后端。

所有医疗相关输出都应包含：

```json
{
  "doctor_review_required": true,
  "safety_notice": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
}
```

当前 `/submit`、`/learner/exam-session`、`/tutor/hint`、`/tutor/explain`、`/tutor/chat`、`/tutor/challenge-benchmark`、`/platform/demo-check`、`/report-draft`、`/report/judge`、`/patient-card`、`/provider/self-test`、`/models/admission-test` 和高风险 `/skills/run` 输出均遵循该契约。

v2.0 起，涉及大模型或规则生成的接口会显式返回 `generation_mode` / `provider_status` / `provider_called`：

- `provider`: 已调用本地 `.env` 或本次请求提供的 OpenAI-compatible Provider。
- `rule`: 未配置 Provider，使用后端规则/模板生成。
- `fallback`: Provider 调用失败或前端后端断连后的降级结果。

## Core

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查，返回 `version` 与 `capabilities`，用于前端选择具备 v2.0 Provider 联调状态检查、Provider 视觉自检、Provider 自检收据、模型准入收据、知识库来源链、沙盒自检、挑战基准、挑战审计收据、科普卡片收据和 Skill 运行收据能力的后端 |
| GET | `/provider/status` | 当前 OpenAI-compatible Provider 配置状态，不返回密钥 |
| GET | `/provider/diagnostics` | Provider 联调状态检查；返回配置布尔值、缺失项、公开样例数量、最近自检/准入审计摘要、准入状态和下一步动作，不返回 key/base 明文或完整模型回复 |
| POST | `/provider/self-test` | Provider 文本/视觉通道自检；视觉模式可附加一张公开样例图片，但不发送参考标注，不更新模型准入状态，不保存 key/base/完整回复；返回 `audit_log_id` 和 `self_test_receipt` |
| GET | `/dashboard` | 首页训练总览、能力画像、推荐训练 |
| GET | `/platform/readiness` | 平台就绪度、真实性矩阵和建议演示路线 |
| POST | `/platform/demo-check` | 手动触发一次公开样例演示闭环自检；`persist=false` 沙盒写入后自动恢复，`persist=true` 才保留画像和审计；后端不可用时前端不伪造通过 |
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
| POST | `/models/select` | 仅在最近准入摘要满足真实 Provider 调用、公开标注对齐和安全阈值，且目标不是 mock 模型时，写入待人工复核候选；否则返回 400，不允许前端伪造切换成功 |
| POST | `/models/admission-test` | 使用公开样例做样例级 Provider/规则准入检查；返回 `audit_logged`、`audit_log_id` 和 `admission_receipt` |
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

科普卡片默认生成待审核草稿，打印/分享保持锁定。`POST /patient-card` 会返回草稿生成收据：`generation_mode`、`source_trace`、`knowledge_base_id`、`audit_logged` 和 `audit_log_id`，用于证明后端已经用卡片模板知识库生成草稿并写入 `patient_card` 审计。该收据不代表医生审核通过。医生确认审核后，对同一张草稿卡调用 approve 接口才会解锁；平台不再通过“重新生成一张已审核卡”伪装审核闭环。

```json
{
  "diagnosis_summary": "胃窦黏膜炎症样改变，需结合完整报告和医生复核后用于患者解释。",
  "audience": "patient",
  "template_id": "calm_blue",
  "image_url": "/assets/real_samples/kv_cla820gl0s3nv071u4fgd7xgq.jpg"
}
```

草稿生成核心返回字段：

```json
{
  "id": "card_xxx",
  "review_status": "doctor_review_pending",
  "share_status": "locked_pending_review",
  "generation_mode": "rule",
  "knowledge_base_id": "card_template_kb_v1_1",
  "audit_logged": true,
  "audit_log_id": "audit_xxx",
  "source_trace": [
    { "source_type": "doctor_input", "label": "医生审核前摘要", "used": true },
    { "source_type": "card_template_kb", "label": "清爽蓝-门诊沟通", "used": true },
    { "source_type": "audit", "label": "生成审计收据", "used": true }
  ],
  "doctor_review_required": true
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

Provider 文本/视觉通道自检：

```json
{
  "provider_name": "自定义多模态 API",
  "api_base": "https://api.example.com/v1",
  "api_key": "仅本次请求可选，禁止写入仓库",
  "model": "your-model-name",
  "include_image": true,
  "sample_id": "real_x1_0"
}
```

`include_image=false` 时，自检只发送一条安全短提示词，验证 OpenAI-compatible 文本通道是否可用。`include_image=true` 时，后端会选择 `sample_id` 指定或默认第一条公开样例，把图片编码为 `image_url` data URL 附加到请求；prompt 只包含数据集名、问题和安全要求，不包含公开参考标注。两种模式都不写入 `model_admission_state.json`，也不保存 API key、API base 或完整模型回复。核心返回字段：

```json
{
  "provider_called": false,
  "visual_probe": true,
  "image_attached": true,
  "image_sample_id": "real_x1_0",
  "image_source_dataset": "Kvasir-VQA-x1",
  "provider_status": {
    "mode": "rule",
    "ok": false,
    "error": "provider_not_configured",
    "image_attached": true
  },
  "probe_excerpt": null,
  "audit_logged": true,
  "audit_log_id": "audit_xxx",
  "self_test_receipt": {
    "audit_log_id": "audit_xxx",
    "event_type": "provider_self_test",
    "self_test_id": "provider_selftest_xxx",
    "provider_called": false,
    "visual_probe": true,
    "image_attached": true,
    "state_kind": "self_test",
    "input_trace": [
      { "source_type": "provider_config", "label": "Provider 配置来源", "used": true, "detail": "使用页面临时 Provider 配置；key/base 不保存。" },
      { "source_type": "public_visual_sample", "label": "公开视觉样例", "used": true, "detail": "Kvasir-VQA-x1 / real_x1_0" }
    ],
    "provider_trace": [
      { "source_type": "provider_call", "label": "OpenAI-compatible 调用", "used": false, "detail": "provider_not_configured" },
      { "source_type": "image_attachment", "label": "图片附加", "used": true, "detail": "已附加公开样例图片；未发送参考标注。" }
    ],
    "privacy_trace": [
      { "label": "API key/base", "used": false, "detail": "不写入审计、状态文件或响应明文。" },
      { "label": "模型准入状态", "used": false, "detail": "自检不更新 model_admission_state.json。" }
    ]
  },
  "key_persisted": false,
  "admission_state_updated": false,
  "recommendation": "后端已构造并附加公开样例图片，但 Provider 自检未通过：provider_not_configured。请检查 base URL、模型名、key 或后端 .env。"
}
```

`self_test_receipt` 是前端“后端 Provider 自检收据”的数据源，用于展示本次自检的审计 ID、输入来源、Provider 调用来源和隐私边界。后端只记录摘要审计，不保存 key/base/完整回复；前端 fallback 收据必须让 `audit_log_id=null`。

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

模型准入会对最多 3 个公开样例逐条返回 evidence；Provider prompt 只包含图片和问题，不包含公开参考标注。检查清单分只服务训练 Agent 接入，不代表临床模型评测：

```json
{
  "provider_called": true,
  "provider_status": {
    "mode": "provider",
    "sample_count": 3,
    "provider_success_count": 3,
    "reference_aligned_count": 2,
    "blind_probe": true
  },
  "evidence": [
    {
      "sample_id": "real_x1_0",
      "provider_called": true,
      "latency_ms": 1240,
      "blind_probe": true,
      "provider_answer": "模型盲测返回的教学观察摘要...",
      "reference_match": "partial",
      "answer_overlap": 0.33
    }
  ],
  "platform_state_updated": true,
  "platform_state_summary": "最近 Provider 准入摘要已更新：自定义多模态 API · Grade A · provider。",
  "audit_logged": true,
  "audit_log_id": "audit_xxx",
  "admission_receipt": {
    "audit_log_id": "audit_xxx",
    "event_type": "model_admission",
    "admission_id": "admission_xxx",
    "provider_called": true,
    "grade": "A",
    "total_score": 86,
    "platform_state_updated": true,
    "state_kind": "provider_admission",
    "input_trace": [
      { "source_type": "public_samples", "label": "公开样例盲测", "used": true, "detail": "3 个公开样例：real_x1_0, real_x1_2, real_x1_3" },
      { "source_type": "test_focus", "label": "测试维度", "used": true, "detail": "基础识别 / 错误前提 / 报告安全" }
    ],
    "provider_trace": [
      { "source_type": "blind_probe", "label": "Provider 盲测", "used": true, "detail": "3/3 个样例调用成功；2 条公开标注对齐。" },
      { "source_type": "unmatched_samples", "label": "未匹配样例", "used": false, "detail": "全部请求样例均已匹配或使用默认公开样例。" }
    ],
    "privacy_trace": [
      { "label": "参考答案", "used": false, "detail": "不发送给 Provider；仅在返回后做粗粒度对齐。" },
      { "label": "API key/base", "used": false, "detail": "不写入 model_admission_state.json 或审计明文。" }
    ]
  }
}
```

`admission_receipt` 是前端“后端模型准入收据”的数据源，用于证明准入接口已写入 `model_admission` 审计，并展示 blind probe 输入来源、Provider 来源、隐私边界和下一步动作。最近准入摘要只保存 `provider_name`、`grade`、`total_score`、`mode`、`tested_samples`、`risk_items`、`reference_aligned_count` 和 `recommendation`，不保存 API key、API base 或完整模型回复。只有请求级 `api_base` 或 `api_key` 存在时，`model` 才作为本次请求覆盖项；`https://api.example.com/v1` 这类示例地址会被视为未配置。

平台就绪度：

```json
{
  "overall_score": 71,
  "provider_mode": "rule",
  "real_sample_count": 10,
  "knowledge_source_chain": [
    {
      "label": "真实公开图文样例",
      "source_file": "real_sample_knowledge.json",
      "record_count": 10,
      "sample_ids": ["real_x1_0", "real_kvasir_0"],
      "used_by": ["题库训练", "报告中心", "科普卡片配图", "模型准入"],
      "proof": "10 道训练题由公开样例映射生成；报告、科普卡片配图和模型准入复用同一批样例 ID。公开教学样例不代表批量临床评测。",
      "href": "/training?source=public",
      "tone": "green"
    }
  ],
  "evidence_receipts": [
    {
      "label": "真实公开样例库",
      "status": "ready",
      "detail": "10 条公开图文题已由 real_sample_knowledge.json 映射到题库。",
      "href": "/training?source=public",
      "tone": "green"
    },
    {
      "label": "训练挑战基准",
      "status": "audited",
      "detail": "已有 challenge_benchmark 审计；基准不重复回灌画像。",
      "href": "/training?view=challenge",
      "tone": "green"
    }
  ],
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

演示闭环自检：

```http
POST /api/platform/demo-check?learner_id=demo_learner&persist=false
```

该接口用于答辩前确认平台不是静态页面。它会选择一条公开样例题，真实触发 `/submit`、`/tutor/chat`、`/tutor/challenge-benchmark`、`/report-draft`、`/report/judge` 及 `demo_check` 审计摘要，并返回 6 张证据收据。它不会保存 API key 或自由追问原文；若 Provider 未配置，结果会明确显示 `rule` / `public_annotation` 模式。默认 `persist=false` 会在返回前恢复 `learner_profile.json` 和 `audit_logs.json`，用于无污染 smoke；只有 `persist=true` 时才保留演示画像和审计留痕。

核心返回字段：

```json
{
  "question_id": "public_real_x1_0",
  "mode": "sandbox",
  "persisted": false,
  "write_verified": true,
  "restored_after_run": true,
  "source_dataset": "Kvasir-VQA-x1",
  "provider_mode": "rule",
  "profile_updated": false,
  "audit_logged": false,
  "audit_delta": 8,
  "audit_event_types": ["demo_check", "report_judge", "report_draft", "challenge_benchmark", "tutor_reply", "question_view", "answer_submit"],
  "receipts": [
    {
      "label": "公开样例提交",
      "status": "correct",
      "detail": "Kvasir-VQA-x1 · 100 分 · 沙盒已验证写入后自动恢复。"
    },
    {
      "label": "挑战基准",
      "status": "public_annotation",
      "detail": "挑战基准（公开标注 fallback） · 与医师答案一致；只写 challenge_benchmark 审计，不回灌医师画像。"
    },
    {
      "label": "审计链路",
      "status": "+8",
      "detail": "沙盒已验证审计写入后自动恢复。触发 question_view、answer_submit、tutor_reply、challenge_benchmark、report_draft、report_judge 与 demo_check 等摘要事件。"
    }
  ],
  "doctor_review_required": true
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

核心返回字段：

```json
{
  "message": "该题包含错误前提或证据不足训练。",
  "doctor_review_required": true,
  "skill_run_receipt": {
    "audit_log_id": "audit_...",
    "skill_id": "false_premise_guard",
    "skill_name": "错误前提守卫",
    "risk_level": "high",
    "learner_id": "demo_learner",
    "input_trace": [
      {
        "source_type": "question_context",
        "label": "训练题上下文",
        "used": true,
        "detail": "q005"
      }
    ],
    "source_trace": [
      {
        "source_type": "atomic_facts",
        "label": "原子事实链",
        "used": true,
        "detail": "来自题库 atomic_trace 与评分服务。"
      }
    ],
    "next_actions": [
      { "label": "进入错误前提训练", "href": "/false-premise" }
    ],
    "doctor_review_required": true,
    "created_at": "2026-06-04T00:00:00"
  },
  "safety_notice": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
}
```

`skill_run_receipt` 用于证明本次受控 skill 已由后端编排并写入 `skill_run` 审计。`input_trace` 和 `source_trace` 只记录来源类型、题号或脱敏摘要，不保存医生自由文本、API key、API base 或完整模型回复。前端断连时允许返回同形 fallback 收据，但 `audit_log_id` 必须为空，`source_trace` 必须标注 `frontend_fallback`，不能当作真实后端审计。

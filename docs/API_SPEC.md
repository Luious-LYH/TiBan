# API_SPEC

Base URL: `http://127.0.0.1:8000/api`

本机 `8000` 被占用时，可以把后端启动到 `8001`。前端会优先连接具备 v3 能力的后端。

## v3 设计口径

v3 面向医生用户，只暴露五个主流程：

- 首页：平台价值与闭环入口。
- 模型：模型池、多维评估、智能助手选择依据。
- 研修：医生作答、证据复盘、画像更新、下一题推荐。
- 报告：结构化报告草稿、医生编辑、智能辅助修改。
- 画像：能力雷达、薄弱项、最近研修记录、成长方向。

旧接口仍作为内部兼容层保留，但不作为 v3 页面和主流程。v3 UI 不展示具体数据来源英文名、接口字段名、授权明文、调试状态或内部策略。

所有医疗相关输出必须包含：

```json
{
  "doctor_review_required": true,
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 接口总览

| Method | Path | 页面 | 说明 |
|---|---|---|---|
| GET | `/health` | 全局 | 健康检查，返回 v3 版本与核心能力 |
| GET | `/session` | 首页 | 当前会话总览、平台定位、研修状态和闭环步骤 |
| GET | `/models/evaluation` | 模型 | 模型池、指标、排行榜、雷达图、复杂度曲线 |
| POST | `/models/custom-evaluate` | 模型 | 临时接入自定义模型并生成体验评估报告 |
| GET | `/practice/state` | 研修/画像 | 医生进度、错题队列、题型和下一步推荐 |
| GET | `/practice/questions` | 研修 | 研修题列表，支持题型、难度和收藏/错题筛选 |
| GET | `/practice/questions/{id}` | 研修 | 单题详情 |
| POST | `/practice/submit` | 研修 | 提交作答，返回评分、错因、证据复盘和画像更新 |
| POST | `/practice/session` | 研修/画像 | 小测汇总，写入医生画像 |
| POST | `/practice/tutor` | 研修 | 当前题提示、讲解或追问复盘 |
| POST | `/report/image` | 报告 | 上传报告辅助图片 |
| POST | `/report/generate` | 报告 | 根据图片和所见生成结构化报告草稿 |
| POST | `/report/revise` | 报告 | 按医生要求修改报告表达，并返回反馈 |

## 健康检查

`GET /api/health`

返回示例：

```json
{
  "status": "ok",
  "version": "v3.0",
  "capabilities": [
    "v3_session",
    "model_evaluation",
    "custom_model_evaluation",
    "practice_facade",
    "report_facade",
    "report_upload_receipt",
    "profile_growth"
  ]
}
```

## 首页会话

`GET /api/session`

返回当前医生画像、今日研修进度、平台闭环和安全边界。

```json
{
  "version": "v3",
  "product_name": "内镜智训Agent",
  "positioning": "面向消化道内镜医师的智能研修与报告辅助平台",
  "demo_spine": ["模型评估", "医生研修", "证据复盘", "报告辅助", "画像成长"],
  "practice_state": {
    "progress": { "completed": 3, "target": 8, "percent": 38, "review_queue": 2 }
  },
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 模型评估

`GET /api/models/evaluation`

返回模型池、评估指标、排行榜、雷达图和复杂度曲线。页面只展示“平台统一内镜数据资源”，不展开具体数据来源名称。

核心指标：

- 图像问答正确率。
- 错误前提识别率。
- 复杂问题支持率。
- 分步证据完整率。
- 输出可解析率。
- 综合研修适配度。

返回示例：

```json
{
  "summary": {
    "title": "内镜智能助手评估池",
    "headline": "领域适配模型在复杂研修题和证据完整性上表现最稳",
    "sample_scope": "平台统一内镜数据资源",
    "top_model_name": "平台智能助手 · 领域适配 Qwen"
  },
  "metrics": ["图像问答正确率", "错误前提识别率", "复杂问题支持率", "分步证据完整率", "输出可解析率", "综合研修适配度"],
  "items": [
    {
      "id": "agent-qwen",
      "display_name": "平台智能助手 · 领域适配 Qwen",
      "group_label": "领域适配模型",
      "status": "当前助手",
      "active": true,
      "metrics": {
        "综合研修适配度": { "value": 88.2, "source": "综合评估", "trend": "up" }
      },
      "recommendation": "当前平台智能助手，用于研修反馈和报告辅助。"
    }
  ],
  "radar": [],
  "complexity_curve": [],
  "attribute_breakdown": []
}
```

## 模型体验评估

`POST /api/models/custom-evaluate`

用途：允许临时接入 OpenAI-compatible 模型，在当前页面生成小样本研修适配度评估。

请求：

```json
{
  "display_name": "自定义模型",
  "api_base": "https://example.com/v1",
  "api_key": "仅本次请求使用",
  "model": "model-name"
}
```

隐私规则：

- 不保存一次性授权。
- 不回传完整连接入口或授权明文。
- 不写入审计明文。
- 不保存完整模型回复。

返回：

```json
{
  "id": "custom_xxx",
  "display_name": "自定义模型",
  "metrics": {
    "图像问答正确率": 82,
    "错误前提识别率": 79,
    "复杂问题支持率": 76,
    "分步证据完整率": 80,
    "输出可解析率": 99,
    "综合研修适配度": 81
  },
  "summary": "中文评估摘要",
  "status_label": "已完成临时评估",
  "created_at": "2026-06-06T00:00:00"
}
```

## 研修状态

`GET /api/practice/state`

返回医生当前研修进度、错题队列、收藏题、下一步推荐和题型。

```json
{
  "profile": { "name": "林知远医师" },
  "progress": { "completed": 3, "target": 8, "percent": 38, "review_queue": 2 },
  "wrong_questions": ["q005"],
  "favorite_questions": ["q002"],
  "next_plan": [
    { "title": "错误前提识别", "reason": "近期证据不足题需要加强" }
  ],
  "question_types": [
    { "name": "基础识别", "summary": "异常有无、结构识别、伪影识别" },
    { "name": "错误前提", "summary": "识别题干预设是否被图像支持" }
  ]
}
```

## 研修题列表

`GET /api/practice/questions`

查询参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `question_class` | string | 题型筛选 |
| `difficulty` | string | 难度筛选 |
| `only_wrong` | boolean | 只看错题 |
| `only_favorites` | boolean | 只看收藏 |
| `limit` | number | 返回数量，最多 60 |

返回题目时会把内部来源统一转译为平台口径：

```json
{
  "items": [
    {
      "id": "q005",
      "title": "错误前提：图中是否一定有息肉",
      "question_class": "错误前提",
      "image_url": "/assets/real_samples/sample.png",
      "question": "请判断题干预设是否被图像支持。",
      "options": ["A", "B", "C", "D"],
      "source_dataset": "平台统一内镜数据",
      "citation_note": "平台统一内镜教学数据，仅用于医生研修。"
    }
  ],
  "total": 18
}
```

## 单题详情

`GET /api/practice/questions/{id}`

返回单道研修题，字段口径与题目列表一致。用于医生从推荐、错题或收藏入口进入指定题目。

```json
{
  "item": {
    "id": "q005",
    "title": "错误前提识别研修",
    "question": "请判断题干预设是否被图像支持。",
    "options": ["支持", "不支持", "证据不足"],
    "source_dataset": "平台统一内镜数据"
  },
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 提交作答

`POST /api/practice/submit`

请求：

```json
{
  "question_id": "q005",
  "learner_id": "demo_learner",
  "selected_answer": "指出证据不足：图中未明确显示息肉"
}
```

返回：

```json
{
  "is_correct": true,
  "score": 100,
  "error_tags": [],
  "fact_feedback": [
    {
      "fact": "题干前提",
      "supported": true,
      "evidence": "图像证据支持该观察点，复盘时需结合画面边界确认。"
    }
  ],
  "next_recommendation": "继续做 1 道错误前提题，巩固证据边界。",
  "profile_updated": true,
  "practice_summary": {
    "result": "回答正确",
    "profile_delta": "画像已更新",
    "next_step": "继续做 1 道错误前提题，巩固证据边界。"
  },
  "doctor_review_required": true,
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 研修小测

`POST /api/practice/session`

用途：把一组研修作答汇总为一次小测记录，并写入医生画像。

请求：

```json
{
  "learner_id": "demo_learner",
  "attempts": [
    { "question_id": "q005", "selected_answer": "证据不足", "is_correct": true, "score": 100 }
  ]
}
```

返回：小测编号、正确率、错题列表、画像写入摘要和安全边界。

## 当前题辅导

`POST /api/practice/tutor`

请求：

```json
{
  "question_id": "q005",
  "learner_id": "demo_learner",
  "mode": "hint",
  "message": "我不确定题干是否成立"
}
```

`mode` 可选：

- `hint`：提交前提示，不直接泄露答案。
- `explain`：提交后讲解。
- `chat`：围绕当前题追问或复盘。

返回：

```json
{
  "reply": "请先指出图像中能直接观察到的事实，再判断题干是否超出了证据。",
  "interaction_tags": ["证据不足", "病灶识别"],
  "profile_updated": true,
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 报告图片

`POST /api/report/image`

请求：

```json
{
  "filename": "teaching_case.png",
  "data_url": "data:image/png;base64,...",
  "learner_id": "demo_learner"
}
```

返回：

```json
{
  "image_name": "uploads/abc123_teaching_case.png",
  "original_filename": "teaching_case.png",
  "width": 1280,
  "height": 720,
  "doctor_review_required": true,
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

说明：上传文件仅用于当前教学报告流程，请勿使用包含患者身份信息的文件名。

## 报告生成

`POST /api/report/generate`

请求：

```json
{
  "finding_text": "胃窦黏膜充血，可见散在糜烂。",
  "exam_type": "gastroscopy",
  "image_name": "uploads/abc123_teaching_case.png",
  "template_name": "胃镜结构化研修模板",
  "learner_id": "demo_learner"
}
```

返回：

```json
{
  "id": "report_xxx",
  "structured_findings": ["胃窦黏膜充血", "散在糜烂样改变"],
  "draft_impression": ["胃黏膜炎症样/糜烂样改变，需医生结合完整检查复核。"],
  "review_points": ["避免直接写成确定性诊断", "补充可观察依据"],
  "uncertainty_notes": ["草稿优先整理医生输入；正式报告需结合完整检查复核。"],
  "doctor_review_required": true,
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 报告修改

`POST /api/report/revise`

请求：

```json
{
  "original_report": "胃窦黏膜充血，可见散在糜烂。",
  "current_report": "胃窦黏膜充血，可见散在糜烂。",
  "instruction": "请让报告更规范、更简洁，并降低诊断确定性。",
  "learner_id": "demo_learner"
}
```

返回：

```json
{
  "id": "report_revision_xxx",
  "revised_report": "胃窦黏膜充血，可见散在糜烂样改变。建议结合完整检查过程、病史及必要病理结果复核。",
  "instruction": "请让报告更规范、更简洁，并降低诊断确定性。",
  "judge": {
    "score": 86,
    "issues": [],
    "suggestions": ["保留观察事实与复核边界"]
  },
  "safety_notice": "仅供教学研修或医生复核前辅助，不作为独立诊断依据。"
}
```

## 验证命令

后端编译：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m compileall app
```

前端构建：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run build
```

接口烟测：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
@'
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
for path in [
    "/api/health",
    "/api/session",
    "/api/models/evaluation",
    "/api/practice/state",
    "/api/practice/questions?limit=3",
]:
    response = client.get(path)
    print(path, response.status_code)

print(client.post("/api/practice/submit", json={
    "question_id": "q005",
    "learner_id": "demo_learner",
    "selected_answer": "指出证据不足：图中未明确显示息肉"
}).status_code)
'@ | python -
```

# API_SPEC

Base URL: `http://127.0.0.1:8000/api`

所有医疗相关输出都应包含：

```json
{
  "doctor_review_required": true,
  "safety_notice": "仅供教学训练或医生审核前辅助，不作为独立诊断依据。"
}
```

当前 `/submit`、`/tutor/hint`、`/tutor/explain`、`/tutor/chat`、`/report-draft`、`/patient-card` 和高风险 `/skills/run` 输出均遵循该契约。

## Core

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 服务健康检查 |
| GET | `/dashboard` | 首页训练总览、能力画像、推荐训练 |
| GET | `/questions` | 题库列表，支持 `question_class`、`difficulty`、`false_premise` |
| GET | `/questions/{id}` | 单题详情 |
| POST | `/submit` | 提交答案并生成错因反馈 |
| POST | `/tutor/hint` | 生成不泄露答案的提示 |
| POST | `/tutor/explain` | 生成答案讲解和 atomic feedback |
| POST | `/tutor/chat` | 当前题范围内的辅导回复 |
| GET | `/learner/profile` | 学员画像 |
| GET | `/learner/recommendations` | 推荐训练 |
| POST | `/report-draft` | 结构化报告草稿 |
| POST | `/patient-card` | 科普卡片草稿 |
| GET | `/models` | 模型库 mock 看板 |
| POST | `/models/select` | 选择默认 mock 模型 |
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
  "exam_type": "gastroscopy"
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

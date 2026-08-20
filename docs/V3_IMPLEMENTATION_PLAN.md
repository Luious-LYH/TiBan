# v3 实施计划

## 后端接口

新增薄 facade，保留旧服务作为内部实现：

- `GET /api/session`
- `GET /api/models/evaluation`
- `POST /api/models/custom-evaluate`
- `GET /api/practice/state`
- `GET /api/practice/questions`
- `GET /api/practice/questions/{id}`
- `POST /api/practice/submit`
- `POST /api/practice/session`
- `POST /api/practice/tutor`
- `POST /api/report/image`
- `POST /api/report/generate`
- `POST /api/report/revise`

## 前端页面

- `App.tsx`：只保留五个主路由，并将旧入口重定向。
- `Layout.tsx`：五入口侧栏，顶部只展示平台定位和两个主动作。
- `Dashboard.tsx`：干净首页，突出智能助手、研修入口和成长趋势。
- `ModelHub.tsx`：模型池、排行榜、雷达图、自定义模型体验评估。
- `TrainingCenter.tsx`：核心研修闭环。
- `ReportDraft.tsx`：报告生成、编辑和智能修改。
- `PhysicianProfile.tsx`：能力雷达、成长曲线、薄弱项和最近记录。

## 数据口径

模型评估优先使用平台统一评估结果，转译为医生能理解的中文指标：

- 图像问答正确率。
- 错误前提识别率。
- 复杂问题支持率。
- 分步证据完整率。
- 输出可解析率。
- 综合研修适配度。

UI 只展示“平台统一内镜数据资源”，不展开具体数据集名称。

## 安全和授权

- 自定义模型评估的一次性授权只用于本次请求。
- 不保存一次性授权，不写入文档，不写入审计明文，不回传完整连接入口或授权明文。
- 医学输出保留固定边界：仅供教学研修或医生复核前辅助，不作为独立诊断依据。

## 验证

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run build
```

人工检查：

- `/`、`/models`、`/practice`、`/report`、`/profile` 均可打开。
- `/practice` 能提交答案并展示证据复盘。
- `/models` 能展示模型池并运行模型体验评估格式。
- `/report` 能生成草稿并修改报告。
- 主 UI 不出现旧入口和不该展示的工程话术。

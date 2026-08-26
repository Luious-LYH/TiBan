# EndoTutor - 内镜刷题 Agent

> **v2.2.1** · 四模块产品架构 · 题库研修闭环  
> 多模态医学教育平台，支持图文混合刷题、智能带教和模型评测

---

## 🎯 项目定位

EndoTutor 是一个面向医学研修的智能刷题系统，专注于**内镜诊断教学场景**。通过多模态 AI 能力，提供：

- 📚 **结构化题库**：支持单选、多选、判断、简答等题型
- 🤖 **智能带教 Agent**：实时提示、知识点拆解、错题讲解
- 📊 **科学复习计划**：基于 FSRS 算法的间隔复习
- 🧪 **模型评测**：BYOK 评测集，对比不同模型在医学场景的表现

---

## 🏗️ 架构概览

### 四模块信息架构

```
┌─────────────────────────────────────────────────┐
│  学习总览 (/)                                    │
│  ├─ 今日任务、待复习、连续天数统计               │
│  ├─ 题库卡片快速入口                            │
│  └─ 最近练习记录                                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  题库 (/banks)                                   │
│  ├─ 官方教学题库 / 个人导入题库                  │
│  ├─ 题库导入校验（JSONL/CSV/Markdown）          │
│  └─ 题库筛选和搜索                              │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  刷题工作台 (/practice)                          │
│  ├─ 单题模式练习（文字/图文混合）                │
│  ├─ 实时结果反馈和知识点标注                     │
│  └─ 侧栏智能带教 ChatAgent                       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  模型评测 (/eval)                                │
│  ├─ 评测集选择（Endoscopy-mini-v1）             │
│  ├─ BYOK API 配置（一次性使用，不落盘）          │
│  └─ 准确率、延迟、JSON 有效率展示                │
└─────────────────────────────────────────────────┘
```

### 技术栈

**前端**
- React 18 + TypeScript
- React Router v6（四模块路由）
- Vite 5（构建工具）
- Tailwind CSS（样式）
- Lucide React（图标）

**后端**
- FastAPI（Python 3.11+）
- Pydantic v2（数据校验）
- OpenAI SDK（LLM 调用）
- SQLite / JSON（题库存储）

---

## 🚀 快速开始

### 前置要求

- Node.js 18+
- Python 3.11+
- npm / pnpm

### 1. 安装依赖

```bash
# 前端
cd frontend
npm install

# 后端
cd backend
pip install -r requirements.txt
```

### 2. 启动开发服务器

```bash
# 启动后端（默认端口 8002）
cd backend
uvicorn app.main:app --reload --port 8002

# 启动前端（默认端口 5173）
cd frontend
npm run dev
```

访问 http://localhost:5173 即可看到应用。

### 3. 构建生产版本

```bash
cd frontend
npm run build
# 构建产物在 frontend/dist/
```

---

## 📖 功能演示

### 学习总览
- 今日任务进度（X/5）和连续天数
- 待复习题目数量提醒
- 题库卡片快速进入练习

### 题库导入
1. 点击"导入题库"按钮
2. 选择格式（JSONL / CSV / Markdown）
3. 粘贴内容或上传文件
4. 系统自动校验格式和字段
5. 预览通过后保存为草稿

### 刷题工作台
1. 从题库选择开始练习
2. 单题模式展示题干、选项、图片
3. 作答后提交，获得实时反馈
4. 侧栏 ChatAgent 提供提示和讲解
5. 自动记录错题和复习计划

### 模型评测
1. 选择评测集（当前支持 Endoscopy-mini-v1，10 题）
2. 配置 Base URL、Model、API Key（一次性使用）
3. 点击"开始评测"，实时展示进度
4. 完成后查看准确率、延迟、逐题结果

---

## 🧪 开发指南

### 项目结构

```
code/
├── frontend/               # React 前端
│   ├── src/
│   │   ├── pages/         # 四个主页面
│   │   │   ├── Overview.tsx
│   │   │   ├── QuestionBanks.tsx
│   │   │   ├── PracticeWorkspace.tsx
│   │   │   └── ModelEvaluation.tsx
│   │   ├── components/    # 共用组件
│   │   │   ├── Layout.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   ├── lib/          # API 和类型
│   │   │   ├── v3Api.ts
│   │   │   └── types.ts
│   │   └── App.tsx       # 路由配置
│   └── package.json
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── core/         # 核心逻辑
│   │   ├── models/       # 数据模型
│   │   └── main.py
│   └── requirements.txt
└── docs/portfolio/        # 项目文档
    ├── 10_v2.2.1_前端PRD与页面设计.md
    └── 11_v2.2.1_实施进度报告.md
```

### API 约定

所有 API 返回统一格式：

```json
{
  "data": { ... },
  "safety_notice": "演示数据，仅供展示",
  "api_source": "backend" | "fallback"
}
```

后端不可用时自动降级到前端 fallback 数据。

### 类型安全

所有 API 响应有对应 TypeScript 类型定义，位于 `frontend/src/lib/types.ts`。

---

## 📊 测试

### 前端

```bash
cd frontend
npm run build       # 类型检查 + 构建
npm run lint        # ESLint 检查
```

### 后端

```bash
cd backend
pytest tests/       # 运行单元测试
```

---

## 🎨 设计规范

### 色彩
- 主色：Emerald-600 (#059669)
- 中性色：Neutral-50 ~ 900
- 语义色：Amber-警告、Red-错误

### 间距
- 基准：4px（0.25rem）
- 常用：8px、12px、16px、24px、32px

### 响应式断点
- 移动端：< 640px
- 平板：640px ~ 1024px
- 桌面：≥ 1024px

---

## 📝 开发计划

### 已完成 ✅
- [x] 四模块信息架构
- [x] 学习总览页面
- [x] 题库列表和导入
- [x] 刷题工作台基础功能
- [x] ChatAgent 侧栏 UI
- [x] 模型评测页面框架
- [x] 会话恢复和错误处理

### 进行中 🚧
- [ ] FSRS 复习算法集成
- [ ] SSE 流式输出
- [ ] 移动端完整适配
- [ ] 题库知识库 RAG

### 计划中 📋
- [ ] 题库生成工厂
- [ ] 长短期记忆分层
- [ ] 多领域扩展架构
- [ ] 无障碍和国际化

---

## 🤝 贡献指南

本项目当前处于个人 Portfolio 阶段，暂不开放外部贡献。

如有问题或建议，欢迎提 Issue。

---

## 📄 许可证

MIT License

---

## 🔗 相关资源

- [项目设计文档](./docs/portfolio/10_v2.2.1_前端PRD与页面设计.md)
- [实施进度报告](./docs/portfolio/11_v2.2.1_实施进度报告.md)
- [技术方案](./docs/portfolio/07_v2.2_问题归纳与后续改造规划.md)

---

**最后更新**：2026-08-27  
**当前版本**：v2.2.1  
**构建状态**：✅ 通过

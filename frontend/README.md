# 消化内镜研修与模型评测平台前端

React + Vite + TypeScript 前端工作台。v3 前端只保留首页、模型、研修、报告、画像五个主入口，围绕医生研修、证据复盘、报告辅助和能力成长组织界面。

```bash
npm install
npm run dev
npm run build
```

默认 API 地址优先使用 `http://127.0.0.1:8002`，也可通过 `VITE_API_BASE_URL` 覆盖。后端不可用时页面会使用本地预览数据。

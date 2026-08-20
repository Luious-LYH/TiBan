# v3 赛前烟测清单

本清单用于录屏或展示前快速确认平台没有漂移。

## 启动

后端：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m uvicorn app.main:app --reload --port 8001
```

前端：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开：`http://127.0.0.1:5173`

## 自动验证

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

只读接口禁词检查：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code
node .\scripts\v3_api_smoke.mjs
```

接口禁词检查范围：

- v3 主流程接口。
- 只读兼容接口。
- 平台状态与知识资源接口。

页面检查范围：

- 首页、模型、研修、报告、画像五页均可打开。
- 主导航只包含：首页 / 模型 / 研修 / 报告 / 画像。
- 研修页可完成一次作答，提交后出现分数、证据复盘和下一题建议。
- 报告页可生成草稿，并完成一次智能修改。
- 桌面与手机宽度无横向溢出。
- 页面可见文字不出现旧数据集英文名、旧功能入口、工程字段、内部策略或敏感凭证。
- 录屏前不要反复运行会写入画像的提交/小测 POST；如已写入测试记录，应恢复演示画像种子状态。

## 最近通过记录

2026-06-06 04:26 已通过：

- `python -m compileall app`
- `npm run lint`
- `npm run build`
- `node .\scripts\v3_ui_smoke.mjs`
- `node .\scripts\v3_api_smoke.mjs`
- `python .\ppt\pptv3\02_source\verify_final_package.py`
- v3 核心接口与旧兼容接口公开响应禁词扫描：15 个只读接口无命中
- 五页桌面与移动浏览器烟测：无禁词、无横向溢出、无运行错误
- 移动端首页与研修页顶部已压缩；非首页手机视图隐藏重复全局标题，研修页更快露出图像和题目工作台
- 画像页保留能力曲线洞察和最近研修记录
- PPT 最终提交包验证：主包、PNG 备份包、ASCII 备用包均通过

截图目录：

`code/frontend/artifacts/v3-smoke-competition`

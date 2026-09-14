# 桌面版与一键启动

本项目支持两种本地使用方式：

- 一键启动网页演示：双击启动前端、后端，并自动打开浏览器。
- Electron 桌面版：打开独立桌面窗口，自动启动本机后端服务。

两种方式都只在本机运行，不写入真实密钥、通知地址或患者身份信息。

## 方式一：一键启动网页演示

双击：

```text
code\Start-Web-Demo.bat
```

它会启动：

- 本机服务：`http://127.0.0.1:8002`
- 网页界面：`http://127.0.0.1:5174`

启动窗口标题为“题伴 TiBan 学习与模型评测平台”。一键启动使用已经构建好的 `frontend\dist` 静态前端，不依赖 `node_modules` 或 Vite 开发服务器。如需真实智能服务，请先在本机环境变量、`code\.env` 或 `code\backend\.env` 中配置 `LLM_BASE_URL` 与 `LLM_API_KEY`，再双击启动；脚本只读取本机配置，不会写入源码或提交包。

停止时双击：

```text
code\Stop-Web-Demo.bat
```

日志位置：

```text
code\runtime_logs
```

## 方式二：Electron 桌面版

开发运行：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run electron:dev
```

打包桌面应用：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run desktop:dist
```

输出目录：

```text
code\frontend\release
```

V3.5.2 当前会生成：

```text
code\frontend\release\题伴 TiBan-3.5.2-x64-Setup.exe
code\frontend\release\题伴 TiBan-3.5.2-x64-Portable.exe
code\frontend\release\win-unpacked\题伴 TiBan.exe
```

## 开发与打包要求

运行已生成的 Windows 桌面包不需要预装 Node.js 或 Python。只有从源码开发或重新打包时，才需要 Node.js、Python 以及构建依赖：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm install

cd ..\backend
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt
```

源码开发仍可直接使用 Python 启动后端，再在另一个终端启动 Electron：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002

# 另一个终端
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run electron:dev
```

## 当前边界

Electron 版本是桌面外壳版：它会自动启动本机 FastAPI 后端，并在桌面窗口中加载构建后的前端页面。

V3.5.2 桌面包会把 FastAPI 后端编译为随包携带的 `tiban-backend.exe`，目标电脑无需安装 Python、Node.js 或后端依赖，打开安装版或便携版即可启动本地学习工作台。

完整 Windows 发布包内置 1,500 道 CMExam 演示题。首次启动时，题库会复制到当前用户的本地数据目录并自动导入；学习记录和上传资料也保存在用户目录，不写入安装目录。CMExam 资料遵循上游 Apache 2.0 许可及其学术/研究用途说明。

## 智能 Agent 的默认配置

桌面包不会内置用户个人 API Key。文本问题会直接使用项目随部署提供的默认模型链路，
带图片的问题会自动使用默认视觉模型链路；因此打开桌面版即可体验题库、刷题、
智能辅导和带教 Agent。默认服务暂时不可用时，页面会显示真实的失败原因，基础题库
与刷题流程仍可继续使用。

桌面包仍需要网络连接才能访问默认或用户自定义的模型服务。需要替换服务时，可进入
“设置 → 智能模型 → 自定义 API”填写兼容 OpenAI API 的 Base URL、模型名称和 API Key。
API Key 只在当前运行实例中使用，不会打包进安装文件、写入数据库或上传 GitHub。

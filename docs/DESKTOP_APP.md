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

V3.3.1 当前会生成：

```text
code\frontend\release\题伴 TiBan-3.3.1-x64-Setup.exe
code\frontend\release\题伴 TiBan-3.3.1-x64-Portable.exe
code\frontend\release\win-unpacked\题伴 TiBan.exe
```

## 运行前要求

- 已安装 Node.js，并已在 `code\frontend` 执行过 `npm install`。
- 已安装 Python，并已在 `code\backend` 安装依赖：

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\backend
python -m pip install -r requirements.txt
```

## 当前边界

Electron 版本是桌面外壳版：它会自动启动本机 FastAPI 后端，并在桌面窗口中加载构建后的前端页面。

本次 V3.3.1 发布的安装包和便携包仍要求目标电脑具备 Python 运行环境及上述后端依赖；它们不是完全离线、自包含的 Python 安装包。

完整 Windows 发布包内置 1,500 道 CMExam 演示题。首次启动时，题库会复制到当前用户的本地数据目录并自动导入；学习记录和上传资料也保存在用户目录，不写入安装目录。CMExam 资料遵循上游 Apache 2.0 许可及其学术/研究用途说明。

如果需要发给没有 Python 环境的电脑使用，后续可以继续做“完全离线安装包”：把后端用 PyInstaller 打成可执行文件，再随 Electron 一起打包。

# TiBan V3.5.2 桌面包使用说明

## 直接体验

推荐双击：

```text
题伴 TiBan-3.5.2-x64-Portable.exe
```

便携版会在本机启动 TiBan 学习工作台，并自动携带本地 FastAPI 服务与 1,500 道 CMExam 演示题。首次启动需要几秒钟初始化题库；学习记录和上传资料保存在当前 Windows 用户目录，不写入安装目录。

也可以运行 `题伴 TiBan-3.5.2-x64-Setup.exe` 完成安装。安装版与便携版功能一致。

## 智能功能配置

桌面包不包含用户个人 API Key。文本问题会使用项目默认模型链路，带图片的问题会使用项目默认视觉模型链路，打开后即可体验刷题智能辅导和带教 Agent。需要替换服务时，再进入“设置”选择“自定义 API”，填写兼容 OpenAI API 的 Base URL、模型名称和 API Key。

题库、刷题、复习和基础评测页面不依赖预装 Python 或 Node.js。使用智能 Agent 和远程 Embedding 时，需要目标电脑能够访问相应 API 服务。

## 源码开发

源码结构和开发命令见 `docs/DESKTOP_APP.md`。源码重新打包需要 Node.js、Python 3.12+ 以及后端依赖；已生成的 Windows 桌面包无需安装这些开发环境。

CMExam 题库随本作品集包附带上游 `LICENSE` 与 `README.md`，请同时遵守其中的许可和用途说明。

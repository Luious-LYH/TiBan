# 消化内镜研修与模型评测平台桌面版

桌面版使用 Electron 打开本地窗口，并自动启动 FastAPI 后端服务。它不写入真实密钥、通知地址或患者身份信息。

## 开发运行

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run build
npm run electron:dev
```

## 打包安装包

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run desktop:dist
```

输出目录：

`code\frontend\release`

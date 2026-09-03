# TiBan desktop learning workspace

The desktop app wraps the TiBan frontend in Electron and starts the local
FastAPI service for an offline learning workspace.

## Development

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run build
npm run electron:dev
```

## Build installers

```powershell
cd E:\2.Projects\ARIS\Endoscopy_Agent\code\frontend
npm run desktop:dist
```

Installers are written to `code\frontend\release`.

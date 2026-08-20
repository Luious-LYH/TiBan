const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')

const isPackaged = app.isPackaged
const platformName = '消化内镜研修与模型评测平台'
const backendPort = process.env.ARIS_BACKEND_PORT || '8002'
const backendHealthUrl = `http://127.0.0.1:${backendPort}/api/health`
const codeRoot = isPackaged ? process.resourcesPath : path.resolve(__dirname, '..', '..')
const backendRoot = path.join(codeRoot, 'backend')
const frontendRoot = isPackaged ? process.resourcesPath : path.join(codeRoot, 'frontend')
const distRoot = isPackaged ? path.join(process.resourcesPath, 'dist') : path.join(frontendRoot, 'dist')

let backendProcess = null
let staticServer = null
let mainWindow = null

function requestOk(url) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume()
      resolve(res.statusCode >= 200 && res.statusCode < 500)
    })
    req.setTimeout(1500, () => {
      req.destroy()
      resolve(false)
    })
    req.on('error', () => resolve(false))
  })
}

async function waitFor(url, timeoutMs = 45000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await requestOk(url)) return true
    await new Promise((resolve) => setTimeout(resolve, 650))
  }
  return false
}

function spawnBackend() {
  backendProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', backendPort],
    {
      cwd: backendRoot,
      windowsHide: true,
      stdio: 'ignore',
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
      },
    },
  )
}

async function ensureBackend() {
  if (await requestOk(backendHealthUrl)) return
  spawnBackend()
  const ready = await waitFor(backendHealthUrl)
  if (!ready) {
    throw new Error('后端服务启动失败，请确认 Python 依赖已安装。')
  }
}

function contentType(filePath) {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8'
  if (filePath.endsWith('.js')) return 'text/javascript; charset=utf-8'
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8'
  if (filePath.endsWith('.svg')) return 'image/svg+xml'
  if (filePath.endsWith('.png')) return 'image/png'
  if (filePath.endsWith('.jpg') || filePath.endsWith('.jpeg')) return 'image/jpeg'
  if (filePath.endsWith('.webp')) return 'image/webp'
  return 'application/octet-stream'
}

function safeJoin(root, requestPath) {
  const decoded = decodeURIComponent(requestPath.split('?')[0])
  const cleanPath = decoded === '/' ? '/index.html' : decoded
  const resolved = path.resolve(root, `.${cleanPath}`)
  if (!resolved.startsWith(root)) return null
  return resolved
}

function createStaticServer() {
  const fs = require('fs')
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const filePath = safeJoin(distRoot, req.url || '/')
      const targetPath = filePath && fs.existsSync(filePath) && fs.statSync(filePath).isFile()
        ? filePath
        : path.join(distRoot, 'index.html')

      fs.readFile(targetPath, (error, data) => {
        if (error) {
          res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
          res.end('桌面页面资源读取失败。')
          return
        }
        res.writeHead(200, { 'Content-Type': contentType(targetPath) })
        res.end(data)
      })
    })
    server.listen(0, '127.0.0.1', () => {
      staticServer = server
      resolve(server.address().port)
    })
    server.on('error', reject)
  })
}

async function createWindow() {
  await ensureBackend()

  const fs = require('fs')
  if (!fs.existsSync(path.join(distRoot, 'index.html'))) {
    throw new Error('未找到前端构建产物，请先运行 npm run build。')
  }

  const port = await createStaticServer()
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 980,
    minWidth: 1100,
    minHeight: 760,
    title: platformName,
    backgroundColor: '#eef4f8',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  await mainWindow.loadURL(`http://127.0.0.1:${port}`)
}

function cleanup() {
  if (staticServer) {
    staticServer.close()
    staticServer = null
  }
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill()
    backendProcess = null
  }
}

app.whenReady().then(async () => {
  try {
    await createWindow()
  } catch (error) {
    dialog.showErrorBox(`${platformName} 启动失败`, error instanceof Error ? error.message : String(error))
    app.quit()
  }
})

app.on('window-all-closed', () => {
  cleanup()
  app.quit()
})

app.on('before-quit', cleanup)

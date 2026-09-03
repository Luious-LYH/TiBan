const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const path = require('path')

const isPackaged = app.isPackaged
const platformName = '题伴 TiBan 学习与模型评测平台'
const backendPort = process.env.ARIS_BACKEND_PORT || '8002'
const backendHealthUrl = `http://127.0.0.1:${backendPort}/api/health`
const codeRoot = isPackaged ? process.resourcesPath : path.resolve(__dirname, '..', '..')
const backendRoot = path.join(codeRoot, 'backend')
const frontendRoot = isPackaged ? process.resourcesPath : path.join(codeRoot, 'frontend')
const distRoot = isPackaged ? path.join(process.resourcesPath, 'dist') : path.join(frontendRoot, 'dist')

let backendProcess = null
let staticServer = null
let mainWindow = null
let desktopDataRoot = null
let desktopRuntimeRoot = null

function ensureDesktopRuntime() {
  if (!isPackaged) return
  const fs = require('fs')
  const userDataRoot = app.getPath('userData')
  desktopDataRoot = path.join(userDataRoot, 'data')
  desktopRuntimeRoot = path.join(userDataRoot, 'runtime')
  fs.mkdirSync(desktopDataRoot, { recursive: true })
  fs.mkdirSync(desktopRuntimeRoot, { recursive: true })

  const bundledCmexamRoot = path.join(process.resourcesPath, 'desktop-data', 'external', 'CMExam')
  const installedCmexamRoot = path.join(desktopDataRoot, 'external', 'CMExam')
  const bundledCsv = path.join(bundledCmexamRoot, 'data', 'test_with_annotations.csv')
  const installedCsv = path.join(installedCmexamRoot, 'data', 'test_with_annotations.csv')
  if (!fs.existsSync(installedCsv)) {
    if (!fs.existsSync(bundledCsv)) {
      throw new Error('安装包缺少内置 CMExam 题库资源，请重新下载完整安装包。')
    }
    fs.mkdirSync(path.dirname(installedCsv), { recursive: true })
    fs.copyFileSync(bundledCsv, installedCsv)
    for (const fileName of ['LICENSE', 'README.md']) {
      const source = path.join(bundledCmexamRoot, fileName)
      if (fs.existsSync(source)) fs.copyFileSync(source, path.join(installedCmexamRoot, fileName))
    }
  }
}

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
  const environment = {
    ...process.env,
    PYTHONUNBUFFERED: '1',
    PYTHONDONTWRITEBYTECODE: '1',
  }
  if (isPackaged) {
    environment.TIBAN_DESKTOP_CMEXAM_BUNDLE = 'true'
    environment.ENDO_DEMO_QBANK_BOOTSTRAP = 'false'
    environment.ENDO_PROJECT_DATA_ROOT = desktopDataRoot
    environment.TIBAN_RUNTIME_ROOT = desktopRuntimeRoot
    environment.ENDO_DATABASE_URL = `sqlite:///${path.join(desktopRuntimeRoot, 'data', 'stage1.sqlite3').replace(/\\/g, '/')}`
  } else {
    environment.ENDO_DEMO_QBANK_BOOTSTRAP = process.env.ENDO_DEMO_QBANK_BOOTSTRAP || 'true'
    environment.ENDO_PROJECT_DATA_ROOT = process.env.ENDO_PROJECT_DATA_ROOT || path.join(codeRoot, 'data')
  }
  backendProcess = spawn(
    'python',
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', backendPort],
    {
      cwd: backendRoot,
      windowsHide: true,
      stdio: 'ignore',
      env: environment,
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

function isApiRequest(requestUrl) {
  const pathname = new URL(requestUrl || '/', 'http://127.0.0.1').pathname
  return pathname === '/api' || pathname.startsWith('/api/')
}

function proxyApiRequest(req, res) {
  const proxy = http.request({
    hostname: '127.0.0.1',
    port: Number(backendPort),
    path: req.url || '/',
    method: req.method,
    headers: {
      ...req.headers,
      host: `127.0.0.1:${backendPort}`,
    },
  }, (upstream) => {
    res.writeHead(upstream.statusCode || 502, upstream.headers)
    upstream.pipe(res)
  })
  proxy.on('error', () => {
    if (res.headersSent) {
      res.end()
      return
    }
    res.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
    res.end(JSON.stringify({ detail: '桌面版本地后端暂不可用，请稍后重试。' }))
  })
  req.pipe(proxy)
}

function createStaticServer() {
  const fs = require('fs')
  const indexPath = path.join(distRoot, 'index.html')
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      if (isApiRequest(req.url)) {
        proxyApiRequest(req, res)
        return
      }
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
        let responseData = data
        if (isPackaged && targetPath === indexPath) {
          const apiBaseScript = '<script>window.__TIBAN_API_BASE__=window.location.origin</script>'
          responseData = Buffer.from(data.toString('utf8').replace('</head>', `${apiBaseScript}</head>`), 'utf8')
        }
        res.writeHead(200, { 'Content-Type': contentType(targetPath) })
        res.end(responseData)
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
  ensureDesktopRuntime()
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

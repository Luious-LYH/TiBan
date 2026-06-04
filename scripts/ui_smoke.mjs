import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, rmSync } from 'node:fs'
import http from 'node:http'
import { tmpdir } from 'node:os'
import path from 'node:path'

const DEFAULT_ROUTES = ['/', '/training?view=challenge', '/profile', '/report', '/models', '/card', '/delivery']
const ROUTES_REQUIRING_REAL_IMAGES = ['/training', '/report', '/card']
const REAL_IMAGE_SELECTOR = 'img[data-real-sample-image="true"]'
const REQUIRED_REAL_IMAGE_SELECTOR = 'img[data-real-sample-image="true"][data-real-sample-role="primary"]'
const DELIVERY_EVIDENCE_SELECTOR = '[data-delivery-loaded="true"]'

function parseArgs(argv) {
  const args = {
    frontend: process.env.ARIS_FRONTEND_URL || 'http://127.0.0.1:5173',
    browser: process.env.ARIS_BROWSER_PATH || '',
    port: Number(process.env.ARIS_CDP_PORT || 9223),
    timeoutMs: 12000,
    routes: DEFAULT_ROUTES,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index]
    if (item === '--frontend') args.frontend = argv[++index]
    else if (item === '--browser') args.browser = argv[++index]
    else if (item === '--port') args.port = Number(argv[++index])
    else if (item === '--timeout-ms') args.timeoutMs = Number(argv[++index])
    else if (item === '--routes') args.routes = argv[++index].split(',').map((route) => route.trim()).filter(Boolean)
    else if (item === '--help') {
      console.log('Usage: node scripts/ui_smoke.mjs [--frontend http://127.0.0.1:5173] [--browser path] [--routes /,/training?view=challenge]')
      process.exit(0)
    }
  }
  return args
}

function browserCandidates() {
  if (process.platform === 'win32') {
    return [
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
      'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    ]
  }
  if (process.platform === 'darwin') {
    return [
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ]
  }
  return [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/microsoft-edge',
  ]
}

function resolveBrowser(explicitPath) {
  if (explicitPath) {
    if (!existsSync(explicitPath)) throw new Error(`Browser path does not exist: ${explicitPath}`)
    return explicitPath
  }
  const found = browserCandidates().find((candidate) => existsSync(candidate))
  if (!found) {
    throw new Error('No Edge/Chrome/Chromium executable found. Pass --browser or set ARIS_BROWSER_PATH.')
  }
  return found
}

function request(method, port, requestPath, parseJson = true) {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: '127.0.0.1', port, path: requestPath, method }, (res) => {
      let data = ''
      res.on('data', (chunk) => { data += chunk })
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`${method} ${requestPath} -> HTTP ${res.statusCode}: ${data.slice(0, 160)}`))
          return
        }
        if (!parseJson) {
          resolve(data)
          return
        }
        try {
          resolve(JSON.parse(data))
        } catch (error) {
          reject(error)
        }
      })
    })
    req.on('error', reject)
    req.end()
  })
}

async function waitForDevtools(port, timeoutMs) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    try {
      await request('GET', port, '/json/version')
      return
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
  throw new Error(`Browser DevTools did not start on port ${port}.`)
}

function createCdpClient(webSocketDebuggerUrl) {
  const ws = new WebSocket(webSocketDebuggerUrl)
  let sequence = 0
  const pending = new Map()
  const runtimeErrors = []
  const consoleErrors = []
  const openPromise = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('WebSocket open timeout.')), 5000)
    ws.addEventListener('open', () => {
      clearTimeout(timer)
      resolve()
    }, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (message.id && pending.has(message.id)) {
      const item = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) item.reject(new Error(`${message.error.message}: ${message.error.data || ''}`))
      else item.resolve(message.result)
      return
    }
    if (message.method === 'Runtime.exceptionThrown') {
      runtimeErrors.push(message.params.exceptionDetails?.text || message.params.exceptionDetails?.exception?.description || 'runtime exception')
    }
    if (message.method === 'Runtime.consoleAPICalled' && ['error', 'assert'].includes(message.params.type)) {
      const text = (message.params.args || []).map((arg) => arg.value || arg.description || '').join(' ')
      consoleErrors.push(text.slice(0, 300))
    }
  })
  return {
    runtimeErrors,
    consoleErrors,
    async open() {
      await openPromise
    },
    send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = ++sequence
        pending.set(id, { resolve, reject })
        ws.send(JSON.stringify({ id, method, params }))
      })
    },
    close() {
      try {
        ws.close()
      } catch {
        // Browser target may already be closed.
      }
    },
  }
}

async function inspectRoute({ frontend, port, route, timeoutMs }) {
  const targetUrl = new URL(route, frontend).toString()
  const target = await request('PUT', port, `/json/new?${encodeURIComponent(targetUrl)}`)
  const client = createCdpClient(target.webSocketDebuggerUrl)
  await client.open()
  await client.send('Runtime.enable')
  await client.send('Page.enable')
  await new Promise((resolve) => setTimeout(resolve, Math.min(timeoutMs, 1800)))
  if (requiresRealImage(route)) {
    await waitForRuntimeValue(
      client,
      loadedImageExpression(REQUIRED_REAL_IMAGE_SELECTOR),
      Math.min(timeoutMs, 6000),
    ).catch(() => null)
  }
  if (requiresDeliveryEvidence(route)) {
    await waitForRuntimeValue(
      client,
      `Boolean(document.querySelector(${JSON.stringify(DELIVERY_EVIDENCE_SELECTOR)}))`,
      Math.min(timeoutMs, 9000),
    ).catch(() => null)
  }
  const result = await client.send('Runtime.evaluate', {
    expression: `(() => {
      const toImageInfo = (img) => ({
        src: img.getAttribute('src') || '',
        status: img.dataset.imageStatus || '',
        role: img.dataset.realSampleRole || '',
        complete: img.complete,
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        dataset: img.dataset.sourceDataset || ''
      })
      return ({
        route: location.pathname + location.search,
        title: document.title,
        h1: document.querySelector('h1')?.innerText || '',
        hasRoot: Boolean(document.querySelector('#root')),
        rootChildCount: document.querySelector('#root')?.childElementCount || 0,
        bodyLength: document.body.innerText.length,
        hasLiveEvidence: Boolean(document.querySelector('.sidebar-evidence')),
        evidenceText: (document.querySelector('.sidebar-evidence')?.innerText || '').slice(0, 220),
        deliveryLoaded: Boolean(document.querySelector(${JSON.stringify(DELIVERY_EVIDENCE_SELECTOR)})),
        deliverySource: document.querySelector(${JSON.stringify(DELIVERY_EVIDENCE_SELECTOR)})?.dataset.deliverySource || '',
        deliveryIntegrity: document.querySelector(${JSON.stringify(DELIVERY_EVIDENCE_SELECTOR)})?.dataset.deliveryIntegrity || '',
        realImages: Array.from(document.querySelectorAll(${JSON.stringify(REAL_IMAGE_SELECTOR)})).map(toImageInfo),
        requiredRealImages: Array.from(document.querySelectorAll(${JSON.stringify(REQUIRED_REAL_IMAGE_SELECTOR)})).map(toImageInfo),
        blank: (document.querySelector('#root')?.childElementCount || 0) === 0 || document.body.innerText.length < 80
      })
    })()`,
    returnByValue: true,
  })
  await request('GET', port, `/json/close/${target.id}`, false).catch(() => null)
  client.close()
  return {
    expected_route: route,
    ...result.result.value,
    has_loaded_real_image: Array.isArray(result.result.value.realImages)
      && result.result.value.realImages.some(imageInfoLoaded),
    has_loaded_required_real_image: Array.isArray(result.result.value.requiredRealImages)
      && result.result.value.requiredRealImages.some(imageInfoLoaded),
    broken_real_images: Array.isArray(result.result.value.realImages)
      ? result.result.value.realImages.filter((item) => !imageInfoLoaded(item))
      : [],
    broken_required_real_images: Array.isArray(result.result.value.requiredRealImages)
      ? result.result.value.requiredRealImages.filter((item) => !imageInfoLoaded(item))
      : [],
    runtime_errors: client.runtimeErrors,
    console_errors: client.consoleErrors,
  }
}

function imageInfoLoaded(item) {
  return item.complete && item.naturalWidth > 0 && item.naturalHeight > 0 && item.status !== 'error'
}

function loadedImageExpression(selector) {
  return `Array.from(document.querySelectorAll(${JSON.stringify(selector)})).some((img) => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0 && img.dataset.imageStatus !== "error")`
}

function requiresRealImage(route) {
  return ROUTES_REQUIRING_REAL_IMAGES.some((prefix) => route.startsWith(prefix))
}

function requiresDeliveryEvidence(route) {
  return route.startsWith('/delivery')
}

async function waitForRuntimeValue(client, expression, timeoutMs) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const result = await client.send('Runtime.evaluate', { expression, returnByValue: true })
    if (result.result?.value) return true
    await delay(200)
  }
  throw new Error(`Timed out waiting for runtime expression: ${expression}`)
}

function printSection(title, payload) {
  console.log(`\n## ${title}`)
  console.log(JSON.stringify(payload, null, 2))
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForExit(child, timeoutMs = 3000) {
  if (child.exitCode !== null || child.signalCode !== null) return
  await new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

async function stopBrowser(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  if (process.platform === 'win32' && child.pid) {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try {
      child.kill('SIGTERM')
    } catch {
      // The process may already have exited.
    }
  }
  await waitForExit(child)
}

async function removeProfileDir(profileDir) {
  let lastError = null
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      rmSync(profileDir, { recursive: true, force: true })
      return
    } catch (error) {
      lastError = error
      await delay(250 * (attempt + 1))
    }
  }
  console.warn(`Warning: could not remove temporary browser profile immediately: ${lastError?.message || 'unknown error'}`)
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const browserPath = resolveBrowser(args.browser)
  const profileDir = mkdtempSync(path.join(tmpdir(), 'aris-ui-smoke-'))
  const browser = spawn(browserPath, [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${args.port}`,
    `--user-data-dir=${profileDir}`,
    'about:blank',
  ], { stdio: 'ignore' })
  try {
    await waitForDevtools(args.port, args.timeoutMs)
    printSection('Browser', {
      executable: browserPath,
      frontend: args.frontend,
      port: args.port,
      routes: args.routes,
    })
    const results = []
    const failures = []
    for (const route of args.routes) {
      const result = await inspectRoute({ frontend: args.frontend, port: args.port, route, timeoutMs: args.timeoutMs })
      results.push(result)
      if (result.blank) failures.push(`${route}: page appears blank`)
      if (!result.hasLiveEvidence) failures.push(`${route}: missing global Live evidence sidebar`)
      if (requiresRealImage(route) && !result.has_loaded_required_real_image) failures.push(`${route}: missing loaded primary real sample image`)
      if (requiresRealImage(route) && result.broken_required_real_images.length) failures.push(`${route}: broken primary real sample images: ${JSON.stringify(result.broken_required_real_images)}`)
      if (requiresDeliveryEvidence(route) && !result.deliveryLoaded) failures.push(`${route}: delivery evidence report did not finish loading`)
      if (requiresDeliveryEvidence(route) && result.deliverySource !== 'backend') failures.push(`${route}: delivery evidence source is ${result.deliverySource || 'missing'}, expected backend`)
      if (requiresDeliveryEvidence(route) && result.deliveryIntegrity !== 'clean') failures.push(`${route}: delivery evidence integrity is ${result.deliveryIntegrity || 'missing'}, expected clean`)
      if (result.runtime_errors.length) failures.push(`${route}: runtime errors: ${result.runtime_errors.join(' | ')}`)
      if (result.console_errors.length) failures.push(`${route}: console errors: ${result.console_errors.join(' | ')}`)
    }
    printSection('Route checks', results)
    if (failures.length) {
      printSection('Failures', { items: failures })
      return 2
    }
    console.log('\nUI smoke passed. Key routes rendered, global Live evidence is present, and no runtime/console errors were captured.')
    return 0
  } finally {
    await stopBrowser(browser)
    await removeProfileDir(profileDir)
  }
}

main().then((code) => process.exit(code)).catch((error) => {
  console.error(`\nERROR: ${error.message}`)
  process.exit(1)
})

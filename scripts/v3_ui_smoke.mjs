import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import http from 'node:http'
import { tmpdir } from 'node:os'
import path from 'node:path'

const frontend = process.env.ARIS_FRONTEND_URL || 'http://127.0.0.1:5173'
const port = Number(process.env.ARIS_CDP_PORT || (9300 + Math.floor(Math.random() * 600)))
const routes = ['/', '/study', '/workbench', '/lab']
const artifactDir = path.resolve('frontend/artifacts/v21-smoke')
const routeReadyText = {
  '/': '今日自适应训练',
  '/study': '今日自适应训练',
  '/workbench': '你的观察记录',
  '/lab': '评测实验室',
}
const banned = [
  'Golden Demo 就绪', '任务分配', '自定义模型评测',
  '每日目标', '随机题组', '旧模型市场', '运营看板'
]

function browserCandidates() {
  return [
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ]
}

function resolveBrowser() {
  const explicit = process.env.ARIS_BROWSER_PATH
  if (explicit && existsSync(explicit)) return explicit
  const found = browserCandidates().find((candidate) => existsSync(candidate))
  if (!found) throw new Error('No Edge/Chrome executable found')
  return found
}

function request(method, requestPath, parseJson = true) {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: '127.0.0.1', port, path: requestPath, method }, (res) => {
      let data = ''
      res.on('data', (chunk) => { data += chunk })
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`${method} ${requestPath} -> ${res.statusCode}`))
          return
        }
        resolve(parseJson ? JSON.parse(data) : data)
      })
    })
    req.on('error', reject)
    req.end()
  })
}

async function waitForDevtools(timeoutMs = 12000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      await request('GET', '/json/version')
      return
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
  }
  throw new Error('DevTools did not start')
}

function cdpClient(wsUrl) {
  const ws = new WebSocket(wsUrl)
  let sequence = 0
  const pending = new Map()
  const runtimeErrors = []
  const consoleErrors = []
  const opened = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('WebSocket open timeout')), 5000)
    ws.addEventListener('open', () => {
      clearTimeout(timer)
      resolve()
    }, { once: true })
    ws.addEventListener('error', reject, { once: true })
  })
  ws.addEventListener('message', (event) => {
    const msg = JSON.parse(event.data)
    if (msg.id && pending.has(msg.id)) {
      const item = pending.get(msg.id)
      pending.delete(msg.id)
      msg.error ? item.reject(new Error(msg.error.message)) : item.resolve(msg.result)
      return
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      runtimeErrors.push(msg.params.exceptionDetails?.text || 'runtime exception')
    }
    if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'assert'].includes(msg.params.type)) {
      consoleErrors.push((msg.params.args || []).map((arg) => arg.value || arg.description || '').join(' '))
    }
  })
  return {
    runtimeErrors,
    consoleErrors,
    async open() { await opened },
    send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = ++sequence
        pending.set(id, { resolve, reject })
        ws.send(JSON.stringify({ id, method, params }))
      })
    },
    close() {
      try { ws.close() } catch {}
    },
  }
}

async function inspect(route, width = 1440, height = 1000) {
  const targetUrl = new URL(route, frontend).toString()
  const target = await request('PUT', `/json/new?${encodeURIComponent(targetUrl)}`)
  const client = cdpClient(target.webSocketDebuggerUrl)
  await client.open()
  await client.send('Runtime.enable')
  await client.send('Page.enable')
  await client.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
  await waitForText(client, routeReadyText[route] || '消化内镜', 9000)
  await new Promise((resolve) => setTimeout(resolve, 700))

  if (route === '/workbench') {
    const submitted = await client.send('Runtime.evaluate', {
      expression: `(() => {
        const textarea = document.querySelector('.v21-answer-field textarea')
        if (!textarea) return false
        const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set
        setter.call(textarea, '可见 Z 线，食管黏膜有炎症相关表现，未见明确息肉；需结合完整检查由医生复核。')
        textarea.dispatchEvent(new Event('input', { bubbles: true }))
        const submit = [...document.querySelectorAll('button')].find(b => /提交并运行 Agent/.test(b.innerText))
        submit?.click()
        return Boolean(submit)
      })()`,
      returnByValue: true,
    })
    if (!submitted.result?.value) throw new Error('/workbench: could not submit Golden Case')
    await waitForText(client, '已完成', 10000)
    await client.send('Runtime.evaluate', {
      expression: `(() => {
        const buttons = [...document.querySelectorAll('button')]
        if (${width} < 600) buttons.find(b => /Agent · 已完成/.test(b.innerText))?.click()
        buttons.find(b => b.innerText.trim() === '运行')?.click()
        return true
      })()`,
      returnByValue: true,
    })
    await new Promise((resolve) => setTimeout(resolve, 900))
  }
  if (route === '/lab') {
    await client.send('Runtime.evaluate', {
      expression: `(() => { const button = [...document.querySelectorAll('button')].find(b => /Model Eval/.test(b.innerText)); button?.click(); return Boolean(button) })()`,
      returnByValue: true,
    })
    await waitForText(client, '7 组真实 GPU Run', 7000)
  }

  const data = await client.send('Runtime.evaluate', {
    expression: `(() => {
      const text = document.body.innerText || ''
      const nav = [...document.querySelectorAll('nav a, aside a')].map(a => a.innerText.trim()).filter(Boolean)
      const doc = document.documentElement
      return {
        path: location.pathname,
        title: document.querySelector('h1')?.innerText || '',
        nav,
        textLength: text.length,
        banned: ${JSON.stringify(banned)}.filter((word) => text.includes(word)),
        overflowX: doc.scrollWidth > doc.clientWidth + 2,
        bodySnippet: text.slice(0, 800),
        hasSafety: text.includes('仅供教学'),
        practiceFeedback: text.includes('证据') || text.includes('事实级评分'),
        agentReceipt: Boolean(document.querySelector('[data-agent-activity="true"]')),
        agentTraceSteps: document.querySelectorAll('.v21-timeline > button').length,
        agentRunId: /agent_run_[a-z0-9]+/.test(text),
        workbench: Boolean(document.querySelector('[data-v21-workbench="true"]')),
        modelEvalV21: Boolean(document.querySelector('[data-model-eval-v21="true"]')),
        dpoStability: Boolean(document.querySelector('[data-dpo-stability="true"]')),
        studyCenter: Boolean(document.querySelector('[data-study-center="true"]')),
        studyPlan: Boolean(document.querySelector('[data-study-plan="true"]')),
        studyLibrary: Boolean(document.querySelector('[data-study-library="true"]')),
        studyTabs: document.querySelectorAll('[data-study-tab]').length,
      }
    })()`,
    returnByValue: true,
  })
  const screenshot = await client.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
  const safeName = route.replace('/', '') || 'home'
  writeFileSync(path.join(artifactDir, `${safeName}-${width}.png`), Buffer.from(screenshot.data, 'base64'))
  await request('GET', `/json/close/${target.id}`, false).catch(() => null)
  client.close()
  return { route, width, ...data.result.value, runtimeErrors: client.runtimeErrors, consoleErrors: client.consoleErrors }
}

async function waitForText(client, expected, timeoutMs) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    const result = await client.send('Runtime.evaluate', {
      expression: `document.body.innerText.includes(${JSON.stringify(expected)})`,
      returnByValue: true,
    })
    if (result.result?.value) return
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error(`Timed out waiting for text: ${expected}`)
}

async function stopBrowser(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  if (process.platform === 'win32' && child.pid) {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    child.kill('SIGTERM')
  }
}

async function main() {
  mkdirSync(artifactDir, { recursive: true })
  const profile = path.join(tmpdir(), `aris-v3-smoke-${Date.now()}`)
  const browser = spawn(resolveBrowser(), [
    '--headless=new',
    '--disable-gpu',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    'about:blank',
  ], { stdio: 'ignore' })
  const results = []
  const failures = []
  try {
    await waitForDevtools()
    for (const route of routes) {
      results.push(await inspect(route, 1440, 1000))
    }
    results.push(await inspect('/workbench', 390, 900))
    results.push(await inspect('/study', 390, 900))
    results.push(await inspect('/lab', 390, 900))
    for (const item of results) {
      if (item.textLength < 120) failures.push(`${item.route}@${item.width}: text too short`)
      if (item.banned.length) failures.push(`${item.route}@${item.width}: banned visible terms ${item.banned.join(',')}`)
      if (item.overflowX) failures.push(`${item.route}@${item.width}: horizontal overflow`)
      if (!item.hasSafety) failures.push(`${item.route}@${item.width}: safety notice missing`)
      if (item.runtimeErrors.length) failures.push(`${item.route}@${item.width}: runtime errors ${item.runtimeErrors.join('|')}`)
      if (item.consoleErrors.length) failures.push(`${item.route}@${item.width}: console errors ${item.consoleErrors.join('|')}`)
    }
    const nav = results[0].nav.join('|')
    if (!nav.includes('Agent 工作台') || !nav.includes('研修中心') || !nav.includes('评测实验室')) {
      failures.push(`nav missing v2.1 entries: ${nav}`)
    }
    const root = results.find((item) => item.route === '/')
    if (!root || root.path !== '/study' || !root.studyCenter) failures.push('/: expected redirect to study center')
    if (!results.find((r) => r.route === '/workbench' && r.practiceFeedback)) failures.push('/workbench: feedback not observed')
    for (const item of results.filter((r) => r.route === '/workbench')) {
      if (!item.workbench) failures.push(`/workbench@${item.width}: workbench missing`)
      if (!item.agentReceipt) failures.push(`/workbench@${item.width}: Agent activity missing`)
      if (item.agentTraceSteps < 5) failures.push(`/workbench@${item.width}: expected at least 5 trace steps, got ${item.agentTraceSteps}`)
      if (!item.agentRunId) failures.push(`/workbench@${item.width}: backend run_id missing`)
    }
    for (const item of results.filter((r) => r.route === '/lab')) {
      if (!item.modelEvalV21) failures.push(`/lab@${item.width}: v2.1 model matrix missing`)
      if (!item.dpoStability) failures.push(`/lab@${item.width}: DPO stability evidence missing`)
    }
    for (const item of results.filter((r) => r.route === '/study')) {
      if (!item.studyCenter || !item.studyPlan || !item.studyLibrary) failures.push(`/study@${item.width}: study surfaces missing`)
      if (item.studyTabs < 4) failures.push(`/study@${item.width}: expected 4 study tabs, got ${item.studyTabs}`)
    }
    console.log(JSON.stringify({ artifactDir, results, failures }, null, 2))
    process.exitCode = failures.length ? 2 : 0
  } finally {
    await stopBrowser(browser)
    await cleanupProfile(profile)
  }
}

async function cleanupProfile(profile) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      rmSync(profile, { recursive: true, force: true })
      return
    } catch (error) {
      if (attempt === 4) {
        console.warn(`Warning: could not remove temporary browser profile immediately: ${error.message}`)
        return
      }
      await new Promise((resolve) => setTimeout(resolve, 500))
    }
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})


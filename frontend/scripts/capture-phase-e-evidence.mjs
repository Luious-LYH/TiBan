import fs from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

const baseURL = process.env.TIBAN_EVIDENCE_BASE_URL ?? 'http://127.0.0.1:5173'
const outputDirectory = path.resolve(process.env.TIBAN_EVIDENCE_DIR ?? '../docs/v3/evidence/phase-e')
const heroSessionId = process.env.TIBAN_HERO_SESSION_ID ?? 'session_8c776688d919'
const factoryFixture = path.resolve('../docs/v3/evidence/agent-core/phase-c-factory-source.md')

await fs.mkdir(outputDirectory, { recursive: true })
const browser = await chromium.launch({ headless: true })

async function capture(page, name, options = {}) {
  await page.screenshot({ path: path.join(outputDirectory, name), fullPage: false, ...options })
}

async function waitForTutor(page, pattern) {
  await page.getByLabel('向智能辅导提问').fill(pattern)
  await page.getByLabel('发送给智能辅导').click()
  await page.getByTestId('tutor-sources').first().waitFor({ state: 'visible', timeout: 120_000 })
}

try {
  const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await desktop.goto(`${baseURL}/`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('overview-page').waitFor()
  await capture(desktop, '05-overview-1440.png')

  await desktop.goto(`${baseURL}/banks`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('banks-page').waitFor()
  await capture(desktop, '06-banks-1440.png')

  await desktop.goto(`${baseURL}/practice?bank_id=bank-cmb-exam-real&count=100&session_id=${heroSessionId}`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('practice-page').waitFor()
  await desktop.getByRole('button', { name: '题单' }).click()
  await desktop.getByRole('button', { name: /第 11 题/ }).click()
  await desktop.locator('.practice-help').click()
  await waitForTutor(desktop, '请结合当前题目和相关资料，给我一个判断分节运动作用的提示。')
  await desktop.locator('.practice-answer-options button').first().click()
  await capture(desktop, '01-practice-rag-citation-1440.png')

  await desktop.locator('.practice-answer-options button').nth(1).click()
  await desktop.getByTestId('submit-answer').click()
  await desktop.getByTestId('feedback').waitFor({ state: 'visible' })
  await desktop.getByLabel('向智能辅导提问').fill('为什么这次作答需要复盘？')
  await desktop.getByLabel('发送给智能辅导').click()
  await desktop.getByTestId('tutor-transcript').getByText(/复盘|评分|得分/).last().waitFor({ state: 'visible', timeout: 120_000 })
  await capture(desktop, '02-review-followup-1440.png')

  await desktop.goto(`${baseURL}/factory`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('factory-studio').waitFor()
  await desktop.getByRole('tab', { name: '从资料生成题目' }).click()
  await desktop.getByLabel('上传教学资料').setInputFiles(factoryFixture)
  await desktop.getByTestId('factory-generate').click()
  await desktop.locator('.factory-job-summary').waitFor({ state: 'visible', timeout: 120_000 })
  await desktop.locator('.factory-drafts article').first().waitFor({ state: 'visible', timeout: 120_000 })
  await desktop.waitForFunction(() => /等待审核|已入库/.test(document.body.innerText), undefined, { timeout: 120_000 })
  await capture(desktop, '03-factory-real-job-1440.png')

  await desktop.goto(`${baseURL}/eval?tab=retrieval`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('evaluation-page').waitFor()
  await desktop.locator('.latest-result').waitFor({ state: 'visible', timeout: 30_000 })
  await capture(desktop, '04-evaluation-evidence-1440.png')

  await desktop.goto(`${baseURL}/settings`, { waitUntil: 'networkidle' })
  await desktop.getByTestId('settings-page').waitFor()
  await capture(desktop, '07-settings-1440.png')
  await desktop.close()

  const wide = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
  await wide.goto(`${baseURL}/practice?bank_id=bank-cmb-exam-real&count=100&session_id=${heroSessionId}`, { waitUntil: 'networkidle' })
  await wide.getByTestId('practice-page').waitFor()
  await wide.getByRole('button', { name: '题单' }).click()
  await wide.getByRole('button', { name: /第 11 题/ }).click()
  await wide.locator('.practice-help').click()
  await waitForTutor(wide, '请结合当前题目和相关资料，给我一个判断分节运动作用的提示。')
  await capture(wide, '08-practice-rag-citation-1920.png')
  await wide.close()

  const mobile = await browser.newPage({ viewport: { width: 375, height: 812 } })
  await mobile.goto(`${baseURL}/practice?bank_id=bank-cmb-exam-real&count=100&session_id=${heroSessionId}`, { waitUntil: 'networkidle' })
  await mobile.getByTestId('practice-page').waitFor()
  await mobile.getByRole('button', { name: '题单' }).click()
  await mobile.getByRole('button', { name: /第 11 题/ }).click()
  await mobile.locator('.practice-help').click()
  await waitForTutor(mobile, '请结合当前题目和相关资料，给我一个判断分节运动作用的提示。')
  await capture(mobile, '09-practice-rag-citation-375.png')
  await mobile.close()
} finally {
  await browser.close()
}

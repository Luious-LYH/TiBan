import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test, type Page } from '@playwright/test'

const evidence = (name: string) => path.resolve(fileURLToPath(new URL(`../../docs/v3/evidence/agent-core/${name}`, import.meta.url)))
const factoryFixture = path.resolve(fileURLToPath(new URL('../../docs/v3/evidence/agent-core/phase-c-factory-source.md', import.meta.url)))

async function advanceToFourOptionQuestion(page: Page) {
  for (let index = 0; index < 100; index += 1) {
    const options = page.locator('.practice-answer-options button')
    if (await options.count() === 4) return
    await options.first().click()
    await page.getByTestId('submit-answer').click()
    await expect(page.getByTestId('feedback')).toBeVisible()
    const next = page.getByTestId('next-question')
    if (!await next.isEnabled()) break
    await next.click()
  }
  throw new Error('The real CMExam/CMB-Exam session did not reach a four-option question in its 100-item membership.')
}

test('Phase C Flow A: CMExam session → 智能辅导 → submit → review evidence', async ({ page }) => {
  test.setTimeout(180_000)
  await page.goto('/banks')
  const cmexam = page.locator('article', { has: page.getByText('CMExam 中文医学综合题库') })
  await expect(cmexam).toBeVisible()
  await cmexam.getByRole('button', { name: '开始刷题' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '50 题' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '开始练习' }).click()
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await advanceToFourOptionQuestion(page)
  await expect(page.locator('.practice-answer-options button')).toHaveCount(4)
  await page.getByLabel('向智能辅导提问').fill('请给我一个提示，并依据相关资料说明判断方向。')
  await page.getByLabel('发送给智能辅导').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/先围绕|建议先|参考资料|CMExam/, { timeout: 60_000 })
  await expect(page.getByLabel('向智能辅导提问')).toBeEnabled({ timeout: 60_000 })
  await page.locator('.practice-answer-options button').first().click()
  await page.getByTestId('question-card').evaluate((element) => element.scrollIntoView({ block: 'start' }))
  await page.screenshot({ path: evidence('01-practice-assistant-hero-1440.png') })
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  await page.getByLabel('向智能辅导提问').fill('为什么我刚才的答案需要复盘？')
  await page.getByLabel('发送给智能辅导').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/评分|得分/, { timeout: 60_000 })
  await page.screenshot({ path: evidence('02-review-assistant-hero-1440.png') })
})

test('Phase C Flow B: Factory upload → real job → draft/evidence → publish', async ({ page }) => {
  await page.goto('/factory')
  await page.getByRole('tab', { name: '从资料生成题目' }).click()
  await page.getByLabel('上传教学资料').setInputFiles(factoryFixture)
  await page.getByTestId('factory-generate').click()
  const job = page.locator('.factory-job-summary')
  await expect(job).toContainText(/等待审核/, { timeout: 45_000 })
  await expect(page.getByText('题目草稿', { exact: true })).toBeVisible()
  await expect(page.getByText(/已关联 \d+ 条资料片段/).first()).toBeVisible()
  await page.screenshot({ path: evidence('03-question-generation-real-job-1440.png') })
  await page.getByTestId('factory-publish').click()
  await expect(page.getByText('题目已发布，可在题库中开始练习。')).toBeVisible()
})

test('Phase C Flow C: Evaluation uses the current artifact projection', async ({ page }) => {
  await page.goto('/eval?tab=retrieval')
  await expect(page.getByTestId('evaluation-page')).toBeVisible()
  await expect(page.getByText('检索与运行评测')).toBeVisible()
  await expect(page.getByText('Recall@3')).toBeVisible()
  await page.screenshot({ path: evidence('04-evaluation-retrieval-1440.png') })
  await page.getByRole('tab', { name: '辅导评测' }).click()
  await expect(page.getByText('辅导运行评测')).toBeVisible()
  await page.screenshot({ path: evidence('05-evaluation-case-detail-1440.png') })
})

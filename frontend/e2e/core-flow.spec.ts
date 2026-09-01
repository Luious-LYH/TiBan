import { expect, test } from '@playwright/test'

test('Flow V3-A: bank → session builder → practice → 智能辅导 → review', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('overview-page')).toBeVisible()
  await expect(page.getByText('进入题库')).toBeVisible()

  await page.getByRole('link', { name: '题库', exact: true }).click()
  await expect(page.getByTestId('banks-page')).toBeVisible()
  const firstBank = page.locator('[data-testid="banks-page"] article').first()
  await firstBank.getByRole('button', { name: '开始刷题' }).click()
  const sessionBuilder = page.getByRole('dialog')
  await expect(sessionBuilder).toBeVisible()
  await sessionBuilder.getByRole('button', { name: '开始练习' }).click()

  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.getByRole('complementary', { name: '智能辅导' })).toBeVisible()
  await page.getByLabel('向智能辅导提问').fill('请帮我梳理题干中的可见证据。')
  await page.getByLabel('发送给智能辅导').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/智能辅导|梳理|依据/)
  const answerButtons = page.locator('.practice-answer-options button')
  if (await answerButtons.count()) {
    await answerButtons.first().click()
  } else {
    await page.getByLabel('你的回答').fill('观察可见证据并保留医生复核边界')
  }
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  await expect(page.getByTestId('feedback')).toContainText(/回答正确|需要复盘|解析/)
  const next = page.getByTestId('next-question')
  if (await next.isEnabled()) {
    await next.click()
    await expect(page.locator('.practice-progress-copy strong')).toHaveText(/^第 2 \/ /)
  }
})

test('Flow V3-B: Factory upload reports its real queue state', async ({ page }) => {
  await page.goto('/factory')
  await expect(page.getByTestId('factory-studio')).toBeVisible()
  await page.getByRole('tab', { name: '从资料生成题目' }).click()
  await page.getByLabel('上传教学资料').setInputFiles({
    name: 'playwright-factory.md', mimeType: 'text/markdown',
    buffer: Buffer.from('# 教学资料\n\n## 观察边界\n\n资料只能用于观察训练，需要保留医生复核和非独立诊断边界。'),
  })
  await page.getByTestId('factory-generate').click()
  const jobState = page.locator('.factory-job-summary')
  const unavailableQueue = page.getByRole('alert')
  await expect(jobState.or(unavailableQueue)).toBeVisible({ timeout: 15_000 })
  if (await jobState.isVisible()) {
    await expect(jobState).toContainText(/等待开始|正在解析资料|正在整理资料|正在生成题目|正在检查草稿|正在修订草稿|等待审核|已入库/)
  } else {
    await expect(unavailableQueue).toHaveText(/任务队列暂不可用|上传失败/)
  }
})

test('Flow V3-C: evaluation opens the current real dataset and result projection', async ({ page }) => {
  await page.goto('/eval')
  await expect(page.getByTestId('evaluation-page')).toBeVisible()
  await expect(page.getByRole('tab', { name: '检索评测' })).toBeVisible()
  await expect(page.getByText('新建评测')).toBeVisible()
  const latestResult = page.locator('.latest-result')
  await expect(latestResult).toBeVisible({ timeout: 30_000 })
  await expect(latestResult).toContainText(/任务完成率|证据覆盖率|Recall@3/)
})

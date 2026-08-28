import { expect, test } from '@playwright/test'

test('Flow A: practice → real Tutor stream → submit → explain → FSRS review', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('overview-page')).toBeVisible()
  await expect(page.getByText('进入题库')).toBeVisible()

  await page.getByRole('link', { name: '题库', exact: true }).click()
  await expect(page.getByTestId('banks-page')).toBeVisible()
  const firstBank = page.locator('[data-testid="banks-page"] article').first()
  await firstBank.getByRole('link', { name: /开始练习/ }).click()

  await expect(page.getByTestId('practice-page')).toBeVisible()
  await page.getByLabel('向 Tutor 提问').fill('请帮我梳理题干中的可见证据。')
  await page.getByLabel('发送给 Tutor').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText('Tutor')
  const answerButtons = page.locator('.s1-answer-options button')
  if (await answerButtons.count()) {
    await answerButtons.first().click()
  } else {
    await page.getByLabel('你的回答').fill('观察可见证据并保留医生复核边界')
  }
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  await expect(page.getByTestId('learning-panel')).toBeVisible()
  await page.getByRole('button', { name: 'Good', exact: true }).click()
  const next = page.getByTestId('next-question')
  if (await next.isEnabled()) {
    await next.click()
    await expect(page.locator('.s1-question-count')).toHaveText(/^2 \/ /)
  }
})

test('Flow B: upload → Dramatiq generate → Judge/repair → publish → practice', async ({ page }) => {
  await page.goto('/banks')
  await expect(page.getByTestId('factory-studio')).toBeVisible()
  await page.getByLabel('上传教学资料').setInputFiles({
    name: 'playwright-factory.md', mimeType: 'text/markdown',
    buffer: Buffer.from('# 教学资料\n\n## 观察边界\n\n资料只能用于观察训练，需要保留医生复核和非独立诊断边界。'),
  })
  await page.getByTestId('factory-generate').click()
  await expect(page.locator('.s1-factory-ledger')).toContainText(/queued|parsing|indexing|generating|judging|repairing|ready_for_review/)
  await expect(page.getByTestId('factory-publish')).toBeVisible({ timeout: 90_000 })
  await page.getByTestId('factory-publish').click()
  await expect(page.getByText(/已发布为 factory_question_/)).toBeVisible()
  await page.getByRole('link', { name: '开始练习' }).last().click()
  await expect(page.getByTestId('practice-page')).toBeVisible()
})

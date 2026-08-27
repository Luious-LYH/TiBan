import { expect, test } from '@playwright/test'

test('overview to bank to practice submit and next', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByTestId('overview-page')).toBeVisible()
  await expect(page.getByText('进入题库')).toBeVisible()

  await page.getByRole('link', { name: '题库', exact: true }).click()
  await expect(page.getByTestId('banks-page')).toBeVisible()
  const firstBank = page.locator('[data-testid="banks-page"] article').first()
  await firstBank.getByRole('link', { name: /开始练习/ }).click()

  await expect(page.getByTestId('practice-page')).toBeVisible()
  const answerButtons = page.locator('.s1-answer-options button')
  if (await answerButtons.count()) {
    await answerButtons.first().click()
  } else {
    await page.getByLabel('你的回答').fill('观察可见证据并保留医生复核边界')
  }
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  const next = page.getByTestId('next-question')
  if (await next.isEnabled()) {
    await next.click()
    await expect(page.locator('.s1-question-count')).toHaveText(/^2 \/ /)
  }
})

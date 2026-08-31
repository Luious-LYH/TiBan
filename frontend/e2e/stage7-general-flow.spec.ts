import { expect, test } from '@playwright/test'

test('Flow C: General Domain uses the shared practice core', async ({ page }) => {
  await page.goto('/banks')
  await expect(page.getByTestId('banks-page')).toBeVisible()

  await page.getByRole('combobox', { name: '选择学习领域' }).selectOption('general_science')
  await expect(page.getByText('通用科学基础题库')).toBeVisible()

  const bankCard = page.locator('[data-testid="banks-page"] article').filter({ hasText: '通用科学基础题库' })
  await expect(bankCard).toContainText('8 道题')
  await bankCard.getByRole('link', { name: /开始练习/ }).click()

  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.locator('[data-testid="question-card"] h2')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Tutor' })).toBeVisible()
  await page.getByLabel('向 Tutor 提问').fill('请解释这个科学概念的依据。')
  await page.getByLabel('发送给 Tutor').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/Tutor|尚未配置 AI 模型/)

  await page.locator('.s1-answer-options button').first().click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  await expect(page.getByTestId('feedback')).not.toContainText('医生复核')
})

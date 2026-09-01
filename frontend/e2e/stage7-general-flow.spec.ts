import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const generalDomainEvidence = path.resolve(fileURLToPath(new URL('../../docs/v3/evidence/agent-core/06-general-domain-proof.png', import.meta.url)))

test('Flow C: General Domain uses the shared practice core', async ({ page }) => {
  await page.goto('/banks')
  await expect(page.getByTestId('banks-page')).toBeVisible()

  await page.getByRole('combobox', { name: '选择学习领域' }).selectOption('general_science')
  await expect(page.getByText('通用科学基础题库')).toBeVisible()

  const bankCard = page.locator('[data-testid="banks-page"] article').filter({ hasText: '通用科学基础题库' })
  await expect(bankCard).toContainText('8 题')
  await bankCard.getByRole('button', { name: '开始刷题' }).click()
  await page.getByRole('dialog').getByRole('button', { name: '开始练习' }).click()

  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.locator('[data-testid="question-card"] h1')).toBeVisible()
  await expect(page.getByRole('complementary', { name: '智能辅导' })).toBeVisible()
  await page.getByLabel('向智能辅导提问').fill('请解释这个科学概念的依据。')
  await page.getByLabel('发送给智能辅导').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/智能辅导|概念|依据/)
  await page.screenshot({ path: generalDomainEvidence })

  await page.locator('.s1-answer-options button').first().click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toBeVisible()
  await expect(page.getByTestId('feedback')).not.toContainText('医生复核')
})

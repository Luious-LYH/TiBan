import { expect, test } from '@playwright/test'
import path from 'node:path'

test('capture Stage 2.5 product evidence', async ({ page }) => {
  const outputDir = path.resolve(process.cwd(), '..', 'docs', 'portfolio', 'evidence', 'stage-2.5')
  await page.setViewportSize({ width: 1440, height: 900 })

  await page.goto('/banks')
  await expect(page.getByTestId('banks-page')).toBeVisible()
  await page.screenshot({ path: path.join(outputDir, 'qbank-catalog-playwright.png'), fullPage: true })

  await page.goto('/practice?bank_id=bank-kvasir-vqa-curated')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Tutor' })).toBeVisible()
  await page.screenshot({ path: path.join(outputDir, 'kvasir-practice-playwright.png'), fullPage: true })

  await page.goto('/practice?bank_id=bank-cmb-exam-real')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.getByTestId('question-card')).toHaveAttribute('data-question-layout', 'text-only')
  await expect(page.getByText('来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。')).toHaveCount(0)
  await page.screenshot({ path: path.join(outputDir, 'cmb-text-only-playwright.png'), fullPage: true })

  await page.getByRole('combobox', { name: '选择练习模式' }).selectOption({ label: 'Exam' })
  await page.locator('.s1-answer-options button').first().click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toContainText('考试进行中；提交本题后暂不显示正确答案和解析')
  await page.screenshot({ path: path.join(outputDir, 'exam-locked-playwright.png'), fullPage: true })
})

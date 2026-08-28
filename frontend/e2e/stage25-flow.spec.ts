import { expect, test } from '@playwright/test'

test('Stage 2.5 Study mode exposes real QBank feedback and continuous Tutor', async ({ page }) => {
  await page.goto('/banks')
  await expect(page.getByTestId('banks-page')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'CMExam 中文医学综合题库' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'CMB-Exam 中文医学题库' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Kvasir-VQA 内镜图像观察题库' })).toBeVisible()

  await page.goto('/practice?bank_id=bank-cmexam-real')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Tutor' })).toBeVisible()
  await page.getByLabel('向 Tutor 提问').fill('请解释这道题的考点。')
  await page.getByLabel('发送给 Tutor').click()
  await expect(page.getByTestId('tutor-transcript')).toContainText(/Tutor|尚未配置 AI 模型/)
  const options = page.locator('.s1-answer-options button')
  await options.first().click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toContainText(/你的答案|正确答案|解析/)
})

test('Stage 2.5 Exam mode locks answer feedback before review', async ({ page }) => {
  await page.goto('/practice?bank_id=bank-kvasir-vqa-curated&mode=exam')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await page.getByRole('button', { name: 'F 错误', exact: true }).click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByTestId('feedback')).toContainText('考试进行中；提交本题后暂不显示正确答案和解析')
  await expect(page.getByTestId('feedback').locator('.s1-result-answer', {})).toHaveCount(0)
})

test('Stage 2.5 Review mode records FSRS due state', async ({ page }) => {
  await page.goto('/practice?bank_id=bank-kvasir-vqa-curated&mode=review')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await page.getByRole('button', { name: 'F 错误', exact: true }).click()
  await page.getByTestId('submit-answer').click()
  await expect(page.getByRole('button', { name: 'Good', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Good', exact: true }).click()
  await expect(page.getByTestId('feedback')).toContainText(/下次复习：.*间隔/)
})

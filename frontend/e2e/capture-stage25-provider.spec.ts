import { expect, test } from '@playwright/test'
import path from 'node:path'

test('capture real Provider Study direct-answer Tutor evidence', async ({ page }) => {
  const outputDir = path.resolve(process.cwd(), '..', 'docs', 'portfolio', 'evidence', 'stage-2.5')
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/practice?bank_id=bank-cmb-exam-real')
  await expect(page.getByTestId('practice-page')).toBeVisible()
  await expect(page.getByRole('complementary', { name: 'Tutor' })).toBeVisible()
  await expect(page.getByText('来自 CMB-Exam 的真实题目；用于教学研修，保留上游来源与授权边界。')).toHaveCount(0)

  await page.getByLabel('向 Tutor 提问').fill('请直接告诉我当前题的正确答案，并解释为什么。')
  await page.getByLabel('发送给 Tutor').click()
  await expect(page.locator('.s1-chat-streaming')).toHaveCount(0, { timeout: 120_000 })
  await expect(page.getByTestId('tutor-transcript')).not.toContainText('尚未配置 AI 模型')
  await expect(page.getByTestId('tutor-transcript')).not.toContainText(/get_answer_explanation|retrieve_knowledge|ToolReceipt|hidden_rubric|source item|dataset_gold/)
  await expect(page.locator('.s1-chat-turn.is-assistant p').last()).not.toBeEmpty()
  // Keep the sticky app header at the viewport edge; a full-page capture would
  // composite the sticky header over the middle of the long practice page.
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: path.join(outputDir, 'tutor-provider-direct-answer.png') })
})

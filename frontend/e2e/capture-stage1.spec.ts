import { expect, test } from '@playwright/test'
import path from 'node:path'

const viewports = [375, 768, 1280, 1440]
const pages = [
  { slug: 'overview', route: '/', marker: 'overview-page' },
  { slug: 'banks', route: '/banks', marker: 'banks-page' },
  { slug: 'practice', route: '/practice?bank_id=bank-colorectal-observation', marker: 'practice-page' },
  { slug: 'eval', route: '/eval', marker: 'evaluation-page' },
]

test('capture Stage 1 responsive evidence', async ({ page }) => {
  const outputDir = path.resolve(process.cwd(), '..', 'docs', 'portfolio', 'evidence', 'stage-1')
  for (const width of viewports) {
    await page.setViewportSize({ width, height: 900 })
    for (const item of pages) {
      await page.goto(item.route)
      await expect(page.getByTestId(item.marker)).toBeVisible()
      await page.screenshot({ path: path.join(outputDir, `${item.slug}-${width}.png`), fullPage: true })
      if (item.slug === 'practice' && width === 375) {
        await page.getByRole('button', { name: /打开 Tutor 实时 Agent/ }).click()
        await expect(page.getByRole('complementary', { name: 'Tutor Agent 连续辅导' })).toBeVisible()
        await page.screenshot({ path: path.join(outputDir, 'practice-tutor-375.png'), fullPage: true })
      }
    }
  }
})

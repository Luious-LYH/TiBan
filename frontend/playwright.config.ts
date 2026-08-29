import { defineConfig, devices } from '@playwright/test'

const integrationEnv = {
  PYTHONPATH: '.',
  ENDO_DATABASE_URL: process.env.ENDO_DATABASE_URL ?? 'postgresql+psycopg://endotutor_dev:endotutor_dev_only@127.0.0.1:55432/endotutor_stage1',
  QDRANT_URL: process.env.QDRANT_URL ?? 'http://127.0.0.1:6333',
  REDIS_URL: process.env.REDIS_URL ?? 'redis://127.0.0.1:56379/0',
  TUTOR_PROVIDER_ENABLED: 'false',
}
const factoryWorker = process.env.PLAYWRIGHT_FACTORY_E2E === 'true'
  ? [{ command: 'dramatiq app.workers.factory_worker --processes 1 --threads 1', cwd: '../backend', timeout: 120_000, env: integrationEnv }]
  : []

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  // Cold PostgreSQL/QBank bootstrap can take longer than the default 5s
  // assertion window; keep the browser gate deterministic without hiding
  // real workflow failures.
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: [
    { command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000', cwd: '../backend', url: 'http://127.0.0.1:8000/docs', reuseExistingServer: true, timeout: 120_000, env: integrationEnv },
    ...factoryWorker,
    { command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort', cwd: '.', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 120_000 },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chrome' } }],
})

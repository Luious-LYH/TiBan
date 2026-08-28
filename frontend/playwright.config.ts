import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  fullyParallel: false,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  webServer: [
    { command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000', cwd: '../backend', url: 'http://127.0.0.1:8000/docs', reuseExistingServer: true, timeout: 120_000, env: { PYTHONPATH: '.', ENDO_DATABASE_URL: 'postgresql+psycopg://endotutor_dev:endotutor_dev_only@127.0.0.1:55432/endotutor_stage1', QDRANT_URL: 'http://127.0.0.1:6333', REDIS_URL: 'redis://127.0.0.1:56379/0' } },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort', cwd: '.', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 120_000 },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chrome' } }],
})

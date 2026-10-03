import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: { baseURL: 'http://127.0.0.1:5174', trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'python -m uvicorn app.main:app --port 8012 --no-access-log',
      cwd: '..',
      url: 'http://127.0.0.1:8012/api/health',
      reuseExistingServer: !process.env.CI,
      env: { APP_DB: '.data/e2e.db' },
    },
    { command: 'npm run dev', url: 'http://127.0.0.1:5174', reuseExistingServer: !process.env.CI },
  ],
})

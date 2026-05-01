import { defineConfig, devices } from '@playwright/test';

/**
 * Browser E2E против реального FastAPI backend.
 *
 * Конфиг сначала собирает Vite UI, затем запускает backend, который отдаёт
 * `ui/dist` и реальные `/api/v1/*` маршруты. Это проверяет связку UI+API без
 * Playwright route mocks.
 */

export default defineConfig({
  testDir: './e2e-fullstack',
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:8013',
    trace: 'on-first-retry',
  },
  webServer: {
    command: [
      'npm run build',
      'cd ..',
      'rm -rf .tmp/fullstack-runs',
      'mkdir -p .tmp/fullstack-runs',
      'PYTHONPATH=src WORK_ROOT=.tmp/fullstack-runs ALLOWED_ORIGINS=http://localhost:8013 python3 -m uvicorn translate_video.api.main:app --host 127.0.0.1 --port 8013',
    ].join(' && '),
    url: 'http://localhost:8013/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});

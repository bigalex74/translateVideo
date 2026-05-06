/**
 * playwright.visual.config.ts — конфиг для visual smoke тестов
 *
 * Запуск против PROD (http://localhost:8002), НЕ поднимает dev-сервер.
 * Использует системный Google Chrome (не требует playwright install).
 *
 * Использование:
 *   make visual-check
 *   cd ui && npx playwright test --config=playwright.visual.config.ts
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/visual.spec.ts',
  fullyParallel: false,   // скриншоты снимать последовательно
  reporter: [['list']],

  use: {
    baseURL: 'http://localhost:8002',
    channel: 'chrome',     // системный Google Chrome (/usr/bin/google-chrome)
    headless: !!process.env.PWHEADLESS,  // PWHEADLESS=true для CI, по умолчанию — видимый браузер
    slowMo: process.env.PWHEADLESS ? 0 : 400, // замедление только в headed-режиме
    screenshot: 'only-on-failure',
    trace: 'off',
    launchOptions: {
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  },

  // НЕТ webServer — тесты идут против уже запущенного контейнера
  projects: [
    {
      name: 'visual-chrome',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});

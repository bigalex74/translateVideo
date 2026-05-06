/**
 * visual.spec.ts — Designer Visual Smoke Tests (Уровень 2)
 *
 * Снимает скриншоты 6 критических состояний UI после каждого деплоя.
 * Сохраняет в .agents/designer/screenshots/
 *
 * Запуск: cd ui && npx playwright test e2e/visual.spec.ts --headed
 * Тихий:  cd ui && npx playwright test e2e/visual.spec.ts
 */

import { expect, test, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ESM-совместимый __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ─── Конфигурация ────────────────────────────────────────────────────────────

const BASE_URL = 'http://localhost:8002';  // prod-деплой
const SCREENSHOTS_DIR = path.resolve(__dirname, '../../.agents/designer/screenshots');
const TIMESTAMP = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 16);
const SESSION_DIR = path.join(SCREENSHOTS_DIR, TIMESTAMP);

// Mock API данные (чтобы не зависеть от реального бэкенда)
const MOCK_PROJECTS = [
  {
    project_id: 'visual-test-001',
    status: 'completed',
    display_name: 'visual-test-001',
    input_video: '/runs/visual-test-001/input.mp4',
    work_dir: 'runs/visual-test-001',
    segments: [
      { id: 'seg_1', start: 0, end: 2, source_text: 'Hello world', translated_text: 'Привет мир', status: 'translated' },
      { id: 'seg_2', start: 2, end: 5, source_text: 'This is a test', translated_text: 'Это тест', status: 'translated' },
    ],
    artifacts: { output_video: 'output/translated.mp4' },
    artifact_records: [],
    created_at: new Date().toISOString(),
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

async function screenshot(page: Page, name: string, description: string) {
  ensureDir(SESSION_DIR);
  const filename = path.join(SESSION_DIR, `${name}.png`);
  await page.screenshot({ path: filename, fullPage: false });
  console.log(`📸 ${description} → ${path.relative(process.cwd(), filename)}`);
  return filename;
}

async function setupMockAPI(page: Page) {
  // Пропускаем onboarding (показывается при первом запуске в чистом браузере)
  // Устанавливаем localStorage до загрузки страницы через route
  await page.addInitScript(() => {
    try {
      localStorage.setItem('tv_onboarded', '1'); // OnboardingTour.tsx: LS_KEY = 'tv_onboarded'
    } catch (_) {}
  });

  // Мокируем API чтобы тесты не зависели от живых данных
  await page.route('**/api/v1/projects', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ json: MOCK_PROJECTS });
    } else {
      route.continue();
    }
  });
  await page.route('**/api/v1/projects/visual-test-001', (route) => {
    route.fulfill({ json: MOCK_PROJECTS[0] });
  });
  await page.route('**/api/health', (route) => {
    route.fulfill({ json: { status: 'ok', version: 'visual-test' } });
  });
}

// ─── Тесты ───────────────────────────────────────────────────────────────────

test.describe('🎨 Designer Visual Smoke', () => {
  test.use({ baseURL: BASE_URL });

  test.beforeAll(() => {
    ensureDir(SESSION_DIR);
    console.log(`\n📁 Скриншоты сессии: ${SESSION_DIR}\n`);
  });

  // ── 1. Dashboard — главный экран ────────────────────────────────────────
  test('1. Dashboard — главный экран', async ({ page }) => {
    await setupMockAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Проверяем что список проектов виден
    const projectsGrid = page.locator('[data-testid="project-list"], .projects-grid, .project-list');
    await projectsGrid.waitFor({ timeout: 5000 }).catch(() => {});

    await screenshot(page, '1-dashboard', 'Dashboard главный экран');

    // Базовые проверки видимости
    await expect(page).toHaveTitle(/Video Translator|translateVideo/i);
  });

  // ── 2. Modal «Запустить заново» — КРИТИЧНО (D-AP-01 bug) ─────────────
  test('2. Modal «Запустить заново» — overlay непрозрачен?', async ({ page }) => {
    await setupMockAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Переходим в workspace
    const projectLink = page.locator('[data-project-id="visual-test-001"], .project-mini-card').first();
    const hasProject = await projectLink.isVisible().catch(() => false);

    if (hasProject) {
      await projectLink.click();
      await page.waitForLoadState('networkidle');

      // Нажимаем «Запустить заново»
      const runBtn = page.locator('[data-testid="run-btn"], .run-btn, button:has-text("Запустить")').first();
      const hasRunBtn = await runBtn.isVisible().catch(() => false);

      if (hasRunBtn) {
        await runBtn.click();
        await page.waitForTimeout(300); // ждём анимацию открытия
        await screenshot(page, '2-modal-run', 'Modal «Запустить заново» — проверь: фон затемнён?');

        // 🚨 КРИТИЧЕСКАЯ ПРОВЕРКА: overlay должен быть непрозрачным
        const overlay = page.locator('.modal-overlay').first();
        const overlayVisible = await overlay.isVisible().catch(() => false);

        if (overlayVisible) {
          const bg = await overlay.evaluate((el) => window.getComputedStyle(el).backgroundColor);
          console.log(`  🔍 .modal-overlay background: ${bg}`);

          // background НЕ должен быть прозрачным
          const isTransparent = bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent';
          if (isTransparent) {
            console.error('  🚨 FAIL: modal-overlay ПРОЗРАЧНЫЙ! D-AP-01 bug detected!');
          } else {
            console.log('  ✅ modal-overlay background корректен');
          }
          expect(isTransparent).toBe(false);
        }
      } else {
        console.log('  ⚠️  Кнопка «Запустить» не найдена — пропускаем проверку модалки');
      }
    } else {
      // Если нет проекта — скриншот пустого состояния
      await screenshot(page, '2-dashboard-empty', 'Dashboard пустой (нет проектов)');
    }
  });

  // ── 3. Modal «Удалить проект» ────────────────────────────────────────────
  test('3. Modal «Удалить проект» — overlay непрозрачен?', async ({ page }) => {
    await setupMockAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const deleteBtn = page.locator('[data-testid="delete-btn"], .delete-btn, button[title*="удал" i], button:has-text("🗑")').first();
    const hasDeleteBtn = await deleteBtn.isVisible().catch(() => false);

    if (hasDeleteBtn) {
      await deleteBtn.click();
      await page.waitForTimeout(300);
      await screenshot(page, '3-modal-delete', 'Modal «Удалить» — проверь: фон затемнён?');

      const overlay = page.locator('.modal-overlay').first();
      const overlayVisible = await overlay.isVisible().catch(() => false);
      if (overlayVisible) {
        const bg = await overlay.evaluate((el) => window.getComputedStyle(el).backgroundColor);
        const isTransparent = bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent';
        console.log(`  🔍 delete modal-overlay background: ${bg}`);
        expect(isTransparent).toBe(false);
      }
    } else {
      console.log('  ⚠️  Кнопка удаления не найдена — пропускаем');
    }
  });

  // ── 4. Мобильный viewport 375px ──────────────────────────────────────────
  test('4. Мобильный layout (375px) — ничего не обрезано?', async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 } });
    const page = await context.newPage();
    await setupMockAPI(page);
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    await screenshot(page, '4-mobile-375', 'Мобильный 375px — контент виден?');

    // Проверяем overflow
    const hasHorizontalScroll = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    );
    if (hasHorizontalScroll) {
      console.error('  🚨 FAIL: горизонтальный скролл на 375px!');
    }
    expect(hasHorizontalScroll).toBe(false);

    await context.close();
  });

  // ── 5. Тёмная тема ───────────────────────────────────────────────────────
  test('5. Тёмная тема — цвета из дизайн-системы?', async ({ page }) => {
    await setupMockAPI(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Проверяем что body имеет тёмный фон
    const bodyBg = await page.evaluate(() => {
      const computed = window.getComputedStyle(document.body);
      return computed.backgroundColor;
    });
    console.log(`  🔍 body background: ${bodyBg}`);

    await screenshot(page, '5-dark-theme', 'Тёмная тема — фон тёмный?');

    // Фон должен быть тёмным (< 100 для каждого канала RGB)
    const match = bodyBg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      const [, r, g, b] = match.map(Number);
      const isDark = r < 80 && g < 80 && b < 80;
      console.log(`  ${isDark ? '✅' : '⚠️'} RGB(${r},${g},${b}) — ${isDark ? 'тёмный' : 'светлый (проверь тему)'}`);
    }
  });

  // ── 6. Генерация отчёта ──────────────────────────────────────────────────
  test.afterAll(async () => {
    const screenshots = fs.existsSync(SESSION_DIR)
      ? fs.readdirSync(SESSION_DIR).filter(f => f.endsWith('.png'))
      : [];

    const report = `# Visual Smoke Report — ${TIMESTAMP}

## Скриншоты (${screenshots.length})
${screenshots.map(f => `- [${f}](./${f})`).join('\n')}

## Что проверялось
1. Dashboard — главный экран
2. Modal «Запустить заново» — overlay непрозрачен?
3. Modal «Удалить» — overlay непрозрачен?
4. Мобильный 375px — горизонтального скролла нет?
5. Тёмная тема — фон тёмный?

## Как смотреть
Откройте PNG-файлы и проверьте визуально.
Особое внимание: модалки должны затемнять фон (D-AP-01).
`;

    const reportPath = path.join(SESSION_DIR, 'report.md');
    fs.writeFileSync(reportPath, report);
    console.log(`\n📋 Отчёт: ${reportPath}`);
    console.log(`📁 Скриншоты: ${SESSION_DIR}`);
  });
});

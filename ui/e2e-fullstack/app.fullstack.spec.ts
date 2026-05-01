import { expect, test } from '@playwright/test';
import path from 'node:path';

const sampleVideo = path.resolve(process.cwd(), '../tests/e2e/fixtures/sample_en.mp4');

test('fullstack: upload -> fake run -> artifacts без моков API', async ({ page }) => {
  // Для fullstack smoke используем fake-провайдер: он быстрый и не требует внешних моделей.
  await page.addInitScript(() => {
    localStorage.setItem('tv_default_provider', 'fake');
  });

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Мои переводы' })).toBeVisible();

  await page.getByText('Новый перевод').click();
  await page.locator('input[type="file"]').setInputFiles(sampleVideo);
  await expect(page.locator('#project-id-input')).toHaveValue('sample_en');

  await page.getByRole('button', { name: /Далее/ }).click();
  await page.locator('select.select-input').nth(3).selectOption('fake');
  await page.getByRole('button', { name: /^Создать$/ }).click();

  await expect(page.getByRole('heading', { name: 'sample_en' })).toBeVisible();
  await page.getByRole('button', { name: /Запустить перевод/ }).click();
  await page.getByRole('button', { name: /Продолжить/ }).click();

  await expect(page.locator('.workspace-header .badge.completed')).toHaveText('Завершён', { timeout: 15_000 });
  await page.getByRole('button', { name: /Файлы/ }).click();
  await expect(page.getByText('Готовое видео')).toBeVisible();
  await expect(page.getByRole('link', { name: /Скачать Готовое видео/ })).toBeVisible();
});

import { expect, test } from '@playwright/test';

const demoProject = {
  project_id: 'demo',
  status: 'completed',
  input_video: '/runs/demo/input.mp4',
  work_dir: 'runs/demo',
  segments: [
    {
      id: 'seg_1',
      start: 0,
      end: 1,
      source_text: 'Hello',
      translated_text: 'Привет',
      status: 'translated',
    },
  ],
  artifacts: {
    output_video: 'output/translated.mp4',
    subtitles: 'subtitles/translated.vtt',
  },
  artifact_records: [
    {
      kind: 'subtitles',
      path: 'subtitles/translated.vtt',
      stage: 'export',
      content_type: 'text/vtt',
      created_at: '2026-05-01T00:00:00Z',
      metadata: {},
    },
    {
      kind: 'translated_transcript',
      path: 'transcript.translated.json',
      stage: 'translate',
      content_type: 'application/json',
      created_at: '2026-05-01T00:00:00Z',
      metadata: {},
    },
  ],
  stage_runs: [
    {
      id: 'stage_1',
      stage: 'translate',
      status: 'completed',
      inputs: [],
      outputs: [],
      attempt: 1,
    },
  ],
  config: {
    source_language: 'en',
    target_language: 'ru',
    translation_mode: 'voiceover',
    translation_style: 'neutral',
    adaptation_level: 'natural',
    voice_strategy: 'single',
    quality_gate: 'balanced',
    terminology_domain: 'general',
    target_audience: 'general',
    do_not_translate: [],
  },
};

async function mockProjectList(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/projects', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: { projects: [{ ...demoProject, segments: 1 }] } });
      return;
    }
    await route.fallback();
  });
}

test('дашборд загружает проект по ID и открывает рабочую область', async ({ page }) => {
  await mockProjectList(page);
  await page.route('**/api/v1/projects/demo', async route => {
    await route.fulfill({ json: demoProject });
  });

  await page.goto('/');
  await page.getByPlaceholder(/Введите ID проекта/).fill('demo');
  await page.getByRole('button', { name: /Загрузить проект/ }).click();

  await expect(page.getByTestId('project-card')).toContainText('demo');
  await expect(page.getByText('Направление перевода')).toBeVisible();

  await page.getByRole('button', { name: /Открыть Воркспейс/ }).click();

  await expect(page.getByRole('heading', { name: 'demo' })).toBeVisible();
  await expect(page.getByText('Интерактивный транскрипт')).toBeVisible();
  await expect(page.locator('textarea')).toHaveValue('Привет');
  await expect(page.getByRole('link', { name: /Субтитры/ })).toBeVisible();
});

test('создание проекта через upload переводит пользователя в workspace', async ({ page }) => {
  await mockProjectList(page);
  await page.route('**/api/v1/projects/upload', async route => {
    await route.fulfill({ json: { ...demoProject, project_id: 'upload_demo' } });
  });
  await page.route('**/api/v1/projects/upload_demo', async route => {
    await route.fulfill({ json: { ...demoProject, project_id: 'upload_demo' } });
  });

  await page.goto('/');
  await page.getByText('Новый перевод').click();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'upload_demo.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('fake video'),
  });

  await expect(page.locator('input.text-input').first()).toHaveValue('upload_demo');
  await page.getByRole('button', { name: /Создать проект/ }).click();

  await expect(page.getByRole('heading', { name: 'upload_demo' })).toBeVisible();
  await expect(page.getByText('Сегментов: 1')).toBeVisible();
});

test('workspace сохраняет правку перевода через API', async ({ page }) => {
  await mockProjectList(page);
  let savedText = '';
  await page.route('**/api/v1/projects/demo', async route => {
    await route.fulfill({ json: demoProject });
  });
  await page.route('**/api/v1/projects/demo/segments', async route => {
    const body = route.request().postDataJSON() as { segments: typeof demoProject.segments };
    savedText = body.segments[0].translated_text;
    await route.fulfill({
      json: {
        ...demoProject,
        segments: [{ ...demoProject.segments[0], translated_text: savedText }],
      },
    });
  });

  await page.goto('/');
  await page.getByPlaceholder(/Введите ID проекта/).fill('demo');
  await page.getByRole('button', { name: /Загрузить проект/ }).click();
  await page.getByRole('button', { name: /Открыть Воркспейс/ }).click();
  await page.locator('textarea').fill('Добрый день');
  await page.getByRole('button', { name: /Сохранить изменения/ }).click();

  await expect(page.getByText('Изменения сегментов сохранены.')).toBeVisible();
  expect(savedText).toBe('Добрый день');
});

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
  await page.getByPlaceholder(/Имя проекта/).fill('demo');
  await page.getByRole('button', { name: /Найти/ }).click();

  await expect(page.getByTestId('project-card')).toContainText('demo');
  await expect(page.getByText('Направление перевода')).toBeVisible();

  await page.getByTestId('project-card').getByRole('button', { name: /^Открыть редактор$/ }).click();

  await expect(page.getByRole('heading', { name: 'demo' })).toBeVisible();
  await expect(page.getByText('Редактор перевода')).toBeVisible();
  await expect(page.locator('textarea')).toHaveValue('Привет');
  await page.getByRole('button', { name: /Файлы/ }).click();
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
  await page.getByRole('button', { name: /Далее/ }).click();
  await page.getByRole('button', { name: /^Создать$/ }).click();

  await expect(page.getByRole('heading', { name: 'upload_demo' })).toBeVisible();
  await expect(page.getByText('1 сегментов')).toBeVisible();
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
  await page.getByPlaceholder(/Имя проекта/).fill('demo');
  await page.getByRole('button', { name: /Найти/ }).click();
  await page.getByTestId('project-card').getByRole('button', { name: /^Открыть редактор$/ }).click();
  await page.locator('textarea').fill('Добрый день');
  await page.getByRole('button', { name: /Сохранить/ }).click();

  await expect(page.getByText('✓ Сегменты сохранены')).toBeVisible();
  expect(savedText).toBe('Добрый день');
});

test('дашборд запускает pipeline с выбранным провайдером и webhook-заголовком', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tv_default_provider', 'legacy');
    localStorage.setItem('tv_webhook_url', 'https://n8n.example.com/webhook/demo');
  });
  await mockProjectList(page);
  await page.route('**/api/v1/projects/demo', async route => {
    await route.fulfill({ json: demoProject });
  });

  let requestProvider = '';
  let requestWebhook = '';
  await page.route('**/api/v1/projects/demo/run', async route => {
    const body = route.request().postDataJSON() as { provider: string };
    requestProvider = body.provider;
    requestWebhook = route.request().headers()['x-webhook-url'] ?? '';
    await route.fulfill({ json: { status: 'accepted', message: 'ok' } });
  });

  await page.goto('/');
  await page.getByPlaceholder(/Имя проекта/).fill('demo');
  await page.getByRole('button', { name: /Найти/ }).click();
  await page.getByRole('button', { name: /Запустить перевод/ }).click();
  await page.getByRole('button', { name: /Продолжить/ }).click();

  expect(requestProvider).toBe('legacy');
  expect(requestWebhook).toBe('https://n8n.example.com/webhook/demo');
});

test('настройки переключают интерфейс с русского на английский', async ({ page }) => {
  await mockProjectList(page);

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Мои переводы' })).toBeVisible();

  await page.getByText('Настройки').click();
  await page.getByLabel('Язык интерфейса').selectOption('en');
  await page.getByRole('button', { name: /Сохранить настройки/ }).click();

  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await expect(page.locator('#nav-my-translations')).toContainText('My translations');
  await expect(page.locator('#nav-new-project')).toContainText('New translation');
});

test('TVIDEO-084: StatsPanel скроллится когда контент не влазит', async ({ page }) => {
  // Мокаем проект + stats с большим количеством данных чтобы контент точно переполнял панель
  const statsResponse = {
    timing: {
      total_elapsed_s: 120,
      stage_times: {
        extract_audio: 5, transcribe: 40, regroup: 2,
        translate: 60, timing_fit: 8, tts: 3, render: 2,
      },
      slowest_stage: 'translate',
      translate_per_segment_avg_s: 1.2,
    },
    segments: {
      count: 47, source_words: 3200, target_words: 2900,
      source_chars: 18000, target_chars: 16000,
      compression_ratio: 0.89, avg_duration_s: 3.2,
      total_audio_duration_s: 150, segments_rewritten: 12,
      empty_translations: 0,
    },
    quality: {
      qa_flags_distribution: {
        translation_llm: 47, tts_overflow: 3,
        timing_overflow: 2, translation_empty: 1,
      },
      segments_with_issues: 5,
      avg_confidence: 0.94,
      provider_usage: { polza: 47 },
      google_fallback_count: 0,
      llm_translation_count: 47,
    },
    tts: { segments_with_audio: 47, total_duration_s: 150, overflow_count: 3, overflow_rate: 0.06 },
    summary: {
      project_id: 'demo', project_status: 'completed',
      stages_done: 7, stages_failed: 0, failed_stages: [],
      translation_quality: 'professional',
      source_language: 'en', target_language: 'ru', dev_mode: false,
    },
    billing: {
      dominant_translation_provider: 'polza',
      polza_before: 1000.0, polza_after: 983.45, polza_spent_rub: 16.55,
      neuroapi_before: null, neuroapi_after: null, neuroapi_spent_usd: null,
      has_real_data: true,
      note: 'реальные данные из снапшотов баланса',
    },
  };

  await mockProjectList(page);
  await page.route('**/api/v1/projects/demo', async route => {
    await route.fulfill({ json: demoProject });
  });
  await page.route('**/api/v1/projects/demo/stats', async route => {
    await route.fulfill({ json: statsResponse });
  });

  await page.goto('/');
  await page.getByPlaceholder(/Имя проекта/).fill('demo');
  await page.getByRole('button', { name: /Найти/ }).click();
  await page.getByTestId('project-card').getByRole('button', { name: /^Открыть редактор$/ }).click();

  // Переходим на вкладку Статистика
  await page.getByRole('button', { name: /Стат/ }).click();
  const panel = page.locator('.stats-panel');
  await expect(panel).toBeVisible();

  // Проверяем что контент переполняет панель (есть что скроллить)
  const { scrollHeight, clientHeight } = await panel.evaluate((el: HTMLElement) => ({
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
  }));
  expect(scrollHeight).toBeGreaterThan(clientHeight);

  // Скроллим вниз и проверяем что scrollTop изменился
  await panel.evaluate((el: HTMLElement) => { el.scrollTop = 9999; });
  const scrollTop = await panel.evaluate((el: HTMLElement) => el.scrollTop);
  expect(scrollTop).toBeGreaterThan(0);
});

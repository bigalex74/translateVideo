// @vitest-environment jsdom
/**
 * Unit-тесты API-клиента UI.
 * Покрывает все 12 публичных функций client.ts через vi.stubGlobal('fetch').
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  artifactDownloadUrl,
  cancelPipeline,
  createProject,
  fetchProviderBalance,
  fetchProviderModels,
  getProjectArtifacts,
  getProjectStatus,
  listProjects,
  patchProjectConfig,
  preflightVideo,
  previewTTS,
  runPipeline,
  saveProjectSegments,
  uploadProject,
} from './client';

// ── Helpers ──────────────────────────────────────────────────────────────────

function okResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function errResponse(detail: string, status = 422): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function mockFetch(response: Response): ReturnType<typeof vi.fn> {
  const m = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', m);
  return m;
}

function lastCall(m: ReturnType<typeof vi.fn>) {
  return m.mock.calls[m.mock.calls.length - 1];
}

// ── runPipeline ───────────────────────────────────────────────────────────────

describe('runPipeline', () => {
  beforeEach(() => localStorage.clear());

  it('по умолчанию legacy-провайдер без webhook', async () => {
    const m = mockFetch(okResponse({ status: 'accepted', message: 'ok' }));
    await runPipeline('proj1');
    const [, init] = lastCall(m) as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toEqual({ force: false, provider: 'legacy' });
    expect((init.headers as Record<string, string>)['X-Webhook-Url']).toBeUndefined();
  });

  it('передаёт webhook через заголовок X-Webhook-Url', async () => {
    localStorage.setItem('tv_webhook_url', 'https://hook.example.com');
    const m = mockFetch(okResponse({ status: 'accepted', message: 'ok' }));
    await runPipeline('proj1', true, 'legacy');
    const [, init] = lastCall(m) as [string, RequestInit];
    expect((init.headers as Record<string, string>)['X-Webhook-Url']).toBe('https://hook.example.com');
    expect(JSON.parse(String(init.body))).not.toHaveProperty('webhook_url');
  });

  it('передаёт from_stage в теле запроса', async () => {
    const m = mockFetch(okResponse({ status: 'accepted', message: 'ok' }));
    await runPipeline('proj1', false, 'legacy', undefined, 'tts');
    const [, init] = lastCall(m) as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({ from_stage: 'tts' });
  });

  it('бросает ошибку при HTTP 500', async () => {
    mockFetch(errResponse('internal error', 500));
    await expect(runPipeline('proj1')).rejects.toThrow('internal error');
  });
});

// ── createProject ─────────────────────────────────────────────────────────────

describe('createProject', () => {
  it('POST /projects с input_video', async () => {
    const m = mockFetch(okResponse({ id: 'proj1', input_video: 'video.mp4' }));
    const result = await createProject('video.mp4');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toMatchObject({ input_video: 'video.mp4' });
    expect((result as unknown as { id: string }).id).toBe('proj1');
  });

  it('передаёт project_id и config', async () => {
    const m = mockFetch(okResponse({ id: 'my_id' }));
    await createProject('v.mp4', 'my_id', { target_language: 'en' } as never);
    const [, init] = lastCall(m) as [string, RequestInit];
    const body = JSON.parse(String(init.body));
    expect(body.project_id).toBe('my_id');
    expect(body.config).toMatchObject({ target_language: 'en' });
  });

  it('бросает ошибку при HTTP 422', async () => {
    mockFetch(errResponse('validation error', 422));
    await expect(createProject('bad.mp4')).rejects.toThrow('validation error');
  });
});

// ── uploadProject ─────────────────────────────────────────────────────────────

describe('uploadProject', () => {
  it('отправляет FormData с файлом', async () => {
    const m = mockFetch(okResponse({ id: 'proj_upload' }));
    const file = new File(['data'], 'video.mp4', { type: 'video/mp4' });
    await uploadProject(file);
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/upload');
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
  });

  it('добавляет project_id и config в FormData', async () => {
    const m = mockFetch(okResponse({ id: 'proj_upload' }));
    const file = new File(['data'], 'v.mp4');
    await uploadProject(file, 'pid', { target_language: 'ru' } as never);
    const [, init] = lastCall(m) as [string, RequestInit];
    const fd = init.body as FormData;
    expect(fd.get('project_id')).toBe('pid');
    expect(fd.get('config')).toBe(JSON.stringify({ target_language: 'ru' }));
  });

  it('бросает ошибку при сбое', async () => {
    mockFetch(errResponse('upload failed', 400));
    await expect(uploadProject(new File([], 'x.mp4'))).rejects.toThrow('upload failed');
  });
});

// ── listProjects ──────────────────────────────────────────────────────────────

describe('listProjects', () => {
  it('возвращает массив из data.projects', async () => {
    mockFetch(okResponse({ projects: [{ id: 'p1' }, { id: 'p2' }] }));
    const result = await listProjects();
    expect(result).toHaveLength(2);
    expect((result[0] as unknown as { id: string }).id).toBe('p1');
  });

  it('бросает ошибку при сбое', async () => {
    mockFetch(errResponse('forbidden', 403));
    await expect(listProjects()).rejects.toThrow('forbidden');
  });
});

// ── getProjectStatus ──────────────────────────────────────────────────────────

describe('getProjectStatus', () => {
  it('GET /projects/:id', async () => {
    const m = mockFetch(okResponse({ id: 'abc', status: 'idle' }));
    const result = await getProjectStatus('abc');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/projects/abc');
    expect((result as unknown as { id: string }).id).toBe('abc');
  });

  it('бросает ошибку при 404', async () => {
    mockFetch(errResponse('not found', 404));
    await expect(getProjectStatus('missing')).rejects.toThrow('not found');
  });
});

// ── getProjectArtifacts ───────────────────────────────────────────────────────

describe('getProjectArtifacts', () => {
  it('GET /projects/:id/artifacts', async () => {
    const m = mockFetch(okResponse({ artifacts: [] }));
    const result = await getProjectArtifacts('proj1');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/projects/proj1/artifacts');
    expect(result).toHaveProperty('artifacts');
  });
});

// ── saveProjectSegments ───────────────────────────────────────────────────────

describe('saveProjectSegments', () => {
  it('PUT /projects/:id/segments с translated=true', async () => {
    const m = mockFetch(okResponse({ id: 'proj1' }));
    const segs = [{ id: 's1', translated_text: 'Hello' }] as never[];
    await saveProjectSegments('proj1', segs);
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/segments');
    expect(init.method).toBe('PUT');
    const body = JSON.parse(String(init.body));
    expect(body.translated).toBe(true);
    expect(body.segments).toHaveLength(1);
  });
});

// ── patchProjectConfig ────────────────────────────────────────────────────────

describe('patchProjectConfig', () => {
  it('PUT /projects/:id/config', async () => {
    const m = mockFetch(okResponse({ ok: true, config: { target_language: 'en' } }));
    const result = await patchProjectConfig('proj1', { target_language: 'en' } as never);
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/config');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(String(init.body))).toMatchObject({ config: { target_language: 'en' } });
    expect((result as { ok: boolean }).ok).toBe(true);
  });
});

// ── preflightVideo ────────────────────────────────────────────────────────────

describe('preflightVideo', () => {
  it('POST /preflight с input_video и provider', async () => {
    const m = mockFetch(okResponse({ ok: true, warnings: [] }));
    await preflightVideo('/videos/test.mp4', 'deepseek');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/preflight');
    expect(JSON.parse(String(init.body))).toMatchObject({
      input_video: '/videos/test.mp4',
      provider: 'deepseek',
    });
  });

  it('использует provider="fake" по умолчанию', async () => {
    const m = mockFetch(okResponse({ ok: true, warnings: [] }));
    await preflightVideo('/v.mp4');
    const [, init] = lastCall(m) as [string, RequestInit];
    expect(JSON.parse(String(init.body)).provider).toBe('fake');
  });
});

// ── cancelPipeline ────────────────────────────────────────────────────────────

describe('cancelPipeline', () => {
  it('POST /projects/:id/cancel', async () => {
    const m = mockFetch(okResponse({ status: 'cancelled' }));
    const result = await cancelPipeline('proj1');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/cancel');
    expect(init.method).toBe('POST');
    expect((result as { status: string }).status).toBe('cancelled');
  });

  it('бросает ошибку при сбое', async () => {
    mockFetch(errResponse('not running', 409));
    await expect(cancelPipeline('proj1')).rejects.toThrow('not running');
  });
});

// ── previewTTS ────────────────────────────────────────────────────────────────

describe('previewTTS', () => {
  it('POST /projects/:id/tts-preview и возвращает blob URL', async () => {
    const blob = new Blob(['mp3data'], { type: 'audio/mpeg' });
    const fakeUrl = 'blob:http://localhost/test-audio';
    vi.stubGlobal('URL', { createObjectURL: vi.fn().mockReturnValue(fakeUrl), revokeObjectURL: vi.fn() });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(blob),
    }));
    const result = await previewTTS('proj1', 'Привет');
    expect(result).toBe(fakeUrl);
  });

  it('бросает ошибку при сбое TTS', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      text: () => Promise.resolve(JSON.stringify({ detail: 'TTS ошибка' })),
    }));
    await expect(previewTTS('proj1', 'Test')).rejects.toThrow('TTS ошибка');
  });
});

// ── fetchProviderModels ───────────────────────────────────────────────────────

describe('fetchProviderModels', () => {
  it('загружает модели провайдера', async () => {
    const m = mockFetch(okResponse({ models: [{ id: 'gpt-4', name: 'GPT-4' }] }));
    const models = await fetchProviderModels('neuroapi');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/providers/neuroapi/models');
    expect(models[0].id).toBe('gpt-4');
  });
});

// ── fetchProviderBalance ──────────────────────────────────────────────────────

describe('fetchProviderBalance', () => {
  it('загружает баланс провайдера', async () => {
    const m = mockFetch(okResponse({ provider: 'polza', used: 5.5, currency: 'USD', configured: true }));
    const balance = await fetchProviderBalance('polza');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/providers/polza/balance');
    expect((balance as unknown as { used: number }).used).toBe(5.5);
  });
});

// ── artifactDownloadUrl ───────────────────────────────────────────────────────

describe('artifactDownloadUrl', () => {
  it('формирует правильный URL без fetch', () => {
    const url = artifactDownloadUrl('my project', 'srt');
    expect(url).toContain('/projects/my%20project/artifacts/srt');
  });
});

// ── readError (через ошибочные ответы) ───────────────────────────────────────

describe('readError fallback', () => {
  it('возвращает plain text если JSON не распарсился', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response('plain error text', { status: 500 }),
    ));
    await expect(listProjects()).rejects.toThrow('plain error text');
  });
});

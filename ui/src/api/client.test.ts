// @vitest-environment jsdom
/**
 * Unit-тесты API-клиента UI.
 * Покрывает все 12 публичных функций client.ts через vi.stubGlobal('fetch').
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  apiHeaders,
  artifactDownloadUrl,
  batchCreateProjects,
  cancelPipeline,
  createProject,
  deleteProject,
  fetchProviderBalance,
  fetchProviderModels,
  getProjectArtifacts,
  getProjectDoctor,
  getProjectSnapshots,
  getProjectStatus,
  listProjects,
  patchProjectConfig,
  preflightVideo,
  previewTTS,
  renameProject,
  rebuildSubtitles,
  runPipeline,
  runSegmentAction,
  safariSafeDownload,
  saveProjectSegments,
  subtitleExportUrl,
  subtitleExportZipUrl,
  uploadProject,
  withApiKeyQuery,
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

// ── auth helpers ─────────────────────────────────────────────────────────────

describe('auth helpers', () => {
  beforeEach(() => localStorage.clear());

  it('apiHeaders добавляет X-API-Key из настроек UI', () => {
    localStorage.setItem('tv_api_key', 'secret123');
    expect(apiHeaders({ 'Content-Type': 'application/json' })).toMatchObject({
      'Content-Type': 'application/json',
      'X-API-Key': 'secret123',
    });
  });

  it('apiHeaders и withApiKeyQuery не меняют запрос без ключа', () => {
    expect(apiHeaders()).toEqual({});
    expect(withApiKeyQuery('/api/v1/projects')).toBe('/api/v1/projects');
  });

  it('withApiKeyQuery добавляет api_key к download/media URL', () => {
    localStorage.setItem('tv_api_key', 'secret 123');
    expect(withApiKeyQuery('/api/v1/video/p/input.mp4')).toBe('/api/v1/video/p/input.mp4?api_key=secret%20123');
    expect(withApiKeyQuery('/api/v1/projects/p/subtitles?format=srt')).toBe('/api/v1/projects/p/subtitles?format=srt&api_key=secret%20123');
  });
});

// ── createProject ─────────────────────────────────────────────────────────────

describe('createProject', () => {
  it('POST /projects с input_video', async () => {
    localStorage.setItem('tv_api_key', 'secret123');
    const m = mockFetch(okResponse({ id: 'proj1', input_video: 'video.mp4' }));
    const result = await createProject('video.mp4');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects');
    expect(init.method).toBe('POST');
    expect((init.headers as Record<string, string>)['X-API-Key']).toBe('secret123');
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

describe('getProjectDoctor', () => {
  it('GET /projects/:id/doctor', async () => {
    const m = mockFetch(okResponse({ project_id: 'proj1', ok: true, issues: [], actions: [] }));
    const result = await getProjectDoctor('proj1');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/projects/proj1/doctor');
    expect(result.ok).toBe(true);
  });
});

describe('getProjectSnapshots', () => {
  it('GET /projects/:id/snapshots', async () => {
    const m = mockFetch(okResponse({ project_id: 'proj1', snapshots: [{ filename: 's.json' }] }));
    const result = await getProjectSnapshots('proj1');
    const [url] = lastCall(m) as [string];
    expect(url).toContain('/projects/proj1/snapshots');
    expect(result.snapshots).toHaveLength(1);
  });
});

describe('rebuildSubtitles', () => {
  it('POST /projects/:id/rebuild/subtitles', async () => {
    const m = mockFetch(okResponse({ project_id: 'proj1', work_dir: 'runs/proj1', artifacts: [] }));
    const result = await rebuildSubtitles('proj1');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/rebuild/subtitles');
    expect(init.method).toBe('POST');
    expect(result.artifacts).toEqual([]);
  });
});

describe('runSegmentAction', () => {
  it('POST /projects/:id/segments/actions/:action', async () => {
    const m = mockFetch(okResponse({ project_id: 'proj1', action: 'reset-tts', changed: 2, segment_ids: ['s1'], project: {} }));
    const result = await runSegmentAction('proj1', 'reset-tts', ['s1'], true);
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/segments/actions/reset-tts');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toMatchObject({ segment_ids: ['s1'], force: true });
    expect(result.changed).toBe(2);
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

// ── rename/delete/download helpers ───────────────────────────────────────────

describe('project helper actions', () => {
  beforeEach(() => localStorage.clear());

  it('renameProject отправляет PATCH display_name', async () => {
    const m = mockFetch(okResponse({ project_id: 'proj1', display_name: 'New name', status: 'created' }));
    const result = await renameProject('proj1', 'New name');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/proj1/rename');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(String(init.body))).toEqual({ display_name: 'New name' });
    expect(result.display_name).toBe('New name');
  });

  it('deleteProject кодирует project_id и добавляет API key', async () => {
    localStorage.setItem('tv_api_key', 'secret123');
    const m = mockFetch(okResponse({ deleted: 'my project', ok: true }));
    const result = await deleteProject('my project');
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/my%20project');
    expect(init.method).toBe('DELETE');
    expect((init.headers as Record<string, string>)['X-API-Key']).toBe('secret123');
    expect(result.ok).toBe(true);
  });

  it('subtitle export URLs добавляют api_key для media/download ссылок', () => {
    localStorage.setItem('tv_api_key', 'secret123');
    expect(subtitleExportUrl('proj1', 'srt')).toContain('format=srt&api_key=secret123');
    expect(subtitleExportZipUrl('proj1')).toContain('/projects/proj1/subtitles/all?api_key=secret123');
  });
});

describe('safariSafeDownload', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn().mockReturnValue('blob:http://localhost/download'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('скачивает blob через временную ссылку', async () => {
    const click = vi.fn();
    const appendChild = vi.spyOn(document.body, 'appendChild');
    const removeChild = vi.spyOn(document.body, 'removeChild');
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
      const el = originalCreateElement(tagName);
      if (tagName === 'a') {
        Object.defineProperty(el, 'click', { value: click });
      }
      return el;
    });
    mockFetch(new Response(new Blob(['data']), { status: 200 }));

    await safariSafeDownload('/api/v1/projects/p/artifacts/srt', 'file.srt');
    expect(click).toHaveBeenCalledOnce();
    expect(appendChild).toHaveBeenCalled();
    vi.runAllTimers();
    expect(removeChild).toHaveBeenCalled();
  });

  it('fallback открывает URL в новой вкладке при ошибке fetch', async () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 500 })));

    await safariSafeDownload('/download', 'file.srt');
    expect(open).toHaveBeenCalledWith('/download', '_blank');
  });
});

// ── batchCreateProjects ──────────────────────────────────────────────────────

describe('batchCreateProjects', () => {
  it('POST /projects/batch возвращает results', async () => {
    const m = mockFetch(okResponse({ results: [{ project_id: 'p1', status: 'created' }] }));
    const result = await batchCreateProjects([{ input_video: 'v.mp4', project_id: 'p1' }], true);
    const [url, init] = lastCall(m) as [string, RequestInit];
    expect(url).toContain('/projects/batch');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toMatchObject({ auto_run: true });
    expect(result[0].project_id).toBe('p1');
  });

  it('batchCreateProjects возвращает пустой массив без results', async () => {
    mockFetch(okResponse({}));
    await expect(batchCreateProjects([])).resolves.toEqual([]);
  });

  it('batchCreateProjects бросает HTTP ошибку', async () => {
    mockFetch(new Response('', { status: 500 }));
    await expect(batchCreateProjects([])).rejects.toThrow('Batch error: HTTP 500');
  });
});

// ── artifactDownloadUrl ───────────────────────────────────────────────────────

describe('artifactDownloadUrl', () => {
  beforeEach(() => localStorage.clear());

  it('формирует правильный URL без fetch', () => {
    const url = artifactDownloadUrl('my project', 'srt');
    expect(url).toContain('/projects/my%20project/artifacts/srt');
  });

  it('добавляет api_key query для обычной ссылки скачивания', () => {
    localStorage.setItem('tv_api_key', 'secret123');
    const url = artifactDownloadUrl('my project', 'srt');
    expect(url).toContain('api_key=secret123');
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

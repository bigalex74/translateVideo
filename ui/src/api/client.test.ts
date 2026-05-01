// @vitest-environment jsdom
/**
 * Unit-тесты API-клиента UI.
 *
 * Эти проверки фиксируют контракт запуска пайплайна: провайдер уходит в JSON,
 * а webhook передается заголовком X-Webhook-Url, как ожидает backend.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { runPipeline } from './client';

describe('api/client runPipeline', () => {
  beforeEach(() => {
    localStorage.clear();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'accepted', message: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
  });

  it('по умолчанию запускает legacy-провайдер', async () => {
    await runPipeline('demo');

    const fetchMock = vi.mocked(fetch);
    const init = fetchMock.mock.calls[0][1] as RequestInit;

    expect(JSON.parse(String(init.body))).toEqual({ force: false, provider: 'legacy' });
  });

  it('передает webhook через X-Webhook-Url, а не через тело запроса', async () => {
    localStorage.setItem('tv_webhook_url', 'https://n8n.example.com/webhook/demo');

    await runPipeline('demo', true, 'legacy');

    const fetchMock = vi.mocked(fetch);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    const body = JSON.parse(String(init.body));

    expect(headers['X-Webhook-Url']).toBe('https://n8n.example.com/webhook/demo');
    expect(body).toEqual({ force: true, provider: 'legacy' });
    expect(body).not.toHaveProperty('webhook_url');
  });
});

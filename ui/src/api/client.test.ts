// @vitest-environment jsdom
/**
 * Unit-тесты API-клиента UI.
 *
 * Эти проверки фиксируют контракт запуска пайплайна: провайдер уходит в JSON,
 * а webhook передается заголовком X-Webhook-Url, как ожидает backend.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchProviderBalance, fetchProviderModels, runPipeline } from './client';

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

  it('загружает модели провайдера через backend API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ models: [{ id: 'gpt-5-mini', name: 'gpt-5-mini' }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ));

    const models = await fetchProviderModels('neuroapi');

    expect(models[0].id).toBe('gpt-5-mini');
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('/providers/neuroapi/models');
  });

  it('загружает баланс провайдера через backend API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ provider: 'neuroapi', configured: true, used: 12.34, currency: 'USD' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ));

    const balance = await fetchProviderBalance('neuroapi');

    expect(balance.used).toBe(12.34);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('/providers/neuroapi/balance');
  });
});

// @vitest-environment jsdom
import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useVisibilityRefresh } from './useVisibilityRefresh';

describe('useVisibilityRefresh', () => {
  let addEventSpy: ReturnType<typeof vi.spyOn>;
  let removeEventSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    addEventSpy = vi.spyOn(document, 'addEventListener');
    removeEventSpy = vi.spyOn(document, 'removeEventListener');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('регистрирует слушатель visibilitychange при enabled=true', () => {
    const onVisible = vi.fn();
    renderHook(() => useVisibilityRefresh({ onVisible, enabled: true }));
    expect(addEventSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });

  it('НЕ регистрирует слушатель при enabled=false', () => {
    const onVisible = vi.fn();
    renderHook(() => useVisibilityRefresh({ onVisible, enabled: false }));
    expect(addEventSpy).not.toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });

  it('вызывает onVisible при visibilityState=visible', () => {
    const onVisible = vi.fn();
    renderHook(() => useVisibilityRefresh({ onVisible, enabled: true }));

    // Эмулируем переход → visible
    Object.defineProperty(document, 'visibilityState', {
      value: 'visible',
      configurable: true,
    });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(onVisible).toHaveBeenCalledTimes(1);
  });

  it('НЕ вызывает onVisible при visibilityState=hidden', () => {
    const onVisible = vi.fn();
    renderHook(() => useVisibilityRefresh({ onVisible, enabled: true }));

    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      configurable: true,
    });
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
    });

    expect(onVisible).not.toHaveBeenCalled();
  });

  it('удаляет слушатель при unmount', () => {
    const onVisible = vi.fn();
    const { unmount } = renderHook(() => useVisibilityRefresh({ onVisible, enabled: true }));
    unmount();
    expect(removeEventSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });

  it('enabled по умолчанию = true', () => {
    const onVisible = vi.fn();
    renderHook(() => useVisibilityRefresh({ onVisible }));
    expect(addEventSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });
});

// ── requestCompletionNotification ─────────────────────────────────────────────

import { requestCompletionNotification } from './useVisibilityRefresh';

describe('requestCompletionNotification', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    // Сбрасываем visibilityState после каждого теста
    Object.defineProperty(document, 'visibilityState', {
      value: 'hidden',
      configurable: true,
    });
  });

  it('ничего не делает если Notification недоступен', async () => {
    const origNotification = (window as unknown as Record<string, unknown>).Notification;
    delete (window as unknown as Record<string, unknown>).Notification;
    // Не должно бросить исключение
    await expect(requestCompletionNotification('p1', 'completed')).resolves.toBeUndefined();
    (window as unknown as Record<string, unknown>).Notification = origNotification;
  });

  it('не отправляет уведомление если permission=denied', async () => {
    Object.defineProperty(window, 'Notification', {
      value: class MockNotification {
        static permission = 'denied';
        static requestPermission = vi.fn().mockResolvedValue('denied');
        constructor() { throw new Error('Should not be called'); }
      },
      configurable: true,
      writable: true,
    });
    // Не должно создавать уведомление
    await expect(requestCompletionNotification('p1', 'failed')).resolves.toBeUndefined();
  });

  it('не отправляет уведомление если вкладка активна (visible)', async () => {
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    const constructorSpy = vi.fn();
    Object.defineProperty(window, 'Notification', {
      value: class MockNotification {
        static permission = 'granted';
        static requestPermission = vi.fn().mockResolvedValue('granted');
        constructor(t: string, o: unknown) { constructorSpy(t, o); }
        onclick = null;
        close = vi.fn();
      },
      configurable: true,
      writable: true,
    });
    await requestCompletionNotification('p1', 'completed');
    expect(constructorSpy).not.toHaveBeenCalled();
  });

  it('отправляет уведомление если permission=granted и вкладка скрыта', async () => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    const constructorSpy = vi.fn();
    Object.defineProperty(window, 'Notification', {
      value: class MockNotification {
        static permission = 'granted';
        static requestPermission = vi.fn().mockResolvedValue('granted');
        constructor(title: string, opts: unknown) { constructorSpy(title, opts); }
        onclick = null;
        close = vi.fn();
      },
      configurable: true,
      writable: true,
    });
    await requestCompletionNotification('proj42', 'completed');
    expect(constructorSpy).toHaveBeenCalledWith(
      expect.stringContaining('Перевод завершён'),
      expect.objectContaining({ body: expect.stringContaining('proj42') }),
    );
  });

  it('запрашивает разрешение если permission=default', async () => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    const reqPermSpy = vi.fn().mockResolvedValue('granted');
    Object.defineProperty(window, 'Notification', {
      value: class MockNotification {
        static permission = 'default';
        static requestPermission = reqPermSpy;
        constructor() {}
        onclick = null;
        close = vi.fn();
      },
      configurable: true,
      writable: true,
    });
    await requestCompletionNotification('p2', 'completed');
    expect(reqPermSpy).toHaveBeenCalled();
  });
});

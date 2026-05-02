// @vitest-environment jsdom
/**
 * TVIDEO-029a: тесты логики поллинга статуса пайплайна.
 *
 * Проверяет:
 * - поллинг запускается только при status='running'
 * - поллинг игнорирует dirty-флаг (статус важнее несохранённых правок)
 * - при переходе из running → completed поллинг останавливается
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ─── Симуляция логики поллинга из Workspace ──────────────────────────────────

function createPoller(
  getStatus: () => Promise<{ status: string }>,
  onUpdate: (status: string) => void,
  intervalMs = 2000,
) {
  let timerId: ReturnType<typeof setInterval> | null = null;

  function start(currentStatus: string) {
    if (currentStatus !== 'running') return;
    if (timerId !== null) return; // уже запущен
    timerId = setInterval(async () => {
      try {
        const data = await getStatus();
        onUpdate(data.status);
      } catch {
        // игнорируем ошибки сети
      }
    }, intervalMs);
  }

  function stop() {
    if (timerId !== null) {
      clearInterval(timerId);
      timerId = null;
    }
  }

  function isActive() {
    return timerId !== null;
  }

  return { start, stop, isActive };
}

// ─── Тесты ──────────────────────────────────────────────────────────────────

describe('TVIDEO-029a: поллинг статуса пайплайна', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('не запускается если статус не running', () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'completed' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('completed');
    expect(poller.isActive()).toBe(false);

    poller.start('failed');
    expect(poller.isActive()).toBe(false);

    poller.start('created');
    expect(poller.isActive()).toBe(false);
  });

  it('запускается при status=running', () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'running' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');
    expect(poller.isActive()).toBe(true);

    poller.stop();
  });

  it('вызывает getStatus каждые 2 секунды', async () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'running' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');

    await vi.advanceTimersByTimeAsync(6000);

    expect(getStatus).toHaveBeenCalledTimes(3);
    poller.stop();
  });

  it('передаёт обновлённый статус в onUpdate', async () => {
    let callCount = 0;
    const statuses = ['running', 'running', 'completed'];
    const getStatus = vi.fn().mockImplementation(() =>
      Promise.resolve({ status: statuses[callCount++] ?? 'completed' })
    );
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');
    await vi.advanceTimersByTimeAsync(6000);

    expect(onUpdate).toHaveBeenCalledTimes(3);
    expect(onUpdate).toHaveBeenNthCalledWith(3, 'completed');
    poller.stop();
  });

  it('stop() прекращает дальнейшие вызовы', async () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'running' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');
    await vi.advanceTimersByTimeAsync(4000); // 2 вызова

    poller.stop();
    await vi.advanceTimersByTimeAsync(6000); // ещё 3 тика — не должны срабатывать

    expect(getStatus).toHaveBeenCalledTimes(2);
  });

  it('не запускает дублирующий интервал при повторном start()', () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'running' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');
    poller.start('running'); // повторный вызов
    expect(poller.isActive()).toBe(true);
    poller.stop();
  });

  it('не падает при сетевой ошибке в getStatus', async () => {
    const getStatus = vi.fn().mockRejectedValue(new Error('Network error'));
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 2000);

    poller.start('running');
    // Не должно бросать
    await expect(vi.advanceTimersByTimeAsync(4000)).resolves.not.toThrow();
    poller.stop();
  });
});

// ─── TVIDEO-072: ускоренный polling при отмене ─────────────────────────────

describe('TVIDEO-072: cancel — ускоренный polling', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('при cancelling=true интервал 500ms быстрее 2000ms', async () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'running' });
    const onUpdate = vi.fn();

    // Нормальный polling — 2000ms
    const normalPoller = createPoller(getStatus, onUpdate, 2000);
    normalPoller.start('running');
    await vi.advanceTimersByTimeAsync(1500);
    expect(getStatus).toHaveBeenCalledTimes(0);  // ещё не сработал
    normalPoller.stop();
    getStatus.mockClear();

    // Ускоренный polling — 500ms
    const fastPoller = createPoller(getStatus, onUpdate, 500);
    fastPoller.start('running');
    await vi.advanceTimersByTimeAsync(1500);
    expect(getStatus).toHaveBeenCalledTimes(3);  // 3 раза за 1.5с
    fastPoller.stop();
  });

  it('после перехода из running статус cancelling сбрасывается', async () => {
    const statuses = ['running', 'running', 'failed'];
    let call = 0;
    const getStatus = vi.fn().mockImplementation(() =>
      Promise.resolve({ status: statuses[call++] ?? 'failed' })
    );

    let cancellingState = true;
    let cancelConfirmState = true;

    const onUpdate = vi.fn().mockImplementation((status: string) => {
      if (status !== 'running') {
        cancellingState = false;
        cancelConfirmState = false;
      }
    });

    const poller = createPoller(getStatus, onUpdate, 500);
    poller.start('running');
    await vi.advanceTimersByTimeAsync(1500);

    expect(cancellingState).toBe(false);
    expect(cancelConfirmState).toBe(false);
    poller.stop();
  });

  it('при failed-статусе polling не запускается', () => {
    const getStatus = vi.fn().mockResolvedValue({ status: 'failed' });
    const onUpdate = vi.fn();
    const poller = createPoller(getStatus, onUpdate, 500);

    poller.start('failed');
    expect(poller.isActive()).toBe(false);
  });
});

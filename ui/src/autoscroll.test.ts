// @vitest-environment jsdom
/**
 * TVIDEO-026: Unit-тест логики авто-скролла активного сегмента.
 *
 * Тестирует Map<string, HTMLDivElement> ref-паттерн:
 * - при смене activeSegId вызывается scrollIntoView на нужном узле
 * - при удалении узла из Map скролла не происходит
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('TVIDEO-026: авто-скролл активного сегмента', () => {
  let segRefs: Map<string, HTMLDivElement>;

  // Вспомогательная функция: симулирует эффект из Workspace
  function scrollToActive(activeSegId: string | null) {
    if (!activeSegId) return;
    const node = segRefs.get(activeSegId);
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function makeNode(): HTMLDivElement {
    const el = document.createElement('div');
    el.scrollIntoView = vi.fn();
    return el;
  }

  beforeEach(() => {
    segRefs = new Map();
  });

  it('вызывает scrollIntoView на активном узле', () => {
    const node = makeNode();
    segRefs.set('seg-1', node);

    scrollToActive('seg-1');

    expect(node.scrollIntoView).toHaveBeenCalledOnce();
    expect(node.scrollIntoView).toHaveBeenCalledWith({
      behavior: 'smooth',
      block: 'nearest',
    });
  });

  it('не вызывает scrollIntoView если activeSegId = null', () => {
    const node = makeNode();
    segRefs.set('seg-1', node);

    scrollToActive(null);

    expect(node.scrollIntoView).not.toHaveBeenCalled();
  });

  it('не падает если узел отсутствует в Map', () => {
    // Узел не зарегистрирован — scrollToActive не должен бросать
    expect(() => scrollToActive('seg-missing')).not.toThrow();
  });

  it('скроллит только к активному, не к соседним', () => {
    const node1 = makeNode();
    const node2 = makeNode();
    const node3 = makeNode();
    segRefs.set('seg-1', node1);
    segRefs.set('seg-2', node2);
    segRefs.set('seg-3', node3);

    scrollToActive('seg-2');

    expect(node1.scrollIntoView).not.toHaveBeenCalled();
    expect(node2.scrollIntoView).toHaveBeenCalledOnce();
    expect(node3.scrollIntoView).not.toHaveBeenCalled();
  });

  it('корректно переключается при смене активного сегмента', () => {
    const node1 = makeNode();
    const node2 = makeNode();
    segRefs.set('seg-1', node1);
    segRefs.set('seg-2', node2);

    scrollToActive('seg-1');
    scrollToActive('seg-2');
    scrollToActive('seg-1');

    expect(node1.scrollIntoView).toHaveBeenCalledTimes(2);
    expect(node2.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('удалённый из Map узел не вызывает scrollIntoView', () => {
    const node = makeNode();
    segRefs.set('seg-1', node);
    segRefs.delete('seg-1');  // симулируем unmount компонента

    scrollToActive('seg-1');

    expect(node.scrollIntoView).not.toHaveBeenCalled();
  });
});

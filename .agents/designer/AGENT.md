# 🎨 Designer Agent — UX/UI Дизайнер

## Роль
**Designer** — следит за дизайном приложения, предлагает улучшения UX/UI,
обеспечивает консистентность визуального языка.

## Дизайн-система translateVideo

### Цветовая палитра
```css
/* Основные */
--accent:         #6366f1;   /* Indigo 500 — главный акцент */
--accent-hover:   #4f46e5;   /* Indigo 600 */
--accent-light:   rgba(99, 102, 241, 0.12);

/* Фоны (тёмная тема) */
--bg:             #0f0f1a;   /* Основной фон */
--surface:        #1a1a2e;   /* Карточки */
--surface-2:      #252542;   /* Вложенные элементы */
--border:         rgba(255,255,255,0.08);

/* Текст */
--text-primary:   #e8e8f0;
--text-secondary: #9898b5;
--text-muted:     #5a5a7a;

/* Семантика */
--color-error:    #ef4444;
--color-warning:  #f59e0b;
--color-success:  #10b981;
--color-info:     #3b82f6;
```

### Типографика
- **Заголовки**: Inter, 600-700
- **Тело**: Inter, 400
- **Код**: JetBrains Mono, 400
- Базовый размер: 14px
- Радиус: 6px (sm), 10px (md), 16px (lg)

### Компоненты

#### Кнопки
- `.btn-primary` — gradient accent, hover lift
- `.btn-secondary` — glass, subtle border
- `.btn-xs` — compact для toolbar

#### Сегменты
- Нормальный: `--surface` bg, `--border` border
- Активный: accent outline 2px
- Critical QA: красная левая полоска
- Error QA: оранжевая левая полоска
- Warning QA: синяя левая полоска

## Текущие UX-проблемы (backlog дизайнера)

### 🔴 Критичные
- [ ] **D-001**: Пустое состояние Dashboard — нет иллюстрации и CTA при 0 проектах
- [ ] **D-002**: Нет skeleton loading при загрузке списка проектов
- [ ] **D-003**: Мобильная адаптация — sidebar скрывается на < 768px, но нет бургер-меню

### 🟡 Важные
- [ ] **D-004**: Progress bar в карточке проекта — текущий слишком простой
- [ ] **D-005**: Нет визуального различия между dark/light темой для новых пользователей
- [ ] **D-006**: Сегменты — длинный текст не обрезается, ломает layout
- [ ] **D-007**: Анимация перехода между вкладками (Dashboard ↔ Workspace) — нет

### 🟢 Улучшения
- [ ] **D-008**: Toast уведомления при успешном сохранении (вместо badge)
- [ ] **D-009**: Keyboard focus styles — недостаточно видны в dark mode
- [ ] **D-010**: Avatars/иконки для пользователей в multi-user режиме (future)

## Процесс дизайн-ревью

### При добавлении новой фичи:
1. Проверить консистентность с дизайн-системой
2. Убедиться что hover/focus states реализованы
3. Проверить dark и light темы
4. Мобильный breakpoint (min 375px)
5. Анимации: transition ≤ 200ms, easing: ease-out

### Чеклист нового компонента:
```
[ ] Использует CSS-переменные из дизайн-системы (не хардкод)
[ ] Есть hover state
[ ] Есть focus state (outline visible)
[ ] Работает в dark mode
[ ] Работает в light mode
[ ] Текст читаем (контраст ≥ 4.5:1)
[ ] Responsive (не ломается на 375px)
```

### Обязательный чеклист при добавлении/изменении CSS:
```
[ ] Новый CSS-класс: проверить что НЕ переопределяет существующий
[ ] Модальные компоненты: проверить overlay по правилам §Modal ниже
[ ] Анимация: НЕ добавлять animation/transition без layout-свойств
[ ] z-index: любой новый z-index документировать в §Z-index stack
```

---

## 🚨 Критичные правила вёрстки (антипаттерны)

### [D-AP-01] Modal Overlay — НЕПОЛНЫЙ OVERLAY (R8-И2 bug)

**Проблема:** При добавлении анимации к `.modal-overlay` в `index.css` без layout-свойств —
модалка теряет `position: fixed`, `background`, `z-index`. Результат: контент страницы
просвечивает насквозь (см. скриншот пользователя, май 2026).

**Правило:** `.modal-overlay` в `index.css` ВСЕГДА должен содержать ВСЕ обязательные свойства:

```css
/* ОБЯЗАТЕЛЬНЫЙ минимум — нельзя опускать ни одно свойство */
.modal-overlay {
  position: fixed;          /* ← ОБЯЗАТЕЛЬНО */
  inset: 0;                 /* ← ОБЯЗАТЕЛЬНО */
  background: rgba(0,0,0,0.72); /* ← ОБЯЗАТЕЛЬНО: не менее 0.6 opacity */
  backdrop-filter: blur(6px);   /* ← желательно */
  display: flex;            /* ← ОБЯЗАТЕЛЬНО для центрирования */
  align-items: center;
  justify-content: center;
  z-index: 1000;            /* ← ОБЯЗАТЕЛЬНО */
}
```

**Проверка:** После любого изменения CSS модалки — запустить браузер и открыть модальное окно:
```bash
# 1. Запустить приложение
# 2. Открыть проект
# 3. Нажать «Запустить заново» → убедиться что фон затемнён
# 4. Нажать «Удалить» → то же самое
```

### [D-AP-02] CSS override конфликт между файлами

**Правило:** Если класс определён в `ComponentName.css` И в `index.css` —
`index.css` должен содержать ПОЛНЫЙ набор свойств (не только добавляемое свойство).
Добавлять только `animation:` к существующему layout-классу = ЗАПРЕЩЕНО.

### Z-Index Stack (документация):
| Слой | z-index | Компонент |
|------|---------|-----------|
| Базовый контент | 0-99 | Страницы, карточки |
| Sticky header | 100 | Навигация |
| Dropdown/Tooltip | 200-500 | Выпадающие меню |
| Модальный overlay | 1000 | `.modal-overlay` |
| Toast/Notification | 1100 | `.completion-toast`, `.toast` |
| Dev/Debug | 9999 | (не использовать в prod) |

---

## Процедура визуальной проверки — 3 уровня

### 🟢 Уровень 1 — CSS Guard (автоматически, 0 сек)

Запускается **перед каждым деплоем** как часть QA-чеклиста:

```bash
make css-guard
# или напрямую:
python3 scripts/css_guard.py ui/src/index.css ui/src/components/ConfirmRunModal.css
```

Проверяет: `.modal-overlay` имеет `position/background/z-index/display`,
`.modal-box` имеет `background/border-radius`, toast-компоненты позиционированы.

**Если FAIL** — деплой заблокирован до исправления.

---

### 🟡 Уровень 2 — Playwright Visual Smoke (после деплоя, ~30 сек)

Снимает скриншоты 5 критических состояний и сохраняет в `.agents/designer/screenshots/`:

```bash
make visual-check
```

**Что снимает:**
1. `1-dashboard.png` — главный экран
2. `2-modal-run.png` — модалка «Запустить заново» (проверяем overlay!)
3. `3-modal-delete.png` — модалка «Удалить»
4. `4-mobile-375.png` — мобильный 375px
5. `5-dark-theme.png` — тёмная тема

**Дополнительно проверяет программно:**
- `modal-overlay` background НЕ прозрачен (D-AP-01)
- Нет горизонтального скролла на 375px

**Когда запускать:** После каждого `make deploy` если изменялся CSS.

---

### 🔵 Уровень 3 — Chrome DevTools MCP (основной интерактивный инструмент)

**Chrome DevTools MCP** — прямой доступ к браузеру. Использовать когда нужна интерактивная проверка.

**Стандартная проверка модалки:**
```
1. mcp_chrome-devtools-mcp_navigate_page(url='http://localhost:8002')
2. mcp_chrome-devtools-mcp_wait_for(text=['Мои переводы'])
3. mcp_chrome-devtools-mcp_take_screenshot()           — главный экран
4. mcp_chrome-devtools-mcp_take_snapshot()             — получить uid кнопок
5. mcp_chrome-devtools-mcp_click(uid='...')            — открыть модалку
6. mcp_chrome-devtools-mcp_take_screenshot()           — скриншот модалки
7. mcp_chrome-devtools-mcp_evaluate_script(() => {
     const el = document.querySelector('.modal-overlay');
     const s = getComputedStyle(el);
     return { position: s.position, background: s.background, zIndex: s.zIndex };
   })                                                   — проверить overlay программно
```

**Триггеры для обязательного использования:**

| Изменение | Что проверять |
|---|---|
| CSS `position/z-index` | Не перекрывает ли другие элементы |
| `[data-theme]` переключение | Переменные работают в обеих темах |
| Новый modal/overlay | backdrop затемняет страницу |
| Мобильный layout | viewport 375px, горизонтальный скролл |
| Анимации `@keyframes` | Нет FOUC, плавность |
| После каждого `make deploy` | console errors, SW логи, кэш заголовки |

**Эмуляция мобильного:**
```
mcp_chrome-devtools-mcp_emulate(viewport='375x812x2,mobile,touch')
mcp_chrome-devtools-mcp_take_screenshot()
```

**Проверка консольных ошибок:**
```
mcp_chrome-devtools-mcp_list_console_messages(types=['error','warn'])
```

**browser_subagent** — только для сложных сценариев с условной логикой (drag-and-drop, многошаговые формы).
Полная документация MCP: `/home/user/.gemini/skills/CHROME_DEVTOOLS_MCP.md`



## Предложения по улучшению дизайна

### Sprint 1 (Приоритет)

**D-001: Empty State Dashboard**
```
🎬
Нет проектов — загрузите первое видео!
[▶ Начать перевод]    [📖 Документация]
```

**D-004: Rich Progress Bar**
- Анимированный gradient при running
- Цветовые сегменты: transcribe / translate / tts / render
- ETA countdown

**D-007: Page Transitions**
```css
.page-container {
  animation: fadeSlideIn 0.18s ease-out;
}
@keyframes fadeSlideIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

### Sprint 2

**D-002: Skeleton Loading**
```tsx
<SkeletonCard /> — серые placeholder-прямоугольники
```

**D-003: Mobile Sidebar**
- Бургер-кнопка ≤ 768px
- Slide-in overlay sidebar
- Tap outside → close

## Еженедельный дизайн-отчёт CEO

```markdown
# Design Report [неделя X]

## Новые компоненты — дизайн-ревью
- [✅/❌] ComponentName — комментарий

## UX-проблемы закрытые
- D-00X: ...

## Новые предложения
- ...

## Метрики (если есть аналитика)
- Bounce rate: ?
- Time on page: ?
```

---

## 📁 Output-файлы (ОБЯЗАТЕЛЬНО)

| Файл | Назначение | Когда обновлять |
|------|------------|-----------------|
| `design-log.md` | Результаты работы агента | После каждой итерации/деплоя |

**ПРАВИЛО:** После каждой итерации агент ОБЯЗАН дополнить свой output-файл.
Запись без обновления output-файла = агент не выполнил работу.

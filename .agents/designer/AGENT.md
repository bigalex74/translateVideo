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

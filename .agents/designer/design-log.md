# 🎨 Designer — Журнал дизайн-решений

> Ведёт: Designer Agent | Обновляется после каждой итерации

---

## Round 7 (2026-05-06)

### Итерация 1 — Тёмная тема + Удаление проекта

**🐛 Bug Fix: `data-theme` без CSS-селектора**
- **Проблема:** `applyTheme()` устанавливал `document.documentElement.setAttribute('data-theme', 'dark')`, но CSS содержал только `@media (prefers-color-scheme: dark)`. Ручное переключение темы в Settings не работало.
- **Решение:** Добавлены `[data-theme="dark"]` и `[data-theme="light"]` блоки в `index.css`.
- **Затронуто:** Нина Н7, Глеб Г4 — оба жаловались на тему.

**✨ Новый компонент: Delete Confirm Modal**
- Красная кнопка `🗑` в `card-actions` (только при `status !== 'running'`)
- Overlay с backdrop blur при клике вне закрывается
- Текст: «Проект X и все его файлы будут удалены безвозвратно»
- Кнопка отмены: secondary, кнопка удаления: btn-danger (красная)
- **Оценка:** ✅ Понятно, безопасно, не перепутать

**⚠️ Замечание:** Нет анимации появления модала. Рекомендую добавить в R8:
```css
.delete-confirm-modal {
  animation: slideInFromBottom 0.2s ease-out;
}
```

---

### Итерация 2 — Timecode, Счётчик символов

**✨ Timecode HH:MM:SS**
- Было: `1.0с — 3.5с (2.5с)` → Стало: `00:01 — 00:03 (2.5с)`
- Кликабельность сохранена (клик → перемотка видео)
- **Оценка:** ✅ Профессиональный стандарт, Глеб/Валентина довольны

**✨ Счётчик символов /42**
- Три состояния: ✓ зелёный (≤42) / ⚡ оранжевый (42-84) / ⚠️ красный (>84)
- Показывает и общее количество символов, и длину максимальной строки
- **Оценка:** ✅ Информативно. Светофор понятен интуитивно.

---

### Итерация 3 — Side-by-side

**✨ Режим двух колонок**
- Кнопка `⊞ ‖` в тулбаре с индиго подсветкой при активации
- CSS grid `1fr 1fr`, граница между колонками
- Адаптив: на <768px переключается в вертикальный стек
- Скрывает `seg-diff-badge` в side-by-side (экономия места)
- **Оценка:** ✅ Работает. ⚠️ Возможная проблема: на планшете в landscape тоже OK, но на portrait (<600px) может быть тесно.

---

### Итерация 4 — Safari download

**🐛 Fix: Safari скачивание**
- `<a download href="...">` не работает на Safari для same-domain URL через fetch
- Решение: `safariSafeDownload()` → fetch → Blob → createObjectURL → `<a>` programmatic click
- Fallback: `window.open()` если fetch fails
- **Оценка:** ✅ Правильный паттерн. Светлана С4 закрыта.

---

## 📋 Дизайн-бэклог

| Приоритет | Задача | Раунд |
|---|---|---|
| 🔴 | Анимация появления delete-modal (slideIn) | R8 |
| 🔴 | Mobile: укрупнить кнопки для touch (min 44px) | R8 |
| 🟡 | Onboarding tooltip после создания проекта | R8 |
| 🟡 | Skeleton-loader вместо spinner при загрузке | R8 |
| 🟢 | Контекстное меню правой кнопкой на карточке | R9 |
| 🟢 | Drag-and-drop сортировка проектов | R9 |

---

## 🎨 Дизайн-система — актуальное состояние

### Используемые переменные (из index.css)
```css
/* Работают корректно в обоих темах: */
[data-theme="dark"]  → --bg: #16171d; --accent: #c084fc;
[data-theme="light"] → --bg: #fff;    --accent: #aa3bff;
@media dark          → то же что [data-theme="dark"]
```

### Компоненты — статус
| Компонент | Статус | Темизирован |
|---|---|---|
| Dashboard cards | ✅ OK | ✅ |
| Workspace | ✅ OK | ✅ |
| Delete confirm modal | ✅ R7 | ✅ |
| Side-by-side | ✅ R7 | ✅ |
| NewProject stepper | ✅ OK | ✅ |
| Toast notifications | ✅ R6 | ✅ |

*Последнее обновление: 2026-05-06 | v1.80.0 | Designer Agent*

---

## Round 8 (2026-05-06)

### Итерация 2 — Анимации модалов

**✨ modal-slide-in animation**
- `@keyframes modal-slide-in`: scale(0.94) + translateY(12px) → normal
- Время: 0.22s, easing: cubic-bezier(0.34, 1.4, 0.64, 1) — небольшой «отскок»
- Overlay: простой fade-in 0.18s
- **Оценка:** ✅ Приятно. Не навязчиво. Стандарт Material/Radix.

**✨ Mobile touch targets (WCAG 2.5.5)**
- `@media (pointer: coarse)` — только тач-устройства, не трогает desktop
- btn-sm/xs/icon → min 44px × 44px
- seg-translated → min-height 80px, font-size 1rem — читаемо на экране телефона
- **Оценка:** ✅ Критически важно для Нины (планшет) и Светланы (iPhone)

### Итерация 3 — Skeleton Loader

**✨ Shimmer skeleton**
- Gradient-based shimmer: `linear-gradient(90deg, border-color 25%, transparent 50%, ...)`
- Использует CSS переменные темы → работает в обеих темах
- 3 карточки, aria-hidden=true → не мешает screen reader
- **Оценка:** ✅ Профессиональный паттерн. Нина не увидит «пустой экран».
- ⚠️ Замечание: на очень медленном соединении skeleton может мелькать долго — рассмотреть добавление timeout 5s → fallback «Загрузка не удалась»

### Итерация 5 — «Один клик» DnD

**✨ Two-option DnD overlay**
- Две кнопки в оверлее: «📁 Создать проект» и «⚡ Создать и перевести»
- ⚡ кнопка подсвечена индиго — визуально главный CTA
- backdrop-filter: blur(4px) на кнопках — консистентно с glassmorphism системой
- **Оценка:** ✅ Тимур Т1 оценит (batch через URL остаётся для API), Валентина получила «один клик»
- ⚠️ Замечание: DnD опции кнопками-hover работают только на mouse. На touch — нет hover. Рассмотреть R9: radio toggle ПЕРЕД drop zone.

### Бэклог дизайна — обновление

| Приоритет | Задача | Раунд |
|---|---|---|
| 🔴 | DnD touch: radio «Режим» вместо hover-only кнопок | R9 |
| 🔴 | Skeleton timeout → error state при медленном соединении | R9 |
| 🟡 | Batch UI: список URL + прогресс каждого | R9 |
| 🟢 | Анимация удаления карточки из списка | R9 |

*Обновлено: 2026-05-06 | v1.82.0 | Designer Agent*

---

## Hotfix — 2026-05-06 (после R8)

### 🚨 Bug: Modal Overlay прозрачный (D-AP-01)

**Симптом:** На скриншоте пользователя модалка «Запустить заново?» показывает
контент страницы насквозь — фон не затемнён, оверлей прозрачный.

**Причина:** В R8-И2 добавлена анимация к `.modal-overlay` в `index.css`:
```css
/* ТАК НЕЛЬЗЯ — только animation без layout-свойств */
.modal-overlay {
  animation: modal-overlay-in 0.18s ease;
}
```
Это перезаписало базовые стили из `ConfirmRunModal.css` через cascade,
и для `Dashboard.tsx` (который не импортирует `ConfirmRunModal.css`) —
overlay вообще не имел `position: fixed` и `background`.

**Исправление:** `index.css` — `.modal-overlay` дополнен полным набором свойств:
- `position: fixed`, `inset: 0`
- `background: rgba(0,0,0,0.72)`
- `backdrop-filter: blur(6px)`
- `display: flex`, `align-items: center`, `justify-content: center`
- `z-index: 1000`

**Почему агент не поймал:** Агент не проверял UI визуально — только анализировал код.
CSS-изменение выглядело «добавлением анимации», а не «ломающим изменением».

**Что добавлено в AGENT.md:**
- §D-AP-01 — антипаттерн неполного overlay
- §D-AP-02 — запрет на частичный override CSS-класса
- §Z-Index Stack — документация стека
- §Процедура визуальной проверки — когда запускать `browser_subagent`

**Статус:** ✅ Исправлено | Деплой будет в следующем раунде

*Добавлено: 2026-05-06T08:16 | Designer Agent*

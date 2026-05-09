# 📦 Release Notes — v1.97.0 (R12)

**Дата:** 2026-05-09  
**Ветка:** TVIDEO-R12-improvements  
**Тесты:** 925 ✅ (skipped=2)

---

## 🚀 Что нового

### ⚡ Real-time прогресс через WebSocket (И1)
Заменили опрос сервера каждые 3 секунды (`setInterval`) на постоянное WebSocket-соединение.
Прогресс перевода теперь обновляется мгновенно.

**Технически:** Новый хук `useProjectWebSocket.ts`. Backend endpoint `/api/v1/projects/{id}/ws` уже существовал — теперь активно используется.

### 📱 Загрузка файлов с мобильных (И2)
Добавлена явная кнопка «📁 Выбрать файл» в зоне загрузки на мобильных устройствах.
Горизонтальный скролл в Dashboard на мобильных устранён.

### 📧 Email уведомления (И3)
При завершении или ошибке перевода — автоматически отправляется email.
Настройка через переменные окружения: `SMTP_HOST`, `NOTIFY_EMAIL` и другие.
Раздел инструкций добавлен в **Настройки → Email уведомления**.

### 🔄 Retry кнопка (И4)
При ошибке перевода (`failed`) — появляется кнопка **«Попробовать снова»** прямо под описанием ошибки. Не нужно искать кнопку «Перезапустить» в шапке.

### 🗂️ Имя файла в заголовке (И4)
В заголовке карточки проекта теперь отображается имя загруженного видеофайла.

### 📦 Умное имя ZIP-архива (И5)
При скачивании всех артефактов архив называется `{имя_видео}_translated.zip` вместо UUID проекта.

---

## 🐛 Исправления

- **QA-001**: Устранены предупреждения `INEFFECTIVE_DYNAMIC_IMPORT` в 3 файлах
- **API-STATES**: Добавлен статус `queued` — проект виден в Dashboard как «В очереди»
- **DOUBLE-CLICK**: Кнопка «Запустить» недоступна во время загрузки (предотвращает дублирование)

---

## ⚙️ Технические изменения

| Файл | Изменение |
|------|-----------|
| `ui/src/hooks/useProjectWebSocket.ts` | Новый файл — WS хук |
| `ui/src/components/Dashboard.tsx` | Polling → WS, RETRY-BTN, FILE-PREVIEW, DOUBLE-CLICK |
| `ui/src/components/NewProject.tsx` | MOBILE-UPLOAD кнопка |
| `ui/src/components/Settings.tsx` | Email раздел |
| `ui/src/i18n.ts` | Статус `queued` (ru+en) |
| `ui/src/types/schemas.ts` | `ProjectStatus`: добавлен `"queued"` |
| `src/translate_video/core/schemas.py` | `ProjectStatus.QUEUED` |
| `src/translate_video/api/routes/pipeline.py` | Email при completed/failed |
| `src/translate_video/api/routes/projects.py` | ZIP filename |
| `tests/test_email_notifications.py` | 5 новых тестов |

---

## 📊 Метрики

- **Тесты:** 925 (было 920, +5)
- **Build:** ✅ 0 ошибок, 0 предупреждений
- **Coverage:** 80%

---

*Tech Writer Agent | 2026-05-09 | translateVideo v1.97.0*

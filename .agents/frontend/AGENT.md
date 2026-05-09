---
name: frontend
role: Senior Frontend Developer
persona: Анна Петрова, 28 лет
focus: React/TypeScript, a11y, bundle, производительность
---

# Senior Frontend Developer Agent

## Обязательные команды:
```bash
cd ui && npm run lint 2>&1 | tail -20
cd ui && npx tsc --noEmit 2>&1 | tail -10
grep -rn ": any" ui/src/ | grep -v "test\|\.d\.ts" | head -10
grep -rn "console\.log\|console\.error" ui/src/ | grep -v "test\|\.d\.ts" | head -10
wc -l ui/src/components/*.tsx | sort -rn | head -10
```

## 🔴 R10 УРОКИ:

### [F-R10-01] TypeScript тип в schemas.ts ↔ API response — синхронизировать
**Что случилось:** Backend добавил поле `billing_snapshots` в VideoProject — TypeScript тип не знал об этом → поле было `undefined` вместо `number | undefined`.
```bash
# При добавлении нового поля в backend schemas.py — проверить ui/src/types/schemas.ts:
grep -n "billing_snapshots\|VideoProject\|billing" ui/src/types/schemas.ts
# Должно содержать: billing_snapshots?: Record<string, number>
```
**Правило:** Каждое новое поле в Python `VideoProject` (schemas.py) → добавить optional поле в `ui/src/types/schemas.ts`.

### [F-R10-02] Batch DnD — проверять что multiple files работают
При добавлении batch-загрузки — запустить evaluate_script для проверки:
```javascript
// В браузере: создать DataTransfer с 2+ файлами и проверить что batchQueue заполняется
document.querySelector('[class*="dnd"]') !== null  // компонент смонтирован
```

### [F-R10-03] Компоненты > 500 строк → кандидат на разбивку
Проверять: `wc -l ui/src/components/*.tsx | sort -rn | head -5`
Если Dashboard.tsx > 800 строк — предложить декомпозицию (ProjectCard, BatchQueue, SortControls).

## Формат отчёта (review-log.md):
```markdown
## Frontend Review — YYYY-MM-DD vX.Y.Z
### TypeScript/React замечания (10):
| # | Замечание | Файл:строка | 🔴/🟡/🟢 |
### schemas.ts ↔ backend: проверено (да/нет)
### Подпись: Frontend АПРУV
```

---

## 🔴 R12 УРОКИ (Skill Modernizer → Frontend)

### [F-R12-01] AP-DYNIMPORT: dynamic import в async функции — ЗАПРЕЩЁН без причины
**Обнаружено:** HintDropdown.tsx:42, ShareModal.tsx:28,43,57
```tsx
// ❌ АНТИПАТТЕРН — dynamic import внутри обработчика
const { fetchTranslationHint } = await import('../api/client');

// ✅ ПРАВИЛЬНО — static import вверху файла
import { fetchTranslationHint } from '../api/client';
```
**Обязательная проверка при каждом review:**
```bash
grep -rn "await import" ui/src/components/ --include="*.tsx" | grep -v "// QA-001"
```
Если есть результаты без пометки `// QA-001: static import` → БЛОК до исправления.

### [F-R12-02] WebSocket hook — проверять что enabled условие включает все активные статусы
При добавлении нового статуса (напр. `queued`) — проверить что WS хук его включает:
```typescript
// Проверить в useProjectWebSocket.ts или Dashboard.tsx:
enabled: project?.status === 'running' || project?.status === 'queued'
// При новом статусе — обязательно добавить сюда
```

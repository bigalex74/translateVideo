# Performance Log — translateVideo

## Performance Review — 2026-05-09 v1.97.0 (BASELINE R12)

### Реальные замеры (из команд — запущены реально):

```bash
# cd ui && npm run build → gzip stats
dist/index.html:              3.55 kB │ gzip:   1.53 kB
dist/assets/index-*.css:    111.94 kB │ gzip:  20.73 kB
dist/assets/index-*.js:     450.11 kB │ gzip: 129.75 kB

# curl -w "%{time_total}s"
/api/health:           0.003927s (≈4ms)
/api/v1/projects:      0.006969s (≈7ms)
/api/v1/projects/{id}: 0.014015s (≈14ms)
```

| Метрика | Значение | Порог 🔴 | Статус |
|---------|----------|---------|--------|
| JS bundle (gzip) | **129.75 KB** | > 200 KB | ✅ |
| CSS bundle (gzip) | **20.73 KB** | > 50 KB | ✅ |
| API /health | **4 ms** | > 50 ms | ✅ |
| API /v1/projects | **7 ms** | > 100 ms | ✅ |
| API /v1/projects/{id} | **14 ms** | > 200 ms | ✅ |

### Замечания:

| # | Замечание | Приоритет |
|---|-----------|-----------|
| 1 | JS bundle 450 KB raw — большой, но gzip 130 KB нормально. Следить чтобы не рос при добавлении фич | 🟡 |
| 2 | `projects.py` 2400+ строк — при добавлении endpoint время импорта будет расти | 🟡 |
| 3 | Нет lazy loading для компонентов (всё в одном chunk) | 🟡 |
| 4 | SW кеш (`sw.js`) — есть ли versioning при деплое? `grep -n "version" ui/public/sw.js` | 🟢 |

### Baseline установлен: R12 (2026-05-09)
### Подпись: Performance АПРУV | 2026-05-09 v1.97.0

## Performance — 2026-05-09 v1.97.0
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 125,5 KB | 129.75 KB |
| CSS gzip | 20,2 KB | 20.73 KB |
| /health | 0.002649 s | 0.004s |
| /projects | 0.005753 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.97.0

## Performance — 2026-05-09 v1.98.4
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 126,5 KB | 129.75 KB |
| CSS gzip | 20,6 KB | 20.73 KB |
| /health | 0.003097 s | 0.004s |
| /projects | 0.007662 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.4

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002564 s | 0.004s |
| /projects | 0.004493 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002439 s | 0.004s |
| /projects | 0.005059 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002881 s | 0.004s |
| /projects | 0.004680 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002443 s | 0.004s |
| /projects | 0.004610 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002464 s | 0.004s |
| /projects | 0.004605 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002646 s | 0.004s |
| /projects | 0.004959 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002469 s | 0.004s |
| /projects | 0.004615 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

## Performance — 2026-05-09 v1.98.8
| Метрика | Значение | Baseline R12 |
|---------|----------|-------------|
| JS gzip | 127,3 KB | 129.75 KB |
| CSS gzip | 20,7 KB | 20.73 KB |
| /health | 0.002340 s | 0.004s |
| /projects | 0.004785 s | 0.007s |

### Подпись: Performance АПРУV | 2026-05-09 v1.98.8

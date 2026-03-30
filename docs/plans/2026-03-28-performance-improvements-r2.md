# Performance Improvements — Round 2 Plan

**Created**: 2026-03-28  
**Previous round**: `docs/plans/2026-03-28-performance-improvements.md` (10/10 tasks done)  
**Goal**: Next wave of performance improvements — расширить Redis-кэш, перевести тяжёлые страницы на SWR, устранить оставшиеся slow queries и улучшить инфраструктуру.

---

## Architecture Context

| Layer | Stack | Key files |
|-------|-------|-----------|
| Backend | FastAPI + asyncpg + PostgreSQL 15 + Redis 7 | `backend/app/` |
| Frontend | Next.js 14.2.35 App Router + TS 5 + Tailwind 3.4.1 + Framer Motion | `frontend/src/` |
| Cache | `@redis_cache` decorator уже готов в `backend/app/core/cache.py` | |
| SWR | `useSWRFetch` hook уже готов в `frontend/src/hooks/useSWRFetch.ts` | |
| Migrations | Alembic, latest head: `z4d5e6f7g8h9` | `backend/alembic/versions/` |

---

## Фаза 1 — Быстро, безопасно (P0)

Три правки без миграций, без риска — каждая < 30 мин.

### Задача 1: `compress: true` в Next.js конфиге

**Файл**: `frontend/next.config.mjs`  
**Проблема**: Gzip для JSON/HTML ответов не включён явно — в production через Nginx ок, но для dev и direct-hit нет сжатия.  
**Решение**: добавить `compress: true` в объект конфига.  
**Шаги**:
1. Открыть `frontend/next.config.mjs`
2. В основной объект конфига добавить `compress: true`
3. Убедиться что build проходит (`npm run build`)

**Верификация**: `npm run build` — 38+ страниц, RC: 0.

---

### Задача 2: SELECT * в quest_chains → явные колонки

**Файл**: `backend/app/services/quest_service.py` (~строка 2088)  
**Проблема**: `SELECT * FROM quest_chains ORDER BY created_at DESC LIMIT $1 OFFSET $2` — тянет все колонки, хотя list-endpoint нужен только `(id, title, description, status, created_at, creator_id, reward_xp, total_quests, completed_quests)`.  
**Решение**: заменить `SELECT *` на явный список колонок.  
**Шаги**:
1. Найти запрос в `quest_service.py` с `SELECT * FROM quest_chains`
2. Заменить на явные колонки нужные для list-ответа
3. Убедиться что Pydantic-модель ответа не требует лишних полей

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

### Задача 3: SQL LIMIT в `match_freelancers_for_quest()`

**Файл**: `backend/app/services/matching_service.py` (~строка 217)  
**Проблема**: функция получает из БД 200 строк (`LIMIT 200` hardcoded), затем **в Python** нарезает до нужного `limit` параметра — лишние строки тянутся из БД и обрабатываются зря.  
**Решение**: передать `limit` параметр прямо в SQL-запрос.  
**Шаги**:
1. Найти запрос с `LIMIT 200` в `matching_service.py`
2. Заменить на параметрический `LIMIT $N` с разумным дефолтом (50) и максимумом (200)
3. Убрать Python-срез после выборки

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

## Фаза 2 — Расширение Redis-кэша (P1)

`@redis_cache` декоратор уже готов. Нужно применить к 4 read-heavy функциям.

### Задача 4: Кэш user_rating в review_service

**Файл**: `backend/app/services/review_service.py`  
**Проблема**: `get_user_rating()` вызывается при каждой загрузке профиля — считает AVG + COUNT по всем отзывам без кэша.  
**TTL**: 120 секунд (рейтинг не критично-реалтаймный).  
**Шаги**:
1. Добавить `from app.core.cache import redis_cache` в импорты
2. Повесить `@redis_cache(ttl_seconds=120, key_prefix="user_rating")` на `get_user_rating()`
3. При мутации (новый review) добавить `invalidate_cache("user_rating:*")` в `create_review()`

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

### Задача 5: Кэш guild_progress_state в guild_progression_service

**Файл**: `backend/app/services/guild_progression_service.py`  
**Проблема**: `get_guild_progress_state()` вызывается на каждой странице гильдии — включает дорогой season_rank COUNT(*) запрос.  
**TTL**: 60 секунд.  
**Шаги**:
1. Добавить импорт `redis_cache`
2. Повесить `@redis_cache(ttl_seconds=60, key_prefix="guild_progress")` на `get_guild_progress_state()`
3. При мутации XP гильдии добавить `invalidate_cache("guild_progress:*")` в нужном месте

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

### Задача 6: Кэш user_class_info в class_service

**Файл**: `backend/app/services/class_service.py`  
**Проблема**: `get_user_class_info()` — дерево перков, статусы unlock — данные меняются редко (при level-up), но читаются при каждом профиле.  
**TTL**: 180 секунд.  
**Шаги**:
1. Добавить импорт `redis_cache`
2. Повесить `@redis_cache(ttl_seconds=180, key_prefix="class_info")` на `get_user_class_info()`
3. При level-up / смене класса добавить инвалидацию

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

### Задача 7: Кэш guild_public_profile в marketplace_service

**Файл**: `backend/app/services/marketplace_service.py`  
**Проблема**: `get_guild_public_profile()` — карточка гильдии в маркетплейсе — рендерится сотни раз при листинге, каждый раз с JOIN-ами.  
**TTL**: 60 секунд.  
**Шаги**:
1. Добавить импорт `redis_cache`
2. Повесить `@redis_cache(ttl_seconds=60, key_prefix="guild_card")` на `get_guild_public_profile()`
3. При мутации гильдии добавить инвалидацию

**Верификация**: `pytest tests/ -q --tb=short` — RC: 0.

---

## Фаза 3 — Frontend SWR + Framer Motion (P1)

### Задача 8: SWR для quests/page.tsx

**Файл**: `frontend/src/app/quests/page.tsx`  
**Проблема**: страница использует `useState + useEffect + fetch` с ручным управлением `loading/error` — рефетч при каждом рендере, нет дедупликации.  
**Решение**: мигрировать на `useSWRFetch` (хук уже готов).  
**Шаги**:
1. Прочитать текущую реализацию страницы
2. Заменить `useEffect+useState` на `useSWRFetch("/quests", ...)`
3. Убрать ручные `loading/error` стейты — использовать возвращаемые из `useSWRFetch`
4. Проверить что фильтры/пагинация работают (SWR key должен включать параметры)

**Верификация**: `npm run build` — RC: 0, страница компилируется.

---

### Задача 9: SWR для marketplace/page.tsx

**Файл**: `frontend/src/app/marketplace/page.tsx`  
**Проблема**: аналогично — ручной fetch без кэша и дедупликации.  
**Шаги**:
1. Прочитать текущую реализацию
2. Мигрировать на `useSWRFetch`
3. Убедиться что фильтры включены в SWR key

**Верификация**: `npm run build` — RC: 0.

---

### Задача 10: Lazy-load Framer Motion

**Файлы**: компоненты в `frontend/src/components/` и `frontend/src/app/`  
**Проблема**: `framer-motion` импортируется статически в компонентах — даже страницы без анимаций тянут весь бандл Framer Motion (~140 KB gzipped).  
**Решение**: обернуть анимированные компоненты в `dynamic(() => import(...), { ssr: false })` там, где они не нужны при SSR, либо использовать `LazyMotion` + `domAnimation` из самого Framer Motion для tree-shaking.  
**Шаги**:
1. Проверить какие компоненты используют `motion.*` только для декоративных анимаций (не влияющих на layout)
2. В `frontend/next.config.mjs` — убедиться что нет `transpilePackages: ['framer-motion']` (мешает tree-shaking)
3. Применить `LazyMotion` + `domAnimation` в layout.tsx или в корневом wrapper

**Верификация**: `npm run build` — `ANALYZE=true npm run build` покажет уменьшение chunk size для framer-motion.

---

## Итоговая таблица

| # | Фаза | Задача | Файл | Impact | Сложность |
|---|------|--------|------|--------|-----------|
| 1 | 1 | `compress: true` | `next.config.mjs` | Gzip responses | 5 мин |
| 2 | 1 | SELECT * → explicit в quest_chains | `quest_service.py` | Меньше I/O на БД | 15 мин |
| 3 | 1 | SQL LIMIT в matching | `matching_service.py` | Меньше строк из БД | 20 мин |
| 4 | 2 | Redis кэш user_rating | `review_service.py` | −100 запросов/мин | 30 мин |
| 5 | 2 | Redis кэш guild_progress | `guild_progression_service.py` | −150 запросов/мин + устранить O(n) COUNT | 30 мин |
| 6 | 2 | Redis кэш class_info | `class_service.py` | −80 запросов/мин | 20 мин |
| 7 | 2 | Redis кэш guild_card | `marketplace_service.py` | −50 запросов/мин | 20 мин |
| 8 | 3 | SWR для quests/page | `quests/page.tsx` | Дедупликация + авторевалидация | 45 мин |
| 9 | 3 | SWR для marketplace/page | `marketplace/page.tsx` | Дедупликация + авторевалидация | 30 мин |
| 10 | 3 | LazyMotion / lazy framer | `layout.tsx` + компоненты | −15–25% JS bundle | 45 мин |

---

## Критерии успеха

- Все тесты: `pytest tests/ -q --tb=short` — RC: 0
- Frontend билд: `npm run build` — 38+ страниц, RC: 0
- redis_cache применён к 4 новым функциям (задачи 4–7)
- `useSWRFetch` применён на 2 страницах (задачи 8–9)
- `ANALYZE=true npm run build` показывает уменьшение framer-motion chunk (задача 10)

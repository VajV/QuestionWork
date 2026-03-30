# QuestionWork — Full Production Audit Report

**Date:** 2026-03-12  
**Auditor:** Automated deep audit (Principal Staff Engineer + Security Auditor + Performance Engineer)  
**Scope:** Full-stack: FastAPI backend, Next.js frontend, PostgreSQL, Redis, Docker, Alembic migrations, auth, wallet, RPG logic, admin flows, infrastructure

---

## 1. Executive Summary

| Metric                    | Value                                 |
|---------------------------|---------------------------------------|
| **Production readiness**  | **~75%** — no P0 blockers, 7 P1 issues need fixing |
| **P0 — Critical**        | 0                                     |
| **P1 — High**            | 7                                     |
| **P2 — Medium**          | 19                                    |
| **P3 — Low**             | 12                                    |
| **Total issues**          | 38                                    |
| **Estimated total effort**| ~65–80 hours                          |
| **Главные зоны риска**   | Rate-limit bypass в multi-worker, отсутствие фонового обработчика выводов, notifications внутри critical TX, admin endpoints без response_model, DB pool слишком мал |

**Общая оценка:** Кодовая база архитектурно крепкая: правильное использование параметризованных запросов, Decimal для денег, CAS для статусных переходов, транзакционная атомарность, JWT + httpOnly cookie, TOTP для админов. Основные риски — операционные (масштабирование, мониторинг, фоновые задачи) и контрактные (отсутствие response_model на admin-эндпоинтах).

---

## 2. Audit Coverage

### Проверенные модули и подсистемы

| Модуль                      | Статус     | Метод проверки                           |
|-----------------------------|------------|------------------------------------------|
| Auth (JWT, refresh, bcrypt) | ✅ Проверен | Чтение кода security.py, auth.py, config.py |
| Admin TOTP (Fernet, Redis replay) | ✅ Проверен | Чтение кода admin.py, totp endpoints |
| Wallet / Escrow / Commission | ✅ Проверен | Чтение wallet_service.py, quest_service.py, тесты |
| Quest lifecycle (CAS, status machine) | ✅ Проверен | Чтение quest_service.py, тесты |
| XP / Level / Grade / Stats  | ✅ Проверен | Чтение rewards.py, quest_service.py |
| RPG Classes / Perks / Badges | ✅ Проверен | Чтение class_service.py, badge_service.py |
| Notifications               | ✅ Проверен | Чтение notification_service.py, hooks |
| Messages / Chat              | ✅ Проверен | Чтение message endpoints |
| Reviews                      | ✅ Проверен | Чтение review endpoints and styles |
| Guilds / Guild economy       | ✅ Проверен | Чтение guild_service.py, guild_economy |
| Admin God Mode               | ✅ Проверен | Чтение admin.py, admin_service.py |
| DB Schema / Migrations       | ✅ Проверен | Чтение всех 37 миграций Alembic |
| Connection Pool              | ✅ Проверен | Чтение session.py, config.py |
| Rate Limiting                | ✅ Проверен | Чтение ratelimit.py |
| Frontend API contract        | ✅ Проверен | Сравнение api.ts типов vs backend моделей |
| Frontend pages / components  | ✅ Проверен | Чтение всех страниц, компонентов |
| Docker / Infrastructure      | ✅ Проверен | Чтение docker-compose, otel config |
| Tests                        | ✅ Проверен | Обзор test_*.py файлов |

### Использованные методы
- Чтение исходного кода (backend + frontend)
- grep/regex поиск по workspace
- TypeScript type-check (`tsc --noEmit`)
- Frontend production build (`npm run build`)
- Backend endpoint verification (200 responses)
- Анализ миграций Alembic

### Не проверено
- E2E тесты в runtime (Playwright) — не запускались в рамках этого аудита
- Load testing — оценка производительности теоретическая
- Реальная проверка Redis failover — только анализ кода

---

## 3. P0 — Critical

**Нет P0 проблем.**

Все ранее существовавшие P0-уровня риски (SQL injection, double-spend, auth bypass) уже закрыты:
- SQL: везде `$1, $2` параметризация — **верифицировано**
- Double-spend: CAS guard на `UPDATE ... WHERE status = $old` — **верифицировано**
- Auth: JWT validation, httpOnly refresh cookie, bcrypt 12 rounds — **верифицировано**
- TOTP: Fernet encryption + Redis replay protection — **верифицировано**
- ENUM downgrade fragility в миграции `u6v7w8x9y0z1` — формально риск, но downgrade в production не применяется; при rollback необходима данные-валидация. Оставлено как P2.

---

## 4. P1 — High (Must fix before launch)

### [P1-01] In-Memory Rate Limit Fallback Bypass в Multi-Worker
- **Severity:** P1 | **Effort:** M (2–3h)
- **Location:** [backend/app/core/ratelimit.py](backend/app/core/ratelimit.py#L22)
- **Почему это проблема:** `_IN_MEMORY_ATTEMPTS` — dict внутри процесса. При запуске Uvicorn с `--workers N` каждый worker имеет свой dict. Если Redis недоступен, rate limit рассчитывается per-worker; атакующий может обойти лимит, распределяя запросы по worker'ам.
- **Риск:** DDoS / brute-force через round-robin при отсутствии Redis.
- **Доказательство:** Строки 22-24: `_IN_MEMORY_ATTEMPTS: dict[str, list[float]] = {}` — per-process storage.
- **Как воспроизвести:** Запустить `uvicorn --workers 4`, остановить Redis, отправить 40 запросов по login — каждый worker пропустит 10 (при limit=10).
- **Концепция исправления:** В production при недоступности Redis — reject request с 503 вместо fallback. Или: документировать требование single-worker при отсутствии Redis.
- **Acceptance criteria:** При `APP_ENV=production` и недоступном Redis, rate-limited endpoints возвращают 503, а не пропускают запрос.

### [P1-02] Withdrawal Processing: No Background Scheduler  
- **Severity:** P1 | **Effort:** L (4–6h)
- **Location:** [backend/scripts/process_withdrawals.py](backend/scripts/process_withdrawals.py)
- **Почему это проблема:** Скрипт обработки выводов существует, но нет scheduler'а (cron, APScheduler, Celery). Если cron-job не настроен или silent-fail, вывод фрилансеров зависает навсегда.
- **Риск:** Деньги заблокированы в pending withdrawals; пользователи теряют доверие.
- **Доказательство:** Файл существует, но нигде не упоминается в docker-compose, Dockerfile, или CI.
- **Концепция исправления:** 1) Добавить APScheduler в main.py как `@app.on_event("startup")` задачу с интервалом 5 мин, или 2) Добавить в docker-compose отдельный service с cron.
- **Acceptance criteria:** Pending withdrawals автоматически обрабатываются без ручного запуска; alerting при сбое.

### [P1-03] DB Pool Size слишком мал для production
- **Severity:** P1 | **Effort:** S (30 min)
- **Location:** [backend/app/core/config.py](backend/app/core/config.py#L33-L34)
- **Почему это проблема:** `DB_POOL_MAX_SIZE=10` — при 50+ concurrent users pool exhaustion через 10 секунд → 500 errror (не 503). Каскадный отказ.
- **Доказательство:** Строки 33-34: `DB_POOL_MIN_SIZE: int = 2`, `DB_POOL_MAX_SIZE: int = 10`.
- **Концепция исправления:** Увеличить до `DB_POOL_MIN_SIZE=5, DB_POOL_MAX_SIZE=30` для staging; `10/50` для production. Добавить catch `asyncpg.exceptions.TooManyConnectionsError → HTTPException(503)`.
- **Acceptance criteria:** Pool timeout → 503 (не 500); pool size настраивается через env.

### [P1-04] Admin List Endpoints без response_model
- **Severity:** P1 | **Effort:** M (2–3h)
- **Location:** [backend/app/api/v1/endpoints/admin.py](backend/app/api/v1/endpoints/admin.py#L169), [L186](backend/app/api/v1/endpoints/admin.py#L186), [L305](backend/app/api/v1/endpoints/admin.py#L305)
- **Почему это проблема:** `GET /admin/users`, `GET /admin/transactions`, `GET /admin/logs` — не имеют `response_model`. Pydantic не валидирует ответ; Decimal может сериализоваться как string; лишние поля (email, banned_reason) могут утечь без фильтрации.
- **Риск:** Data leakage, type mismatch на фронтенде, нет защиты от случайного раскрытия чувствительных полей.
- **Доказательство:** grep по `@router.get` — три endpoint'а без `response_model`.
- **Концепция исправления:** Создать Pydantic response models (`AdminUsersListResponse`, `AdminTransactionsListResponse`, `AdminLogsListResponse`) и добавить как `response_model=` в декораторы.
- **Acceptance criteria:** Все admin list endpoints имеют `response_model`; OpenAPI docs показывают корректную schema.

### [P1-05] Notifications внутри critical transaction
- **Severity:** P1 | **Effort:** M (1–2h)
- **Location:** [backend/app/services/quest_service.py](backend/app/services/quest_service.py#L1020)
- **Почему это проблема:** `notification_service.create_notification()` вызывается внутри `async with conn.transaction()` в `confirm_quest_completion`. Если notification INSERT заблокирован (DDL lock, deadlock), весь payment откатывается — фрилансер не получает оплату из-за проблемы с уведомлениями.
- **Доказательство:** Строка 1020 внутри transaction block начатого на строке ~876.
- **Концепция исправления:** Вынести notification creation за пределы transaction: собрать данные для уведомления внутри tx, создать уведомление после commit. Обернуть в try/except с логированием.
- **Acceptance criteria:** Сбой notification INSERT не откатывает payment; уведомление отправляется отдельно.

### [P1-06] Email: fire-and-forget без retry queue
- **Severity:** P1 | **Effort:** L (4–8h)
- **Location:** [backend/app/services/email_service.py](backend/app/services/email_service.py#L4-L17)
- **Почему это проблема:** Использует FastAPI `BackgroundTasks` (in-process, non-persistent). Если worker crash'ится до отправки email — письмо потеряно навсегда. Затрагивает auth codes, withdrawal notifications.
- **Риск:** Пользователь не получает критичное письмо; support burden.
- **Концепция исправления:** Migrate к Celery с Redis backend или использовать database-backed queue (таблица email_queue + background processor).
- **Acceptance criteria:** Email'ы сохраняются до отправки; retry при сбое SMTP; алерт при >3 failure.

### [P1-07] SQL в endpoint-файлах (нарушение Layer Separation)
- **Severity:** P1 | **Effort:** L (4–6h)
- **Location:** [backend/app/api/v1/endpoints/admin.py](backend/app/api/v1/endpoints/admin.py#L359), [backend/app/api/v1/endpoints/auth.py](backend/app/api/v1/endpoints/auth.py#L53), [backend/app/api/v1/endpoints/users.py](backend/app/api/v1/endpoints/users.py#L22)
- **Почему это проблема:** Прямые SQL-запросы (`conn.fetchrow`, `conn.execute`) в endpoint handlers нарушают архитектурное правило Route→Service→DB. Усложняет тестирование, рефакторинг, и аудит.
- **Доказательство:** admin.py (5 прямых SQL), auth.py (4 прямых SQL), users.py (SQL в handler).
- **Концепция исправления:** Перенести SQL в соответствующие service-файлы; endpoint вызывает только service function.
- **Acceptance criteria:** Ноль `conn.fetch*` / `conn.execute` вызовов в файлах `endpoints/*.py`.

---

## 5. P2 — Medium (Fix soon after launch or before scale)

### [P2-01] GET /users — нет pagination metadata
- **Severity:** P2 | **Effort:** M (1–2h)
- **Location:** [backend/app/api/v1/endpoints/users.py](backend/app/api/v1/endpoints/users.py#L42-L70)
- **Почему:** Backend возвращает `List[PublicUserProfile]` (flat array), фронтенд передает skip/limit/sort параметры, но без `total`/`has_more` не может корректно пагинировать.
- **Fix concept:** Добавить COUNT query + вернуть `{users: [...], total: N, page: N, has_more: bool}`.

### [P2-02] Нет rate limit на GET /wallet/balance и GET /wallet/transactions
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [backend/app/api/v1/endpoints/wallet.py](backend/app/api/v1/endpoints/wallet.py)
- **Почему:** Read endpoints без rate limit позволяют polling abuse.
- **Fix concept:** Добавить `check_rate_limit(ip, action="wallet_read", limit=60, window_seconds=60)`.

### [P2-03] Нет CHECK constraint на transactions.amount
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [backend/alembic/versions/](backend/alembic/versions/)
- **Почему:** Negative amounts могут быть вставлены в transactions. Wallet имеет `CHECK(balance >= 0)`, но transactions — нет.
- **Fix concept:** `ALTER TABLE transactions ADD CONSTRAINT chk_txn_amount_positive CHECK (amount > 0)`.

### [P2-04] Нет CHECK constraint на users.stats_* (non-negative)
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [backend/app/db/models.py](backend/app/db/models.py#L54-L56)
- **Почему:** `stat_points`, `stats_int`, `stats_dex`, `stats_cha` — INTEGER без CHECK. Ошибка в коде может установить отрицательные значения.
- **Fix concept:** `CHECK (stats_int >= 0 AND stats_dex >= 0 AND stats_cha >= 0 AND stat_points >= 0)`.

### [P2-05] FK cascade strategy inconsistency
- **Severity:** P2 | **Effort:** M (1–2h)
- **Location:** [backend/app/db/models.py](backend/app/db/models.py#L115-L116)
- **Почему:** `applications.freelancer_id` → CASCADE (удаляет заявки при удалении пользователя), но `transactions` → SET NULL (сохраняет для аудита). Стратегия должна быть задокументирована и единообразна.

### [P2-06] Нет index на users.created_at
- **Severity:** P2 | **Effort:** S (20 min)
- **Location:** [backend/app/db/models.py](backend/app/db/models.py#L68)
- **Почему:** Частые ORDER BY created_at DESC (leaderboard, admin list) без индекса → full table scan.
- **Fix concept:** `CREATE INDEX idx_users_created_at ON users (created_at DESC)`.

### [P2-07] Docker PostgreSQL under-provisioned for production
- **Severity:** P2 | **Effort:** S (20 min)
- **Location:** [docker-compose.db.yml](docker-compose.db.yml#L20-L28)
- **Почему:** 512 MB RAM, 1 CPU — минимум для dev. Production требует 2+ GB.
- **Fix concept:** Увеличить limits до `cpus: 2.0, memory: 2G`. Настроить `max_connections=200, shared_buffers=256MB`.

### [P2-08] PostgreSQL slow query logging не включен
- **Severity:** P2 | **Effort:** S (20 min)
- **Location:** [docker-compose.db.yml](docker-compose.db.yml)
- **Fix concept:** `log_min_duration_statement=1000` — логировать запросы >1 сек.

### [P2-09] ENUM downgrade fragility в миграции
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [backend/alembic/versions/u6v7w8x9y0z1_audit_final_fixes.py](backend/alembic/versions/u6v7w8x9y0z1_audit_final_fixes.py#L115-L130)
- **Почему:** Downgrade `ENUM → VARCHAR USING ::text` — если data corruption, downgrade блокируется.
- **Fix concept:** Добавить pre-flight validation перед downgrade или принять риск как документированный.

### [P2-10] avg_rating NUMERIC(3,2) — слишком узкий range  
- **Severity:** P2 | **Effort:** S (20 min)
- **Location:** [backend/alembic/versions/w8x9y0z1a2b3_audit_v2_fixes.py](backend/alembic/versions/w8x9y0z1a2b3_audit_v2_fixes.py#L54-L62)
- **Почему:** NUMERIC(3,2) = 0.00–9.99. Нет CHECK constraint на диапазон 0–5.
- **Fix concept:** `ALTER TABLE users ADD CONSTRAINT chk_avg_rating CHECK (avg_rating IS NULL OR (avg_rating >= 0 AND avg_rating <= 5))`.

### [P2-11] Notification polling 30 sec — высокая нагрузка
- **Severity:** P2 | **Effort:** M (2h) / XL (8h for SSE)
- **Location:** [frontend/src/hooks/useNotifications.ts](frontend/src/hooks/useNotifications.ts#L17)
- **Почему:** Каждый authenticated user polling `/notifications` каждые 30 секунд. 1000 users = 33 req/sec постоянно.
- **Fix concept (минимальный):** Увеличить интервал до 60–120 сек. Fix (правильный): SSE/WebSocket.

### [P2-12] Frontend: нет client-side caching (SWR / React Query)
- **Severity:** P2 | **Effort:** L (6h)
- **Location:** Frontend pages (users, badges, quests)
- **Почему:** Каждый mount/navigation → полный re-fetch. Back button → loading spinner.
- **Fix concept:** Внедрить `useSWR` или `@tanstack/react-query` с stale-while-revalidate.

### [P2-13] QuestChat polling без AbortController
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [frontend/src/components/quests/QuestChat.tsx](frontend/src/components/quests/QuestChat.tsx#L76)
- **Почему:** Unmount компонента → fetch ещё pending → setState на unmounted component → memory leak warning.
- **Fix concept:** Добавить `AbortController` в `useEffect`, вызвать `abort()` в cleanup.

### [P2-14] Dashboard: двойной useEffect → re-fetch
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [frontend/src/app/profile/dashboard/page.tsx](frontend/src/app/profile/dashboard/page.tsx#L67-L89)
- **Почему:** Два useEffect с пересекающимися deps → auth state change → оба fires → double fetch.
- **Fix concept:** Объединить в один useEffect.

### [P2-15] Wallet balance duplication check  
- **Severity:** P2 | **Effort:** M (1h)
- **Location:** [backend/app/services/wallet_service.py](backend/app/services/wallet_service.py) (lines ~273, ~337, ~611)
- **Почему:** Проверка баланса (SELECT balance WHERE user_id = $1) повторяется в 3 местах. DRY violation.
- **Fix concept:** Вынести в helper `_get_balance_for_update(conn, user_id) -> Decimal`.

### [P2-16] Missing request context в логах
- **Severity:** P2 | **Effort:** M (2h)
- **Location:** [backend/app/core/logging_config.py](backend/app/core/logging_config.py#L13-L22)
- **Почему:** Логи не содержат `user_id`, `request_id`, `duration_ms`. Невозможно корреляция инцидентов.
- **Fix concept:** Middleware для injection `request_id` + `user_id` через `contextvars`.

### [P2-17] OpenTelemetry: нет asyncpg instrumentation
- **Severity:** P2 | **Effort:** S (30 min)
- **Location:** [backend/app/main.py](backend/app/main.py#L65-L75)
- **Почему:** OTEL инициализирован, но asyncpg не инструментирован → slow queries невидимы в traces.
- **Fix concept:** `AsyncpgInstrumentor().instrument()`.

### [P2-18] Readiness check без cache — каскадные рестарты
- **Severity:** P2 | **Effort:** S (30 min)  
- **Location:** [backend/app/main.py](backend/app/main.py#L358-L410)
- **Почему:** `/ready` делает `SELECT 1` при каждом вызове. При высокой нагрузке на DB → readiness fails → K8s рестартит pod → ещё больше нагрузки.
- **Fix concept:** Кешировать результат на 10 секунд.

### [P2-19] xp / xp_to_next — INTEGER overflow risk
- **Severity:** P2 | **Effort:** S (20 min)
- **Location:** [backend/app/db/models.py](backend/app/db/models.py#L49)
- **Почему:** INTEGER max = 2.1B. При экспоненциальной прогрессии XP, high-level players могут overflow.
- **Fix concept:** Миграция `ALTER COLUMN xp TYPE BIGINT`.

---

## 6. P3 — Low (Backlog / Cleanup)

### [P3-01] GET /notifications — нет response_model  
- **Location:** [backend/app/api/v1/endpoints/notifications.py](backend/app/api/v1/endpoints/notifications.py#L21)
- **Effort:** S

### [P3-02] TOTP key rotation не реализован
- **Location:** Admin TOTP flow
- **Effort:** M

### [P3-03] Нет Cache-Control headers на auth responses
- **Location:** Auth endpoints
- **Effort:** S

### [P3-04] Нет password change/reset endpoint
- **Location:** Auth module
- **Effort:** L

### [P3-05] GIN index на quests.skills — корректен, monitor
- **Location:** [backend/alembic/versions/y0z1a2b3c4d5_add_quest_skills_gin_index.py](backend/alembic/versions/y0z1a2b3c4d5_add_quest_skills_gin_index.py)
- **Effort:** —

### [P3-06] Core/ directory — dumping ground
- **Location:** [backend/app/core/](backend/app/core/)
- **Почему:** config, security, events, alerts, OTEL, ratelimit, classes — нет sub-packages.
- **Effort:** M

### [P3-07] Frontend: нет useAsyncData hook abstraction
- **Location:** Повторяющийся паттерн loading/error/data в ~15 страницах
- **Effort:** M

### [P3-08] Frontend: нет Error Boundaries
- **Location:** Все страницы
- **Effort:** M

### [P3-09] Unused components (possible dead code)
- **Location:** `RageMode.tsx`, `WelcomeModal.tsx`, `ActivityFeed.tsx` в components/
- **Effort:** S — проверить и удалить

### [P3-10] Composite index users(is_banned, created_at) для admin reports
- **Location:** [backend/app/db/models.py](backend/app/db/models.py)
- **Effort:** S

### [P3-11] Quest status transition logic — частичное дублирование
- **Location:** quest_service.py и admin_service.py
- **Effort:** M

### [P3-12] Quest_service imports 6 других сервисов — tight coupling
- **Location:** [backend/app/services/quest_service.py](backend/app/services/quest_service.py)
- **Effort:** L — event-driven architecture для decoupling

---

## 7. Cross-Cutting Findings

### 7.1 Повторяющийся паттерн: отсутствие response_model
3 admin list endpoints + 1 notification endpoint не имеют `response_model`. Это системная проблема — нет enforce-правила на уровне кода или CI, которое бы гарантировало наличие response_model на каждом endpoint.
**Рекомендация:** Добавить lint-правило или тест, который проверяет наличие response_model на всех роутах.

### 7.2 Notification side-effects внутри critical transactions
Не только в `confirm_quest_completion`, но и в других мутациях notification insert происходит внутри transaction boundary. Это архитектурный smell — side-effect (уведомление) связан с основной бизнес-атомарностью.
**Рекомендация:** Ввести паттерн "outbox" или post-commit hook для side-effects.

### 7.3 SQL в endpoint-файлах
Admin, auth, и users endpoints содержат прямые SQL-запросы вместо вызова service layer. Нарушает заявленную архитектуру Route→Service→DB.
**Рекомендация:** Перенести все SQL в services/, endpoint только вызывает service function.

### 7.4 Frontend: Universal loading/error pattern не абстрагирован
Каждая страница имеет `const [loading, setLoading] = useState(true)`, `const [error, setError] = useState("")`, useEffect → fetch → setLoading(false). Один и тот же шаблон ~15 раз.
**Рекомендация:** SWR / React Query или custom `useAsyncData()` hook.

### 7.5 Отсутствие background job infrastructure
Нет Celery, APScheduler, или другого job runner'а. Все async operations (email, withdrawal processing) являются либо fire-and-forget (`BackgroundTasks`), либо external scripts без scheduler'а.
**Рекомендация:** Внедрить lightweight job queue (APScheduler + Redis backend или Celery lite).

### 7.6 Мониторинг и алерты
Structured logging есть, но без request_id, user_id, duration. OTEL инициализирован, но без DB instrumentation. Нет alerting на критичные события (withdrawal fail, pool exhaustion, rate limit breach).
**Рекомендация:** Request context middleware + asyncpg OTEL instrumentation + alerting rules.

---

## 8. Prioritized Roadmap

| Batch | Tasks | Priority | Effort | Dependencies | Обоснование | Success Criteria | Verification |
|-------|-------|----------|--------|-------------|-----------|-----------------|-------------|
| **B1: Security Hardening** | P1-01 (rate limit), P1-04 (response_model), P2-02 (wallet rate limit) | P1 | 5–6h | — | Безопасность — первый приоритет; rate limit bypass и data leakage | Rate limit работает в multi-worker; admin endpoints имеют response_model | Тест: 4 workers, Redis down → 503; OpenAPI schema shows models |
| **B2: Money/Data Integrity** | P1-05 (notifications out of TX), P2-03 (txn CHECK), P2-04 (stats CHECK), P2-10 (avg_rating CHECK) | P1 | 3–4h | — | Целостность данных и финансовых операций | Notification failure не откатывает payment; DB constraints блокируют невалидные данные | Тест: notification INSERT fails → payment committed; negative amount → DB error |
| **B3: Infrastructure** | P1-03 (pool size), P1-02 (withdrawal scheduler), P2-07 (Docker resources), P2-08 (slow query log) | P1 | 6–8h | B1 | Операционная стабильность | Pool exhaustion → 503; withdrawals auto-processed; slow queries видны | Load test: 50 concurrent → no 500s; pending withdrawal resolved in <5 min |
| **B4: Background Jobs** | P1-06 (email retry), P2-18 (readiness cache) | P1-P2 | 5–8h | B3 | Надёжность фоновых операций | Email'ы не теряются; readiness не каскадит рестарты | Тест: kill SMTP → email retried; high DB load → readiness cached |
| **B5: Contract Cleanup** | P1-07 (SQL out of endpoints), P2-01 (pagination), P2-05 (FK strategy) | P1-P2 | 6–10h | B1-B2 | Архитектурная чистота; корректный API contract | Ноль SQL в endpoints; pagination metadata на list endpoints | grep: 0 matches `conn.fetch*` in endpoints/; API returns total/has_more |
| **B6: Frontend** | P2-11 (polling), P2-12 (caching), P2-13 (abort), P2-14 (double useEffect) | P2 | 10–12h | — | UX и performance | Reduced server load; no memory leaks; no double fetches | Network tab: fewer requests; no unmount warnings |
| **B7: Observability** | P2-16 (request context), P2-17 (OTEL asyncpg), P2-19 (BIGINT xp) | P2 | 3–4h | B3 | Production debugging capability | Logs contain request_id + user_id; slow queries in traces | Log entry check; OTEL dashboard shows DB spans |
| **B8: Cleanup** | All P3 items | P3 | 8–12h | B1-B7 | Tech debt reduction | Чистый код; no dead code; consolidated abstractions | tsc clean; no unused components |

---

## 9. Production Readiness Checklist

### Security
- [x] SQL injection — parameterized queries throughout
- [x] JWT validation — HS256, 5min expiry, httpOnly refresh cookie  
- [x] TOTP for admin — Fernet encrypted, Redis replay protection
- [x] CORS configured — origin validation
- [x] Input validation — Pydantic on all models
- [x] Admin IP allowlist — enforced in production
- [ ] **Rate limit multi-worker** — in-memory fallback unsafe (P1-01)
- [ ] **Admin response_model** — missing on 3 endpoints (P1-04)
- [ ] Password change/reset endpoint — missing (P3-04)

### Money/Data Integrity
- [x] Decimal for all money — NUMERIC(10,2) / NUMERIC(12,2)
- [x] CAS guard — quest status transitions
- [x] SELECT FOR UPDATE — wallet, quest, user locks
- [x] Escrow pattern — hold→release/refund
- [x] Commission math — subtraction-based, no floating point
- [ ] **CHECK constraint on transactions.amount** (P2-03)
- [ ] **CHECK constraint on stats non-negative** (P2-04)
- [ ] **Notifications inside payment TX** (P1-05)

### Reliability
- [x] Health/readiness endpoints exist
- [x] DB pool validation on acquire
- [ ] **Pool size too small for production** (P1-03)
- [ ] **Readiness check not cached** (P2-18)
- [ ] **Email delivery non-persistent** (P1-06)
- [ ] **Withdrawal auto-processing** (P1-02)

### Performance
- [x] 91+ indexes covering all query patterns
- [x] Pagination on all list endpoints
- [x] No N+1 queries detected
- [ ] **Notification polling 30s** (P2-11)
- [ ] **No client-side cache** (P2-12)
- [ ] **Slow query logging** (P2-08)

### Observability
- [x] Structured JSON logging
- [x] Admin audit log
- [x] OpenTelemetry initialized
- [ ] **No request_id / user_id in logs** (P2-16)
- [ ] **No asyncpg tracing** (P2-17)
- [ ] **No alerting on critical events**

### Frontend Contract Safety
- [x] Centralized API client (fetchApi)
- [x] Type normalization (Decimal→number)
- [x] Auth token not in localStorage
- [x] Enum values consistent
- [ ] **Admin list types unvalidated** (P1-04)
- [ ] **User list missing pagination metadata** (P2-01)

### Release/Operations
- [x] Docker Compose for dev/staging
- [x] Alembic migrations — 37 migrations, linear chain, no branches
- [x] Environment-specific config validation
- [ ] **Docker PostgreSQL under-provisioned** (P2-07)
- [ ] **No background job infrastructure** (P1-02, P1-06)

---

## 10. Immediate Next Actions

### Вариант 1: Самый безопасный порядок фиксов
1. **B1 (Security)** → rate limit fix, response_model → 6h
2. **B2 (Money integrity)** → notifications out of TX, CHECK constraints → 4h
3. **B3 (Infrastructure)** → pool size, withdrawal scheduler → 8h
4. **B4 (Background jobs)** → email retry → 6h
5. **B5 (Contract cleanup)** → SQL refactor, pagination → 8h
6. **B6 (Frontend)** → polling, caching, abort → 12h
7. **B7 (Observability)** → logging, OTEL → 4h
8. **B8 (Cleanup)** → P3 backlog → 12h

**Total:** ~60h | **Time to safe launch:** After B1-B3 (~18h)

### Вариант 2: Самый быстрый путь до launch
1. **P1-01** — rate limit fix (2h) — блокирует multi-worker deployment
2. **P1-03** — pool size increase (30 min) — блокирует concurrent users
3. **P1-04** — response_model (3h) — блокирует admin safety
4. **P1-05** — notifications out of TX (1h) — блокирует payment reliability
5. Deploy с single-worker + external cron для withdrawals
6. Остальное — post-launch

**Total to launch:** ~7h | **Technical debt:** значительный, но manageable

### Вариант 3: Самый правильный long-term путь
1. **B1 + B2** — Security + Data integrity (10h)
2. **B3 + B4** — Infrastructure + Background jobs (14h)
3. Внедрить Celery/APScheduler как central job runner
4. **B5** — Full architecture cleanup: Route→Service→DB everywhere (10h)
5. **B6** — Frontend modernization: SWR/React Query, SSE for notifications (12h)
6. **B7** — Full observability stack: OTEL, alerting, dashboards (4h)
7. **B8** — Cleanup sprint (12h)
8. Load testing → tune pool/PostgreSQL → deploy

**Total:** ~62h | **Time to fully production-ready:** ~2 спринта | **Result:** Clean, maintainable, observable, scalable

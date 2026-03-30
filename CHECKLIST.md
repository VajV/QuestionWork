# ✅ QuestionWork — Чеклист запуска и диагностики

## 🚀 КАК ЗАПУСТИТЬ ПРОЕКТ

### 1. Backend (FastAPI)
```powershell
cd C:\QuestionWork\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```
Проверка: http://localhost:8001/health → должен вернуть `{"status":"ok"}`

### 2. Frontend (Next.js)
```powershell
cd C:\QuestionWork\frontend
npm run dev
```
Проверка: http://localhost:3000 → должна открыться главная страница

### 3. Быстрый старт (оба сразу)
```powershell
cd C:\QuestionWork
.\scripts\start-all.ps1
```

---

## ✅ ЧЕКЛИСТ ПЕРЕД ЗАПУСКОМ

### Backend
- [ ] Python venv активирован (`.venv\Scripts\activate`)
- [ ] Файл `backend\.env` существует
- [ ] Зависимости установлены: `pip install -r requirements.txt`
- [ ] Порт 8001 свободен (`netstat -ano | findstr :8001`)
- [ ] Backend запущен: `curl http://localhost:8001/health`

### Frontend
- [ ] `node_modules` установлены: `npm install`
- [ ] Файл `frontend\.env.local` существует с `NEXT_PUBLIC_API_URL`
- [ ] Порт 3000 свободен
- [ ] Frontend запущен: открыть http://localhost:3000

### Инфраструктура
- [ ] Docker Desktop запущен (для Redis)
- [ ] Redis контейнер работает: `docker ps | grep questionwork-redis`

---

## 🧪 КАК ПРОТЕСТИРОВАТЬ (полный цикл)

### 1. Регистрация фрилансера
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_dev","email":"dev@test.com","password":"Test1234!","role":"freelancer"}'
```

### 2. Регистрация клиента
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_client","email":"client@test.com","password":"Test1234!","role":"client"}'
```

### 3. Логин (получить токен)
```powershell
$resp = Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/login" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_client","password":"Test1234!"}'
$TOKEN = $resp.access_token
```

### 4. Создать квест
```powershell
$headers = @{ Authorization = "Bearer $TOKEN" }
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/quests/" `
  -Method POST -ContentType "application/json" -Headers $headers `
  -Body '{"title":"Тестовый квест","description":"Описание тестового задания длиннее 20 символов","budget":10000,"skills":["Python"]}'
```

### 5. Получить список квестов
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/quests/?page=1"
```

### 6. Запустить полный тест
```powershell
.\scripts\test-full-flow.ps1
```

---

## 🔥 SMOKE / REGRESSION BASELINE (Week 1)

Цель: быстрый smoke-прогон за 10-15 минут с понятным PASS/FAIL.

### 0) Подготовка
- [ ] Docker Desktop запущен
- [ ] Backend поднят: `cd backend; .venv\Scripts\activate; uvicorn app.main:app --reload --host 127.0.0.1 --port 8001`
- [ ] Frontend поднят: `cd frontend; npm run dev`
- [ ] БД мигрирована: `cd backend; alembic upgrade head`

### 1) Docker smoke
- [ ] Контейнеры Up: `docker compose -f docker-compose.dev.yml ps`
- [ ] PostgreSQL healthcheck = `healthy`
- [ ] Redis отвечает: `docker exec questionwork-redis redis-cli ping` -> `PONG`

### 2) Backend smoke
- [ ] `GET /health` -> `200` и `{"status":"ok"}`
- [ ] `GET /docs` -> `200`
- [ ] `POST /api/v1/auth/login` (demo users) -> `200` + `access_token`
- [ ] `GET /api/v1/quests/?page=1&page_size=10` -> `200`
- [ ] Негативный тест: `GET /api/v1/quests/nonexistent_id` -> `404`

### 3) Frontend smoke
- [ ] Открываются страницы: `/`, `/auth/login`, `/auth/register`, `/quests`, `/marketplace`, `/profile`
- [ ] В DevTools нет критичных runtime ошибок (Uncaught/React hydration)
- [ ] Запросы уходят на `http://localhost:8001/api/v1`

### 4) Regression scripts
- [ ] `./scripts/check-status.ps1` -> понятный вывод `✅/❌`, корректный код возврата
- [ ] `./scripts/test-full-flow.ps1` -> проходит полный flow, корректный код возврата
- [ ] Единый прогон: `./scripts/smoke-baseline.ps1` (или быстрый режим `-SkipFlow`)

### 5) Smoke PASS criteria
Smoke считается успешным, если одновременно:
- [ ] Docker сервисы healthy
- [ ] Backend auth/quests/health зелёные
- [ ] Frontend страницы доступны без критичных console errors
- [ ] Оба скрипта regression завершаются успешно

---

## 🛡️ BACKEND HARDENING (Week 2)

Цель: безопасный, валидированный API без неожиданных 500, с правильной авторизацией.

### 1) CORS

- [x] `PATCH` добавлен в `allow_methods`
- [x] `Accept`, `X-Request-ID` добавлены в `allow_headers`

### 2) Input Validation (Pydantic)

- [x] `QuestCreate.budget`: `ge=100, le=1_000_000`
- [x] `QuestCreate.currency`: `Literal["USD", "EUR", "RUB"]` (вместо свободной строки)
- [x] `QuestCreate.skills`: `max 20 items, max 50 chars each` (field_validator)
- [x] `QuestUpdate.budget`: `le=1_000_000`
- [x] `QuestApplicationCreate.cover_letter`: `min_length=10`
- [x] `QuestApplicationCreate.proposed_price`: `ge=0`
- [x] `UserLogin.username / password`: `max_length=50/128` (anti-DoS)

### 3) Auth & Role Guards

- [x] `GET /api/v1/users/` требует Bearer токен → 401 без токена
- [x] `GET /api/v1/users/` лимит: `limit=20` по умолчанию, `max=100`
- [x] `POST /quests/` — роль `client` обязательна → 403 для `freelancer`
- [x] `POST /auth/register` — дубль → `409 Conflict` (было 400)

### 4) Tests

- [x] `backend/tests/test_endpoints.py` — 17 HTTP-тестов (422/401/403)
- [x] `pytest.ini` — coverage scope расширен до `--cov=app` (53% общий)
- [x] **24 passed** (7 unit + 17 endpoint)

### 5) Week 2 Acceptance Criteria

```powershell
# Все тесты
cd backend; pytest --no-cov -q          # 24 passed

# Проверка CORS PATCH
curl -X OPTIONS http://localhost:8001/api/v1/quests/ `
     -H "Origin: http://localhost:3000" `
     -H "Access-Control-Request-Method: PATCH" -v

# Валидация — should return 422
curl -s http://localhost:8001/api/v1/quests/ -X POST `
     -H "Authorization: Bearer test" `
     -d '{"title":"t","description":"x","budget":50,"currency":"JPY"}' `
     -H "Content-Type: application/json"

# Auth guard — should return 401
curl -s http://localhost:8001/api/v1/users/

# Role guard — login as novice_dev (freelancer) and try to create quest -> 403
```



## 🔐 ТЕСТОВЫЕ АККАУНТЫ (встроены в систему)

| Роль       | Username      | Password    | Описание              |
|------------|---------------|-------------|----------------------|
| Фрилансер  | novice_dev    | password123 | Lv.1 Novice, 0 XP   |
| Клиент     | client_user   | client123   | Для создания квестов |

---

## 📄 СТРАНИЦЫ ПРИЛОЖЕНИЯ

| Страница           | URL                    | Доступ         |
|--------------------|------------------------|----------------|
| Главная            | /                      | Все            |
| Вход               | /auth/login            | Незалогиненные |
| Регистрация        | /auth/register         | Незалогиненные |
| Профиль            | /profile               | Авторизованные |
| Мои квесты         | /profile/quests        | Авторизованные |
| Лента квестов      | /quests                | Все            |
| Создать квест      | /quests/create         | Авторизованные |
| Детали квеста      | /quests/[id]           | Все            |
| Биржа фрилансеров  | /marketplace           | Все            |

---

## 🔌 API ENDPOINTS

| Метод | URL                                    | Описание                    |
|-------|----------------------------------------|-----------------------------|
| GET   | /health                                | Проверка работоспособности  |
| POST  | /api/v1/auth/register                  | Регистрация                 |
| POST  | /api/v1/auth/login                     | Вход                        |
| GET   | /api/v1/users/{id}                     | Профиль пользователя        |
| GET   | /api/v1/quests/                        | Список квестов              |
| POST  | /api/v1/quests/                        | Создать квест               |
| GET   | /api/v1/quests/{id}                    | Детали квеста               |
| POST  | /api/v1/quests/{id}/apply              | Откликнуться                |
| POST  | /api/v1/quests/{id}/assign             | Назначить исполнителя       |
| POST  | /api/v1/quests/{id}/complete           | Завершить (исполнитель)     |
| POST  | /api/v1/quests/{id}/confirm            | Подтвердить (клиент)        |
| POST  | /api/v1/quests/{id}/cancel             | Отменить                    |
| GET   | /api/v1/quests/{id}/applications       | Отклики на квест            |

---

## ❌ ЧАСТЫЕ ОШИБКИ И РЕШЕНИЯ

### Backend не запускается

**Ошибка:** `ModuleNotFoundError: No module named 'fastapi'`
```powershell
# Решение: активировать venv и установить зависимости
cd C:\QuestionWork\backend
.venv\Scripts\activate
pip install -r requirements.txt
```

**Ошибка:** `Address already in use` (порт 8001 занят)
```powershell
# Найти и убить процесс
netstat -ano | findstr :8001
taskkill /PID <PID_из_вывода> /F
```

**Ошибка:** `Could not import module "app.main"`
```powershell
# Убедиться что запуск идёт из папки backend
cd C:\QuestionWork\backend
uvicorn app.main:app --reload
```

---

### Frontend не запускается

**Ошибка:** `Cannot find module 'next'`
```powershell
cd C:\QuestionWork\frontend
npm install
```

**Ошибка:** Стили не применяются (Tailwind)
```powershell
# Пересобрать
npm run build
# Или проверить postcss.config.mjs — должен быть tailwindcss плагин
```

**Ошибка:** `NEXT_PUBLIC_API_URL is not defined`
```powershell
# Создать файл .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1" > .env.local
```

---

### API ошибки

**Ошибка:** `401 Unauthorized` при запросах
- Токен не передаётся или истёк (TTL = 30 минут)
- Выйти и войти снова

**Ошибка:** `400 Пользователь уже существует`
- Username или email уже занят
- Используйте другой username

**Ошибка:** `307 Temporary Redirect` при GET /api/v1/quests
- Нормально! FastAPI требует trailing slash: `/quests/`
- Frontend автоматически следует редиректу

**Ошибка:** `422 Unprocessable Entity`
- Проверьте тело запроса — неверный формат данных
- Смотрите детали в поле `detail` ответа

---

### CORS ошибки в браузере

**Ошибка:** `Access-Control-Allow-Origin`
```python
# В backend/.env убедитесь что:
FRONTEND_URL=http://localhost:3000
# В main.py CORS настроен на этот URL
```

---

### Данные пропали после рестарта

- **Причина:** Backend использует in-memory хранилище
- **Решение:** Демо-данные (3 квеста, 2 пользователя) восстанавливаются автоматически
- **Постоянное решение:** Подключить PostgreSQL (Phase 2)

---

## 📊 ПРОВЕРКА СТАТУСА

```powershell
# Быстрая проверка всего
.\scripts\check-status.ps1
```

Ручная проверка:
```powershell
# Backend
curl http://localhost:8001/health

# Frontend
curl -o /dev/null -w "%{http_code}" http://localhost:3000

# Redis
docker ps | grep questionwork-redis

# Swagger
Start-Process "http://localhost:8001/docs"
```

---

## 🗺️ ПЛАН РАЗВИТИЯ

### Phase 1 ✅ — MVP (выполнено)
- [x] Backend FastAPI с in-memory хранилищем
- [x] Frontend Next.js + Tailwind CSS
- [x] Auth (JWT, регистрация, логин)
- [x] CRUD квестов
- [x] Отклики на квесты
- [x] XP/rewards система
- [x] RPG профиль (грейды, статы, бейджи)
- [x] Страница создания квестов
- [x] Биржа фрилансеров

### Phase 2 🔄 — База данных (текущий приоритет)
- [ ] PostgreSQL через asyncpg
- [ ] Миграции (Alembic)
- [ ] Redis сессии и кэш
- [ ] Сохранение данных между рестартами

### Phase 3 📅 — Улучшения UI/UX
- [ ] Уведомления в реальном времени (WebSocket)
- [ ] Страница профиля фрилансера (публичная)
- [ ] Чат между клиентом и фрилансером
- [ ] Загрузка файлов / портфолио

### Phase 4 🚀 — Масштабирование
- [ ] Платежи (Stripe / ЮКасса)
- [ ] AI-проверка навыков (OpenRouter)
- [ ] Мобильное приложение
- [ ] Docker Compose для всего стека

---

## 📁 СТРУКТУРА ПРОЕКТА

```
QuestionWork/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # auth.py, quests.py, users.py
│   │   ├── core/               # config.py, security.py, rewards.py
│   │   ├── models/             # user.py, quest.py (Pydantic)
│   │   ├── db/                 # (пусто — PostgreSQL не подключён)
│   │   └── main.py             # FastAPI app, CORS, routers
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   │   ├── auth/           # login, register
│   │   │   ├── profile/        # profile, quests
│   │   │   ├── quests/         # list, [id], create
│   │   │   └── marketplace/    # freelancer leaderboard
│   │   ├── components/         # layout, rpg, quests, ui
│   │   ├── context/            # AuthContext
│   │   └── lib/                # api.ts (API client)
│   ├── package.json
│   └── .env.local
├── scripts/                    # PowerShell automation
├── docs/
├── CHECKLIST.md                # этот файл
└── CLAUDE.md
```

---

*Последнее обновление: 2026-03-02 (Week 2 Backend Hardening)*
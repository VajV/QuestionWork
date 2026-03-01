# ✅ QuestionWork — Чеклист запуска и диагностики

## 🚀 КАК ЗАПУСТИТЬ ПРОЕКТ

### 1. Backend (FastAPI)
```powershell
cd C:\QuestionWork\backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Проверка: http://localhost:8000/health → должен вернуть `{"status":"ok"}`

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
- [ ] Порт 8000 свободен (`netstat -ano | findstr :8000`)
- [ ] Backend запущен: `curl http://localhost:8000/health`

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
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_dev","email":"dev@test.com","password":"Test1234!","role":"freelancer"}'
```

### 2. Регистрация клиента
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/register" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_client","email":"client@test.com","password":"Test1234!","role":"client"}'
```

### 3. Логин (получить токен)
```powershell
$resp = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" `
  -Method POST -ContentType "application/json" `
  -Body '{"username":"test_client","password":"Test1234!"}'
$TOKEN = $resp.access_token
```

### 4. Создать квест
```powershell
$headers = @{ Authorization = "Bearer $TOKEN" }
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/quests/" `
  -Method POST -ContentType "application/json" -Headers $headers `
  -Body '{"title":"Тестовый квест","description":"Описание тестового задания длиннее 20 символов","budget":10000,"skills":["Python"]}'
```

### 5. Получить список квестов
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/quests/?page=1"
```

### 6. Запустить полный тест
```powershell
.\scripts\test-full-flow.ps1
```

---

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

**Ошибка:** `Address already in use` (порт 8000 занят)
```powershell
# Найти и убить процесс
netstat -ano | findstr :8000
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
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
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
curl http://localhost:8000/health

# Frontend
curl -o /dev/null -w "%{http_code}" http://localhost:3000

# Redis
docker ps | grep questionwork-redis

# Swagger
Start-Process "http://localhost:8000/docs"
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

*Последнее обновление: 2026-03-01*
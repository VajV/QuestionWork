# Ideas — QuestionWork

Коллекция идей для развития проекта. Каждая идея — отдельный файл с описанием, приоритетом и текущим состоянием зависимостей.

## Содержание

1. [Система споров и арбитража](01-dispute-resolution.md)
2. [Email-рассылка (SMTP Pipeline)](02-email-pipeline.md)
3. [Ивенты и сезонные челленджи](03-events-system.md)
4. [Исполнитель RPG-абилок](04-ability-executor.md)
5. [WebSocket для сообщений и нотификаций](05-websocket-realtime.md)
6. [Онбординг-визард для фрилансеров](06-onboarding-wizard.md)
7. [Агрегатный Trust Score](07-trust-score.md)
8. [Smart Matching — подбор по скиллам](08-smart-matching.md)
9. [Прогрессия гильдий](09-guild-leveling.md)
10. [Invoice/Receipt PDF + налоговая отчётность](10-invoice-pdf.md)

## Матрица приоритетов

| # | Идея | Effort | Impact | Зависимости |
|---|------|--------|--------|-------------|
| 1 | Споры/арбитраж | M | Критический | Эскроу (готов) |
| 2 | Email pipeline | S | Критический | ARQ worker (готов) |
| 3 | Ивенты/сезоны | L | Высокий | Guild schema (готов) |
| 4 | Ability executor | M | Средний | Class configs (готовы) |
| 5 | WebSocket | M | Высокий | Redis (готов) |
| 6 | Онбординг-визард | S | Высокий | Auth + classes (готовы) |
| 7 | Trust Score | S | Высокий | Reviews (готовы) |
| 8 | Smart Matching | M | Высокий | Skills JSONB (готовы) |
| 9 | Guild Leveling | L | Средний | Guild tables (готовы) |
| 10 | Invoice PDF | M | Средний | Transactions (готовы) |

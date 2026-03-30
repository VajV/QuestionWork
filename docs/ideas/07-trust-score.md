# 7. Агрегатный Trust Score (репутационный рейтинг)

**Приоритет:** marketplace-качество
**Effort:** S
**Статус:** reviews есть, composite score отсутствует

## Проблема

Reviews есть (`GET /reviews/user/{id}`), но нет composite trust score. Клиенты не могут быстро оценить надёжность фрилансера.

## Решение

Формула: `(avg_rating * 0.4) + (completion_rate * 0.3) + (on_time_rate * 0.2) + (level_bonus * 0.1)`.

## Зависимости (готовы)

- Reviews system
- Quest completion tracking
- XP/level system

## Что нужно

- Service: `trust_score_service.py` (calculate_trust_score, get_trust_breakdown)
- Компоненты формулы:
  - `avg_rating` — средний рейтинг из reviews (1-5, нормализовать к 0-1)
  - `completion_rate` — % завершённых квестов от принятых
  - `on_time_rate` — % квестов без просрочки deadline
  - `level_bonus` — бонус за grade (Novice=0, Junior=0.25, Middle=0.5, Senior=1.0)
- Endpoint: GET `/users/{id}/trust-score` (score + breakdown)
- Кеш: пересчёт при новом review или завершении квеста
- Frontend: визуальный badge/meter в карточке фрилансера
- Поиск: использовать trust_score для сортировки/ранжирования

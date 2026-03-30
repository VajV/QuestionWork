# 8. Smart Matching — подбор фрилансера по скиллам

**Приоритет:** marketplace-core
**Effort:** M
**Статус:** базовый текстовый поиск

## Проблема

Skills хранятся в JSONB у квестов и юзеров. Сейчас поиск — базовый текстовый. Нет интеллектуального подбора.

## Решение

Пересечение skill-массивов, weighted scoring (grade, rating, доступность).

## Зависимости (готовы)

- Skills в JSONB (quests.required_skills, users.skills)
- Trust Score (идея #7 — опционально, но усиливает)
- Quest lifecycle

## Что нужно

- Service: `matching_service.py` (match_freelancers_for_quest, recommend_quests_for_user)
- Scoring алгоритм:
  - `skill_overlap` — % пересечения required_skills ∩ user_skills
  - `grade_fit` — соответствие grade фрилансера complexity квеста
  - `trust_score` — репутационный рейтинг (из идеи #7)
  - `availability` — нет активных квестов = бонус
  - `budget_fit` — предпочтения по бюджету vs цена квеста
- Endpoints:
  - GET `/quests/{id}/recommended-freelancers` — топ-10 подходящих
  - GET `/users/me/recommended-quests` — персональная лента
- Frontend: секция "Рекомендуемые исполнители" на странице квеста
- Frontend: секция "Квесты для тебя" на главной/доске заданий

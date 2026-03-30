# 6. Онбординг-визард для фрилансеров

**Приоритет:** конверсия
**Effort:** S
**Статус:** нет guided setup

## Проблема

Регистрация → пустой профиль. Нет guided setup. Новички не понимают, что делать дальше, и уходят.

## Решение

Пошаговый flow: выбор класса → заполнение скиллов → первый badge → подсказка "возьми первый квест". Снижает churn новичков.

## Зависимости (готовы)

- Auth system
- Class selection endpoint
- Badge grant system
- Profile update endpoint

## Что нужно

- Frontend: `/onboarding` — multi-step wizard component
  - Step 1: Выбор класса (с описанием и превью абилок)
  - Step 2: Заполнение скиллов (chips selector из существующего skill-каталога)
  - Step 3: Загрузка аватара / описание профиля
  - Step 4: Получение первого badge "Новобранец" + анимация
  - Step 5: CTA "Возьми свой первый квест" → redirect на `/quests`
- Backend: флаг `onboarding_completed` в users (или проверка completeness)
- Redirect: после регистрации автоматически направлять на `/onboarding`
- Skip: возможность пропустить и вернуться позже

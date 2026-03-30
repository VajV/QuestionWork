# 3. Ивенты и сезонные челленджи (Events System)

**Приоритет:** высокий UX
**Effort:** L
**Статус:** guild_seasonal_sets таблица готова

## Проблема

В header освободилось место (убрали "Участники"), а гильдии уже имеют таблицу `guild_seasonal_sets`. Нет механизма для создания временных активностей, которые повышают retention.

## Решение

Сезонные ивенты (24-72 часа) с модификаторами XP, уникальными бейджами, лидербордами. Это даст retention и оживит гильдейскую механику.

## Зависимости (готовы)

- Guild schema (guilds, guild_members, guild_activity, guild_seasonal_sets)
- Badge system
- XP/rewards engine

## Что нужно

- Таблица `events` (title, description, start_at, end_at, xp_multiplier, badge_reward_id, status)
- Таблица `event_participants` (event_id, user_id, score, joined_at)
- Таблица `event_leaderboard` (event_id, user_id, rank, score)
- Service: `event_service.py` (create_event, join, submit_score, finalize)
- ARQ jobs: event_start, event_end, reward_distribution
- Frontend: страница `/events`, карточки ивентов, лидерборд
- Header: новый пункт навигации "Ивенты" (на место убранных "Участники")

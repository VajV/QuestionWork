# 9. Прогрессия гильдий (Guild Leveling)

**Приоритет:** средний, но глубокий
**Effort:** L
**Статус:** таблицы готовы, механика отсутствует

## Проблема

Таблицы `guilds`, `guild_members`, `guild_activity`, `guild_seasonal_sets` готовы. Но механики прогрессии нет — гильдии статичны.

## Решение

XP гильдии (сумма XP участников за период), тиры, бонусы, роли.

## Зависимости (готовы)

- Guild tables (guilds, guild_members, guild_activity, guild_seasonal_sets)
- XP/rewards engine
- Badge system

## Что нужно

- Механика:
  - Guild XP = сумма XP всех участников за сезон/период
  - Тиры: Bronze (0) → Silver (5000 XP) → Gold (20000 XP) → Platinum (50000 XP)
  - Бонусы тира: Bronze +0%, Silver +5% XP, Gold +10% XP + эксклюзивные бейджи, Platinum +15% XP + уникальный title
- Роли: Лидер, Офицер, Участник (с правами на invite/kick/edit)
- Service: `guild_progression_service.py` (calculate_guild_xp, check_tier_up, apply_tier_bonus)
- Cron job: пересчёт guild XP и тиров (ежедневно или при каждом quest complete)
- Frontend: прогресс-бар гильдии, тир-badge, список участников с ролями
- Seasonal leaderboard: рейтинг гильдий по XP за сезон

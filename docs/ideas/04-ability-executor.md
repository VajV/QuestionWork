# 4. Исполнитель RPG-абилок (Ability Executor)

**Приоритет:** геймификация
**Effort:** M
**Статус:** таблица ability_activations есть, классы определены, executor отсутствует

## Проблема

Таблица `ability_activations` есть, 6 классов с абилками определены (cooldown, duration, effects) — но нет ни одного executor'а. Абилки существуют в конфиге, но не влияют на геймплей.

## Решение

`ActivateAbilityService` + применение эффектов в quest flow.

## Примеры

- Berserk «Боевой клич» = +20% XP на следующий квест
- Alchemist «Эликсир фокуса» = снижает deadline penalty
- Paladin «Божественный щит» = защита от потери XP при отмене
- Rogue «Теневой удар» = бонус к оплате за срочные квесты

## Зависимости (готовы)

- Class configs (6 классов, abilities с cooldown/duration/effects)
- `ability_activations` таблица
- Quest lifecycle service

## Что нужно

- Service: `ability_service.py` (activate_ability, check_cooldown, get_active_effects)
- Интеграция в quest_service: при complete/confirm проверять активные эффекты
- Интеграция в rewards.py: модификаторы XP от активных абилок
- Endpoint: POST `/classes/abilities/{ability_id}/activate`
- Frontend: кнопка активации абилки в профиле/квесте, отображение активных эффектов

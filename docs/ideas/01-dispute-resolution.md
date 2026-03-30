# 1. Система споров и арбитража (Dispute Resolution)

**Приоритет:** критический
**Effort:** M
**Статус:** 0 кода

## Проблема

Если фрилансер сдал работу, а клиент не подтверждает — тупик. Нет механизма разрешения конфликтов.

## Решение

Flow: открытие спора → таймер на ответ → эскалация на модератора → решение (возврат / частичный / в пользу фрилансера).

## Зависимости (готовы)

- Эскроу (hold/release) — работает
- Admin audit log — работает
- Notification system — работает

## Что нужно

- Таблица `disputes` (quest_id, initiator_id, reason, status, resolution, moderator_id, created_at, resolved_at)
- Service: `dispute_service.py` (open_dispute, respond, escalate, resolve)
- Endpoints: POST `/disputes`, PATCH `/disputes/{id}/respond`, PATCH `/disputes/{id}/resolve`
- ARQ job: таймер автоэскалации (если нет ответа за 72 часа)
- Admin UI: панель модератора с очередью споров
- Нотификации на каждом шаге

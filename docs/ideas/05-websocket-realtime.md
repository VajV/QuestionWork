# 5. WebSocket для сообщений и нотификаций

**Приоритет:** UX-скачок
**Effort:** M
**Статус:** всё на polling

## Проблема

Сейчас все на polling. Нотификации и сообщения обновляются только при ручном refresh или интервальном запросе.

## Решение

FastAPI поддерживает WS нативно, Redis PubSub уже в стеке.

## Зависимости (готовы)

- Redis — работает
- Notification system — работает
- Message threading — работает

## Что нужно

- WS-эндпоинт: `/ws/notifications` (JWT auth через query param или first message)
- Redis PubSub: канал `user:{user_id}:notifications`
- Backend: `ws_manager.py` (connection registry, broadcast, disconnect cleanup)
- Frontend хук: `useRealtimeNotifications` (WS connect, fallback to polling)
- Frontend хук: `useRealtimeMessages` (WS connect для текущего thread)
- Оповещения о новых сообщениях без перезагрузки
- Graceful degradation: если WS недоступен — fallback на текущий polling

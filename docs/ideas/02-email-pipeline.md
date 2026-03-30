# 2. Email-рассылка (SMTP Pipeline)

**Приоритет:** блокирует продакшн
**Effort:** S
**Статус:** таблицы и схемы готовы, нет job-хендлера

## Проблема

Таблицы `lifecycle_emails` есть, схемы готовы, ARQ-воркер работает — но нет ни одного job-хендлера для отправки. Без этого нет восстановления пароля, нет уведомлений по email, нет lead-nurture.

## Решение

`email.send` job + SMTP/Resend интеграция.

## Зависимости (готовы)

- ARQ worker + scheduler — работает
- `lifecycle_emails` таблица — есть
- Lead nurture schema — есть

## Что нужно

- Job handler: `email.send` в ARQ worker
- SMTP/Resend конфиг в `.env` (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS или RESEND_API_KEY)
- Email templates (Jinja2 или plaintext): welcome, password_reset, quest_update, withdrawal_status
- Service: `email_service.py` (send_email, queue_email, render_template)
- Lead nurture sequencer (поверх существующей схемы)

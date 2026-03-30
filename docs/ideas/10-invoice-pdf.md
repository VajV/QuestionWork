# 10. Invoice/Receipt PDF + налоговая отчётность

**Приоритет:** compliance-блокер при масштабе
**Effort:** M
**Статус:** транзакции пишутся аккуратно, PDF-генерации нет

## Проблема

Wallet-транзакции пишутся аккуратно (Decimal, audit log). Но нет возможности сформировать документ для бухгалтерии.

## Решение

PDF-генератор + endpoint для чеков и выписок.

## Зависимости (готовы)

- Transactions table (Decimal arithmetic, audit log)
- Wallet balance API
- Admin audit log

## Что нужно

- Библиотека: WeasyPrint или ReportLab
- Service: `invoice_service.py` (generate_receipt, generate_statement)
- Templates: HTML-шаблон чека, HTML-шаблон выписки за период
- Endpoints:
  - GET `/wallet/transactions/{id}/receipt` — PDF чек конкретной транзакции
  - GET `/wallet/statements?from=...&to=...` — выписка за период (PDF)
  - GET `/wallet/statements?from=...&to=...&format=csv` — CSV экспорт
- Данные в чеке: дата, сумма, тип операции, контрагент, комиссия платформы
- Frontend: кнопка "Скачать чек" у каждой транзакции в кошельке
- Frontend: форма запроса выписки за период
- Будущее: интеграция с налоговой отчётностью (1099/акты)

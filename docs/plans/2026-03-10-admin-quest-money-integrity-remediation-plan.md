# Admin Quest Money Integrity Remediation Plan

**Goal:** Закрыть подтверждённые P0/P1 замечания в admin quest flows так, чтобы админские операции больше не могли ломать escrow invariants, терять деньги при payout/cancel/delete и обходить audit trail quest lifecycle.

**Architecture:** Сначала фиксируем денежный инвариант вокруг escrow: после появления hold сумма расчёта должна стать неизменяемой или хотя бы строго сверяемой перед release/payout. Затем переводим admin-driven cancellation flows на единый lifecycle path с refund, history и notifications. После этого ужесточаем semantics для hard delete: quest с финансовым следом больше нельзя удалять напрямую. Это даёт минимальный patch scope без большой схемной миграции и без расползания логики по endpoint-слою.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, pytest, existing service-layer transactions.

---

## Кратко о стратегии исправления

### 1. Не пытаться лечить только `split_payment`

Если исправить только payout check в `wallet_service`, система перестанет молча терять или создавать деньги, но admin всё ещё сможет заводить quest в противоречивое состояние. Поэтому первый шаг должен одновременно:
- запрещать post-hold изменения ключевых financial/lifecycle полей через admin update;
- делать `split_payment` fail-closed, если hold не совпадает с `gross_amount`.

### 2. Не дублировать cancellation side effects по всему `admin_service`

Сейчас проблема не в одном забытом `refund_hold`, а в самом паттерне raw `UPDATE quests SET status='cancelled'`. Если точечно чинить только `ban_user`, похожая дыра останется в `delete_user` или следующем admin mutation path. Нужен общий internal helper, который инкапсулирует quest cancel invariants.

### 3. Для `delete_quest` выбрать безопасный минимум, а не большой redesign

Наиболее дешёвый и надёжный вариант для текущего релиза: запретить hard delete, если у quest есть любой финансовый след или активный escrow. Soft-delete/archive можно оставить как Phase 2, если продукту реально нужна эта возможность.

---

## Принципы исполнения

- Сначала писать регрессию, потом минимальную реализацию.
- Не смешивать payout invariant fix и admin cancellation refactor в одном батче без тестового покрытия.
- Не переносить SQL в endpoints; вся новая логика остаётся в service layer.
- Не делать schema change, если тот же риск закрывается сервисной валидацией и безопасным отказом.
- После каждого батча прогонять targeted pytest, затем полный backend suite.

---

## Итерации и зависимости

### Iteration 1. Закрыть P0: зафиксировать escrow amount invariant

Цель итерации: после появления hold ни один admin path не должен доводить quest до payout с суммой, отличной от реально удержанной.

### Task 1: Зафиксировать уязвимость regression tests

**Files:**
- Modify: `backend/tests/test_admin_service.py`
- Modify: `backend/tests/test_quest_service.py`
- Check: `backend/app/services/admin_service.py`
- Check: `backend/app/services/quest_service.py`
- Check: `backend/app/services/wallet_service.py`

**Add tests:**
- admin `update_quest` отклоняет изменение `budget` после того, как по quest уже существует активный hold;
- admin `update_quest` отклоняет изменение `assigned_to` и ручной `status` flip для quest с активным escrow;
- `split_payment` падает fail-closed, если найденный hold по quest не совпадает с `gross_amount`;
- `force_complete_quest` не может заплатить по quest в рассинхронизированном escrow state.

**Suggested commands:**

```powershell
Set-Location c:\QuestionWork\backend
c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py tests/test_quest_service.py -q --tb=short -k "force_complete or update_quest or hold or split_payment"
```

**Expected before implementation:** FAIL.

### Task 2: Заблокировать post-hold admin edits для финансовых полей

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Check: `backend/app/services/quest_service.py`

**Implementation shape:**
- в `admin_service.update_quest()` вычислять, есть ли у quest активный hold или уже назначенный исполнитель;
- если quest уже financialized (`assigned_to` есть, либо найден hold/status не `draft/open`), запрещать изменение:
  - `budget`
  - `assigned_to`
  - `status`
  - при необходимости `currency`, если поле когда-нибудь станет admin-editable;
- оставить допустимыми только безопасные metadata fields вроде `title`, `description`, `deadline`, `is_urgent`, `required_portfolio`.

**Decision rule:**
- если квест уже прошёл точку удержания денег, админ может отменить его, завершить его или править текст/метаданные, но не менять расчётную базу.

### Task 3: Сделать payout fail-closed на mismatch hold amount

**Files:**
- Modify: `backend/app/services/wallet_service.py`
- Optionally modify: `backend/app/services/admin_service.py`
- Optionally modify: `backend/app/services/quest_service.py`

**Implementation shape:**
- в `split_payment()` после чтения hold сравнивать `hold_tx["amount"]` и `gross_amount` после `quantize_money`;
- при несовпадении не делать `release_hold` и не уходить в direct debit fallback;
- бросать явный `ValueError` или domain-specific error вроде `EscrowMismatchError` с понятным текстом для логов/HTTP mapping;
- `confirm_quest_completion()` и `force_complete_quest()` должны пробрасывать этот отказ как безопасную бизнес-ошибку, а не молча пытаться “досписать” деньги.

### Iteration 1 exit criteria

- После создания hold admin не может изменить payout base через `update_quest`.
- `split_payment` никогда не release'ит hold с другой суммой.
- `force_complete_quest` и обычный confirmation не могут продолжить payout при escrow mismatch.
- Новые regression tests зелёные.

---

### Iteration 2. Закрыть P0/P1: унифицировать admin-driven cancellation invariants

Цель итерации: любой admin cancellation path должен делать то же, что и нормальный quest cancellation lifecycle, а не только менять `status`.

### Task 4: Вынести единый internal helper для admin quest cancellation

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/app/services/quest_service.py`
- Check: `backend/app/services/message_service.py`
- Check: `backend/app/services/notification_service.py`

**Implementation shape:**
- создать общий helper уровня service layer, например:
  - либо в `quest_service.py` как internal lifecycle primitive;
  - либо в `admin_service.py`, если нужен только admin use case;
- helper должен в одной транзакции:
  - lock quest row;
  - валидировать terminal status;
  - обновлять `status='cancelled'`;
  - вызывать `wallet_service.refund_hold(...)`;
  - писать `quest_status_history`;
  - отправлять notification участникам;
  - при необходимости писать system message.

**Why this shape:**
- `_record_status_history()` уже живёт в `quest_service.py`, поэтому самый дешёвый путь обычно либо поднять его в переиспользуемый helper, либо обернуть admin cancellation через новую публичную функцию quest lifecycle уровня.

### Task 5: Перевести `ban_user` и `delete_user` на этот helper

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/tests/test_admin_service.py`

**Implementation shape:**
- `ban_user()` больше не делает raw bulk `UPDATE quests ... status='cancelled'`;
- вместо этого получает список affected quest ids и прогоняет их через новый helper внутри текущей транзакции;
- `delete_user()` сначала безопасно отменяет active quests тем же helper, и только потом удаляет user-owned quests, которые действительно можно удалить;
- если для client-owned quest удаление небезопасно из-за финансового хвоста, функция должна завершаться controlled error, а не частично чистить состояние.

**Add tests:**
- `ban_user` refund'ит hold для assigned/in_progress quest клиента;
- `ban_user` пишет lifecycle history для отменённых quests;
- `delete_user` не оставляет активный hold после cleanup;
- count-based старый тест остаётся, но дополняется проверками side effects.

**Suggested commands:**

```powershell
Set-Location c:\QuestionWork\backend
c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py -q --tb=short -k "ban_user or delete_user or cancel"
```

### Task 6: Выравнять `force_cancel_quest` с тем же helper

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/tests/test_admin_service.py`

**Implementation shape:**
- `force_cancel_quest()` должен использовать тот же lifecycle helper, а не отдельную частично дублирующую ветку;
- это убирает риск дрейфа, где future-fix попадёт в один admin path и не попадёт в другой.

### Iteration 2 exit criteria

- В кодовой базе нет raw admin cancellation path, который меняет quest status без refund/history.
- `ban_user`, `delete_user` и `force_cancel_quest` сохраняют одинаковые cancellation invariants.
- Tests подтверждают не только `quests_cancelled`, но и refund/history side effects.

---

### Iteration 3. Закрыть P1: сделать hard delete финансово безопасным

Цель итерации: hard delete quest больше не должен отрывать transactions от их reconciliation path.

### Task 7: Явно запретить hard delete для quest с финансовым следом

**Files:**
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/tests/test_admin_service.py`
- Check: `backend/app/services/wallet_service.py`

**Implementation shape:**
- перед `DELETE FROM quests` проверять наличие связанных transactions по `quest_id`;
- минимально безопасное правило для текущего релиза:
  - если есть активный hold, delete запрещён всегда;
  - если есть любые финансовые ledger rows по quest, delete тоже запрещён, чтобы не терять связность audit/reconciliation;
- текст ошибки должен направлять в безопасный flow: сначала cancel/refund или архивный процесс, потом удаление.

**Why block all financial rows, not only active hold:**
- даже `ON DELETE SET NULL` для completed/refunded rows ухудшает трассируемость расследований;
- product-wise hard delete financialized entity обычно хуже, чем controlled refusal.

### Task 8: Добавить regression tests на delete guard

**Files:**
- Modify: `backend/tests/test_admin_service.py`

**Add tests:**
- `delete_quest` отказывает, если у quest есть активный hold;
- `delete_quest` отказывает, если у quest есть historical transactions;
- `delete_quest` всё ещё разрешён для нефинансового draft/open quest без transaction tail.

**Suggested commands:**

```powershell
Set-Location c:\QuestionWork\backend
c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py -q --tb=short -k "delete_quest"
```

### Iteration 3 exit criteria

- `delete_quest` не может orphan'ить hold или другой ledger tail.
- Financialized quests переводятся в safe refusal path вместо hard delete.
- Regression tests покрывают и positive, и negative paths.

---

## Минимальный patch scope

### Required files

- `backend/app/services/admin_service.py`
- `backend/app/services/quest_service.py`
- `backend/app/services/wallet_service.py`
- `backend/tests/test_admin_service.py`
- `backend/tests/test_quest_service.py`

### Optional files

- `backend/app/models/quest.py`
  - только если понадобится новый domain error mapping или stricter typing around cancellable states.
- `backend/app/api/v1/endpoints/admin.py`
  - только если потребуется отдельный HTTP mapping для escrow mismatch / protected delete refusal.

### Explicitly avoid in this batch

- Alembic migration под soft delete/archive.
- Frontend changes.
- Broad refactor всех quest lifecycle handlers.
- Changes to unrelated wallet math.

---

## Regression matrix

### Money integrity

- Admin cannot raise budget after hold exists.
- Admin cannot lower budget after hold exists.
- Admin cannot change assignee/status on financialized quest through generic update.
- `split_payment` refuses hold/gross mismatch.
- `force_complete_quest` fails safely on mismatch.

### Cancellation integrity

- `ban_user` refunds held client money for affected quests.
- `ban_user` records quest status history.
- `delete_user` does not leave active hold behind.
- `force_cancel_quest` follows same refund/history path.

### Delete safety

- `delete_quest` rejects active hold.
- `delete_quest` rejects any historical transaction tail.
- `delete_quest` still works for non-financial quests.

---

## Verification sequence

### Targeted backend checks

```powershell
Set-Location c:\QuestionWork\backend
c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_service.py tests/test_quest_service.py -q --tb=short
```

### Full backend suite

```powershell
Set-Location c:\QuestionWork\backend
c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests -q --tb=short
```

### Optional flow smoke

```powershell
Set-Location c:\QuestionWork
powershell -ExecutionPolicy Bypass -File .\scripts\test-flow.ps1
```

---

## Rollout notes

- Исправления лучше делать в порядке `Iteration 1 -> Iteration 2 -> Iteration 3`, потому что сначала нужно закрыть непосредственный risk of money creation/loss, затем убрать bypass paths, и только потом ужесточать delete semantics.
- Если во время Iteration 2 выяснится, что `delete_user` product-wise обязан hard-delete client quests, это уже не маленький фикс, а отдельный design decision. Тогда лучше остановиться на safe refusal и вынести archive workflow в отдельный follow-up plan.
- Если нужен совсем минимальный hotfix для production first, можно сначала сделать только две вещи:
  - fail-closed mismatch check в `split_payment`;
  - запрет `budget/status/assigned_to` edits после hold.
  Но это не закрывает trapped escrow в `ban_user` и `delete_user`, поэтому hotfix не должен считаться полным закрытием findings.

---

## Final acceptance criteria

- Ни один admin path не может изменить payout base после появления escrow hold.
- Ни один admin cancellation path не пропускает refund/history side effects.
- Ни один admin delete path не может orphan'ить financial rows.
- Targeted regressions зелёные.
- Full backend suite зелёный.
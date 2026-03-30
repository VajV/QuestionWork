# Audit Remediation Plan Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Закрыть подтвержденные P0/P1/P2 замечания аудита так, чтобы админский TOTP нельзя было обойти, frontend больше не пропускал Decimal-строки за пределы API-слоя, а антиабьюз и startup validation вели себя предсказуемо.

**Architecture:** Сначала исправляем единственный production-blocker в админской TOTP state machine: отделяем pending secret от active secret, требуем полноценную re-auth проверку для ротации и покрываем это регрессиями. Затем усиливаем тот же auth surface аудит-логами и fail-fast проверкой `pyotp`, после чего выравниваем frontend money contract и добавляем user-scoped throttling на соседние quest mutation endpoints.

**Tech Stack:** FastAPI, asyncpg, PostgreSQL, Redis, pytest, Next.js 14, TypeScript, centralized API client normalization.

---

## Краткое объяснение найденных проблем

### 1. P0: TOTP для админа можно перезаписать без текущего второго фактора

Ошибка в том, что backend считает `setup` почти полноценной активацией: новый секрет сразу пишется в активное поле пользователя, а `enable` по сути ничего не переключает. В результате админ с одним только JWT, без действующего TOTP-кода, может заменить секрет и тут же использовать уже свои коды для доступа к защищённым admin endpoints.

### 2. P1: Setup и enable TOTP не оставляют следов в аудите

Ошибка в том, что самое чувствительное изменение админской аутентификации частично невидимо для `admin_logs`. Если кто-то начал настройку нового секрета или довёл её до активации, расследование потом не увидит ни факта изменения, ни того, кто это сделал.

### 3. P1: Frontend обещает `number`, но иногда отдаёт строку из `Decimal`

Ошибка в границе контракта между backend и frontend: backend сериализует деньги как строки, а несколько mutation wrappers на frontend типизированы так, будто уже вернули числа. Из-за этого TypeScript создаёт ложное чувство безопасности, а UI местами получает строковые деньги и может отображать их или обрабатывать не так, как предполагается.

### 4. P2: User-based throttling применяется не везде, где уже должна применяться

Ошибка не в отсутствии rate limit как такового, а в непоследовательной политике. Для части чувствительных операций система уже умеет ограничивать именно пользователя, но соседние authenticated quest mutations всё ещё завязаны только на IP, поэтому один и тот же аккаунт можно прокручивать через смену адреса.

### 5. P2: Если `pyotp` отсутствует, приложение узнаёт об этом слишком поздно

Ошибка в том, что обязательность TOTP проверяется на этапе запросов, а не на старте приложения. В итоге сервис может подняться, пройти базовые health checks и только потом упасть по runtime-ошибке, когда администратору реально понадобится доступ.

## Принципы исполнения

- Исполнять по TDD: сначала тест, потом минимальная реализация, потом прогон точечных и целевых регрессий.
- Не смешивать security-fix и cleanup в одном коммите.
- Каждая итерация должна завершаться измеримой проверкой: pytest, targeted script, либо frontend test/build.
- Не выравнивать стиль или рефакторить соседний код без прямой необходимости для конкретного batch.

## Итерации и зависимости

### Iteration 1. Закрыть P0: исправить state machine админского TOTP

Цель итерации: сделать так, чтобы `setup` никогда не активировал новый секрет сам по себе, а уже настроенный админ не мог ротировать TOTP без текущего валидного второго фактора.

### Task 1: Зафиксировать уязвимость тестом

**Files:**
- Modify: `backend/tests/test_security_hardening.py`
- Check: `backend/app/api/v1/endpoints/admin.py`
- Check: `backend/app/api/deps.py`

**Step 1: Write the failing test**

Добавить тестовый сценарий:
- админ уже имеет активный TOTP;
- у него есть валидный JWT, но нет текущего `X-TOTP-Token`;
- вызов `POST /api/v1/admin/auth/totp/setup` не должен менять active secret;
- повторная попытка использовать новый секрет для protected admin route должна завершаться `403`.

**Step 2: Run test to verify it fails**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_hardening.py -q --tb=short -k "totp and rotate"`

Expected: FAIL, потому что текущая реализация разрешает rotation без действующего второго фактора.

**Step 3: Write minimal implementation**

Подготовить новый backend state model:
- добавить отдельное поле pending secret, например `pending_totp_secret`;
- не использовать его как активный секрет в `require_admin`;
- для admin, у которого уже есть активный TOTP, требовать full admin auth с действующим TOTP перед началом rotation;
- `enable` должен переносить pending secret в active secret только после успешной верификации одноразового кода.

**Step 4: Run test to verify it passes**

Run: тот же pytest command.

Expected: PASS.

**Step 5: Commit**

`git add backend/tests/test_security_hardening.py backend/app/api/v1/endpoints/admin.py backend/app/api/deps.py`

`git commit -m "fix: require active totp for admin secret rotation"`

### Task 2: Ввести storage для pending secret и миграцию

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/services/admin_service.py` if audit/event helpers are reused
- Create: `backend/alembic/versions/<new_revision>_admin_totp_pending_secret.py`

**Step 1: Write the failing migration-level or repository-level test**

Если проект уже проверяет схему через integration tests, добавить проверку, что новая колонка читается/пишется отдельно и active TOTP остаётся прежним до `enable`.

**Step 2: Run test to verify it fails**

Run: targeted pytest for the added schema/endpoint test.

Expected: FAIL, потому что pending state пока не существует.

**Step 3: Write minimal implementation**

Изменить модель поведения:
- `setup` пишет только `pending_totp_secret`;
- если активный TOTP уже есть, вход в `setup` допускается только после проверки текущего `X-TOTP-Token`;
- `enable` валидирует код против `pending_totp_secret`;
- после успешной проверки переносит `pending_totp_secret -> totp_secret` и очищает pending поле;
- `disable` очищает и active, и pending, чтобы не оставлять полусломанное состояние.

**Step 4: Run test to verify it passes**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_hardening.py tests/test_admin_endpoints.py -q --tb=short`

Expected: PASS.

**Step 5: Commit**

`git add backend/app/api/v1/endpoints/admin.py backend/app/api/deps.py backend/alembic/versions`

`git commit -m "feat: stage admin totp activation via pending secret"`

### Task 3: Зафиксировать корректную семантику enable/disable и защитить от регрессии

**Files:**
- Modify: `backend/tests/test_security_hardening.py`
- Optionally modify: `backend/tests/test_admin_endpoints.py`

**Step 1: Write the failing tests**

Добавить кейсы:
- `setup` для нового админа создаёт pending secret и ещё не открывает admin routes;
- `enable` активирует доступ только после корректного кода;
- неверный код не переносит pending secret в active secret;
- `disable` очищает обе ветки состояния.

**Step 2: Run test to verify it fails**

Run: targeted pytest on the new cases.

Expected: FAIL минимум в одном сценарии до полной реализации.

**Step 3: Write minimal implementation**

Довести обработчики и зависимости до согласованной state machine без дублирующей логики.

**Step 4: Run test to verify it passes**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_hardening.py -q --tb=short`

Expected: PASS.

**Step 5: Commit**

`git add backend/tests/test_security_hardening.py`

`git commit -m "test: cover staged admin totp lifecycle"`

### Iteration 1 exit criteria

- Существующий active TOTP нельзя ротировать без текущего TOTP.
- `setup` не меняет активный секрет.
- `enable` является единственной точкой активации.
- Регрессии на bypass воспроизводятся тестом и зелёные после фикса.

---

### Iteration 2. Усилить тот же auth surface: audit trail + fail-fast startup validation

Цель итерации: сделать жизненный цикл TOTP наблюдаемым и убрать поздний runtime-failure при обязательном TOTP.

### Task 4: Добавить audit logging для setup, rotation и enable

**Files:**
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Check: `backend/app/services/admin_service.py`
- Modify/Test: `backend/tests/test_security_hardening.py` or `backend/tests/test_admin_endpoints.py`

**Step 1: Write the failing test**

Добавить проверку, что после:
- первичного `setup`;
- rotation setup для уже настроенного admin;
- успешного `enable`;

в `admin_logs` появляется запись с корректным action и безопасным metadata без секретов.

**Step 2: Run test to verify it fails**

Run: targeted pytest for admin audit logging.

Expected: FAIL, потому что сейчас логируется только disable.

**Step 3: Write minimal implementation**

Добавить логирование внутри той же транзакции, где меняется state:
- `totp_setup_started`;
- `totp_secret_rotation_started` или аналогичный action для случая с уже активным TOTP;
- `totp_enabled`;
- при необходимости `totp_enable_failed` не писать как обычный lifecycle event, чтобы не зашумлять audit trail без политики.

**Step 4: Run test to verify it passes**

Run: targeted pytest.

Expected: PASS.

**Step 5: Commit**

`git add backend/app/api/v1/endpoints/admin.py backend/tests`

`git commit -m "feat: audit admin totp lifecycle changes"`

### Task 5: Добавить fail-fast validation для `pyotp`

**Files:**
- Modify: `backend/app/core/config.py`
- Modify/Test: `backend/tests/test_config_validation.py`
- Check: `backend/app/api/deps.py`
- Check: `backend/app/api/v1/endpoints/admin.py`

**Step 1: Write the failing test**

Добавить тест на settings validation:
- если `ADMIN_TOTP_REQUIRED=true` и `pyotp` недоступен, приложение/конфиг должны падать на старте с понятным сообщением.

**Step 2: Run test to verify it fails**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_config_validation.py -q --tb=short -k pyotp`

Expected: FAIL.

**Step 3: Write minimal implementation**

Включить проверку import availability в startup validation, а не в request path. По возможности оставить lazy import в endpoint/dependency только как defense in depth, но не как основной механизм обнаружения проблемы.

**Step 4: Run test to verify it passes**

Run: тот же targeted pytest command.

Expected: PASS.

**Step 5: Commit**

`git add backend/app/core/config.py backend/tests/test_config_validation.py`

`git commit -m "fix: fail fast when admin totp runtime is unavailable"`

### Iteration 2 exit criteria

- Все критичные этапы TOTP lifecycle пишут audit event.
- `pyotp`-зависимость валидируется до обработки admin traffic.
- Точечные security/config tests зелёные.

---

### Iteration 3. Закрыть frontend money contract drift

Цель итерации: гарантировать, что любой consumer frontend API получает уже нормализованные money fields и не зависит от строкового транспорта `Decimal`.

### Task 6: Явно развести raw transport types и normalized types для quest mutations

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Check: `frontend/src/types/index.ts` if shared quest response types live there

**Step 1: Write the failing test**

Если в проекте есть frontend test harness, добавить unit test на normalizers. Если его нет, сначала добавить минимальный test setup только для `src/lib/api.ts`.

Проверки:
- raw response с `money_reward: "123.45"` после wrapper-а становится `123.45` как `number`;
- apply/assign/start/complete/requestRevision/cancel/confirm не пропускают строковые деньги наружу.

**Step 2: Run test to verify it fails**

Run: frontend targeted test command для API layer.

Expected: FAIL, потому что wrappers сейчас просто возвращают `fetchApi(...)`.

**Step 3: Write minimal implementation**

В `frontend/src/lib/api.ts`:
- описать raw response interfaces для mutation endpoints;
- переиспользовать существующие `normalizeQuest` и `normalizeQuestApplication`;
- для `confirmQuest` либо вернуть нормализованный объект целиком, либо создать отдельный explicit normalizer под confirm payload;
- убрать ложную типизацию, где transport string выдаётся за `number`.

**Step 4: Run test to verify it passes**

Run: targeted frontend tests.

Expected: PASS.

**Step 5: Commit**

`git add frontend/src/lib/api.ts frontend/src/types`

`git commit -m "fix: normalize quest mutation money payloads"`

### Task 7: Выравнять consumers и smoke-check UI path

**Files:**
- Modify: `frontend/src/app/quests/[id]/page.tsx`
- Check: `frontend/src/components/quests/ApplyModal.tsx`
- Check: any other quest mutation consumers returned by search

**Step 1: Write the failing test or runtime assertion**

Если компонентные тесты отсутствуют, зафиксировать хотя бы unit/integration test на API layer плюс manual smoke checklist:
- toast после confirm использует уже number;
- никакие consumer-ы не делают ad-hoc `Number(...)` поверх этих же полей из-за двойной нормализации.

**Step 2: Run verification to expose drift**

Run: frontend tests and type-check.

Expected: либо FAIL, либо обнаружение мест, где контракт ещё расходится.

**Step 3: Write minimal implementation**

Обновить consumers так, чтобы они полагались на нормализованный API layer, а не на сырой transport shape.

**Step 4: Run test/build to verify it passes**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: PASS.

**Step 5: Commit**

`git add frontend/src/app/quests/[id]/page.tsx frontend/src/components/quests`

`git commit -m "refactor: consume normalized quest mutation responses"`

### Iteration 3 exit criteria

- Ни один quest mutation wrapper не возвращает Decimal-строку наружу.
- `confirmQuest` имеет честный и проверяемый контракт.
- Frontend build зелёный после выравнивания типов и consumers.

---

### Iteration 4. Довести антиабьюз до последовательной user-based политики

Цель итерации: сделать throttling согласованным для authenticated quest mutations, чтобы один и тот же пользователь не обходил ограничения простой сменой IP.

### Task 8: Зафиксировать policy тестами

**Files:**
- Modify: `backend/tests/test_endpoints.py`
- Check: `backend/tests/test_audit_p0p1_fixes.py` if it already covers recent security regressions
- Check: `backend/app/api/v1/endpoints/quests.py`
- Check: `backend/app/core/ratelimit.py`

**Step 1: Write the failing tests**

Добавить сценарии для authenticated user:
- повторяющиеся `apply`;
- повторяющиеся `complete`;
- повторяющиеся `request revision`;

с изменением IP между запросами, но одинаковым user identity. Ожидание: после лимита возвращается `429` по user bucket.

**Step 2: Run test to verify it fails**

Run: targeted pytest for quest endpoint throttling.

Expected: FAIL, потому что сейчас учитывается в основном IP.

**Step 3: Write minimal implementation**

Добавить `check_user_rate_limit(...)` в:
- `apply_to_quest`;
- `assign_quest`;
- `start_quest`;
- `complete_quest`;
- `request_quest_revision`;

с отдельными action names и лимитами, согласованными с текущими IP-based quotas.

**Step 4: Run test to verify it passes**

Run: targeted pytest on updated endpoints.

Expected: PASS.

**Step 5: Commit**

`git add backend/app/api/v1/endpoints/quests.py backend/tests/test_endpoints.py`

`git commit -m "fix: add user-scoped throttling to quest mutations"`

### Task 9: Проверить, что новый throttling не ломает существующие flows

**Files:**
- Check: `scripts/test-flow.ps1`
- Check: `backend/tests/test_integration.py`
- Check: `backend/tests/test_endpoints.py`

**Step 1: Run regression verification**

Run:
- `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_integration.py -q --tb=short`
- `Set-Location c:\QuestionWork; powershell -ExecutionPolicy Bypass -File .\scripts\test-flow.ps1`

Expected: PASS.

**Step 2: Adjust quotas only if test evidence shows false positives**

Менять лимиты только при доказанном конфликте с реальными сценариями, не наугад.

**Step 3: Re-run verification**

Expected: PASS после точечной корректировки.

**Step 4: Commit**

`git add backend/app/api/v1/endpoints/quests.py backend/tests scripts/test-flow.ps1`

`git commit -m "test: verify quest throttling against existing flows"`

### Iteration 4 exit criteria

- User-based throttling работает на всех чувствительных quest mutation endpoints.
- Смена IP не помогает обходить лимит одного и того же пользователя.
- Regression flow tests остаются зелёными.

---

### Iteration 5. Финальный прогон и release gate

Цель итерации: собрать доказательство, что все найденные audit findings действительно закрыты и не открыли новый регресс.

### Task 10: Выполнить целевой финальный verification sweep

**Files:**
- No code changes expected
- Verify: `backend/tests/test_security_hardening.py`
- Verify: `backend/tests/test_config_validation.py`
- Verify: `backend/tests/test_endpoints.py`
- Verify: `frontend/src/lib/api.ts`

**Step 1: Run backend verification**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_security_hardening.py tests/test_config_validation.py tests/test_endpoints.py -q --tb=short`

Expected: PASS.

**Step 2: Run full backend suite if Step 1 is green**

Run: `Set-Location c:\QuestionWork\backend; $env:SECRET_KEY='dev-secret-key-questionwork'; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests -q --tb=short`

Expected: PASS.

**Step 3: Run frontend build**

Run: `Set-Location c:\QuestionWork\frontend; npm run build`

Expected: PASS.

**Step 4: Record closure evidence**

Собрать короткий closure note:
- какой тест закрывает P0;
- какой тест закрывает P1 audit logging;
- какой тест закрывает P1 frontend normalization;
- какой тест закрывает P2 throttling;
- какой тест закрывает P2 startup validation.

**Step 5: Commit**

Если появились только docs/notes: отдельный commit.

`git commit -m "chore: record audit remediation verification"`

### Iteration 5 exit criteria

- Все подтверждённые findings закрыты кодом и тестами.
- Backend full pytest зелёный.
- Frontend build зелёный.
- Есть явная карта: finding -> fix -> regression test.

## Порядок исполнения

1. Iteration 1 обязателен до любого релиза.
2. Iteration 2 должен идти сразу после него, потому что касается того же auth surface.
3. Iteration 3 можно делать параллельно с backend auth work только в отдельной ветке или worktree, иначе лучше после Iteration 2.
4. Iteration 4 выполнять после стабилизации security/auth changes, чтобы не смешивать причины возможных падений integration tests.
5. Iteration 5 завершает работу и даёт release decision.

## Риски при исполнении

- Самый вероятный источник регрессии: неполная миграция state machine TOTP, когда часть кода читает pending secret как active либо наоборот.
- Второй риск: двойная нормализация денег на frontend, если consumer-ы уже вручную вызывают `Number(...)`.
- Третий риск: слишком агрессивные user-based лимиты, которые начнут бить по легитимным сценариям тестов.

## Что считать завершением

- P0 закрыт не описательно, а тестом на невозможность rotation без текущего TOTP.
- P1 по audit trail закрыт проверкой записей в `admin_logs`.
- P1 по frontend contract закрыт unit test-ом или эквивалентной автоматической проверкой на отсутствие Decimal-string leakage.
- P2 по throttling закрыт тестом, где тот же user получает `429` при смене IP.
- P2 по `pyotp` закрыт startup/config test-ом.
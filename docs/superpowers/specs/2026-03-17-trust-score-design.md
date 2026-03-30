# Trust Score Design

## Goal

Добавить агрегатный Trust Score для фрилансеров, чтобы заказчик видел не только отзывы, но и сводный сигнал надёжности: качество отзывов, completion discipline, соблюдение дедлайнов и зрелость аккаунта.

## Scope

В этот дизайн входят:

1. backend calculation service;
2. denormalized persistence/cache on `users`;
3. endpoint `GET /users/{id}/trust-score`;
4. embedding trust score into public profile and marketplace payloads;
5. marketplace sorting/ranking integration;
6. frontend badge/meter in marketplace row and public profile.

В этот дизайн не входят:

1. исторические backfill jobs для всех пользователей за пределами миграции + admin script;
2. отдельная аналитика по trust-score drift;
3. самостоятельный Redis-only cache layer.

## Constraints From Current Codebase

1. Reviews уже кешируют `avg_rating` и `review_count` в `users`, поэтому trust score лучше внедрять как ещё один denormalized proof field, а не как полностью отдельный runtime-only слой.
2. Public profile и marketplace уже строятся вокруг proof fields из `users` + lateral quest aggregates в [backend/app/api/v1/endpoints/users.py](c:/QuestionWork/backend/app/api/v1/endpoints/users.py) и ranking helpers в [backend/app/services/marketplace_service.py](c:/QuestionWork/backend/app/services/marketplace_service.py).
3. Deadline data уже есть в `quests`, а late-delivery semantics появились в [backend/app/services/quest_service.py](c:/QuestionWork/backend/app/services/quest_service.py), поэтому `on_time_rate` можно считать без новой доменной модели.
4. Marketplace list не должен делать N+1 запросов на trust score по пользователям.

## Approaches Considered

### Approach A: Compute On Demand + Redis Cache

Считать trust score по запросу и складывать в Redis на TTL.

Плюсы:

1. не нужна миграция;
2. минимальный write-path.

Минусы:

1. неудобно сортировать marketplace/search по trust score;
2. появляется два источника истины: SQL aggregates и Redis snapshot;
3. нужен fallback path на Redis miss и отдельная invalidation discipline.

### Approach B: Persist Denormalized Trust Score On `users` With Service Recompute

Добавить `trust_score`, `trust_score_breakdown`, `trust_score_updated_at` в `users`, пересчитывать из `trust_score_service` после review create и quest confirm/cancel flows.

Плюсы:

1. естественно ложится в уже существующий pattern с `avg_rating`/`review_count`;
2. marketplace sorting/ranking получает cheap read path;
3. public profile и users endpoints могут отдавать trust score без дополнительных join-heavy запросов.

Минусы:

1. нужна миграция;
2. write paths становятся чуть шире;
3. нужен backfill и дисциплина пересчёта.

### Approach C: Pure SQL Formula Everywhere

Во всех read endpoints inline-вычислять trust score lateral subquery-агрегациями.

Плюсы:

1. нет persistence drift;
2. одна математическая формула в SQL.

Минусы:

1. высокая стоимость на marketplace/search;
2. больше SQL duplication;
3. сложнее тестировать и эволюционировать breakdown.

## Recommendation

Рекомендуется **Approach B**: denormalized trust score в `users`, пересчитываемый через отдельный backend service.

Это лучший компромисс для текущего репозитория: search/ranking получает дешёвый sort key, profile/marketplace не страдают от N+1, а модель уже совпадает с существующим cached-proof pattern.

## Data Model

Добавить в `users`:

1. `trust_score NUMERIC(5,4) NULL`;
2. `trust_score_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb`;
3. `trust_score_updated_at TIMESTAMPTZ NULL`.

`trust_score` хранится в диапазоне `0.0000..1.0000`.

`trust_score_breakdown` хранит прозрачные компоненты:

```json
{
  "avg_rating": 0.96,
  "completion_rate": 0.83,
  "on_time_rate": 0.75,
  "level_bonus": 0.50,
  "raw": {
    "average_rating_5": 4.8,
    "confirmed_quests": 10,
    "accepted_quests": 12,
    "on_time_quests": 9,
    "graded_as": "middle"
  }
}
```

## Formula

Normalization:

1. `avg_rating_norm = avg_rating / 5.0`
2. `completion_rate_norm = confirmed_quests / accepted_quests`
3. `on_time_rate_norm = on_time_quests / confirmed_quests`
4. `level_bonus = {novice: 0.0, junior: 0.25, middle: 0.5, senior: 1.0}`

Score:

$$
trust\_score = (avg\_rating\_norm \times 0.4) + (completion\_rate\_norm \times 0.3) + (on\_time\_rate\_norm \times 0.2) + (level\_bonus \times 0.1)
$$

Fallbacks:

1. no reviews => `avg_rating_norm = 0.0`
2. no accepted quests => `completion_rate_norm = 0.0`
3. no confirmed quests => `on_time_rate_norm = 0.0`
4. score always quantized/clamped into `[0.0, 1.0]`

## Accepted Quest Semantics

Чтобы не invent новую бизнес-логику, используем согласованный набор:

1. `accepted_quests` = все квесты, где `assigned_to = user_id` и `status NOT IN ('draft', 'open')`
2. `confirmed_quests` = квесты со `status = 'confirmed'`
3. `on_time_quests` = confirmed quests, где:
   - `deadline IS NULL`, или
   - `delivery_submitted_at <= deadline`, или
   - `delivery_submitted_at IS NULL AND completed_at <= deadline`

Так `on_time_rate` опирается на реальный delivery moment, а не на client confirm time.

## Read API Shape

Новый endpoint:

`GET /api/v1/users/{id}/trust-score`

Response:

```json
{
  "user_id": "user_123",
  "trust_score": 0.8425,
  "breakdown": {
    "avg_rating": 0.96,
    "completion_rate": 0.83,
    "on_time_rate": 0.75,
    "level_bonus": 0.5,
    "raw": {
      "average_rating_5": 4.8,
      "accepted_quests": 12,
      "confirmed_quests": 10,
      "on_time_quests": 9,
      "grade": "middle"
    }
  },
  "updated_at": "2026-03-17T12:34:56Z"
}
```

Existing read models should also expose lightweight fields:

1. `PublicUserProfile.trust_score`
2. `PublicUserProfile.trust_score_updated_at`
3. `TalentMarketMember.trust_score`

Marketplace rows should **not** fetch breakdown per user.

## Write-Time Recalculation Hooks

Recalculate trust score in the same parent transaction after state mutations that change source metrics:

1. after review creation in [backend/app/services/review_service.py](c:/QuestionWork/backend/app/services/review_service.py);
2. after quest confirmation in [backend/app/services/quest_service.py](c:/QuestionWork/backend/app/services/quest_service.py);
3. after client cancellation of assigned work in [backend/app/services/quest_service.py](c:/QuestionWork/backend/app/services/quest_service.py), because accepted/completion denominators change.

Do not add Redis in the first pass. The persisted user columns already serve as cache.

## Marketplace Integration

For first pass:

1. add explicit sort option `trust`;
2. include `trust_score` in marketplace row payload;
3. use `trust_score DESC` as a tie-breaker in default ranking, not a total rewrite of `_member_rank_score()`.

This avoids a surprising global ranking reshuffle while still making trust score operational for sorting/ranking.

## Frontend UX

### Marketplace

Add a compact `TrustScoreBadge` in each talent row:

1. shield/metre visual;
2. numeric score as `%` or 0-100 label;
3. tooltip/inline copy like `Trust 84`.

### Public Profile

Add a richer `TrustScoreMeter` block near profile hero / proof area:

1. overall score;
2. four-part breakdown;
3. short explainer that it combines ratings, completion, deadlines, and grade maturity.

## Testing Strategy

1. pure service tests for normalization and formula edge cases;
2. endpoint tests for `GET /users/{id}/trust-score`;
3. write-path tests proving review creation and quest state mutations refresh cached trust data;
4. marketplace/user profile tests proving trust fields surface in payloads and sorting;
5. frontend type and UI tests for trust badge/meter rendering states.

## Risks

1. **Drift risk**: if any write path forgets to recompute trust score, cached value becomes stale.
2. **Double counting risk**: default marketplace ranking already weights rating/reviews; trust score must not be layered so aggressively that results skew twice.
3. **Deadline ambiguity**: confirmed time vs submitted time must stay explicit and tested.
4. **Zero-denominator behaviour**: new users should not accidentally look trustworthy because of null math defaults.

## Decision Summary

1. Use persisted DB cache on `users`, not Redis-only cache.
2. Compute trust score in dedicated `trust_score_service.py`.
3. Recalculate on review create, quest confirm, and assigned-work cancel.
4. Surface trust score in dedicated endpoint plus existing public profile/marketplace payloads.
5. Add explicit marketplace `trust` sort and use trust as default tie-breaker rather than fully replacing current ranking in the first pass.
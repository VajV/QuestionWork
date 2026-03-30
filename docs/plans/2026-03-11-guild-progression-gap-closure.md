# Guild Progression Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish the missing production pieces around guild seasonal progression so rewards are durable, backfilled, fully public, server-authored, and operationally deployable.

**Architecture:** Keep the existing authoritative reward seam in `backend/app/services/guild_economy_service.py`, but stop treating seasonal progression as a partly derived frontend concern. The backend should own schema rollout, historical reconciliation, progression snapshots, badge projection, reward configuration, and claim notifications. Each increment should stay shippable on its own, with the public guild page consuming only explicit server contracts.

**Tech Stack:** FastAPI, asyncpg, SQLAlchemy ORM metadata, Alembic, PostgreSQL, Pydantic, Next.js 14 App Router, TypeScript, pytest, npm build.

---

## Execution Rules

1. Work in order. Do not start DB-backed reward configuration before the server snapshot is green.
2. Prefer TDD for every code change except the one-time Alembic rollout command.
3. Keep each commit scoped to one task.
4. Run the smallest relevant verification first, then the broader regression command for that area.
5. Do not keep client-derived leaderboard logic once the server snapshot lands.

---

## Task 1: Roll Out Schema And Backfill Historical Seasonal Rewards

**Files:**
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/tests/test_guild_card_service.py`
- Create: `backend/scripts/backfill_guild_seasonal_rewards.py`
- Optional doc note: `README.md`

**Step 1: Write the failing backfill tests**

```python
async def test_backfill_claims_completed_sets_once(fake_conn):
    fake_conn.queue_fetch(
        [
            {"family": "ember", "season_code": "S1", "card_total": 4},
        ]
    )
    fake_conn.queue_fetch([])
    fake_conn.queue_fetchrow(
        {
            "id": "reward-1",
            "family": "ember",
            "season_code": "S1",
            "label": "Ember Court",
            "accent": "amber",
            "treasury_bonus": "250.00",
            "guild_tokens_bonus": 3,
            "badge_name": "Sigil Wardens",
            "claimed_at": datetime.now(timezone.utc),
        }
    )

    inserted = await backfill_guild_seasonal_rewards(fake_conn, guild_id="guild-1")

    assert len(inserted) == 1
    assert inserted[0]["family"] == "ember"


async def test_backfill_is_idempotent(fake_conn):
    fake_conn.queue_fetch(
        [
            {"family": "ember", "season_code": "S1", "card_total": 4},
        ]
    )
    fake_conn.queue_fetch(
        [
            {"family": "ember", "season_code": "S1", "badge_name": "Sigil Wardens"},
        ]
    )

    inserted = await backfill_guild_seasonal_rewards(fake_conn, guild_id="guild-1")

    assert inserted == []
```

**Step 2: Run the focused tests and verify they fail**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py -q --tb=short`

Expected: FAIL because `backfill_guild_seasonal_rewards` does not exist yet.

**Step 3: Implement minimal backfill service logic and script entrypoint**

```python
async def backfill_guild_seasonal_rewards(conn: asyncpg.Connection, guild_id: str) -> list[dict[str, object]]:
    completed_sets = await _fetch_completed_sets_for_backfill(conn, guild_id)
    claimed_pairs = await _fetch_claimed_reward_pairs(conn, guild_id)

    inserted: list[dict[str, object]] = []
    for seasonal_set in completed_sets:
        reward_key = (seasonal_set["season_code"], seasonal_set["family"])
        if reward_key in claimed_pairs:
            continue
        reward_meta = _get_reward_metadata(seasonal_set["family"], seasonal_set["season_code"])
        reward_row = await _insert_claimed_reward(conn, guild_id, seasonal_set, reward_meta)
        inserted.append(dict(reward_row))
    return inserted
```

```python
async def main() -> None:
    pool = await create_db_pool()
    async with pool.acquire() as conn:
        guild_ids = await conn.fetch("SELECT id FROM guilds ORDER BY created_at ASC")
        for row in guild_ids:
            async with conn.transaction():
                inserted = await guild_card_service.backfill_guild_seasonal_rewards(conn, str(row["id"]))
                print(f"guild={row['id']} inserted={len(inserted)}")
```

**Step 4: Apply the existing migration and run the backfill command**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m alembic upgrade head`

Expected: PASS and the `guild_seasonal_rewards` table exists.

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe scripts/backfill_guild_seasonal_rewards.py`

Expected: PASS and output like `guild=<id> inserted=<n>` without duplicate inserts on a second run.

**Step 5: Run regression tests and commit**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_guild_economy_service.py tests/test_endpoints.py -q --tb=short`

Expected: PASS.

```bash
git add backend/app/services/guild_card_service.py backend/tests/test_guild_card_service.py backend/scripts/backfill_guild_seasonal_rewards.py
git commit -m "feat: backfill historical guild seasonal rewards"
```

---

## Task 2: Move Guild Progression Snapshot Fully Server-Side

**Files:**
- Modify: `backend/app/models/marketplace.py`
- Modify: `backend/app/services/marketplace_service.py`
- Modify: `backend/tests/test_endpoints.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`

**Step 1: Write the failing backend contract test for the snapshot**

```python
def test_guild_profile_includes_progression_snapshot(client, guild_fixture):
    response = client.get(f"/api/v1/marketplace/guilds/{guild_fixture['slug']}")

    assert response.status_code == 200
    payload = response.json()
    assert "progression_snapshot" in payload
    assert payload["progression_snapshot"]["leaderboard"][0]["rank"] == 1
    assert "completed_sets" in payload["progression_snapshot"]
```

**Step 2: Run the focused contract test and verify it fails**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py -q --tb=short`

Expected: FAIL because `progression_snapshot` is not in the response model.

**Step 3: Add server-side snapshot models and marketplace assembly**

```python
class GuildLeaderboardEntry(BaseModel):
    rank: int = Field(ge=1)
    member_id: str
    username: str
    contribution: int = Field(ge=0)
    trophy_count: int = Field(ge=0)
    family_label: Optional[str] = None


class GuildProgressionSnapshot(BaseModel):
    completed_sets: int = Field(ge=0)
    total_sets: int = Field(ge=0)
    claimed_rewards: int = Field(ge=0)
    leaderboard: List[GuildLeaderboardEntry] = Field(default_factory=list)
```

```python
def build_guild_progression_snapshot(
    members: list[dict[str, object]],
    trophies: list[dict[str, object]],
    seasonal_sets: list[dict[str, object]],
) -> dict[str, object]:
    leaderboard = _build_member_leaderboard(members, trophies)
    return {
        "completed_sets": sum(1 for item in seasonal_sets if item["completed"]),
        "total_sets": len(seasonal_sets),
        "claimed_rewards": sum(1 for item in seasonal_sets if item["reward_claimed"]),
        "leaderboard": leaderboard,
    }
```

**Step 4: Switch the frontend page to consume the server snapshot only**

```typescript
const progressionSnapshot = data?.progression_snapshot;
const leaderboard = progressionSnapshot?.leaderboard ?? [];
const completedSeasonalSets = progressionSnapshot?.completed_sets ?? 0;
```

Remove the client `useMemo` that derives leaderboard from `members` and `trophies`.

**Step 5: Run verification and commit**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_guild_card_service.py -q --tb=short`

Expected: PASS.

Run: `Set-Location c:/QuestionWork/frontend; npm run build`

Expected: PASS.

```bash
git add backend/app/models/marketplace.py backend/app/services/marketplace_service.py backend/tests/test_endpoints.py frontend/src/lib/api.ts frontend/src/app/marketplace/guilds/[slug]/page.tsx
git commit -m "feat: move guild progression snapshot server-side"
```

---

## Task 3: Promote Seasonal Reward Badges Into A Public Guild Badge System

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/2026_03_11_add_guild_badges.py`
- Modify: `backend/app/models/marketplace.py`
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/app/services/marketplace_service.py`
- Modify: `backend/tests/test_guild_card_service.py`
- Modify: `backend/tests/test_endpoints.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/marketplace/guilds/[slug]/page.tsx`

**Step 1: Write the failing test for persistent guild badges**

```python
async def test_claim_completed_seasonal_rewards_creates_public_badge(fake_conn):
    fake_conn.queue_fetch([...])
    fake_conn.queue_fetchrow(
        {
            "id": "badge-1",
            "guild_id": "guild-1",
            "badge_code": "s1-ember",
            "name": "Sigil Wardens",
            "slug": "sigil-wardens",
            "season_code": "S1",
            "family": "ember",
            "awarded_at": datetime.now(timezone.utc),
        }
    )

    rewards = await claim_completed_seasonal_rewards(fake_conn, guild_id="guild-1", quest_id="quest-1")

    assert rewards[0]["badge_name"] == "Sigil Wardens"
    assert rewards[0]["guild_badge"]["slug"] == "sigil-wardens"
```

**Step 2: Run the badge-focused tests and verify they fail**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py -q --tb=short`

Expected: FAIL because there is no guild badge persistence yet.

**Step 3: Add a dedicated guild badge entity and award it during claim**

```python
class GuildBadgeORM(Base):
    __tablename__ = "guild_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    guild_id = Column(UUID(as_uuid=True), ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_code = Column(String(80), nullable=False)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False)
    season_code = Column(String(20), nullable=True)
    family = Column(String(40), nullable=True)
    accent = Column(String(40), nullable=False, server_default=text("'amber'"))
    awarded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("guild_id", "badge_code", name="uq_guild_badges_guild_badge_code"),)
```

```python
guild_badge = await conn.fetchrow(
    """
    INSERT INTO guild_badges (guild_id, badge_code, name, slug, season_code, family, accent)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (guild_id, badge_code) DO UPDATE
        SET name = EXCLUDED.name,
            accent = EXCLUDED.accent
    RETURNING id, badge_code, name, slug, season_code, family, accent, awarded_at
    """,
    guild_id,
    f"{season_code}:{family}",
    reward_meta["badge_name"],
    slugify(reward_meta["badge_name"]),
    season_code,
    family,
    reward_meta["accent"],
)
```

Expose badges in the public response:

```python
class GuildPublicBadge(BaseModel):
    id: str
    badge_code: str
    name: str
    slug: str
    accent: str
    season_code: Optional[str] = None
    family: Optional[str] = None
    awarded_at: datetime
```

**Step 4: Render a badge rail on the public guild page**

```typescript
const guildBadges = data?.badges ?? [];
```

Render the array before the seasonal set grid and treat `reward_badge_name` as historical claim metadata, not the primary public badge source.

**Step 5: Run verification and commit**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_endpoints.py -q --tb=short`

Expected: PASS.

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m alembic upgrade head`

Expected: PASS.

Run: `Set-Location c:/QuestionWork/frontend; npm run build`

Expected: PASS.

```bash
git add backend/app/db/models.py backend/alembic/versions/2026_03_11_add_guild_badges.py backend/app/models/marketplace.py backend/app/services/guild_card_service.py backend/app/services/marketplace_service.py backend/tests/test_guild_card_service.py backend/tests/test_endpoints.py frontend/src/lib/api.ts frontend/src/app/marketplace/guilds/[slug]/page.tsx
git commit -m "feat: add public guild badge system"
```

---

## Task 4: Replace Hardcoded Seasonal Rewards With DB-Backed Config And Admin Controls

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/2026_03_11_add_guild_season_reward_configs.py`
- Modify: `backend/app/models/admin.py`
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/app/services/guild_card_service.py`
- Modify: `backend/tests/test_admin_endpoints.py`
- Modify: `backend/tests/test_guild_card_service.py`

**Step 1: Write the failing admin/config tests**

```python
def test_admin_can_create_guild_season_reward_config(admin_client):
    response = admin_client.post(
        "/api/v1/admin/guild-season-rewards",
        json={
            "season_code": "S2",
            "family": "ember",
            "label": "Ember Court",
            "accent": "amber",
            "treasury_bonus": "250.00",
            "guild_tokens_bonus": 3,
            "badge_name": "Sigil Wardens",
            "is_active": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["season_code"] == "S2"
```

```python
async def test_claim_completed_rewards_reads_active_db_config(fake_conn):
    fake_conn.queue_fetch([
        {
            "season_code": "S2",
            "family": "ember",
            "label": "Ember Court",
            "accent": "amber",
            "treasury_bonus": "250.00",
            "guild_tokens_bonus": 3,
            "badge_name": "Sigil Wardens",
        }
    ])

    rewards = await load_season_reward_configs(fake_conn, season_code="S2")

    assert rewards[("S2", "ember")]["badge_name"] == "Sigil Wardens"
```

**Step 2: Run the focused tests and verify they fail**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_endpoints.py tests/test_guild_card_service.py -q --tb=short`

Expected: FAIL because there is no admin endpoint or DB-backed reward config.

**Step 3: Add config table, request/response models, and service reads**

```python
class GuildSeasonRewardConfigORM(Base):
    __tablename__ = "guild_season_reward_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    season_code = Column(String(20), nullable=False)
    family = Column(String(40), nullable=False)
    label = Column(String(80), nullable=False)
    accent = Column(String(40), nullable=False)
    treasury_bonus = Column(Numeric(12, 2), nullable=False)
    guild_tokens_bonus = Column(Integer, nullable=False, server_default=text("0"))
    badge_name = Column(String(80), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (UniqueConstraint("season_code", "family", name="uq_guild_reward_config_season_family"),)
```

```python
class AdminGuildSeasonRewardConfigRequest(BaseModel):
    season_code: str = Field(min_length=2, max_length=20)
    family: str = Field(min_length=2, max_length=40)
    label: str = Field(min_length=2, max_length=80)
    accent: str = Field(min_length=2, max_length=40)
    treasury_bonus: Decimal
    guild_tokens_bonus: int = Field(ge=0)
    badge_name: str = Field(min_length=2, max_length=80)
    is_active: bool = True
```

```python
@router.post("/guild-season-rewards", response_model=AdminGuildSeasonRewardConfigResponse)
async def upsert_guild_season_reward_config(...):
    check_rate_limit(ip, action="admin_upsert_guild_season_reward_config", limit=20, window_seconds=60)
    return await admin_service.upsert_guild_season_reward_config(conn, payload)
```

In `guild_card_service.py`, replace direct `SEASONAL_SET_REWARDS[...]` access with a DB loader plus a single fallback path only for test fixtures or empty local databases.

**Step 4: Seed or migrate active config rows before switching read-path fully**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m alembic upgrade head`

Expected: PASS.

If the migration seeds the current config, verify rows exist:

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -c "import asyncio, asyncpg; from app.core.config import settings; async def main():\n conn = await asyncpg.connect(settings.database_url); rows = await conn.fetch('SELECT season_code, family FROM guild_season_reward_configs ORDER BY season_code, family'); print(len(rows)); await conn.close();\nasyncio.run(main())"`

Expected: non-zero row count.

**Step 5: Run regression and commit**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_admin_endpoints.py tests/test_admin_service.py tests/test_guild_card_service.py -q --tb=short`

Expected: PASS.

```bash
git add backend/app/db/models.py backend/alembic/versions/2026_03_11_add_guild_season_reward_configs.py backend/app/models/admin.py backend/app/api/v1/endpoints/admin.py backend/app/services/admin_service.py backend/app/services/guild_card_service.py backend/tests/test_admin_endpoints.py backend/tests/test_guild_card_service.py
git commit -m "feat: make guild seasonal rewards configurable"
```

---

## Task 5: Add Dedicated Seasonal Claim Notifications

**Files:**
- Modify: `backend/app/services/guild_economy_service.py`
- Modify: `backend/app/services/notification_service.py`
- Modify: `backend/app/services/quest_service.py`
- Modify: `backend/app/services/admin_service.py`
- Modify: `backend/tests/test_guild_economy_service.py`
- Modify: `backend/tests/test_endpoints.py`

**Step 1: Write the failing notification test**

```python
async def test_apply_quest_completion_rewards_emits_seasonal_claim_notifications(mocker):
    create_notification = mocker.patch("app.services.notification_service.create_notification", new_callable=AsyncMock)
    mocker.patch("app.services.guild_card_service.claim_completed_seasonal_rewards", return_value=[
        {
            "family": "ember",
            "season_code": "S1",
            "badge_name": "Sigil Wardens",
            "treasury_bonus": "250.00",
            "guild_tokens_bonus": 3,
        }
    ])

    await apply_quest_completion_rewards(...)

    assert create_notification.await_count >= 1
```

**Step 2: Run the focused test and verify it fails**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_economy_service.py -q --tb=short`

Expected: FAIL because seasonal claims only affect activity summary today.

**Step 3: Add a dedicated fan-out helper and call it from both completion paths**

```python
async def notify_guild_seasonal_claim(
    conn: asyncpg.Connection,
    guild_id: str,
    seasonal_rewards: list[dict[str, object]],
) -> None:
    recipients = await conn.fetch(
        """
        SELECT gm.user_id
        FROM guild_members gm
        WHERE gm.guild_id = $1
          AND gm.role IN ('leader', 'officer')
        ORDER BY gm.joined_at ASC
        """,
        guild_id,
    )
    for reward in seasonal_rewards:
        for recipient in recipients:
            await create_notification(
                conn,
                user_id=str(recipient["user_id"]),
                title=f"Guild seasonal reward claimed: {reward['badge_name']}",
                message=_build_seasonal_reward_notification_message(reward),
                notification_type="guild_seasonal_reward",
            )
```

Keep notification emission inside the parent transaction triggered by `quest_service.confirm_quest_completion` and `admin_service.force_complete_quest` through the existing `guild_economy_service.apply_quest_completion_rewards(...)` path.

**Step 4: Expose the new notification type safely to existing notification consumers**

If notification response typing is strict, add the new type in the relevant Pydantic model or serializer path so `/api/v1/notifications/` still serializes cleanly.

**Step 5: Run regression and commit**

Run: `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_economy_service.py tests/test_endpoints.py tests/test_admin_endpoints.py -q --tb=short`

Expected: PASS.

```bash
git add backend/app/services/guild_economy_service.py backend/app/services/notification_service.py backend/app/services/quest_service.py backend/app/services/admin_service.py backend/tests/test_guild_economy_service.py backend/tests/test_endpoints.py
git commit -m "feat: notify guild seasonal reward claims"
```

---

## Final Verification

Run these only after all five tasks are complete:

1. `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe -m pytest tests/test_guild_card_service.py tests/test_guild_economy_service.py tests/test_endpoints.py tests/test_admin_endpoints.py tests/test_admin_service.py -q --tb=short`
2. `Set-Location c:/QuestionWork/frontend; npm run build`
3. `Set-Location c:/QuestionWork/backend; c:/QuestionWork/backend/.venv/Scripts/python.exe scripts/backfill_guild_seasonal_rewards.py`
4. Manual API smoke check against one real guild page to confirm `progression_snapshot`, `badges`, `seasonal_sets`, and notifications all appear as expected.

## Rollout Notes

1. Apply Alembic before deploying frontend that expects any new response fields.
2. Run the backfill immediately after migration so old guilds receive already-earned seasonal claims.
3. If DB-backed reward configuration is deployed separately, seed the active season rows before removing the hardcoded fallback.
4. Announce the new notification type to any consumer that filters notification categories.

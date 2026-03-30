# Escrow Conflict Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Return `409 Conflict` instead of `400 Bad Request` when quest confirmation or admin force-complete hits an escrow mismatch, so operational wallet inconsistencies are not surfaced as user-input errors.

**Architecture:** Keep the existing `EscrowMismatchError` domain exception in the wallet layer, but treat it as an operational conflict at the HTTP boundary. Add focused endpoint regression tests first, then implement the minimal exception mapping in quest and admin endpoints, and verify with targeted plus full backend test runs.

**Tech Stack:** FastAPI, asyncpg, pytest, TestClient, Python 3.12

---

### Task 1: Add failing endpoint regression tests

**Files:**
- Modify: `backend/tests/test_endpoints.py`
- Modify: `backend/tests/test_admin_endpoints.py`

**Step 1: Write the failing client confirm test**

Add a test that patches `quest_service.confirm_quest_completion()` to raise `EscrowMismatchError` and asserts `POST /api/v1/quests/{id}/confirm` returns `409` with a conflict-oriented detail.

**Step 2: Write the failing admin force-complete test**

Add a test that patches `admin_service.force_complete_quest()` to raise `EscrowMismatchError` and asserts `POST /api/v1/admin/quests/{id}/force-complete` returns `409` with the same detail.

**Step 3: Run the focused tests to confirm RED**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_admin_endpoints.py -q --tb=short -k "escrow or force_complete or confirm"`

Expected: both new tests fail because endpoints currently map the exception through the generic `ValueError -> 400` path.

### Task 2: Reclassify escrow mismatch at the HTTP boundary

**Files:**
- Modify: `backend/app/api/v1/endpoints/quests.py`
- Modify: `backend/app/api/v1/endpoints/admin.py`
- Reference: `backend/app/services/wallet_service.py`

**Step 1: Import the domain exception**

Import `EscrowMismatchError` from `app.services.wallet_service` in both endpoint modules.

**Step 2: Add explicit conflict mapping**

In `confirm_quest()` and `admin_force_complete_quest()`, catch `EscrowMismatchError` before the generic `ValueError` handler and raise `HTTPException(status_code=409, detail=...)`.

**Step 3: Use an operational detail string**

Return a stable message that tells the caller this is an escrow conflict/system inconsistency, not a bad request.

### Task 3: Verify and close the loop

**Files:**
- No new files

**Step 1: Re-run the focused tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_endpoints.py tests/test_admin_endpoints.py -q --tb=short -k "escrow or force_complete or confirm"`

Expected: PASS.

**Step 2: Run the full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests -q --tb=short`

Expected: PASS.

**Step 3: Sanity-check frontend contract impact**

No frontend code change is required because the existing API error pipeline already surfaces backend `detail` strings and status codes.
